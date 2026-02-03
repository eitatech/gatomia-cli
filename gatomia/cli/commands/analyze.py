"""
Analyze command for repository structure and dependency analysis.
"""

import sys
import logging
import traceback
from pathlib import Path
from typing import Optional, List
import click
import time

from gatomia.cli.config_manager import ConfigManager
from gatomia.cli.utils.errors import (
    ConfigurationError,
    RepositoryError,
    APIError,
    handle_error,
    EXIT_SUCCESS,
)
from gatomia.cli.utils.repo_validator import (
    validate_repository,
    check_writable_output,
)
from gatomia.cli.utils.logging import create_logger
from gatomia.cli.adapters.doc_generator import CLIDocumentationGenerator
from gatomia.cli.models.config import AgentInstructions


def parse_patterns(patterns_str: str) -> List[str]:
    """Parse comma-separated patterns into a list."""
    if not patterns_str:
        return []
    return [p.strip() for p in patterns_str.split(",") if p.strip()]


@click.command(name="analyze")
@click.option(
    "--output",
    "-o",
    type=click.Path(),
    default="docs",
    help="Output directory for analysis results (default: ./docs)",
)
@click.option(
    "--include",
    "-i",
    type=str,
    default=None,
    help="Comma-separated file patterns to include (e.g., '*.cs,*.py').",
)
@click.option(
    "--exclude",
    "-e",
    type=str,
    default=None,
    help="Comma-separated patterns to exclude (e.g., '*Tests*,*Specs*')",
)
@click.option(
    "--verbose",
    "-v",
    is_flag=True,
    help="Show detailed progress and debug information",
)
@click.option(
    "--max-token-per-module",
    type=int,
    default=None,
    help="Maximum tokens per module for clustering (overrides config)",
)
@click.option(
    "--max-depth",
    type=int,
    default=None,
    help="Maximum depth for hierarchical decomposition (overrides config)",
)
@click.pass_context
def analyze_command(
    ctx,
    output: str,
    include: Optional[str],
    exclude: Optional[str],
    verbose: bool,
    max_token_per_module: Optional[int],
    max_depth: Optional[int],
):
    """
    Perform repository analysis without generating documentation.

    Generates dependency graphs and module trees (module_tree.json,
    first_module_tree.json) in the specified output directory.
    """
    logger = create_logger(verbose=verbose)
    start_time = time.time()

    # Suppress httpx INFO logs
    logging.getLogger("httpx").setLevel(logging.WARNING)

    try:
        # Pre-generation checks
        logger.step("Validating configuration...", 1, 3)

        # Load configuration
        config_manager = ConfigManager()
        if not config_manager.load():
            raise ConfigurationError(
                "Configuration not found or invalid.\n\n"
                "Please run 'mia config set' to configure your LLM API credentials."
            )

        if not config_manager.is_configured():
            raise ConfigurationError(
                "Configuration is incomplete. Please run 'mia config validate'"
            )

        config = config_manager.get_config()
        api_key = config_manager.get_api_key()

        logger.success("Configuration valid")

        # Validate repository
        logger.step("Validating repository...", 2, 3)

        repo_path = Path.cwd()
        repo_path, _ = validate_repository(repo_path)

        # Validate output directory
        output_dir = Path(output).expanduser().resolve()
        check_writable_output(output_dir.parent)

        logger.success("Repository and output path valid")

        # Run analysis
        logger.step("Running analysis...", 3, 3)
        click.echo()

        # Create agent instructions from CLI options
        agent_instructions_dict = None
        if any([include, exclude]):
            instructions = AgentInstructions(
                include_patterns=parse_patterns(include) if include else None,
                exclude_patterns=parse_patterns(exclude) if exclude else None,
            )
            agent_instructions_dict = instructions.to_dict()

        # Create generator adapter
        generator = CLIDocumentationGenerator(
            repo_path=repo_path,
            output_dir=output_dir,
            config={
                "main_model": config.main_model,
                "cluster_model": config.cluster_model,
                "fallback_model": config.fallback_model,
                "base_url": config.base_url,
                "api_key": api_key,
                "llm_provider": config.llm_provider,
                "copilot_token": config.copilot_token,
                "agent_instructions": agent_instructions_dict,
                "max_token_per_module": max_token_per_module
                if max_token_per_module is not None
                else config.max_token_per_module,
                "max_depth": max_depth if max_depth is not None else config.max_depth,
            },
            verbose=verbose,
        )

        # Run analysis only
        job = generator.analyze()

        # Result
        analysis_time = time.time() - start_time

        click.echo()
        click.secho("✓ Analysis completed successfully!", fg="green", bold=True)
        click.echo(f"  Output directory: {output_dir}")
        click.echo(f"  Time elapsed: {analysis_time:.1f}s")
        click.echo(f"  Files analyzed: {job.statistics.total_files_analyzed}")
        click.echo(f"  Modules created: {job.module_count}")
        click.echo()
        click.echo("Files generated:")
        click.echo(f"  - {output_dir}/module_tree.json")
        click.echo(f"  - {output_dir}/first_module_tree.json")
        click.echo(f"  - {output_dir.parent}/dependency_graphs/*.json")
        click.echo()
        click.echo("You can now run 'mia generate' to create full documentation.")

    except ConfigurationError as e:
        logger.error(e.message)
        sys.exit(e.exit_code)
    except RepositoryError as e:
        logger.error(e.message)
        sys.exit(e.exit_code)
    except APIError as e:
        logger.error(e.message)
        sys.exit(e.exit_code)
    except KeyboardInterrupt:
        click.echo("\n\nInterrupted by user")
        sys.exit(130)
    except Exception as e:
        sys.exit(handle_error(e, verbose=verbose))
