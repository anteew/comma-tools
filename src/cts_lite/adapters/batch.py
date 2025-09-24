"""Base adapter for batch analyzer tools."""

import json
import subprocess
import sys
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..models import InputRef


class BatchAdapter(ABC):
    """Base class for batch analyzer adapters."""

    def __init__(self, tool_id: str, version: str):
        self.tool_id = tool_id
        self.version = version

    @abstractmethod
    def build_command(
        self, params: Dict[str, Any], inputs: List[InputRef], work_dir: Path
    ) -> List[str]:
        """Build the command line for the tool."""
        pass

    @abstractmethod
    def parse_progress(self, line: str) -> Optional[Dict[str, Any]]:
        """Parse a progress event from stdout/stderr."""
        pass

    @abstractmethod
    def find_artifacts(self, work_dir: Path) -> List[Path]:
        """Find output artifacts in the work directory."""
        pass

    def execute(
        self, params: Dict[str, Any], inputs: List[InputRef], work_dir: Path, log_callback=None
    ) -> Dict[str, Any]:
        """Execute the tool and return results."""

        cmd = self.build_command(params, inputs, work_dir)

        if log_callback:
            log_callback({"event": "command", "cmd": " ".join(cmd)})

        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            cwd=work_dir,
            env=self._get_environment(),
        )

        output_lines: List[str] = []
        if process.stdout:
            while True:
                line = process.stdout.readline()
                if not line and process.poll() is not None:
                    break

                if line:
                    line = line.rstrip()
                    output_lines.append(line)

                    progress_event = self.parse_progress(line)
                    if progress_event and log_callback:
                        log_callback(progress_event)
                    elif log_callback:
                        log_callback({"event": "log", "line": line})

        return_code = process.wait()

        artifacts = self.find_artifacts(work_dir)

        result: Dict[str, Any] = {
            "return_code": return_code,
            "output_lines": output_lines,
            "artifacts": [str(p) for p in artifacts],
        }

        if return_code != 0:
            error_msg = f"Tool exited with code {return_code}"
            if output_lines:
                last_line = str(output_lines[-1])
                error_msg += f": {last_line}"
            result["error"] = error_msg

        return result

    def _get_environment(self) -> Dict[str, str]:
        """Get environment variables for the subprocess."""
        import os

        env = os.environ.copy()
        env["PYTHONPATH"] = str(Path(__file__).parent.parent.parent.parent)
        return env


class CruiseControlAnalyzerAdapter(BatchAdapter):
    """Adapter for cruise control analyzer."""

    def __init__(self):
        super().__init__("cruise-control-analyzer", "0.8.0")

    def build_command(
        self, params: Dict[str, Any], inputs: List[InputRef], work_dir: Path
    ) -> List[str]:
        """Build command for cruise control analyzer."""
        if not inputs or inputs[0].kind != "path":
            raise ValueError("Cruise control analyzer requires a path input")

        log_file = str(inputs[0].path)
        cmd: List[str] = [
            sys.executable,
            "-m",
            "comma_tools.analyzers.cruise_control_analyzer",
            log_file,
            "--speed-min",
            str(params.get("speed_min", 55.0)),
            "--speed-max",
            str(params.get("speed_max", 56.0)),
            "--marker-type",
            str(params.get("marker_type", "blinkers")),
            "--marker-pre",
            str(params.get("marker_pre", 5.0)),
            "--marker-post",
            str(params.get("marker_post", 5.0)),
            "--marker-timeout",
            str(params.get("marker_timeout", 10.0)),
        ]

        if params.get("export_csv", False):
            cmd.extend(["--export-csv", "--output-dir", str(work_dir)])

        if params.get("export_json", False):
            cmd.extend(["--export-json", "--output-dir", str(work_dir)])

        if params.get("repo_root"):
            repo_root = str(params["repo_root"])
            cmd.extend(["--repo-root", repo_root])

        if params.get("deps_dir"):
            deps_dir = str(params["deps_dir"])
            cmd.extend(["--deps-dir", deps_dir])

        if params.get("install_missing_deps", False):
            cmd.append("--install-missing-deps")

        return cmd

    def parse_progress(self, line: str) -> Optional[Dict[str, Any]]:
        """Parse progress from cruise control analyzer output."""
        if "PROGRESS" in line and "%" in line:
            try:
                parts = line.split()
                for part in parts:
                    if part.endswith("%"):
                        pct = float(part[:-1])
                        return {"event": "progress", "pct": pct, "msg": line}
            except (ValueError, IndexError):
                pass

        if "Analyzing" in line or "Processing" in line or "Generating" in line:
            return {"event": "progress", "msg": line}

        return None

    def find_artifacts(self, work_dir: Path) -> List[Path]:
        """Find artifacts from cruise control analyzer."""
        artifacts: List[Path] = []

        patterns = [
            "*.html",
            "*.png",
            "*.csv",
            "*.json",
            "speed_timeline.png",
            "analysis_report.html",
        ]

        for pattern in patterns:
            artifacts.extend(work_dir.glob(pattern))

        return artifacts


class RlogToCsvAdapter(BatchAdapter):
    """Adapter for rlog to CSV converter."""

    def __init__(self):
        super().__init__("rlog-to-csv", "0.8.0")

    def build_command(
        self, params: Dict[str, Any], inputs: List[InputRef], work_dir: Path
    ) -> List[str]:
        """Build command for rlog to CSV converter."""
        if not inputs or inputs[0].kind != "path":
            raise ValueError("rlog-to-csv requires a path input")

        log_file = str(inputs[0].path)
        output_file = work_dir / "output.csv"

        cmd: List[str] = [
            sys.executable,
            "-m",
            "comma_tools.analyzers.rlog_to_csv",
            "--rlog",
            log_file,
            "--out",
            str(output_file),
        ]

        if params.get("window_start") is not None:
            cmd.extend(["--window-start", str(params["window_start"])])

        if params.get("window_dur") is not None:
            cmd.extend(["--window-dur", str(params["window_dur"])])

        if params.get("repo_root"):
            repo_root = str(params["repo_root"])
            cmd.extend(["--repo-root", repo_root])

        return cmd

    def parse_progress(self, line: str) -> Optional[Dict[str, Any]]:
        """Parse progress from rlog to CSV converter."""
        if "Wrote" in line and "rows" in line:
            return {"event": "progress", "msg": line}
        return None

    def find_artifacts(self, work_dir: Path) -> List[Path]:
        """Find artifacts from rlog to CSV converter."""
        return list(work_dir.glob("*.csv"))


class CanBitwatchAdapter(BatchAdapter):
    """Adapter for CAN bitwatch analyzer."""

    def __init__(self):
        super().__init__("can-bitwatch", "0.8.0")

    def build_command(
        self, params: Dict[str, Any], inputs: List[InputRef], work_dir: Path
    ) -> List[str]:
        """Build command for CAN bitwatch analyzer."""
        if not inputs or inputs[0].kind != "path":
            raise ValueError("can-bitwatch requires a CSV input")

        csv_file = str(inputs[0].path)
        output_prefix = work_dir / params.get("output_prefix", "analysis")

        cmd: List[str] = [
            sys.executable,
            "-m",
            "comma_tools.analyzers.can_bitwatch",
            "--csv",
            csv_file,
            "--output-prefix",
            str(output_prefix),
        ]

        for watch_spec in params.get("watch", []):
            if watch_spec:
                watch_str = str(watch_spec)
                cmd.extend(["--watch", watch_str])

        return cmd

    def parse_progress(self, line: str) -> Optional[Dict[str, Any]]:
        """Parse progress from CAN bitwatch analyzer."""
        if "Analyzing" in line or "Writing" in line:
            return {"event": "progress", "msg": line}
        return None

    def find_artifacts(self, work_dir: Path) -> List[Path]:
        """Find artifacts from CAN bitwatch analyzer."""
        artifacts: List[Path] = []
        patterns = ["*.csv", "*.json"]

        for pattern in patterns:
            artifacts.extend(work_dir.glob(pattern))

        return artifacts
