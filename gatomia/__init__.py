"""
GatomIA: Transform codebases into comprehensive documentation using AI-powered analysis.

This package provides a CLI tool for generating documentation from code repositories.
"""

__version__ = "1.0.1"
__author__ = "GatomIA Contributors"
__license__ = "MIT"

from gatomia.cli.main import cli

__all__ = ["cli", "__version__"]
