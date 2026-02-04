"""
Main CLI application for GatomIA using Click framework.
"""

import sys
import click

from gatomia import __version__


@click.group()
@click.version_option(version=__version__, prog_name="GatomIA CLI")
@click.pass_context
def cli(ctx):
    """
    GatomIA: Transform codebases into comprehensive documentation.

    Generate AI-powered documentation for your code repositories with support
    for Python, Java, JavaScript, TypeScript, C, C++, and C#.
    """
    # Ensure context object exists
    ctx.ensure_object(dict)


@cli.command()
def version():
    """Display version information."""
    click.echo(f"GatomIA CLI v{__version__}")
    click.echo("Python-based documentation generator using AI analysis")


# Import commands
from gatomia.cli.commands.config import config_group
from gatomia.cli.commands.generate import generate_command
from gatomia.cli.commands.analyze import analyze_command
from gatomia.cli.commands.update import update_command

# Register command groups
cli.add_command(config_group)
cli.add_command(generate_command, name="generate")
cli.add_command(analyze_command, name="analyze")
cli.add_command(update_command, name="update")


def main():
    """Entry point for the CLI."""
    try:
        cli(obj={})
    except KeyboardInterrupt:
        click.echo("\n\nInterrupted by user", err=True)
        sys.exit(130)
    except Exception as e:
        click.secho(f"\n✗ Unexpected error: {e}", fg="red", err=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
