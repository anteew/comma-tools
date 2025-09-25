"""
Output rendering and formatting for CTS CLI.

Provides rich-based table formatting, progress bars, and
JSON/NDJSON output for both human and machine consumption.
"""

import json
import sys
from typing import Dict, Any, List, Optional, Union

from pathlib import Path

try:
    from rich.console import Console
    from rich.table import Table
    from rich.progress import Progress, SpinnerColumn, TextColumn, TaskID
    from rich.json import JSON

    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False


class Renderer:
    """Output renderer with support for human and machine formats."""

    def __init__(self, json_output: bool = False, quiet: bool = False):
        """Initialize renderer."""
        self.json_output = json_output
        self.quiet = quiet

        self.console: Optional[object] = None

        if RICH_AVAILABLE and not json_output:
            from rich.console import Console

            self.console = Console()
        else:
            self.console = None

    def print(self, message: str, **kwargs) -> None:
        """Print message with appropriate formatting."""
        if self.quiet and not self.json_output:
            return

        if self.console:
            self.console.print(message, **kwargs)  # type: ignore
        else:
            print(message)

    def print_json(self, data: Dict[str, Any]) -> None:
        """Print JSON data."""
        if self.json_output:
            print(json.dumps(data, indent=2))
        elif self.console:
            from rich.json import JSON

            self.console.print(JSON.from_data(data))  # type: ignore
        else:
            print(json.dumps(data, indent=2))

    def print_table(self, data: List[Dict[str, Any]], title: Optional[str] = None) -> None:
        """Print data as table."""
        if self.json_output:
            print(json.dumps(data, indent=2))
            return

        if not data:
            self.print("No data to display")
            return

        if self.console:
            from rich.table import Table

            table = Table(title=title)

            for key in data[0].keys():
                table.add_column(key.replace("_", " ").title())

            for row in data:
                table.add_row(*[str(v) for v in row.values()])

            self.console.print(table)  # type: ignore
        else:
            if title:
                print(f"\n{title}")
                print("=" * len(title))

            if data:
                headers = list(data[0].keys())
                print("\t".join(headers))
                print("\t".join(["-" * len(h) for h in headers]))

                for row in data:
                    print("\t".join([str(row.get(h, "")) for h in headers]))

    def print_error(self, message: str) -> None:
        """Print error message."""
        if self.console:
            self.console.print(f"Error: {message}", style="red")  # type: ignore
        else:
            print(f"Error: {message}", file=sys.stderr)

    def print_success(self, message: str) -> None:
        """Print success message."""
        if self.console:
            self.console.print(message, style="green")  # type: ignore
        else:
            print(message)

    def print_warning(self, message: str) -> None:
        """Print warning message."""
        if self.console:
            self.console.print(f"Warning: {message}", style="yellow")  # type: ignore
        else:
            print(f"Warning: {message}")

    def progress_context(self, description: str = "Processing..."):
        """Create progress context manager."""
        if self.console and not self.json_output:
            from rich.progress import Progress, SpinnerColumn, TextColumn

            return Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=self.console,  # type: ignore
            )
        else:
            return _NoOpProgress(description)


class _NoOpProgress:
    """No-op progress context for non-rich environments."""

    def __init__(self, description: str):
        self.description = description

    def __enter__(self):
        if not self.description.endswith("..."):
            print(f"{self.description}...")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

    def add_task(self, description: str, **kwargs):
        return 0

    def update(self, task_id, **kwargs):
        pass


def format_bytes(size: int) -> str:
    """Format byte size in human readable format."""
    size_float = float(size)
    for unit in ["B", "KB", "MB", "GB"]:
        if size_float < 1024:
            return f"{size_float:.1f} {unit}"
        size_float /= 1024
    return f"{size_float:.1f} TB"


def format_duration(seconds: float) -> str:
    """Format duration in human readable format."""
    if seconds < 60:
        return f"{seconds:.1f}s"
    elif seconds < 3600:
        minutes = seconds / 60
        return f"{minutes:.1f}m"
    else:
        hours = seconds / 3600
        return f"{hours:.1f}h"


def safe_path_join(base_dir: Path, filename: str) -> Path:
    """Safely join paths, preventing directory traversal."""
    base_resolved = base_dir.resolve()

    result_path = (base_dir / filename).resolve()

    try:
        result_path.relative_to(base_resolved)
        return result_path
    except ValueError:
        raise ValueError(f"Unsafe path: {filename}")
