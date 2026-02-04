import logging
import os
import json
from typing import Dict, List, Any, Callable, Optional
from copy import deepcopy
import traceback

# Configure logging and monitoring
logger = logging.getLogger(__name__)

# Local imports
from gatomia.src.be.dependency_analyzer import DependencyGraphBuilder
from gatomia.src.be.llm_services import call_llm
from gatomia.src.be.prompt_template import (
    format_repo_overview_prompt,
    format_module_overview_prompt,
)
from gatomia.src.be.cluster_modules import cluster_modules
from gatomia.src.config import (
    Config,
    FIRST_MODULE_TREE_FILENAME,
    MODULE_TREE_FILENAME,
    OVERVIEW_FILENAME,
)
from gatomia.src.utils import file_manager
from gatomia.src.be.agent_orchestrator import AgentOrchestrator
from gatomia.src.be.state_manager import StateManager
from gatomia.src.be.hashing import calculate_module_hash
from gatomia.src.be.utils import get_git_author, get_git_version
import shutil


class DocumentationGenerator:
    """Main documentation generation orchestrator."""

    def __init__(self, config: Config, commit_id: str = None):
        self.config = config
        self.commit_id = commit_id
        self.graph_builder = DependencyGraphBuilder(config)
        self.agent_orchestrator = AgentOrchestrator(config)

    def create_documentation_metadata(
        self, working_dir: str, components: Dict[str, Any], num_leaf_nodes: int
    ):
        """Create a metadata file with documentation generation information."""
        from datetime import datetime

        metadata = {
            "generation_info": {
                "timestamp": datetime.now().isoformat(),
                "main_model": self.config.main_model,
                "generator_version": "1.0.1",
                "repo_path": self.config.repo_path,
                "commit_id": self.commit_id,
            },
            "statistics": {
                "total_components": len(components),
                "leaf_nodes": num_leaf_nodes,
                "max_depth": self.config.max_depth,
            },
            "files_generated": ["overview.md", "module_tree.json", "first_module_tree.json"],
        }

        # Add generated markdown files to the metadata
        try:
            for file_path in os.listdir(working_dir):
                if file_path.endswith(".md") and file_path not in metadata["files_generated"]:
                    metadata["files_generated"].append(file_path)
        except Exception as e:
            logger.warning(f"Could not list generated files: {e}")

        metadata_path = os.path.join(working_dir, "metadata.json")
        file_manager.save_json(metadata, metadata_path)

    def get_processing_order(
        self, module_tree: Dict[str, Any], parent_path: List[str] = []
    ) -> List[tuple[List[str], str]]:
        """Get the processing order using topological sort (leaf modules first)."""
        processing_order = []

        def collect_modules(tree: Dict[str, Any], path: List[str]):
            for module_name, module_info in tree.items():
                current_path = path + [module_name]

                # If this module has children, process them first
                if (
                    module_info.get("children")
                    and isinstance(module_info["children"], dict)
                    and module_info["children"]
                ):
                    collect_modules(module_info["children"], current_path)
                    # Add this parent module after its children
                    processing_order.append((current_path, module_name))
                else:
                    # This is a leaf module, add it immediately
                    processing_order.append((current_path, module_name))

        collect_modules(module_tree, parent_path)
        return processing_order

    def is_leaf_module(self, module_info: Dict[str, Any]) -> bool:
        """Check if a module is a leaf module (has no children or empty children)."""
        children = module_info.get("children", {})
        return not children or (isinstance(children, dict) and len(children) == 0)

    def _extract_module_summary(self, markdown_content: str) -> str:
        """
        Extract the module summary (Overview + Architecture) from the markdown content.
        Strategy: Extract content until we hit details sections like 'Core Components' or 'Sub-modules'.
        """
        try:
            lines = markdown_content.splitlines()
            summary_lines = []

            # Headers that signal the start of detailed content we want to skip for parent summary
            stop_headers = [
                "## core components",
                "## sub-modules",
                "## sub modules",
                "## detailed design",
                "## implementation",
                "## classes",
                "## functions",
                "## api",
            ]

            for line in lines:
                stripped = line.strip().lower()

                # Check if we hit a stop header
                if any(stripped.startswith(header) for header in stop_headers):
                    break

                # Check for "Files:" or "Referenced Files" lists which are often huge
                if stripped.startswith("**referenced files:**") or stripped.startswith("<cite>"):
                    continue  # Skip citation block in summary if it's too early, actually we might want to keep it?
                    # Prompt template puts it at top. Let's keep it for now but maybe later.
                    pass

                summary_lines.append(line)

                # Safety valve: if summary exceeds ~80 lines (approx 1-2 pages), stop to avoid token explosion
                if len(summary_lines) > 80:
                    summary_lines.append("\n... [Truncated for Parent Summary] ...")
                    break

            # If logic failed to grab ample content (e.g. empty), fallback to first 50 lines
            if len(summary_lines) < 3:
                return "\n".join(lines[:50])

            return "\n".join(summary_lines)

        except Exception:
            return markdown_content[:2000]  # Fallback to crude truncation

    def build_overview_structure(
        self, module_tree: Dict[str, Any], module_path: List[str], working_dir: str
    ) -> Dict[str, Any]:
        """Build structure for overview generation with 1-depth children docs and target indicator."""

        processed_module_tree = deepcopy(module_tree)
        module_info = processed_module_tree
        for path_part in module_path:
            module_info = module_info[path_part]
            if path_part != module_path[-1]:
                module_info = module_info.get("children", {})
            else:
                module_info["is_target_for_overview_generation"] = True

        if "children" in module_info:
            module_info = module_info["children"]

        for child_name, child_info in module_info.items():
            child_path = os.path.join(working_dir, f"{child_name}.md")
            if os.path.exists(child_path):
                # Optimization: Extract only the summary instead of full content
                full_content = file_manager.load_text(child_path)
                child_info["docs"] = self._extract_module_summary(full_content)
            else:
                logger.warning(f"Module docs not found at {child_path}")
                child_info["docs"] = ""

        return processed_module_tree

    async def generate_module_documentation(
        self,
        components: Dict[str, Any],
        leaf_nodes: List[str],
        force: bool = False,
        resume: bool = False,
        progress_callback: Optional[Callable[[int, int, str, bool], None]] = None,
    ) -> str:
        """Generate documentation for all modules using dynamic programming approach."""
        # Prepare output directory
        working_dir = os.path.abspath(self.config.docs_dir)
        file_manager.ensure_directory(working_dir)

        # Initialize StateManager
        state_manager = StateManager(working_dir)
        if force:
            state_manager.clear_state()

        module_tree_path = os.path.join(working_dir, MODULE_TREE_FILENAME)
        first_module_tree_path = os.path.join(working_dir, FIRST_MODULE_TREE_FILENAME)
        module_tree = file_manager.load_json(module_tree_path)
        first_module_tree = file_manager.load_json(first_module_tree_path)

        # Get processing order (leaf modules first)
        processing_order = self.get_processing_order(first_module_tree)

        # Process modules in dependency order
        final_module_tree = module_tree
        processed_modules = set()

        if len(module_tree) > 0:
            total_modules = len(processing_order)
            current_count = 0

            for module_path, module_name in processing_order:
                current_count += 1
                try:
                    # Get the module info from the tree
                    module_info = module_tree
                    for path_part in module_path:
                        module_info = module_info[path_part]
                        if path_part != module_path[-1]:  # Not the last part
                            module_info = module_info.get("children", {})

                    # Skip if already processed in this run
                    module_key = "/".join(module_path)
                    if module_key in processed_modules:
                        continue

                    # Check if up-to-date (Incremental Update)
                    current_hash = calculate_module_hash(module_info["components"], components)
                    if not force and state_manager.is_module_up_to_date(module_key, current_hash):
                        logger.info(f"⏭️  Skipping up-to-date module: {module_key}")
                        if progress_callback:
                            progress_callback(current_count, total_modules, module_name, True)
                        continue

                    # Update status before processing
                    if progress_callback:
                        progress_callback(current_count, total_modules, module_name, False)

                    # Define progress wrapper for sub-modules
                    progress_wrapper = None
                    if progress_callback:
                        progress_wrapper = lambda msg: progress_callback(
                            current_count, total_modules, f"{module_name} › {msg}", False
                        )

                    # Process the module
                    if self.is_leaf_module(module_info):
                        logger.info(f"📄 Processing leaf module: {module_key}")
                        final_module_tree = await self.agent_orchestrator.process_module(
                            module_name,
                            components,
                            module_info["components"],
                            module_path,
                            working_dir,
                            progress_callback=progress_wrapper,
                        )
                    else:
                        logger.info(f"📁 Processing parent module: {module_key}")
                        final_module_tree = await self.generate_parent_module_docs(
                            module_path, working_dir
                        )

                    processed_modules.add(module_key)
                    # Update state
                    state_manager.update_module_state(module_key, current_hash)

                except Exception as e:
                    logger.error(f"Failed to process module {module_key}: {str(e)}")
                    logger.error(f"Traceback: {traceback.format_exc()}")
                    continue

            # Generate repo overview
            logger.info(f"📚 Generating repository overview")
            final_module_tree = await self.generate_parent_module_docs([], working_dir)
        else:
            logger.info(f"Processing whole repo because repo can fit in the context window")
            repo_name = os.path.basename(os.path.normpath(self.config.repo_path))

            progress_wrapper = None
            if progress_callback:
                progress_wrapper = lambda msg: progress_callback(
                    1, 1, f"{repo_name} › {msg}", False
                )

            final_module_tree = await self.agent_orchestrator.process_module(
                repo_name,
                components,
                leaf_nodes,
                [],
                working_dir,
                progress_callback=progress_wrapper,
            )
            # For whole repo processing, we can treat it as the root module
            root_hash = calculate_module_hash(leaf_nodes, components)
            state_manager.update_module_state("root", root_hash)

            # save final_module_tree to module_tree.json
            file_manager.save_json(
                final_module_tree, os.path.join(working_dir, MODULE_TREE_FILENAME)
            )

            # rename repo_name.md to overview.md
            repo_overview_path = os.path.join(working_dir, f"{repo_name}.md")
            if os.path.exists(repo_overview_path):
                os.rename(repo_overview_path, os.path.join(working_dir, OVERVIEW_FILENAME))

            # Copy overview.md to README.md
            overview_path = os.path.join(working_dir, OVERVIEW_FILENAME)
            readme_path = os.path.join(working_dir, "README.md")
            if os.path.exists(overview_path):
                shutil.copy(overview_path, readme_path)
                logger.info(f"Generated README.md from {OVERVIEW_FILENAME}")

        return working_dir

    async def generate_parent_module_docs(
        self, module_path: List[str], working_dir: str
    ) -> Dict[str, Any]:
        """Generate documentation for a parent module based on its children's documentation."""
        module_name = (
            module_path[-1]
            if len(module_path) >= 1
            else os.path.basename(os.path.normpath(self.config.repo_path))
        )

        logger.info(f"Generating parent documentation for: {module_name}")

        # Load module tree
        module_tree_path = os.path.join(working_dir, MODULE_TREE_FILENAME)
        module_tree = file_manager.load_json(module_tree_path)

        # check if overview docs already exists
        overview_docs_path = os.path.join(working_dir, OVERVIEW_FILENAME)
        if os.path.exists(overview_docs_path):
            logger.info(f"✓ Overview docs already exists at {overview_docs_path}")
            return module_tree

        # check if parent docs already exists
        parent_docs_path = os.path.join(
            working_dir,
            f"{module_name if len(module_path) >= 1 else OVERVIEW_FILENAME.replace('.md', '')}.md",
        )
        if os.path.exists(parent_docs_path):
            logger.info(f"✓ Parent docs already exists at {parent_docs_path}")
            return module_tree

        # Create repo structure with 1-depth children docs and target indicator
        repo_structure = self.build_overview_structure(module_tree, module_path, working_dir)

        # Metadata
        author_name = get_git_author()
        version = get_git_version()

        if len(module_path) >= 1:
            prompt = format_module_overview_prompt(
                module_name=module_name,
                repo_structure=json.dumps(repo_structure, indent=4),
                author_name=author_name,
                version=version,
            )
        else:
            prompt = format_repo_overview_prompt(
                repo_name=module_name,
                repo_structure=json.dumps(repo_structure, indent=4),
                author_name=author_name,
                version=version,
            )

        try:
            parent_docs = await call_llm(prompt, self.config)

            # Parse and save parent documentation
            # Parse and save parent documentation
            if "<OVERVIEW>" in parent_docs and "</OVERVIEW>" in parent_docs:
                parent_content = parent_docs.split("<OVERVIEW>")[1].split("</OVERVIEW>")[0].strip()
            else:
                logger.warning(
                    f"Using full response for parent docs of {module_name} (missing tags)"
                )
                parent_content = parent_docs.strip()

            file_manager.save_text(parent_content, parent_docs_path)

            logger.debug(f"Successfully generated parent documentation for: {module_name}")
            return module_tree

        except Exception as e:
            logger.error(f"Error generating parent documentation for {module_name}: {str(e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            raise

    async def run(
        self,
        force: bool = False,
        resume: bool = False,
        progress_callback: Optional[Callable[[int, int, str, bool], None]] = None,
    ) -> None:
        """Run the complete documentation generation process using dynamic programming."""
        try:
            # Build dependency graph
            components, leaf_nodes = self.graph_builder.build_dependency_graph()

            logger.debug(f"Found {len(leaf_nodes)} leaf nodes")
            # logger.debug(f"Leaf nodes:\n{'\n'.join(sorted(leaf_nodes)[:200])}")
            # exit()

            # Cluster modules
            working_dir = os.path.abspath(self.config.docs_dir)
            file_manager.ensure_directory(working_dir)
            first_module_tree_path = os.path.join(working_dir, FIRST_MODULE_TREE_FILENAME)
            module_tree_path = os.path.join(working_dir, MODULE_TREE_FILENAME)

            # --- SMART CLUSTERING INVALIDATION ---
            state_manager = StateManager(working_dir)
            current_structure_hash = state_manager.calculate_structure_hash(leaf_nodes)
            last_structure_hash = state_manager.get_last_structure_hash()

            clustering_invalidated = False

            # Check 1: Structure Hash (Files added/removed)
            if last_structure_hash and current_structure_hash != last_structure_hash:
                logger.warning(
                    "♻️  File structure changed (files added/removed). Invalidating cached modules."
                )
                clustering_invalidated = True

            # Check 2: Git Commit ID (if available)
            if self.commit_id:
                last_commit_id = state_manager.get_last_commit_id()
                if last_commit_id and last_commit_id != self.commit_id:
                    logger.warning(
                        f"♻️  Commit changed ({last_commit_id[:7] if last_commit_id else 'None'} -> {self.commit_id[:7]}). Verifying structural changes."
                    )
                    # We trust structure hash primarily, but commit ID gives us a good reason to be suspicious.
                    # If both changed, we definitely re-cluster. Detailed git diff check could be here.

            if clustering_invalidated:
                if os.path.exists(first_module_tree_path):
                    os.remove(first_module_tree_path)
                if os.path.exists(module_tree_path):
                    os.remove(module_tree_path)
                logger.info("🧹 Cleared old module tree cache.")

            # Check if module tree exists
            if os.path.exists(first_module_tree_path):
                logger.debug(f"Module tree found at {first_module_tree_path}")
                module_tree = file_manager.load_json(first_module_tree_path)
            else:
                logger.debug(f"Module tree not found at {module_tree_path}, clustering modules")
                module_tree = await cluster_modules(leaf_nodes, components, self.config)
                file_manager.save_json(module_tree, first_module_tree_path)

            file_manager.save_json(module_tree, module_tree_path)

            logger.debug(f"Grouped components into {len(module_tree)} modules")

            # Generate module documentation using dynamic programming approach
            # This processes leaf modules first, then parent modules
            working_dir = await self.generate_module_documentation(
                components,
                leaf_nodes,
                force=force,
                resume=resume,
                progress_callback=progress_callback,
            )

            # Create documentation metadata
            self.create_documentation_metadata(working_dir, components, len(leaf_nodes))

            logger.debug(
                f"Documentation generation completed successfully using dynamic programming!"
            )
            logger.debug(f"Processing order: leaf modules → parent modules → repository overview")
            logger.debug(f"Documentation saved to: {working_dir}")

            # Update State with new structure hash and commit ID
            state_manager.set_structure_hash(current_structure_hash)
            if self.commit_id:
                state_manager.set_commit_id(self.commit_id)

        except Exception as e:
            logger.error(f"Documentation generation failed: {str(e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            raise
