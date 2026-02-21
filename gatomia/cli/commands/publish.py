"""
Publish command for documentation generation to GitHub Wiki.
"""

import os
import sys
import shutil
import tempfile
import traceback
from pathlib import Path
from typing import Optional
import click
import git
from git.exc import GitCommandError

from gatomia.cli.git_manager import GitManager
from gatomia.cli.utils.errors import RepositoryError, handle_error, EXIT_SUCCESS
from gatomia.cli.utils.logging import create_logger


@click.command(name="publish")
@click.option(
    "--input",
    "-i",
    type=click.Path(exists=True, file_okay=False, dir_okay=True),
    default="docs",
    help="Directory containing the Markdown documentation to publish (default: ./docs)",
)
@click.option(
    "--wiki-url",
    type=str,
    default=None,
    help="Override the automatically detected Wiki URL (e.g., git@github.com:user/repo.wiki.git)",
)
@click.option(
    "--verbose",
    "-v",
    is_flag=True,
    help="Show detailed progress and debug information",
)
def publish_command(
    input: str,
    wiki_url: Optional[str],
    verbose: bool,
):
    """
    Publish generated documentation to the repository's GitHub Wiki.

    This command clones the wiki repository (e.g., repository.wiki.git),
    copies the generated Markdown files into it, commits the changes, and pushes
    them to GitHub.

    Examples:

    \b
    # Basic publish (publishes from ./docs)
    $ gatomia publish

    \b
    # Publish from a custom directory
    $ gatomia publish --input ./my-docs

    \b
    # Publish to a specific wiki URL
    $ gatomia publish --wiki-url git@github.com:username/repo.wiki.git
    """
    logger = create_logger(verbose=verbose)

    try:
        input_dir = Path(input).expanduser().resolve()
        repo_path = Path.cwd()

        logger.step("Validating input directory...", 1, 4)
        if not input_dir.exists() or not input_dir.is_dir():
            raise RepositoryError(
                f"Input directory does not exist or is not a directory: {input_dir}"
            )

        # Check for markdown files
        md_files = list(input_dir.rglob("*.md"))
        if not md_files:
            logger.warning(f"No Markdown files found in {input_dir}. Nothing to publish.")
            sys.exit(EXIT_SUCCESS)

        logger.success(f"Found {len(md_files)} Markdown files to publish")

        logger.step("Determining Wiki URL...", 2, 4)
        if wiki_url:
            target_wiki_url = wiki_url
        else:
            git_manager = GitManager(repo_path)
            remote_url = git_manager.get_remote_url()

            if not remote_url:
                raise RepositoryError(
                    "Could not detect git remote URL. Ensure this is a git repository "
                    "with an origin remote, or provide the URL via --wiki-url."
                )

            # Transform standard URL to Wiki URL
            # E.g., https://github.com/user/repo.git -> https://github.com/user/repo.wiki.git
            # or git@github.com:user/repo.git -> git@github.com:user/repo.wiki.git
            if remote_url.endswith(".git"):
                target_wiki_url = remote_url[:-4] + ".wiki.git"
            else:
                target_wiki_url = remote_url + ".wiki.git"

        logger.success(f"Using Wiki URL: {target_wiki_url}")

        logger.step("Cloning Wiki repository...", 3, 4)
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_repo_path = Path(temp_dir) / "wiki"

            try:
                if verbose:
                    logger.debug(f"Cloning {target_wiki_url} into {temp_repo_path}")
                repo = git.Repo.clone_from(target_wiki_url, temp_repo_path)
            except GitCommandError as e:
                raise RepositoryError(
                    f"Failed to clone Wiki repository.\n\n"
                    f"Ensure the Wiki feature is enabled in your GitHub repository settings, "
                    f"and that the URL is correct and accessible.\n\n"
                    f"Error details: {e}"
                )

            logger.success("Wiki repository cloned successfully")

            logger.step("Publishing documentation...", 4, 4)

            # Copy all files from input_dir to the root of the wiki temp_repo_path
            # Warning: GitHub Wiki expects flat markdown files or specific folder structures.
            files_copied = 0
            for item in input_dir.rglob("*"):
                if item.is_file():
                    # Preserve relative path but copy to wiki root path
                    rel_path = item.relative_to(input_dir)
                    target_path = temp_repo_path / rel_path

                    # Ensure target directory exists
                    target_path.parent.mkdir(parents=True, exist_ok=True)

                    shutil.copy2(item, target_path)
                    files_copied += 1
                    if verbose:
                        logger.debug(f"Copied {rel_path}")

            if files_copied == 0:
                logger.warning("No files were copied.")
                sys.exit(EXIT_SUCCESS)

            # Check if there are changes to commit
            if not repo.is_dirty(untracked_files=True):
                logger.info("No changes to publish. Wiki is up to date.")
                sys.exit(EXIT_SUCCESS)

            try:
                # Add all files
                repo.git.add(A=True)

                # Commit
                commit_message = "Update documentation via GatomIA CLI"
                repo.index.commit(commit_message)

                # Push
                if verbose:
                    logger.debug("Pushing changes to remote Wiki repository")
                origin = repo.remote(name="origin")
                origin.push()

                logger.success(
                    f"Successfully published {files_copied} files to the Wiki repository."
                )

            except GitCommandError as e:
                raise RepositoryError(f"Failed to commit or push changes: {e}")

    except RepositoryError as e:
        logger.error(e.message)
        logger.error(f"Traceback: {traceback.format_exc()}")
        sys.exit(e.exit_code)
    except KeyboardInterrupt:
        click.echo("\n\nInterrupted by user")
        sys.exit(130)
    except Exception as e:
        sys.exit(handle_error(e, verbose=verbose))
