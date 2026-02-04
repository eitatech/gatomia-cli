from dataclasses import dataclass
from gatomia.src.be.dependency_analyzer.models.core import Node
from gatomia.src.config import Config


@dataclass
class GatomIADeps:
    absolute_docs_path: str
    absolute_repo_path: str
    registry: dict
    components: dict[str, Node]
    path_to_current_module: list[str]
    current_module_name: str
    module_tree: dict[str, any]
    max_depth: int
    current_depth: int
    config: Config  # LLM configuration
    custom_instructions: str = None
    progress_callback: callable = None  # Optional callback for progress updates
