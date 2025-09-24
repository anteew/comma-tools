"""Base adapter for realtime monitor tools."""

import asyncio
import json
import subprocess
import sys
import threading
import time
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, Optional


class RealtimeAdapter(ABC):
    """Base class for realtime monitor adapters."""

    def __init__(self, tool_id: str, version: str):
        self.tool_id = tool_id
        self.version = version
        self._process: Optional[subprocess.Popen] = None
        self._thread: Optional[threading.Thread] = None
        self._queue: Optional[asyncio.Queue] = None
        self._running = False

    @abstractmethod
    def build_command(self, params: Dict[str, Any]) -> list[str]:
        """Build the command line for the monitor."""
        pass

    @abstractmethod
    def parse_output(self, line: str) -> Optional[Dict[str, Any]]:
        """Parse a JSON event from monitor output."""
        pass

    def start(self, params: Dict[str, Any], event_queue: asyncio.Queue) -> None:
        """Start the monitor in a background thread."""
        if self._running:
            raise RuntimeError("Monitor is already running")

        self._queue = event_queue
        self._running = True

        self._thread = threading.Thread(target=self._monitor_thread, args=(params,), daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Stop the monitor."""
        self._running = False

        if self._process:
            try:
                self._process.terminate()
                self._process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._process.kill()
                self._process.wait()
            finally:
                self._process = None

        if self._thread:
            self._thread.join(timeout=5)
            self._thread = None

    def _monitor_thread(self, params: Dict[str, Any]) -> None:
        """Monitor thread that runs the subprocess and parses output."""
        try:
            cmd = self.build_command(params)

            self._process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                env=self._get_environment(),
            )

            self._send_event({"event": "started", "tool_id": self.tool_id})

            while self._running and self._process.poll() is None:
                if self._process.stdout:
                    line = self._process.stdout.readline()
                    if not line:
                        continue
                else:
                    break

                line = line.rstrip()
                if not line:
                    continue

                event = self.parse_output(line)
                if event:
                    self._send_event(event)
                else:
                    self._send_event({"event": "log", "line": line})

            if self._process:
                return_code = self._process.poll()
                if return_code != 0:
                    self._send_event({"event": "error", "return_code": return_code})
                else:
                    self._send_event({"event": "stopped"})

        except Exception as e:
            self._send_event({"event": "error", "error": str(e)})

        finally:
            self._running = False

    def _send_event(self, event: Dict[str, Any]) -> None:
        """Send an event to the queue."""
        if not self._queue:
            return

        event["ts"] = time.time()

        try:
            self._queue.put_nowait(event)
        except asyncio.QueueFull:
            try:
                self._queue.get_nowait()
                self._queue.put_nowait(event)
            except asyncio.QueueEmpty:
                pass

    def _get_environment(self) -> Dict[str, str]:
        """Get environment variables for the subprocess."""
        import os

        env = os.environ.copy()
        env["PYTHONPATH"] = str(Path(__file__).parent.parent.parent.parent)
        return env


class HybridRxTraceAdapter(RealtimeAdapter):
    """Adapter for hybrid RX trace monitor."""

    def __init__(self):
        super().__init__("hybrid-rx-trace", "0.8.0")

    def build_command(self, params: Dict[str, Any]) -> list[str]:
        """Build command for hybrid RX trace monitor."""
        return [sys.executable, "-m", "comma_tools.monitors.hybrid_rx_trace"]

    def parse_output(self, line: str) -> Optional[Dict[str, Any]]:
        """Parse output from hybrid RX trace monitor."""
        if line.startswith("--- panda"):
            return {"event": "panda_state_change", "line": line}

        if "safety:" in line:
            return {"event": "safety_info", "line": line}

        if "last " in line and "bus=" in line and "addr=" in line:
            return {"event": "signal_timing", "line": line}

        return None


class CanBusCheckAdapter(RealtimeAdapter):
    """Adapter for CAN bus check monitor."""

    def __init__(self):
        super().__init__("can-bus-check", "0.8.0")

    def build_command(self, params: Dict[str, Any]) -> list[str]:
        """Build command for CAN bus check monitor."""
        return [sys.executable, "-m", "comma_tools.monitors.can_bus_check"]

    def parse_output(self, line: str) -> Optional[Dict[str, Any]]:
        """Parse output from CAN bus check monitor."""
        if "addr=" in line and "bus=" in line and "count=" in line:
            try:
                parts = line.split()
                data = {}
                for part in parts:
                    if "=" in part:
                        key, value = part.split("=", 1)
                        if key == "addr":
                            data["address"] = value
                        elif key == "bus":
                            data["bus"] = int(value)
                        elif key == "count":
                            data["count"] = int(value)
                        elif key.startswith("->"):
                            data["name"] = value

                return {"event": "can_count", "data": data}
            except (ValueError, IndexError):
                pass

        return None


class PandaStateAdapter(RealtimeAdapter):
    """Adapter for panda state monitor."""

    def __init__(self):
        super().__init__("panda-state", "0.8.0")

    def build_command(self, params: Dict[str, Any]) -> list[str]:
        """Build command for panda state monitor."""
        return [sys.executable, "-m", "comma_tools.monitors.panda-state"]

    def parse_output(self, line: str) -> Optional[Dict[str, Any]]:
        """Parse output from panda state monitor."""
        if line.startswith("panda") and "model=" in line:
            try:
                parts = line.split()
                panda_id = parts[0].replace(":", "")

                data = {"panda_id": panda_id}
                for part in parts[1:]:
                    if "=" in part:
                        key, value = part.split("=", 1)
                        if key in ("model", "param", "altExp"):
                            data[key] = value
                        elif key in ("controlsAllowed", "rxInvalid"):
                            data[key] = str(value.lower() == "true")

                return {"event": "panda_state", "data": data}
            except (ValueError, IndexError):
                pass

        if "selfdrive enabled=" in line:
            try:
                enabled = line.split("enabled=")[1].strip().lower() == "true"
                return {"event": "selfdrive_state", "data": {"enabled": enabled}}
            except IndexError:
                pass

        return None
