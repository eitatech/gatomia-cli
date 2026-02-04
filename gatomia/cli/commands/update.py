"""
Update command for modifying existing documentation.
"""

import sys
import logging
import traceback
from pathlib import Path
from typing import Optional
import click
import asyncio

from gatomia.cli.config_manager import ConfigManager
from gatomia.cli.utils.errors import (
    ConfigurationError,
    RepositoryError,
    APIError,
    handle_error,
)
from gatomia.cli.utils.repo_validator import (
    validate_repository,
)
from gatomia.cli.utils.logging import create_logger
from gatomia.cli.adapters.doc_updater import CLIDocumentationUpdater


@click.command(name="update")
@click.argument("pattern")
@click.argument("instruction", required=False)
@click.option(
    "--output",
    "-o",
    type=click.Path(),
    default="docs",
    help="Output directory containing the documentation (default: ./docs)",
)
@click.option(
    "--verbose",
    "-v",
    is_flag=True,
    help="Show detailed progress and debug information",
)
@click.option(
    "--refresh",
    "-r",
    is_flag=True,
    help="Force re-analysis of dependencies before updating",
)
def update_command(
    pattern: str,
    instruction: Optional[str],
    output: str,
    verbose: bool,
    refresh: bool,
):
    """
    Update documentation using natural language.

    PATTERN: Partial filename to identify the document (e.g., 'wallet_domain').
    INSTRUCTION: What to change (e.g., 'Add a diagram showing x').
                 If not provided, you will be prompted.
    """
    logger = create_logger(verbose=verbose)

    # Suppress httpx INFO logs
    logging.getLogger("httpx").setLevel(logging.WARNING)

    try:
        # Prompt for instruction if missing
        if not instruction:
            instruction = click.prompt("Please enter your update instruction")

        if not instruction:
            logger.warning("No instruction provided. Exiting.")
            return

        # Load configuration
        config_manager = ConfigManager()
        if not config_manager.load():
            raise ConfigurationError(
                "Configuration not found or invalid.\n"
                "Please run 'gatomia config set' to configure your credentials."
            )

        if not config_manager.is_configured():
            raise ConfigurationError(
                "Configuration is incomplete. Please run 'gatomia config validate'"
            )

        config = config_manager.get_config()

        # Validate repository
        repo_path = Path.cwd()
        # We don't necessarily need strict repo validation for just updating a doc,
        # but it helps to ensure we are in a valid context.
        # repo_path, _ = validate_repository(repo_path)

        output_dir = Path(output).expanduser().resolve()

        logger.info(f"Target pattern: '{pattern}'")
        logger.info(f"Instruction: '{instruction}'")
        if refresh:
            logger.info("Refresh enabled: Dependencies will be re-analyzed.")

        updater = CLIDocumentationUpdater(
            repo_path=repo_path,
            output_dir=output_dir,
            config={
                "base_url": config.base_url,
                "api_key": config_manager.get_api_key(),
                "main_model": config.main_model,
                "cluster_model": config.cluster_model,
                "fallback_model": config.fallback_model,
                "llm_provider": config.llm_provider,
                "copilot_token": config.copilot_token,
                "max_tokens": config.max_tokens,
            },
            verbose=verbose,
        )

        logger.step("Updating documentation...", 1, 1)

        # Run update
        updated_file = asyncio.run(updater.update_document(pattern, instruction, refresh=refresh))

        logger.success(f"Successfully updated: {updated_file}")

    except ConfigurationError as e:
        logger.error(e.message)
        sys.exit(e.exit_code)
    except APIError as e:
        logger.error(str(e))
        sys.exit(1)
    except Exception as e:
        sys.exit(handle_error(e, verbose=verbose))
