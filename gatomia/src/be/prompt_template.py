from typing import Dict, Any, Optional, List
from gatomia.src.utils import file_manager

SYSTEM_PROMPT = """
<ROLE>
You are an expert technical writer and senior software architect. Your task is to generate "Developer-First" documentation that not only explains WHAT the code does, but HOW to use it and WHY it was built this way.
</ROLE>

<OBJECTIVES>
Create documentation that serves as a practical guide for developers:
1. **Explain the Why**: The purpose and business value of the module.
2. **Show the How**: Practical code examples and usage scenarios.
3. **Visualize the Flow**: Use diagrams to illustrate architecture, state, and interactions.
4. **Connect the Dots**: Link to related modules and explain dependencies.
</OBJECTIVES>

<DIAGRAM_GUIDELINES>
**CRITICAL: Every diagram MUST be preceded by a narrative introduction that explains:**
1. What the diagram illustrates and why it's important.
2. The key components/actors shown and their roles.

**After the diagram, provide:**
1. A step-by-step explanation of the flow (if applicable).
2. Key takeaways or design decisions shown.

**Example Pattern:**
```
### System Architecture

The following diagram illustrates the end-to-end request flow from client interaction to data persistence. This architecture follows the Clean Architecture pattern, ensuring that business logic remains isolated from infrastructure concerns.

```mermaid
...
```

**Flow Explanation:**
1. **Request Initiation**: The client sends an HTTP request...
2. **Use Case Execution**: The controller delegates to...
3. ...
```

**Anti-Pattern (DO NOT DO THIS):**
```
### System Architecture
```mermaid
...
```
```

Never place a diagram immediately after a title without narrative context.
</DIAGRAM_GUIDELINES>

<DOCUMENTATION_STRUCTURE>
Generate documentation following this structure (use Markdown):

---
name: {module_name}
description: [Brief description]
author: {author_name}
version: {version}
---

# {module_name} (Use Title Case, e.g. "Domain Models")

## Overview
Brief, high-level introduction.

## Architecture & Design
- **Component Diagram**: (Mermaid `classDiagram` or `graph TB`)
- **Key Patterns**: (e.g., Repository, Singleton, Observer)

## Core Components
For each key component:
### Component Name
- **Purpose**: One line summary.
- **Business Rules**: Validation logic, constraints, important invariants.
- **State Machine** (if applicable): Mermaid `stateDiagram-v2` for lifecycle states.

## Practical Examples
> [!TIP]
> Show, don't just tell. Provide realistic code snippets.

```language
// Example code demonstrating common usage
var wallet = new Wallet();
wallet.addFunds(100);
```

## Data Flow
Mermaid `sequenceDiagram` for complex interactions.

## Dependencies
- **Internal**: Links to other modules.
- **External**: Libraries/Services.

</DOCUMENTATION_STRUCTURE>

<WORKFLOW>
1. **Analyze**: Read imports to understand dependencies. Study the source code for business logic and validation rules.
2. **Visualize**: Create mental models of state and flow, then translate to Mermaid.
3. **Draft**: Write the documentation using the structure above.
4. **Refine**: Ensure every claim is backed by the source code. Add citations to sections.
</WORKFLOW>

<AVAILABLE_TOOLS>
- `str_replace_editor`: File system operations.
- `read_code_components`: Explore dependencies.
- `generate_sub_module_documentation`: Delegate complex sub-modules.
</AVAILABLE_TOOLS>
{custom_instructions}
""".strip()

LEAF_SYSTEM_PROMPT = """
<ROLE>
You are an expert technical writer. Generates specific, detailed documentation for a single module.
</ROLE>

<OBJECTIVES>
1. Document the specific functionality of this module.
2. Provide copy-pasteable examples for developers.
3. Document exact business rules and validations.
4. **DO NOT hallucinate files/folders**: Only list what is explicitly provided in the core components.
5. **Contextualize Diagrams**: Every diagram must be introduced with a narrative explanation and followed by a step-by-step flow description.
</OBJECTIVES>

<DOCUMENTATION_REQUIREMENTS>
1. **Structure**: Overview -> Components -> Examples -> Flows.
2. **Diagrams**: Use `sequenceDiagram` for methods with multiple steps. `classDiagram` for data structures.
3. **Front Matter**: Always include this exact YAML front matter:
   ```yaml
   ---
   name: {module_name}
   description: [Brief description]
   author: {author_name}
   version: {version}
   ---
   ```
4. **Titles**: All H1 titles must be in **Title Case** (e.g., `# Domain Events` not `# domain_events`).
</DOCUMENTATION_REQUIREMENTS>

<WORKFLOW>
1. Analyze code and imports.
2. Identify "Public API" (methods likely to be used by others).
3. Create examples for the Public API.
4. Generate documentation.
</WORKFLOW>

<AVAILABLE_TOOLS>
- `str_replace_editor`: File system operations.
- `read_code_components`: Explore dependencies.
</AVAILABLE_TOOLS>
{custom_instructions}
""".strip()

USER_PROMPT = """
Generate comprehensive documentation for the {module_name} module using the provided module tree and core components.

<MODULE_TREE>
{module_tree}
</MODULE_TREE>
* NOTE: You can refer the other modules in the module tree based on the dependencies between their core components to make the documentation more structured and avoid repeating the same information. Know that all documentation files are saved in the same folder not structured as module tree. e.g. [alt text]([ref_module_name].md)

<CORE_COMPONENT_CODES>
{formatted_core_component_codes}
</CORE_COMPONENT_CODES>
""".strip()

REPO_OVERVIEW_PROMPT = """
You are an AI documentation assistant. Your task is to generate a brief overview of the {repo_name} repository.

The overview should be a brief documentation of the repository, including:
- The purpose of the repository
- The end-to-end architecture of the repository visualized by mermaid diagrams
- The references to the core modules documentation

**IMPORTANT: Diagram Contextualization**
Every mermaid diagram MUST be preceded by a narrative paragraph that:
1. Explains what the diagram illustrates and why it's relevant.
2. Introduces the key components/actors shown.

After the diagram, provide a step-by-step explanation of the flow if applicable.
Never place a diagram immediately after a title without narrative context.

Ensure the generated markdown has the following YAML Front Matter at the very top:
```yaml
---
name: {repo_name}
description: [Brief description]
author: {author_name}
version: {version}
---
```

Also ensure all H1 titles are in **Title Case**.

Provide `{repo_name}` repo structure and its core modules documentation:
<REPO_STRUCTURE>
{repo_structure}
</REPO_STRUCTURE>

Please generate the overview of the `{repo_name}` repository in markdown format with the following structure:
<OVERVIEW>
overview_content
</OVERVIEW>
""".strip()

MODULE_OVERVIEW_PROMPT = """
You are an AI documentation assistant. Your task is to generate a brief overview of `{module_name}` module.

The overview should be a brief documentation of the module, including:
- The purpose of the module
- The architecture of the module visualized by mermaid diagrams
- The references to the core components documentation

**IMPORTANT: Diagram Contextualization**
Every mermaid diagram MUST be preceded by a narrative paragraph that:
1. Explains what the diagram illustrates and why it's relevant.
2. Introduces the key components/actors shown.

After the diagram, provide a step-by-step explanation of the flow if applicable.
Never place a diagram immediately after a title without narrative context.

Ensure the generated markdown has the following YAML Front Matter at the very top:
```yaml
---
name: {module_name}
description: [Brief description]
author: {author_name}
version: {version}
---
```

Also ensure all H1 titles are in **Title Case**.

Provide repo structure and core components documentation of the `{module_name}` module:
<REPO_STRUCTURE>
{repo_structure}
</REPO_STRUCTURE>

Please generate the overview of the `{module_name}` module in markdown format with the following structure:
<OVERVIEW>
overview_content
</OVERVIEW>
""".strip()

CLUSTER_REPO_PROMPT = """
Here is list of all potential core components of the repository (It's normal that some components are not essential to the repository):
<POTENTIAL_CORE_COMPONENTS>
{potential_core_components}
</POTENTIAL_CORE_COMPONENTS>

Please group the components into groups such that each group is a set of components that are closely related to each other and together they form a module. DO NOT include components that are not essential to the repository.
Firstly reason about the components and then group them and return the result in the following format:
<GROUPED_COMPONENTS>
{{
    "module_name_1": {{
        "path": <path_to_the_module_1>, # the path to the module can be file or directory
        "components": [
            <component_name_1>,
            <component_name_2>,
            ...
        ]
    }},
    "module_name_2": {{
        "path": <path_to_the_module_2>,
        "components": [
            <component_name_1>,
            <component_name_2>,
            ...
        ]
    }},
    ...
}}
</GROUPED_COMPONENTS>
""".strip()

CLUSTER_MODULE_PROMPT = """
Here is the module tree of a repository:

<MODULE_TREE>
{module_tree}
</MODULE_TREE>

Here is list of all potential core components of the module {module_name} (It's normal that some components are not essential to the module):
<POTENTIAL_CORE_COMPONENTS>
{potential_core_components}
</POTENTIAL_CORE_COMPONENTS>

Please group the components into groups such that each group is a set of components that are closely related to each other and together they form a smaller module. DO NOT include components that are not essential to the module.

Firstly reason based on given context and then group them and return the result in the following format:
<GROUPED_COMPONENTS>
{{
    "module_name_1": {{
        "path": <path_to_the_module_1>, # the path to the module can be file or directory
        "components": [
            <component_name_1>,
            <component_name_2>,
            ...
        ]
    }},
    "module_name_2": {{
        "path": <path_to_the_module_2>,
        "components": [
            <component_name_1>,
            <component_name_2>,
            ...
        ]
    }},
    ...
}}
</GROUPED_COMPONENTS>
""".strip()

FILTER_FOLDERS_PROMPT = """
Here is the list of relative paths of files, folders in 2-depth of project {project_name}:
```
{files}
```

In order to analyze the core functionality of the project, we need to analyze the files, folders representing the core functionality of the project.

Please shortlist the files, folders representing the core functionality and ignore the files, folders that are not essential to the core functionality of the project (e.g. test files, documentation files, etc.) from the list above.

Reasoning at first, then return the list of relative paths in JSON format.
"""


EXTENSION_TO_LANGUAGE = {
    ".py": "python",
    ".md": "markdown",
    ".sh": "bash",
    ".json": "json",
    ".yaml": "yaml",
    ".java": "java",
    ".js": "javascript",
    ".ts": "typescript",
    ".cpp": "cpp",
    ".c": "c",
    ".h": "c",
    ".hpp": "cpp",
    ".tsx": "typescript",
    ".cc": "cpp",
    ".cxx": "cpp",
    ".jsx": "javascript",
    ".mjs": "javascript",
    ".cjs": "javascript",
    ".cs": "csharp",
    ".php": "php",
    ".phtml": "php",
    ".inc": "php",
}


def format_user_prompt(
    module_name: str,
    core_component_ids: list[str],
    components: Dict[str, Any],
    module_tree: dict[str, any],
    max_tokens: Optional[int] = None,
) -> str:
    """
    Format the user prompt with module name and organized core component codes.

    Args:
        module_name: Name of the module to document
        core_component_ids: List of component IDs to include
        components: Dictionary mapping component IDs to CodeComponent objects
        module_tree: Module structure
        max_tokens: Optional maximum tokens for all code components combined

    Returns:
        Formatted user prompt string
    """

    # format module tree
    lines = []

    def _format_module_tree(module_tree: dict[str, any], indent: int = 0):
        for key, value in module_tree.items():
            if key == module_name:
                lines.append(f"{'  ' * indent}{key} (current module)")
            else:
                lines.append(f"{'  ' * indent}{key}")

            lines.append(f"{'  ' * (indent + 1)} Core components: {', '.join(value['components'])}")
            if isinstance(value["children"], dict) and len(value["children"]) > 0:
                lines.append(f"{'  ' * (indent + 1)} Children:")
                _format_module_tree(value["children"], indent + 2)

    _format_module_tree(module_tree, 0)
    formatted_module_tree = "\n".join(lines)

    # print(f"Formatted module tree:\n{formatted_module_tree}")

    # Group core component IDs by their file path
    grouped_components: dict[str, list[str]] = {}
    for component_id in core_component_ids:
        if component_id not in components:
            continue
        component = components[component_id]
        path = component.relative_path
        if path not in grouped_components:
            grouped_components[path] = []
        grouped_components[path].append(component_id)

    # Calculate per-file character limit if max_tokens is set
    # Crude estimation: 1 token ~= 4 characters
    char_limit_per_file = None
    if max_tokens and grouped_components:
        total_char_limit = max_tokens * 4
        char_limit_per_file = total_char_limit // len(grouped_components)

    core_component_codes = ""
    core_component_codes = ""
    for path, component_ids_in_file in grouped_components.items():
        core_component_codes += f"# File: {path}\n"

        # Try to extract imports from the actual file
        try:
            # Just read the first 50 lines to catch imports, or full file if small
            full_content = file_manager.load_text(components[component_ids_in_file[0]].file_path)
            lines = full_content.splitlines()
            imports = []
            for line in lines:
                stripped = line.strip()
                # Basic heuristic for imports in common languages
                if stripped.startswith(("import ", "from ", "using ", "#include ", "package ")):
                    imports.append(line)
                elif (
                    len(imports) > 0 and not stripped
                ):  # Stop after imports block (rough heuristic)
                    if len(imports) > 20:
                        break  # Safety break

            if imports:
                core_component_codes += "## Imports/Context:\n```text\n"
                core_component_codes += "\n".join(imports)
                core_component_codes += "\n```\n"

        except Exception:
            pass  # Ignore import extraction errors

        core_component_codes += "\n## Core Components in this file:\n"

        for component_id in component_ids_in_file:
            component = components[component_id]
            core_component_codes += f"### {component.name} ({component.component_type})\n"

            # Use source_code from Node if available, otherwise fallback to file reading logic
            code_content = component.source_code

            if not code_content:
                # Fallback to reading file (legacy behavior, but applied to component range if possible)
                # For now, if no source_code, we rely on the previous file read logic or just skip
                # Assuming source_code is populated by the analyzer as per learnings
                try:
                    content = file_manager.load_text(component.file_path)
                    # If we have start/end lines, use them
                    if component.start_line > 0 and component.end_line >= component.start_line:
                        file_lines = content.splitlines()
                        # Adjust for 0-based indexing if needed, usually line numbers are 1-based
                        start = max(0, component.start_line - 1)
                        end = min(len(file_lines), component.end_line)
                        code_content = "\n".join(file_lines[start:end])
                    else:
                        code_content = content  # Fallback to full content if no lines
                except Exception as e:
                    code_content = f"Error reading component code: {e}"

            lang = EXTENSION_TO_LANGUAGE.get("." + path.split(".")[-1], "text")
            core_component_codes += f"```{lang}\n{code_content}\n```\n\n"

    return USER_PROMPT.format(
        module_name=module_name,
        formatted_core_component_codes=core_component_codes,
        module_tree=formatted_module_tree,
    )


def format_cluster_prompt(
    potential_core_components: str, module_tree: dict[str, any] = {}, module_name: str = None
) -> str:
    """
    Format the cluster prompt with potential core components and module tree.
    """

    # format module tree
    lines = []

    # print(f"Module tree:\n{json.dumps(module_tree, indent=2)}")

    def _format_module_tree(module_tree: dict[str, any], indent: int = 0):
        for key, value in module_tree.items():
            if key == module_name:
                lines.append(f"{'  ' * indent}{key} (current module)")
            else:
                lines.append(f"{'  ' * indent}{key}")

            lines.append(f"{'  ' * (indent + 1)} Core components: {', '.join(value['components'])}")
            if (
                ("children" in value)
                and isinstance(value["children"], dict)
                and len(value["children"]) > 0
            ):
                lines.append(f"{'  ' * (indent + 1)} Children:")
                _format_module_tree(value["children"], indent + 2)

    _format_module_tree(module_tree, 0)
    formatted_module_tree = "\n".join(lines)

    if module_tree == {}:
        return CLUSTER_REPO_PROMPT.format(potential_core_components=potential_core_components)
    else:
        return CLUSTER_MODULE_PROMPT.format(
            potential_core_components=potential_core_components,
            module_tree=formatted_module_tree,
            module_name=module_name,
        )


def format_system_prompt(
    module_name: str, author_name: str, version: str, custom_instructions: str = None
) -> str:
    """
    Format the system prompt with module name and optional custom instructions.

    Args:
        module_name: Name of the module to document
        author_name: Author name from git
        version: Version string from git
        custom_instructions: Optional custom instructions to append

    Returns:
        Formatted system prompt string
    """
    custom_section = ""
    if custom_instructions:
        custom_section = f"\n\n<CUSTOM_INSTRUCTIONS>\n{custom_instructions}\n</CUSTOM_INSTRUCTIONS>"

    return SYSTEM_PROMPT.format(
        module_name=module_name,
        author_name=author_name,
        version=version,
        custom_instructions=custom_section,
    ).strip()


def format_leaf_system_prompt(
    module_name: str, author_name: str, version: str, custom_instructions: str = None
) -> str:
    """
    Format the leaf system prompt with module name and optional custom instructions.

    Args:
        module_name: Name of the module to document
        author_name: Author name from git
        version: Version string from git
        custom_instructions: Optional custom instructions to append

    Returns:
        Formatted leaf system prompt string
    """
    custom_section = ""
    if custom_instructions:
        custom_section = f"\n\n<CUSTOM_INSTRUCTIONS>\n{custom_instructions}\n</CUSTOM_INSTRUCTIONS>"

    return LEAF_SYSTEM_PROMPT.format(
        module_name=module_name,
        author_name=author_name,
        version=version,
        custom_instructions=custom_section,
    ).strip()


def format_repo_overview_prompt(
    repo_name: str, repo_structure: str, author_name: str, version: str
) -> str:
    """Format the repository overview prompt."""
    return REPO_OVERVIEW_PROMPT.format(
        repo_name=repo_name,
        repo_structure=repo_structure,
        author_name=author_name,
        version=version,
    ).strip()


def format_module_overview_prompt(
    module_name: str, repo_structure: str, author_name: str, version: str
) -> str:
    """Format the module overview prompt."""
    return MODULE_OVERVIEW_PROMPT.format(
        module_name=module_name,
        repo_structure=repo_structure,
        author_name=author_name,
        version=version,
    ).strip()


UPDATE_DOC_PROMPT = """
<ROLE>
You are an expert technical editor. Your task is to update the following documentation based on the user's request.
</ROLE>

<INPUT_DOCUMENT>
{current_content}
</INPUT_DOCUMENT>

<USER_REQUEST>
{user_instruction}
</USER_REQUEST>

<PROJECT_STRUCTURE>
{repo_structure}
</PROJECT_STRUCTURE>

<DEPENDENCIES>
{dependency_graph}
</DEPENDENCIES>

<CONTEXT>
{repo_context}
</CONTEXT>

<INSTRUCTIONS>
1. Read the input document and the user request.
2. Apply the requested changes while maintaining the existing style and structure.
3. Use the PROJECT_STRUCTURE and DEPENDENCIES to ensure accuracy (e.g., correct paths, class names).
4. Ensure all H1s remain Title Case.
5. Return the fully updated markdown content.
</INSTRUCTIONS>
""".strip()


CREATE_DOC_PROMPT = """
<ROLE>
You are an expert technical writer. Your task is to create a NEW documentation page based on the user's request.
</ROLE>

<USER_REQUEST>
{user_instruction}
</USER_REQUEST>

<PROJECT_STRUCTURE>
{repo_structure}
</PROJECT_STRUCTURE>

<DEPENDENCIES>
{dependency_graph}
</DEPENDENCIES>

<CONTEXT>
{repo_context}
</CONTEXT>

<INSTRUCTIONS>
1. Analyze the USER_REQUEST, PROJECT_STRUCTURE, and DEPENDENCIES.
2. Create a comprehensive documentation page.
3. Use the Standard Structure:
   - Title (H1, Title Case)
   - Overview
   - Content (Diagrams, Tables, Lists as appropriate)
4. Ensure all H1s are Title Case.
5. Return the full markdown content.
</INSTRUCTIONS>
""".strip()


def format_update_doc_prompt(
    current_content: str,
    user_instruction: str,
    repo_structure: str = "",
    dependency_graph: str = "",
    repo_context: str = "",
) -> str:
    """Format the documentation update prompt."""
    return UPDATE_DOC_PROMPT.format(
        current_content=current_content,
        user_instruction=user_instruction,
        repo_structure=repo_structure,
        dependency_graph=dependency_graph,
        repo_context=repo_context,
    ).strip()


def format_create_doc_prompt(
    user_instruction: str,
    repo_structure: str = "",
    dependency_graph: str = "",
    repo_context: str = "",
) -> str:
    """Format the documentation creation prompt."""
    return CREATE_DOC_PROMPT.format(
        user_instruction=user_instruction,
        repo_structure=repo_structure,
        dependency_graph=dependency_graph,
        repo_context=repo_context,
    ).strip()
