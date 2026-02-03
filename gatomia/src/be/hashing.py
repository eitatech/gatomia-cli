import hashlib
from typing import Dict, List, Any
import logging

logger = logging.getLogger(__name__)


def calculate_file_hash(file_path: str) -> str:
    """Calculate SHA-256 hash of a file."""
    sha256_hash = hashlib.sha256()
    try:
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()
    except Exception as e:
        logger.warning(f"Failed to calculate hash for {file_path}: {e}")
        return ""


def calculate_module_hash(components: List[str], all_components: Dict[str, Any]) -> str:
    """
    Calculate a combined hash for a module based on its components.

    Args:
        components: List of component IDs in the module.
        all_components: Dictionary mapping component IDs to node objects.

    Returns:
        A SHA-256 hash representing the combined state of the module's components.
    """
    combined_hash = hashlib.sha256()

    # Sort components to ensure deterministic order
    sorted_components = sorted(components)

    files_processed = set()

    for comp_id in sorted_components:
        if comp_id not in all_components:
            continue

        comp_node = all_components[comp_id]
        file_path = comp_node.file_path

        # We hash the file content once per file, but multiple components might be in one file.
        # Alternatively, we can hash the component's source code if available, but file hash is robust.
        # To strictly follow "updates", a file change should invalidate modules using it.

        if file_path in files_processed:
            continue

        file_hash = calculate_file_hash(file_path)
        combined_hash.update(file_hash.encode("utf-8"))
        files_processed.add(file_path)

    return combined_hash.hexdigest()
