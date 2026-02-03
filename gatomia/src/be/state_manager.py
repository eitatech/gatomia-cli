import json
import os
import logging
from typing import Dict, Any, Optional
from datetime import datetime
from gatomia.src.utils import file_manager

logger = logging.getLogger(__name__)

STATE_FILENAME = "generation_state.json"


class StateManager:
    """Manages the state of documentation generation for checkpointing and incremental updates."""

    def __init__(self, working_dir: str):
        self.working_dir = working_dir
        self.state_path = os.path.join(working_dir, STATE_FILENAME)
        self.state = self._load_state()

    def _load_state(self) -> Dict[str, Any]:
        """Load state from file or return empty state."""
        loaded_state = file_manager.load_json(self.state_path)
        if loaded_state:
            return loaded_state
        return {
            "modules": {},
            "metadata": {"created_at": datetime.now().isoformat(), "last_run": None},
        }

    def save_state(self) -> None:
        """Save current state to file."""
        self.state["metadata"]["last_run"] = datetime.now().isoformat()

        # We don't update structure_hash or commit_id here automatically
        # They should be set explicitly when we confirm the structure/commit is valid

        file_manager.save_json(self.state, self.state_path)

    def is_module_up_to_date(self, module_name: str, current_hash: str) -> bool:
        """
        Check if a module is up-to-date.

        Args:
            module_name: The unique name/identifier of the module.
            current_hash: The calculated hash of the module's current content.

        Returns:
            True if module exists in state, is completed, and hash matches.
        """
        module_data = self.state["modules"].get(module_name)
        if not module_data:
            return False

        if module_data.get("status") != "completed":
            return False

        stored_hash = module_data.get("hash")
        return stored_hash == current_hash

    def update_module_state(
        self, module_name: str, hash_value: str, status: str = "completed"
    ) -> None:
        """Update the state for a processed module."""
        self.state["modules"][module_name] = {
            "status": status,
            "hash": hash_value,
            "timestamp": datetime.now().isoformat(),
        }
        self.save_state()

    def calculate_structure_hash(self, leaf_nodes: list[str]) -> str:
        """Calculate a hash representing the current file structure."""
        import hashlib

        # Sort to ensure consistent ordering
        sorted_files = sorted(leaf_nodes)
        content = "\n".join(sorted_files)
        return hashlib.md5(content.encode("utf-8")).hexdigest()

    def get_last_structure_hash(self) -> Optional[str]:
        """Get the stored structure hash from the last run."""
        return self.state["metadata"].get("structure_hash")

    def set_structure_hash(self, hash_value: str) -> None:
        """Update the stored structure hash."""
        self.state["metadata"]["structure_hash"] = hash_value
        self.save_state()

    def get_last_commit_id(self) -> Optional[str]:
        """Get the stored commit ID from the last run."""
        return self.state["metadata"].get("commit_id")

    def set_commit_id(self, commit_id: str) -> None:
        """Update the stored commit ID."""
        self.state["metadata"]["commit_id"] = commit_id
        self.save_state()

    def clear_state(self) -> None:
        """Clear all state data (e.g., for force regeneration)."""
        self.state = {
            "modules": {},
            "metadata": {"created_at": datetime.now().isoformat(), "last_run": None},
        }
        self.save_state()
