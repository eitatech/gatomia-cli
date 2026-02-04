"""
CLI adapter for documentation generator backend.

This adapter wraps the existing backend documentation_generator.py
and provides CLI-specific functionality like progress reporting.
"""

from pathlib import Path
from typing import Dict, Any
import asyncio
import os
import logging
import sys


from gatomia.cli.utils.progress import ProgressTracker
from gatomia.cli.models.job import DocumentationJob, LLMConfig
from gatomia.cli.utils.errors import APIError

# Import backend modules
from gatomia.src.be.documentation_generator import DocumentationGenerator
from gatomia.src.config import Config as BackendConfig, set_cli_context


class CLIDocumentationGenerator:
    """
    CLI adapter for documentation generation with progress reporting.

    This class wraps the backend documentation generator and adds
    CLI-specific features like progress tracking and error handling.
    """

    def __init__(
        self,
        repo_path: Path,
        output_dir: Path,
        config: Dict[str, Any],
        verbose: bool = False,
        generate_html: bool = False,
    ):
        """
        Initialize the CLI documentation generator.

        Args:
            repo_path: Repository path
            output_dir: Output directory
            config: LLM configuration
            verbose: Enable verbose output
            generate_html: Whether to generate HTML viewer
        """
        self.repo_path = repo_path
        self.output_dir = output_dir
        self.config = config
        self.verbose = verbose
        self.generate_html = generate_html
        self.progress_tracker = ProgressTracker(total_stages=5, verbose=verbose)
        self.job = DocumentationJob()

        # Setup job metadata
        self.job.repository_path = str(repo_path)
        self.job.repository_name = repo_path.name
        self.job.output_directory = str(output_dir)
        self.job.llm_config = LLMConfig(
            main_model=config.get("main_model", ""),
            cluster_model=config.get("cluster_model", ""),
            base_url=config.get("base_url", ""),
        )

        # Configure backend logging
        self._configure_backend_logging()

    def _configure_backend_logging(self):
        """Configure backend logger for CLI use with colored output."""
        from gatomia.src.be.dependency_analyzer.utils.logging_config import ColoredFormatter

        # Get backend logger (parent of all backend modules)
        backend_logger = logging.getLogger("gatomia.src.be")

        # Remove existing handlers to avoid duplicates
        backend_logger.handlers.clear()

        if self.verbose:
            # In verbose mode, show INFO and above
            backend_logger.setLevel(logging.INFO)

            # Create console handler with formatting
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setLevel(logging.INFO)

            # Use colored formatter for better readability
            colored_formatter = ColoredFormatter()
            console_handler.setFormatter(colored_formatter)

            # Add handler to logger
            backend_logger.addHandler(console_handler)
        else:
            # In non-verbose mode, suppress backend logs (use WARNING level to hide INFO/DEBUG)
            backend_logger.setLevel(logging.WARNING)

            # Create console handler for warnings and errors only
            console_handler = logging.StreamHandler(sys.stderr)
            console_handler.setLevel(logging.WARNING)

            # Use colored formatter even for warnings/errors
            colored_formatter = ColoredFormatter()
            console_handler.setFormatter(colored_formatter)

            backend_logger.addHandler(console_handler)

        # Prevent propagation to root logger to avoid duplicate messages
        backend_logger.propagate = False

    def generate(self) -> DocumentationJob:
        """
        Generate documentation with progress tracking.

        Returns:
            Completed DocumentationJob

        Raises:
            APIError: If LLM API call fails
        """
        self.job.start()

        try:
            # Set CLI context for backend
            set_cli_context(True)

            # Create backend config with CLI settings
            backend_config = self._create_backend_config()

            # Run backend documentation generation
            asyncio.run(self._run_backend_generation(backend_config))

            # Stage 4: HTML Generation (optional)
            if self.generate_html:
                self._run_html_generation()
            else:
                self.progress_tracker.start_stage(4, "HTML Generation (Skipped)")
                self.progress_tracker.complete_stage()

            # Stage 5: Finalization
            self.progress_tracker.start_stage(5, "Finalization")
            self._finalize_metadata()
            self.progress_tracker.complete_stage("Done!")

            # Complete job
            self.job.complete()

            return self.job

        except APIError as e:
            self.job.fail(str(e))
            raise
        except Exception as e:
            self.job.fail(str(e))
            raise
        finally:
            self.progress_tracker.stop()

    def analyze(self) -> DocumentationJob:
        """
        Perform repository analysis (dependency graph and module tree) without generating docs.

        Returns:
            DocumentationJob with analysis results
        """
        self.job.start()

        try:
            # Set CLI context for backend
            set_cli_context(True)

            # Create backend config with CLI settings
            backend_config = self._create_backend_config()

            # Run only analysis stages
            asyncio.run(self._run_analysis_only(backend_config))

            # Complete job
            self.job.complete()
            return self.job

        except APIError as e:
            self.job.fail(str(e))
            raise
        except Exception as e:
            self.job.fail(str(e))
            raise
        finally:
            self.progress_tracker.stop()

    def _create_backend_config(self) -> BackendConfig:
        """Create backend configuration from CLI settings."""
        return BackendConfig.from_cli(
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
            max_token_per_module=self.config.get("max_token_per_module", 36369),
            max_token_per_leaf_module=self.config.get("max_token_per_leaf_module", 16000),
            max_depth=self.config.get("max_depth", 2),
            agent_instructions=self.config.get("agent_instructions"),
        )

    async def _run_analysis_only(self, backend_config: BackendConfig):
        """Run only the analysis stages of the backend."""
        # Stage 1: Dependency Analysis
        self.progress_tracker.start_stage(1, "Dependency Analysis")
        doc_generator = DocumentationGenerator(backend_config)
        components, leaf_nodes = doc_generator.graph_builder.build_dependency_graph()
        self.job.statistics.total_files_analyzed = len(components)
        self.job.statistics.leaf_nodes = len(leaf_nodes)
        self.progress_tracker.complete_stage()

        # Stage 2: Module Clustering
        self.progress_tracker.start_stage(2, "Module Clustering")
        from gatomia.src.be.cluster_modules import cluster_modules
        from gatomia.src.utils import file_manager
        from gatomia.src.config import FIRST_MODULE_TREE_FILENAME, MODULE_TREE_FILENAME

        working_dir = str(self.output_dir.absolute())
        file_manager.ensure_directory(working_dir)
        first_module_tree_path = os.path.join(working_dir, FIRST_MODULE_TREE_FILENAME)
        module_tree_path = os.path.join(working_dir, MODULE_TREE_FILENAME)

        if os.path.exists(first_module_tree_path):
            module_tree = file_manager.load_json(first_module_tree_path)
        else:
            module_tree = await cluster_modules(leaf_nodes, components, backend_config)
            file_manager.save_json(module_tree, first_module_tree_path)

        file_manager.save_json(module_tree, module_tree_path)
        self.job.module_count = len(module_tree)
        self.progress_tracker.complete_stage()

        # Stage 3 is skipped in analyze mode
        self.progress_tracker.start_stage(3, "Documentation Generation (Skipped)")
        self.progress_tracker.complete_stage()
        self.progress_tracker.start_stage(4, "HTML Generation (Skipped)")
        self.progress_tracker.complete_stage()
        self.progress_tracker.start_stage(5, "Finalization")
        self.progress_tracker.complete_stage()

    async def _run_backend_generation(self, backend_config: BackendConfig):
        """Run the backend documentation generation with progress tracking."""

        # Stage 1: Dependency Analysis
        self.progress_tracker.start_stage(1, "Dependency Analysis")
        # if self.verbose:
        #     self.progress_tracker.update_stage(0.2, "Initializing dependency analyzer...")

        # Create documentation generator
        doc_generator = DocumentationGenerator(backend_config)

        # if self.verbose:
        #     self.progress_tracker.update_stage(0.5, "Parsing source files...")

        # Build dependency graph
        try:
            components, leaf_nodes = doc_generator.graph_builder.build_dependency_graph()
            self.job.statistics.total_files_analyzed = len(components)
            self.job.statistics.leaf_nodes = len(leaf_nodes)

            # if self.verbose:
            #     self.progress_tracker.update_stage(1.0, f"Found {len(leaf_nodes)} leaf nodes")
        except Exception as e:
            raise APIError(f"Dependency analysis failed: {e}")

        self.progress_tracker.complete_stage()

        # Stage 2: Module Clustering
        self.progress_tracker.start_stage(2, "Module Clustering")
        # if self.verbose:
        #     self.progress_tracker.update_stage(0.5, "Clustering modules with LLM...")

        # Import clustering function
        from gatomia.src.be.cluster_modules import cluster_modules
        from gatomia.src.utils import file_manager
        from gatomia.src.config import FIRST_MODULE_TREE_FILENAME, MODULE_TREE_FILENAME

        working_dir = str(self.output_dir.absolute())
        file_manager.ensure_directory(working_dir)
        first_module_tree_path = os.path.join(working_dir, FIRST_MODULE_TREE_FILENAME)
        module_tree_path = os.path.join(working_dir, MODULE_TREE_FILENAME)

        try:
            if os.path.exists(first_module_tree_path):
                module_tree = file_manager.load_json(first_module_tree_path)
            else:
                module_tree = await cluster_modules(leaf_nodes, components, backend_config)
                file_manager.save_json(module_tree, first_module_tree_path)

            file_manager.save_json(module_tree, module_tree_path)
            self.job.module_count = len(module_tree)

            # if self.verbose:
            #     self.progress_tracker.update_stage(1.0, f"Created {len(module_tree)} modules")
        except Exception as e:
            raise APIError(f"Module clustering failed: {e}")

        self.progress_tracker.complete_stage()

        # Stage 3: Documentation Generation
        self.progress_tracker.start_stage(3, "Documentation Generation")

        # Define progress callback for backend
        def update_progress(current: int, total: int, module_name: str, cached: bool):
            progress = current / total if total > 0 else 0
            status = " (cached)" if cached else ""
            self.progress_tracker.update_stage(progress, message=f"{module_name}{status}")

        try:
            # Run the actual documentation generation
            await doc_generator.generate_module_documentation(
                components,
                leaf_nodes,
                force=self.config.get("force", False),
                resume=self.config.get("resume", False),
                progress_callback=update_progress,
            )

            # if self.verbose:
            #     self.progress_tracker.update_stage(0.9, "Creating repository overview...")

            # Create metadata
            doc_generator.create_documentation_metadata(working_dir, components, len(leaf_nodes))

            # Collect generated files
            for file_path in os.listdir(working_dir):
                if file_path.endswith(".md") or file_path.endswith(".json"):
                    self.job.files_generated.append(file_path)

        except Exception as e:
            raise APIError(f"Documentation generation failed: {e}")

        self.progress_tracker.complete_stage()

    def _finalize_metadata(self):
        """Finalize the job (metadata already created by backend)."""
        # Just verify metadata exists
        metadata_path = self.output_dir / "metadata.json"

        if not metadata_path.exists():
            # Create our own if backend didn't
            with open(metadata_path, "w") as f:
                f.write(self.job.to_json())
