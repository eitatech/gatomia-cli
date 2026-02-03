import logging
import os
import traceback
import asyncio
from typing import Dict, Any, List

# pydantic_ai
from pydantic_ai import Agent, ModelSettings

# Local imports
from gatomia.src.be.agent_tools.deps import GatomIADeps
from gatomia.src.be.agent_tools.read_code_components import read_code_components_tool
from gatomia.src.be.agent_tools.str_replace_editor import str_replace_editor_tool
from gatomia.src.be.agent_tools.generate_sub_module_documentations import (
    generate_sub_module_documentation_tool,
)
from gatomia.src.be.llm_services import create_fallback_models
from gatomia.src.be.prompt_template import (
    format_user_prompt,
    format_system_prompt,
    format_leaf_system_prompt,
)
from gatomia.src.be.utils import is_complex_module
from gatomia.src.config import (
    Config,
    MODULE_TREE_FILENAME,
    OVERVIEW_FILENAME,
)
from gatomia.src.utils import file_manager
from gatomia.src.be.dependency_analyzer.models.core import Node

# Configure logging
logger = logging.getLogger(__name__)


class AgentOrchestrator:
    """Orchestrates the AI agents for documentation generation."""

    def __init__(self, config: Config):
        self.config = config
        self._semaphore = asyncio.Semaphore(5)  # Limit concurrent LLM calls
        self.fallback_models = create_fallback_models(config)
        self.custom_instructions = config.get_prompt_addition() if config else None

    def create_agent(
        self, module_name: str, components: Dict[str, Any], core_component_ids: List[str]
    ) -> Agent:
        """Create an appropriate agent based on module complexity."""

        if is_complex_module(components, core_component_ids):
            return Agent(
                self.fallback_models,
                name=module_name,
                deps_type=GatomIADeps,
                tools=[
                    read_code_components_tool,
                    str_replace_editor_tool,
                    generate_sub_module_documentation_tool,
                ],
                system_prompt=format_system_prompt(module_name, self.custom_instructions),
            )
        else:
            return Agent(
                self.fallback_models,
                name=module_name,
                deps_type=GatomIADeps,
                tools=[read_code_components_tool, str_replace_editor_tool],
                system_prompt=format_leaf_system_prompt(module_name, self.custom_instructions),
            )

    async def process_module(
        self,
        module_name: str,
        components: Dict[str, Node],
        core_component_ids: List[str],
        module_path: List[str],
        working_dir: str,
    ) -> Dict[str, Any]:
        """Process a single module and generate its documentation."""
        logger.info(f"Processing module: {module_name}")

        # Load or create module tree
        module_tree_path = os.path.join(working_dir, MODULE_TREE_FILENAME)
        module_tree = file_manager.load_json(module_tree_path)

        # Create agent
        agent = self.create_agent(module_name, components, core_component_ids)

        # Create dependencies
        deps = GatomIADeps(
            absolute_docs_path=working_dir,
            absolute_repo_path=str(os.path.abspath(self.config.repo_path)),
            registry={},
            components=components,
            path_to_current_module=module_path,
            current_module_name=module_name,
            module_tree=module_tree,
            max_depth=self.config.max_depth,
            current_depth=1,
            config=self.config,
            custom_instructions=self.custom_instructions,
        )

        # check if overview docs already exists
        overview_docs_path = os.path.join(working_dir, OVERVIEW_FILENAME)
        if os.path.exists(overview_docs_path):
            logger.info(f"✓ Overview docs already exists at {overview_docs_path}")
            return module_tree

        # check if module docs already exists
        docs_path = os.path.join(working_dir, f"{module_name}.md")
        if os.path.exists(docs_path):
            logger.info(f"✓ Module docs already exists at {docs_path}")
            return module_tree

        # Run agent
        max_retries = 3
        retry_delay = 2

        for attempt in range(max_retries):
            try:
                async with self._semaphore:
                    await agent.run(
                        format_user_prompt(
                            module_name=module_name,
                            core_component_ids=core_component_ids,
                            components=components,
                            module_tree=deps.module_tree,
                            max_tokens=self.config.max_token_per_module,
                        ),
                        deps=deps,
                        model_settings=ModelSettings(max_tokens=self.config.max_tokens),
                    )

                # Save updated module tree
                file_manager.save_json(deps.module_tree, module_tree_path)
                logger.debug(f"Successfully processed module: {module_name}")

                return deps.module_tree

            except Exception as e:
                logger.warning(
                    f"Error processing module {module_name} (attempt {attempt + 1}/{max_retries}): {str(e)}"
                )
                if attempt < max_retries - 1:
                    await asyncio.sleep(retry_delay)
                    retry_delay *= 2  # Exponential backoff
                else:
                    logger.error(
                        f"Failed to process module {module_name} after {max_retries} attempts"
                    )
                    logger.error(f"Traceback: {traceback.format_exc()}")
                    raise
