"""
Output rendering and formatting for CTS CLI.

Provides rich-based table formatting, progress bars, and
JSON/NDJSON output for both human and machine consumption.
"""

import json
import sys
from contextlib import AbstractContextManager
from pathlib import Path
from typing import TYPE_CHECKING, Any, ContextManager, Dict, List, Optional

try:
    import rich.console as _rich_console
    import rich.json as _rich_json
    import rich.progress as _rich_progress
    import rich.table as _rich_table

    RICH_AVAILABLE = True
except ImportError:  # pragma: no cover - rich is optional at runtime
    _rich_console = None  # type: ignore[assignment]
    _rich_json = None  # type: ignore[assignment]
    _rich_progress = None  # type: ignore[assignment]
    _rich_table = None  # type: ignore[assignment]
    RICH_AVAILABLE = False

if TYPE_CHECKING:
    from rich.console import Console as ConsoleType
    from rich.json import JSON as JSONType
    from rich.progress import Progress as ProgressType
    from rich.table import Table as TableType
else:
    ConsoleType = Any  # type: ignore[assignment]
    JSONType = Any  # type: ignore[assignment]
    ProgressType = Any  # type: ignore[assignment]
    TableType = Any  # type: ignore[assignment]


class Renderer:
    """Output renderer with support for human and machine formats."""

    def __init__(self, json_output: bool = False, quiet: bool = False):
        """Initialize renderer."""
        self.json_output = json_output
        self.quiet = quiet

        self.console: Optional[ConsoleType] = None

        if RICH_AVAILABLE and not json_output and _rich_console is not None:
            self.console = _rich_console.Console()

    def print(self, message: str, **kwargs) -> None:
        """Print message with appropriate formatting."""
        if self.quiet and not self.json_output:
            return

        if self.console is not None:
            self.console.print(message, **kwargs)
        else:
            print(message)

    def print_json(self, data: Any) -> None:
        """Print JSON data."""
        if self.json_output:
            print(json.dumps(data, indent=2))
        elif self.console is not None and _rich_json is not None:
            self.console.print(_rich_json.JSON.from_data(data))
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

        if self.console is not None and _rich_table is not None:
            table = _rich_table.Table(title=title)

            for key in data[0].keys():
                table.add_column(key.replace("_", " ").title())

            for row in data:
                table.add_row(*[str(v) for v in row.values()])

            self.console.print(table)
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
        if self.console is not None:
            self.console.print(f"Error: {message}", style="red")
        else:
            print(f"Error: {message}", file=sys.stderr)

    def print_success(self, message: str) -> None:
        """Print success message."""
        if self.console is not None:
            self.console.print(message, style="green")
        else:
            print(message)

    def print_warning(self, message: str) -> None:
        """Print warning message."""
        if self.console is not None:
            self.console.print(f"Warning: {message}", style="yellow")
        else:
            print(f"Warning: {message}")

    def progress_context(self, description: str = "Processing...") -> ContextManager[Any]:
        """Create progress context manager."""
        if (
            self.console is not None
            and not self.json_output
            and _rich_progress is not None
        ):
            return _rich_progress.Progress(
                _rich_progress.SpinnerColumn(),
                _rich_progress.TextColumn("[progress.description]{task.description}"),
                console=self.console,
            )

        return _NoOpProgress(description)


class _NoOpProgress(AbstractContextManager[Any]):
    """No-op progress context for non-rich environments."""

    def __init__(self, description: str):
        self.description = description

    def __enter__(self) -> "_NoOpProgress":
        if not self.description.endswith("..."):
            print(f"{self.description}...")
        return self

    def __exit__(
        self,
        exc_type: Optional[type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[Any],
    ) -> Optional[bool]:
        return None

    def add_task(self, description: str, **kwargs: Any) -> int:
        return 0

    def update(self, task_id: int, **kwargs: Any) -> None:
        return None


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
