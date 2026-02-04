"""
Progress indicator utilities for CLI using Rich.
"""

import time
from typing import Optional, Dict
from rich.progress import (
    Progress,
    SpinnerColumn,
    TextColumn,
    BarColumn,
    TaskProgressColumn,
    TimeRemainingColumn,
    TimeElapsedColumn,
)
from rich.console import Console


class RichProgressTracker:
    """
    Progress tracker with support for multiple bars and detailed status.
    """

    # Stage weights (percentage of total time)
    STAGE_WEIGHTS = {
        1: 0.40,  # Dependency Analysis
        2: 0.20,  # Module Clustering
        3: 0.30,  # Documentation Generation
        4: 0.05,  # HTML Generation (optional)
        5: 0.05,  # Finalization
    }

    STAGE_NAMES = {
        1: "Dependency Analysis",
        2: "Module Clustering",
        3: "Documentation Generation",
        4: "HTML Generation",
        5: "Finalization",
    }

    def __init__(
        self, total_stages: int = 5, verbose: bool = False, console: Optional[Console] = None
    ):
        self.total_stages = total_stages
        self.verbose = verbose
        self.console = console or Console()
        self.current_stage = 0
        self.stage_progress = 0.0

        # Initialize Rich Progress
        self.progress = Progress(
            SpinnerColumn(),
            TextColumn("[bold blue]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            TimeElapsedColumn(),
            TimeRemainingColumn(),
            console=self.console,
            transient=False,  # Keep the final state visible
        )

        # Create Task IDs
        self.overall_task_id = self.progress.add_task("[bold green]Overall Progress", total=100)
        self.current_stage_task_id = self.progress.add_task("[bold blue]Waiting...", total=100)

        self.progress.start()

    def start_stage(self, stage: int, description: Optional[str] = None):
        """Start a new stage."""
        self.current_stage = stage
        self.stage_progress = 0.0

        stage_name = description or self.STAGE_NAMES.get(stage, f"Stage {stage}")

        # Reset current stage bar
        self.progress.reset(self.current_stage_task_id, total=100)
        self.progress.update(
            self.current_stage_task_id, description=f"[bold blue]{stage_name}", completed=0
        )

        # Calculate overall progress base
        overall_base = sum(self.STAGE_WEIGHTS.get(s, 0) for s in range(1, self.current_stage)) * 100
        self.progress.update(self.overall_task_id, completed=overall_base)

    def update_stage(self, progress: float, message: Optional[str] = None):
        """Update progress within current stage."""
        self.stage_progress = min(1.0, max(0.0, progress))

        # Update stage bar (0-100)
        self.progress.update(self.current_stage_task_id, completed=self.stage_progress * 100)

        if message:
            # Append message to description or print it?
            # For a cleaner UI, let's keep the main description static and maybe use console.print for details if verbose
            if self.verbose:
                self.console.print(f"[dim]{message}[/dim]")
            else:
                # Update description temporarily? No, might flicker.
                self.progress.update(
                    self.current_stage_task_id,
                    description=f"[bold blue]{self.STAGE_NAMES.get(self.current_stage)}: {message}",
                )

        # Update overall bar
        overall_progress = self.get_overall_progress() * 100
        self.progress.update(self.overall_task_id, completed=overall_progress)

    def complete_stage(self, message: Optional[str] = None):
        """Complete current stage."""
        self.stage_progress = 1.0
        self.progress.update(self.current_stage_task_id, completed=100)

        overall_progress = self.get_overall_progress() * 100
        self.progress.update(self.overall_task_id, completed=overall_progress)

        if message and self.verbose:
            self.console.print(f"[green]✓ {message}[/green]")

    def get_overall_progress(self) -> float:
        """Calculate overall progress."""
        completed_weight = sum(self.STAGE_WEIGHTS.get(s, 0) for s in range(1, self.current_stage))
        current_weight = self.STAGE_WEIGHTS.get(self.current_stage, 0) * self.stage_progress
        return completed_weight + current_weight

    def stop(self):
        """Stop the progress display."""
        self.progress.stop()


# Alias for compatibility if needed, but we will mostly replace usage
ProgressTracker = RichProgressTracker


class ModuleProgressBar:
    """Helper for module-level progress, integrated with the main tracker if passed."""

    def __init__(self, tracker: RichProgressTracker, total_modules: int):
        self.tracker = tracker
        self.total_modules = total_modules
        self.current_module = 0

    def update(self, module_name: str, cached: bool = False):
        self.current_module += 1
        progress = self.current_module / self.total_modules if self.total_modules > 0 else 0
        status = " (cached)" if cached else ""
        self.tracker.update_stage(progress, message=f"{module_name}{status}")
