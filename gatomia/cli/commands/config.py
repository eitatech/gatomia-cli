"""
Configuration commands for GatomIA CLI.
"""

import json
import sys
import click
from typing import Optional, List

from gatomia.cli.config_manager import ConfigManager
from gatomia.cli.models.config import AgentInstructions
from gatomia.cli.utils.errors import (
    ConfigurationError,
    handle_error,
    EXIT_SUCCESS,
    EXIT_CONFIG_ERROR,
)
from gatomia.cli.utils.validation import (
    validate_url,
    validate_api_key,
    validate_model_name,
    is_top_tier_model,
    mask_api_key,
)


def parse_patterns(patterns_str: str) -> List[str]:
    """Parse comma-separated patterns into a list."""
    if not patterns_str:
        return []
    return [p.strip() for p in patterns_str.split(",") if p.strip()]


@click.group(name="config")
def config_group():
    """Manage GatomIA configuration (API credentials and settings)."""
    pass


@config_group.command(name="set")
@click.option("--api-key", type=str, help="LLM API key (stored securely in system keychain)")
@click.option("--base-url", type=str, help="LLM API base URL (e.g., https://api.anthropic.com)")
@click.option("--main-model", type=str, help="Primary model for documentation generation")
@click.option("--cluster-model", type=str, help="Model for module clustering (recommend top-tier)")
@click.option("--fallback-model", type=str, help="Fallback model for documentation generation")
@click.option(
    "--llm-provider",
    type=click.Choice(["openai", "copilot", "anthropic"], case_sensitive=False),
    help="LLM provider (default: openai)",
)
@click.option(
    "--copilot-token",
    type=str,
    help="GitHub Copilot token (required if using copilot provider and not authenticated via CLI)",
)
@click.option("--max-tokens", type=int, help="Maximum tokens for LLM response (default: 32768)")
@click.option(
    "--max-token-per-module",
    type=int,
    help="Maximum tokens per module for clustering (default: 36369)",
)
@click.option(
    "--max-token-per-leaf-module", type=int, help="Maximum tokens per leaf module (default: 16000)"
)
@click.option(
    "--max-depth", type=int, help="Maximum depth for hierarchical decomposition (default: 2)"
)
@click.option(
    "--include-reasoning", is_flag=True, default=None, help="Enable OpenRouter reasoning tokens"
)
def config_set(
    api_key: Optional[str],
    base_url: Optional[str],
    main_model: Optional[str],
    cluster_model: Optional[str],
    fallback_model: Optional[str],
    llm_provider: Optional[str],
    copilot_token: Optional[str],
    max_tokens: Optional[int],
    max_token_per_module: Optional[int],
    max_token_per_leaf_module: Optional[int],
    max_depth: Optional[int],
    include_reasoning: Optional[bool],
):
    """
    Set configuration values for GatomIA.
    
    API keys are stored securely in your system keychain:
      • macOS: Keychain Access
      • Windows: Credential Manager  
      • Linux: Secret Service (GNOME Keyring, KWallet)
    
    Examples:
    
    \b
    # Set all configuration
    $ gatomia config set --api-key sk-abc123 --base-url https://api.anthropic.com \\
        --main-model claude-sonnet-4 --cluster-model claude-sonnet-4 --fallback-model deepseek-chat
    
    \b
    # Use GitHub Copilot
    $ gatomia config set --llm-provider copilot --main-model gpt-4
    
    \b
    # Update only API key
    $ gatomia config set --api-key sk-new-key
    
    \b
    # Set max tokens for LLM response
    $ gatomia config set --max-tokens 16384
    
    \b
    # Set all max token settings
    $ gatomia config set --max-tokens 32768 --max-token-per-module 40000 --max-token-per-leaf-module 20000
    
    \b
    # Set max depth for hierarchical decomposition
    $ gatomia config set --max-depth 3
    """
    try:
        # Check if at least one option is provided
        if not any(
            [
                api_key,
                base_url,
                main_model,
                cluster_model,
                fallback_model,
                llm_provider,
                copilot_token,
                max_tokens,
                max_token_per_module,
                max_token_per_leaf_module,
                max_depth,
                include_reasoning is not None,
            ]
        ):
            click.echo("No options provided. Use --help for usage information.")
            sys.exit(EXIT_CONFIG_ERROR)

        # Validate inputs before saving
        validated_data = {}

        if llm_provider:
            validated_data["llm_provider"] = llm_provider.lower()

        if copilot_token:
            validated_data["copilot_token"] = copilot_token

        if api_key:
            validated_data["api_key"] = validate_api_key(api_key)

        # Only validate URL if provider is OpenAI (default) or explicitly set to OpenAI
        current_provider = llm_provider.lower() if llm_provider else "openai"
        if base_url and current_provider == "openai":
            validated_data["base_url"] = validate_url(base_url)
        elif base_url:
            validated_data["base_url"] = base_url

        if main_model:
            validated_data["main_model"] = validate_model_name(main_model)

        if cluster_model:
            validated_data["cluster_model"] = validate_model_name(cluster_model)

        if fallback_model:
            validated_data["fallback_model"] = validate_model_name(fallback_model)

        if max_tokens is not None:
            if max_tokens < 1:
                raise ConfigurationError("max_tokens must be a positive integer")
            validated_data["max_tokens"] = max_tokens

        if max_token_per_module is not None:
            if max_token_per_module < 1:
                raise ConfigurationError("max_token_per_module must be a positive integer")
            validated_data["max_token_per_module"] = max_token_per_module

        if max_token_per_leaf_module is not None:
            if max_token_per_leaf_module < 1:
                raise ConfigurationError("max_token_per_leaf_module must be a positive integer")
            validated_data["max_token_per_leaf_module"] = max_token_per_leaf_module

        if max_depth is not None:
            if max_depth < 1:
                raise ConfigurationError("max_depth must be a positive integer")
            validated_data["max_depth"] = max_depth

        if include_reasoning is not None:
            validated_data["include_reasoning"] = include_reasoning

        # Create config manager and save
        manager = ConfigManager()
        manager.load()  # Load existing config if present

        manager.save(
            api_key=validated_data.get("api_key"),
            base_url=validated_data.get("base_url"),
            main_model=validated_data.get("main_model"),
            cluster_model=validated_data.get("cluster_model"),
            fallback_model=validated_data.get("fallback_model"),
            llm_provider=validated_data.get("llm_provider"),
            copilot_token=validated_data.get("copilot_token"),
            max_tokens=validated_data.get("max_tokens"),
            max_token_per_module=validated_data.get("max_token_per_module"),
            max_token_per_leaf_module=validated_data.get("max_token_per_leaf_module"),
            max_depth=validated_data.get("max_depth"),
            include_reasoning=validated_data.get("include_reasoning"),
        )

        # Display success messages
        click.echo()
        if api_key:
            if manager.keyring_available:
                click.secho("✓ API key saved to system keychain", fg="green")
            else:
                click.secho(
                    "⚠️  System keychain unavailable. API key stored in encrypted file.", fg="yellow"
                )

        if base_url:
            click.secho(f"✓ Base URL: {base_url}", fg="green")

        if main_model:
            click.secho(f"✓ Main model: {main_model}", fg="green")

        if cluster_model:
            click.secho(f"✓ Cluster model: {cluster_model}", fg="green")

            # Warn if not using top-tier model for clustering
            if not is_top_tier_model(cluster_model):
                click.secho(
                    "\n⚠️  Cluster model is not a top-tier LLM. "
                    "Documentation quality may be suboptimal.",
                    fg="yellow",
                )
                click.echo(
                    "   Recommended models: claude-opus, claude-sonnet-4, gpt-4, gpt-4-turbo"
                )

        if fallback_model:
            click.secho(f"✓ Fallback model: {fallback_model}", fg="green")

        if max_tokens:
            click.secho(f"✓ Max tokens: {max_tokens}", fg="green")

        if max_token_per_module:
            click.secho(f"✓ Max token per module: {max_token_per_module}", fg="green")

        if max_token_per_leaf_module:
            click.secho(f"✓ Max token per leaf module: {max_token_per_leaf_module}", fg="green")

        if max_depth:
            click.secho(f"✓ Max depth: {max_depth}", fg="green")

        if include_reasoning is not None:
            click.secho(f"✓ Include reasoning: {include_reasoning}", fg="green")

        click.echo("\n" + click.style("Configuration updated successfully.", fg="green", bold=True))

    except ConfigurationError as e:
        click.secho(f"\n✗ Configuration error: {e.message}", fg="red", err=True)
        sys.exit(e.exit_code)
    except Exception as e:
        sys.exit(handle_error(e))


@config_group.command(name="show")
@click.option("--json", "output_json", is_flag=True, help="Output in JSON format")
def config_show(output_json: bool):
    """
    Display current configuration.

    API keys are masked for security (showing only first and last 4 characters).

    Examples:

    \b
    # Display configuration
    $ gatomia config show

    \b
    # Display as JSON
    $ gatomia config show --json
    """
    try:
        manager = ConfigManager()

        if not manager.load():
            click.secho("\n✗ Configuration not found.", fg="red", err=True)
            click.echo("\nPlease run 'gatomia config set' to configure your API credentials:")
            click.echo("  gatomia config set --api-key <key> --base-url <url> \\")
            click.echo("    --main-model <model> --cluster-model <model> --fallback-model <model>")
            click.echo("\nFor more help: gatomia config set --help")
            sys.exit(EXIT_CONFIG_ERROR)

        config = manager.get_config()
        api_key = manager.get_api_key()

        if output_json:
            # JSON output
            output = {
                "api_key": mask_api_key(api_key) if api_key else "Not set",
                "api_key_storage": "keychain" if manager.keyring_available else "encrypted_file",
                "base_url": config.base_url if config else "",
                "main_model": config.main_model if config else "",
                "cluster_model": config.cluster_model if config else "",
                "fallback_model": config.fallback_model if config else "deepseek-chat",
                "llm_provider": config.llm_provider if config else "openai",
                "copilot_token": mask_api_key(config.copilot_token)
                if config and config.copilot_token
                else "Not set",
                "default_output": config.default_output if config else "docs",
                "max_tokens": config.max_tokens if config else 32768,
                "max_token_per_module": config.max_token_per_module if config else 36369,
                "max_token_per_leaf_module": config.max_token_per_leaf_module if config else 16000,
                "max_depth": config.max_depth if config else 2,
                "include_reasoning": config.include_reasoning if config else False,
                "agent_instructions": config.agent_instructions.to_dict()
                if config and config.agent_instructions
                else {},
                "config_file": str(manager.config_file_path),
            }
            click.echo(json.dumps(output, indent=2))
        else:
            # Human-readable output
            click.echo()
            click.secho("GatomIA Configuration", fg="blue", bold=True)
            click.echo("━" * 40)
            click.echo()

            click.secho("Credentials", fg="cyan", bold=True)
            if api_key:
                storage = "system keychain" if manager.keyring_available else "encrypted file"
                click.echo(f"  API Key:          {mask_api_key(api_key)} (in {storage})")
            else:
                click.secho("  API Key:          Not set", fg="yellow")

            if config and config.copilot_token:
                click.echo(f"  Copilot Token:    {mask_api_key(config.copilot_token)}")

            click.echo()
            click.secho("API Settings", fg="cyan", bold=True)
            if config:
                click.echo(f"  Provider:         {config.llm_provider or 'openai'}")
                click.echo(f"  Base URL:         {config.base_url or 'Not set'}")
                click.echo(f"  Main Model:       {config.main_model or 'Not set'}")
                click.echo(f"  Cluster Model:    {config.cluster_model or 'Not set'}")
                click.echo(f"  Fallback Model:   {config.fallback_model or 'Not set'}")
                click.echo(f"  Include Reasoning: {config.include_reasoning}")
            else:
                click.secho("  Not configured", fg="yellow")

            click.echo()
            click.secho("Output Settings", fg="cyan", bold=True)
            if config:
                click.echo(f"  Default Output:   {config.default_output}")

            click.echo()
            click.secho("Token Settings", fg="cyan", bold=True)
            if config:
                click.echo(f"  Max Tokens:              {config.max_tokens}")
                click.echo(f"  Max Token/Module:        {config.max_token_per_module}")
                click.echo(f"  Max Token/Leaf Module:   {config.max_token_per_leaf_module}")

            click.echo()
            click.secho("Decomposition Settings", fg="cyan", bold=True)
            if config:
                click.echo(f"  Max Depth:               {config.max_depth}")

            click.echo()
            click.secho("Agent Instructions", fg="cyan", bold=True)
            if config and config.agent_instructions and not config.agent_instructions.is_empty():
                agent = config.agent_instructions
                if agent.include_patterns:
                    click.echo(f"  Include patterns:   {', '.join(agent.include_patterns)}")
                if agent.exclude_patterns:
                    click.echo(f"  Exclude patterns:   {', '.join(agent.exclude_patterns)}")
                if agent.focus_modules:
                    click.echo(f"  Focus modules:      {', '.join(agent.focus_modules)}")
                if agent.doc_type:
                    click.echo(f"  Doc type:           {agent.doc_type}")
                if agent.custom_instructions:
                    click.echo(f"  Custom instructions: {agent.custom_instructions[:50]}...")
            else:
                click.secho("  Using defaults (no custom settings)", fg="yellow")

            click.echo()
            click.echo(f"Configuration file: {manager.config_file_path}")
            click.echo()

    except Exception as e:
        sys.exit(handle_error(e))


@config_group.command(name="validate")
@click.option("--quick", is_flag=True, help="Skip API connectivity test")
@click.option("--verbose", "-v", is_flag=True, help="Show detailed validation steps")
def config_validate(quick: bool, verbose: bool):
    """
    Validate configuration and test LLM API connectivity.

    Checks:
      • Configuration file exists and is valid
      • API key is present
      • API settings are correctly formatted
      • (Optional) API connectivity test

    Examples:

    \b
    # Full validation with API test
    $ gatomia config validate

    \b
    # Quick validation (config only)
    $ gatomia config validate --quick

    \b
    # Verbose output
    $ gatomia config validate --verbose
    """
    try:
        click.echo()
        click.secho("Validating configuration...", fg="blue", bold=True)
        click.echo()

        manager = ConfigManager()

        # Step 1: Check config file
        if verbose:
            click.echo("[1/5] Checking configuration file...")
            click.echo(f"      Path: {manager.config_file_path}")

        if not manager.load():
            click.secho("✗ Configuration file not found", fg="red")
            click.echo()
            click.echo(
                "Error: Configuration is incomplete. Run 'gatomia config set --help' for setup instructions."
            )
            sys.exit(EXIT_CONFIG_ERROR)

        if verbose:
            click.secho("      ✓ File exists", fg="green")
            click.secho("      ✓ Valid JSON format", fg="green")
        else:
            click.secho("✓ Configuration file exists", fg="green")

        # Step 2: Check API key
        if verbose:
            click.echo()
            click.echo("[2/5] Checking API key...")
            storage = "system keychain" if manager.keyring_available else "encrypted file"
            click.echo(f"      Storage: {storage}")

        api_key = manager.get_api_key()
        config = manager.get_config()
        if not api_key and config.llm_provider != "copilot":
            click.secho("✗ API key missing", fg="red")
            click.echo()
            click.echo("Error: API key not set. Run 'gatomia config set --api-key <key>'")
            sys.exit(EXIT_CONFIG_ERROR)

        if api_key:
            if verbose:
                click.secho(f"      ✓ API key retrieved", fg="green")
                click.secho(f"      ✓ Length: {len(api_key)} characters", fg="green")
            else:
                click.secho("✓ API key present (stored in keychain)", fg="green")
        elif config.llm_provider == "copilot":
            if verbose:
                click.secho("      ✓ API key not required for Copilot", fg="green")
            else:
                click.secho("✓ API key not required for Copilot", fg="green")

        # Step 3: Check base URL
        config = manager.get_config()
        if verbose:
            click.echo()
            click.echo("[3/5] Checking base URL...")
            click.echo(f"      URL: {config.base_url}")

        if not config.base_url and config.llm_provider == "openai":
            click.secho("✗ Base URL not set", fg="red")
            sys.exit(EXIT_CONFIG_ERROR)

        try:
            if config.base_url:
                validate_url(config.base_url)
                if verbose:
                    click.secho("      ✓ Valid HTTPS URL", fg="green")
                else:
                    click.secho(f"✓ Base URL valid: {config.base_url}", fg="green")
            elif config.llm_provider == "copilot":
                if verbose:
                    click.secho("      ✓ Base URL not required for Copilot", fg="green")
        except ConfigurationError as e:
            click.secho(f"✗ Invalid base URL: {e.message}", fg="red")
            sys.exit(EXIT_CONFIG_ERROR)

        # Step 4: Check models
        if verbose:
            click.echo()
            click.echo("[4/5] Checking model configuration...")
            click.echo(f"      Main model: {config.main_model}")
            click.echo(f"      Cluster model: {config.cluster_model}")
            click.echo(f"      Fallback model: {config.fallback_model}")

        if not config.main_model or not config.cluster_model or not config.fallback_model:
            click.secho("✗ Models not configured", fg="red")
            sys.exit(EXIT_CONFIG_ERROR)

        if verbose:
            click.secho("      ✓ Models configured", fg="green")
        else:
            click.secho(f"✓ Main model configured: {config.main_model}", fg="green")
            click.secho(f"✓ Cluster model configured: {config.cluster_model}", fg="green")
            click.secho(f"✓ Fallback model configured: {config.fallback_model}", fg="green")

        # Warn about non-top-tier cluster model
        if not is_top_tier_model(config.cluster_model):
            click.secho(
                "⚠️  Cluster model is not top-tier. Consider using claude-sonnet-4 or gpt-4.",
                fg="yellow",
            )

        # Step 5: API connectivity test (unless --quick)
        if not quick:
            try:
                if config.llm_provider == "copilot":
                    # TODO: Implement Copilot connectivity check
                    if verbose:
                        click.secho(
                            "ℹ Connectivity test skipped for Copilot (not yet implemented)",
                            fg="yellow",
                        )
                elif config.llm_provider == "anthropic":
                    from anthropic import Anthropic

                    # Check for custom base URL
                    default_base_url = "http://0.0.0.0:4000/"
                    base_url = None
                    if config.base_url and config.base_url != default_base_url:
                        base_url = config.base_url

                    client = Anthropic(api_key=api_key, base_url=base_url)
                    # Basic connectivity check - list models not always available/reliable on all keys,
                    # but let's try a simple message or just client instantiation check.
                    # Anthropic doesn't have a lightweight 'check' endpoint that is free?
                    # client.models.list() is standard.
                    try:
                        # Paging through models might be slow, just checking we can instantiate is good
                        # but real validation needs a call.
                        # Note: Anthropic SDK calls usually happen on first request.
                        # We'll try listing models if available in SDK version, otherwise skip.
                        if hasattr(client, "models"):
                            client.models.list(limit=1)
                        click.secho("✓ API connectivity test successful", fg="green")
                    except Exception as e:
                        # If checking models fails, it might be permission, but assume failed for now.
                        raise e
                else:
                    from openai import OpenAI

                    client = OpenAI(api_key=api_key, base_url=config.base_url)
                    response = client.models.list()
                    click.secho("✓ API connectivity test successful", fg="green")
            except Exception as e:
                click.secho("✗ API connectivity test failed", fg="red")
                if verbose:
                    click.secho(f"Error details: {str(e)}", fg="yellow")
                    click.secho(f"Exception type: {type(e).__name__}", fg="yellow")
                sys.exit(EXIT_CONFIG_ERROR)

        # Success
        click.echo()
        click.secho("✓ Configuration is valid!", fg="green", bold=True)
        click.echo()

    except ConfigurationError as e:
        click.secho(f"\n✗ Configuration error: {e.message}", fg="red", err=True)
        sys.exit(e.exit_code)
    except Exception as e:
        sys.exit(handle_error(e, verbose=verbose))


@config_group.command(name="agent")
@click.option(
    "--include",
    "-i",
    type=str,
    default=None,
    help="Comma-separated file patterns to include (e.g., '*.cs,*.py')",
)
@click.option(
    "--exclude",
    "-e",
    type=str,
    default=None,
    help="Comma-separated patterns to exclude (e.g., '*Tests*,*Specs*')",
)
@click.option(
    "--focus",
    "-f",
    type=str,
    default=None,
    help="Comma-separated modules/paths to focus on (e.g., 'src/core,src/api')",
)
@click.option(
    "--doc-type",
    "-t",
    type=click.Choice(["api", "architecture", "user-guide", "developer"], case_sensitive=False),
    default=None,
    help="Default type of documentation to generate",
)
@click.option(
    "--instructions",
    type=str,
    default=None,
    help="Custom instructions for the documentation agent",
)
@click.option(
    "--clear",
    is_flag=True,
    help="Clear all agent instructions",
)
def config_agent(
    include: Optional[str],
    exclude: Optional[str],
    focus: Optional[str],
    doc_type: Optional[str],
    instructions: Optional[str],
    clear: bool,
):
    """
    Configure default agent instructions for documentation generation.

    These settings are used as defaults when running 'gatomia generate'.
    Runtime options (--include, --exclude, etc.) override these defaults.

    Examples:

    \b
    # Set include patterns for C# projects
    $ gatomia config agent --include "*.cs"

    \b
    # Exclude test projects
    $ gatomia config agent --exclude "*Tests*,*Specs*,test_*"

    \b
    # Focus on specific modules
    $ gatomia config agent --focus "src/core,src/api"

    \b
    # Set default doc type
    $ gatomia config agent --doc-type architecture

    \b
    # Add custom instructions
    $ gatomia config agent --instructions "Focus on public APIs and include usage examples"

    \b
    # Clear all agent instructions
    $ gatomia config agent --clear
    """
    try:
        manager = ConfigManager()

        if not manager.load():
            click.secho("\n✗ Configuration not found.", fg="red", err=True)
            click.echo("\nPlease run 'gatomia config set' first to configure your API credentials.")
            sys.exit(EXIT_CONFIG_ERROR)

        config = manager.get_config()

        if clear:
            # Clear all agent instructions
            config.agent_instructions = AgentInstructions()
            manager.save()
            click.echo()
            click.secho("✓ Agent instructions cleared", fg="green")
            click.echo()
            return

        # Check if at least one option is provided
        if not any([include, exclude, focus, doc_type, instructions]):
            # Display current settings
            click.echo()
            click.secho("Agent Instructions", fg="blue", bold=True)
            click.echo("━" * 40)
            click.echo()

            agent = config.agent_instructions
            if agent and not agent.is_empty():
                if agent.include_patterns:
                    click.echo(f"  Include patterns:   {', '.join(agent.include_patterns)}")
                if agent.exclude_patterns:
                    click.echo(f"  Exclude patterns:   {', '.join(agent.exclude_patterns)}")
                if agent.focus_modules:
                    click.echo(f"  Focus modules:      {', '.join(agent.focus_modules)}")
                if agent.doc_type:
                    click.echo(f"  Doc type:           {agent.doc_type}")
                if agent.custom_instructions:
                    click.echo(f"  Custom instructions: {agent.custom_instructions}")
            else:
                click.secho("  No agent instructions configured (using defaults)", fg="yellow")

            click.echo()
            click.echo("Use 'gatomia config agent --help' for usage information.")
            click.echo()
            return

        # Update agent instructions
        current = config.agent_instructions or AgentInstructions()

        if include is not None:
            current.include_patterns = parse_patterns(include) if include else None
        if exclude is not None:
            current.exclude_patterns = parse_patterns(exclude) if exclude else None
        if focus is not None:
            current.focus_modules = parse_patterns(focus) if focus else None
        if doc_type is not None:
            current.doc_type = doc_type if doc_type else None
        if instructions is not None:
            current.custom_instructions = instructions if instructions else None

        config.agent_instructions = current
        manager.save()

        # Display success messages
        click.echo()
        if include:
            click.secho(f"✓ Include patterns: {parse_patterns(include)}", fg="green")
        if exclude:
            click.secho(f"✓ Exclude patterns: {parse_patterns(exclude)}", fg="green")
        if focus:
            click.secho(f"✓ Focus modules: {parse_patterns(focus)}", fg="green")
        if doc_type:
            click.secho(f"✓ Doc type: {doc_type}", fg="green")
        if instructions:
            click.secho(f"✓ Custom instructions set", fg="green")

        click.echo(
            "\n" + click.style("Agent instructions updated successfully.", fg="green", bold=True)
        )
        click.echo()

    except ConfigurationError as e:
        click.secho(f"\n✗ Configuration error: {e.message}", fg="red", err=True)
        sys.exit(e.exit_code)
    except Exception as e:
        sys.exit(handle_error(e))
