"""
CLI adapter for documentation updates.
"""

from pathlib import Path
from typing import Dict, Any, List, Optional
import logging
import asyncio
import json

from gatomia.cli.utils.errors import APIError, ConfigurationError
from gatomia.src.be.llm_services import call_llm
from gatomia.src.be.prompt_template import format_update_doc_prompt, format_create_doc_prompt
from gatomia.src.config import Config as BackendConfig, MODULE_TREE_FILENAME
from gatomia.src.be.dependency_analyzer import DependencyGraphBuilder

logger = logging.getLogger(__name__)


class CLIDocumentationUpdater:
    """
    Handles documentation updates via natural language commands.
    """

    def __init__(
        self,
        repo_path: Path,
        output_dir: Path,
        config: Dict[str, Any],
        verbose: bool = False,
    ):
        self.repo_path = repo_path
        self.output_dir = output_dir
        self.config = config
        self.verbose = verbose

        # Create backend config
        self.backend_config = BackendConfig.from_cli(
            repo_path=str(self.repo_path),
            output_dir=str(self.output_dir),
            llm_base_url=self.config.get("base_url"),
            llm_api_key=self.config.get("api_key"),
            main_model=self.config.get("main_model"),
            cluster_model=self.config.get("cluster_model"),
            fallback_model=self.config.get("fallback_model"),
            llm_provider=self.config.get("llm_provider", "openai"),
            copilot_token=self.config.get("copilot_token"),
            max_tokens=self.config.get("max_tokens", 32768),
        )

        self.graph_builder = DependencyGraphBuilder(self.backend_config)

    async def update_document(
        self, file_pattern: str, instruction: str, refresh: bool = False
    ) -> str:
        """
        Update or Create a document based on user instruction.

        Args:
            file_pattern: Partial or full filename to match
            instruction: User's update instruction
            refresh: Whether to force re-analysis of dependencies

        Returns:
            Path to the updated/created file
        """
        # 1. Smart Context Loading & Refactoring Support
        if refresh or any(
            k in instruction.lower() for k in ["refactor", "new structure", "changed dependencies"]
        ):
            logger.info("Triggering dependency analysis refresh...")
            # We assume build() is synchronous or we'd need await
            # Based on previous analysis, graph builder might be synchronous
            self.graph_builder.build(str(self.backend_config.repo_path))

        repo_structure, dependency_graph = self._load_context()
        repo_context = "(Context loaded from graphs)"

        # 2. Resolve File (Touch Logic)
        target_file = None
        mode = "update"

        try:
            target_file = self._resolve_file(file_pattern)
            logger.info(f"Targeting existing file: {target_file.name}")
        except ConfigurationError:
            # If exact match or pattern not found, assume creation if instruction suggests it
            # For now, we will default to creation mode if not found, but we should make sure the pattern is a valid filename
            logger.info(f"File pattern '{file_pattern}' not found. Switching to CREATION mode.")
            mode = "create"
            if not file_pattern.endswith(".md"):
                file_pattern += ".md"
            target_file = self.output_dir / file_pattern

        # 3. Read Content (Update Mode Only)
        current_content = ""
        if mode == "update":
            try:
                current_content = target_file.read_text(encoding="utf-8")
            except Exception as e:
                raise APIError(f"Failed to read file {target_file.name}: {e}")

        # 4. Prepare Prompt
        if mode == "update":
            system_prompt = format_update_doc_prompt(
                current_content=current_content,
                user_instruction=instruction,
                repo_structure=json.dumps(repo_structure, indent=2),
                dependency_graph=json.dumps(dependency_graph, indent=2),
                repo_context=repo_context,
            )
        else:
            system_prompt = format_create_doc_prompt(
                user_instruction=instruction,
                repo_structure=json.dumps(repo_structure, indent=2),
                dependency_graph=json.dumps(dependency_graph, indent=2),
                repo_context=repo_context,
            )

        logger.info(f"Sending {mode.upper()} request to LLM...")

        try:
            # Call LLM
            full_prompt = f"{system_prompt}\n\nPlease {mode} the documentation as requested."

            response = await call_llm(
                prompt=full_prompt,
                config=self.backend_config,
                model=self.backend_config.main_model,
                temperature=0.2,  # Low temp for precision
            )

            updated_content = response

            # Simple validation
            if not updated_content or len(updated_content) < 10:
                raise APIError("LLM returned empty or invalid response")

            # Write back
            target_file.parent.mkdir(parents=True, exist_ok=True)
            target_file.write_text(updated_content, encoding="utf-8")

            return str(target_file)

        except Exception as e:
            raise APIError(f"Failed to {mode} documentation: {e}")

    def _resolve_file(self, pattern: str) -> Path:
        """Find a single matching file in the output directory."""
        if not self.output_dir.exists():
            # If output dir doesn't exist, we can't find files, so raise Error -> triggers creation flow
            raise ConfigurationError(f"Output directory {self.output_dir} does not exist.")

        files = list(self.output_dir.glob("**/*.md"))
        matches = [f for f in files if pattern.lower() in f.name.lower()]

        if not matches:
            raise ConfigurationError(f"No files found matching pattern '{pattern}'")

        if len(matches) > 1:
            # Try exact match
            exact_matches = [f for f in matches if f.name == pattern or f.name == f"{pattern}.md"]
            if len(exact_matches) == 1:
                return exact_matches[0]

            match_names = ", ".join([f.name for f in matches[:5]])
            raise ConfigurationError(
                f"Multiple files match '{pattern}': {match_names}...\nPlease be more specific."
            )

        return matches[0]

    def _load_context(self):
        """Load module tree and dependency graphs."""
        repo_structure = {}
        dependency_graph = {}

        # Load Module Tree
        module_tree_path = self.output_dir / "temp" / MODULE_TREE_FILENAME
        if module_tree_path.exists():
            try:
                repo_structure = json.loads(module_tree_path.read_text())
            except Exception as e:
                logger.warning(f"Failed to load module tree: {e}")

        # Load Dependency Graphs (merge all)
        dep_graph_dir = self.output_dir / "temp" / "dependency_graphs"
        if dep_graph_dir.exists():
            for f in dep_graph_dir.glob("*.json"):
                try:
                    graph = json.loads(f.read_text())
                    # deeply merge or just update top level?
                    # For simplicity, we assume disjoint graphs or we just update
                    dependency_graph.update(graph)
                except Exception as e:
                    logger.warning(f"Failed to load dependency graph {f.name}: {e}")

        return repo_structure, self._simplify_graph(dependency_graph)

    def _simplify_graph(self, graph: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a lightweight version of the graph for the LLM context.
        Removes heavy fields like 'source_code'.
        """
        simplified = {}
        for key, node in graph.items():
            simplified[key] = {
                "id": node.get("id"),
                "name": node.get("name"),
                "type": node.get("component_type"),
                "depends_on": node.get("depends_on", []),
                # "docstring": node.get("docstring", "")[:200], # Optional: include truncated docstring
            }
        return simplified
