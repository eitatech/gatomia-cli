import sys
import os
from unittest.mock import MagicMock, patch
from gatomia.src.be.documentation_generator import DocumentationGenerator
from gatomia.src.be.prompt_template import format_user_prompt
from gatomia.src.be.dependency_analyzer.models.core import Node
from gatomia.src.config import Config


def verify_summarization():
    print("Verifying Smart Summarization...")
    config = MagicMock(spec=Config)
    config.docs_dir = "/tmp/gatomia_docs"
    # AgentOrchestrator inside generator might be tricky if it does stuff in init, but we mock it or ignoring
    # DocumentationGenerator init:
    # self.agent_orchestrator = AgentOrchestrator(config) -> this might fail if config is mock
    # So we patch AgentOrchestrator

    with patch("gatomia.src.be.documentation_generator.AgentOrchestrator") as MockOrchestrator:
        with patch("gatomia.src.be.documentation_generator.DependencyGraphBuilder"):
            generator = DocumentationGenerator(config)

            full_markdown = """# Module Title

## Overview
This is the overview section.

## Architecture
Architecture details here.

## Core Components
Should be excluded.
"""
            summary = generator._extract_module_summary(full_markdown)

            # Debug output
            # print(f"DEBUG SUMMARY:\n{summary}\n---")

            assert "# Module Title" in summary, "Missing title"
            assert "## Overview" in summary, "Missing Overview"
            assert "## Architecture" in summary, "Missing Architecture"
            assert "## Core Components" not in summary, "Failed to exclude Core Components"
            print("✅ Summarization Logic OK")


def verify_imports_extraction():
    print("Verifying Imports Extraction...")

    node1 = Node(
        id="comp1",
        name="Component1",
        file_path="/tmp/file1.py",
        relative_path="src/file1.py",
        source_code="class Component1:\n    pass",
        start_line=10,
        end_line=12,
        component_type="class",
        component_id="comp1",
    )

    components = {"comp1": node1}
    module_tree = {"MyModule": {"components": ["comp1"], "children": {}}}

    with patch("gatomia.src.utils.file_manager.load_text") as mock_load:
        mock_load.return_value = (
            "import os\nfrom typing import List\n\n\nclass Component1:\n    pass"
        )

        prompt = format_user_prompt(
            module_name="MyModule",
            core_component_ids=["comp1"],
            components=components,
            module_tree=module_tree,
        )

        # print(f"DEBUG PROMPT:\n{prompt[:500]}...\n---")

        assert "## Imports/Context:" in prompt, "Missing Imports section"
        assert "import os" in prompt, "Missing specific import"
        assert "class Component1" in prompt, "Missing component code"
        print("✅ Imports Extraction OK")


if __name__ == "__main__":
    try:
        verify_summarization()
        verify_imports_extraction()
        print("All checks passed successfully.")
    except AssertionError as e:
        print(f"❌ Verification Failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
