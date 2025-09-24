"""Process runner and job orchestration for CTS-Lite."""

import asyncio
import json
import threading
import time
import uuid
from concurrent.futures import ProcessPoolExecutor, Future
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from .adapters.batch import (
    BatchAdapter,
    CruiseControlAnalyzerAdapter,
    RlogToCsvAdapter,
    CanBitwatchAdapter,
)
from .adapters.realtime import (
    RealtimeAdapter,
    HybridRxTraceAdapter,
    CanBusCheckAdapter,
    PandaStateAdapter,
)
from .config import CTSLiteConfig
from .db import DatabaseManager
from .models import InputRef, RunStatus, MonitorStatus
from .storage import StorageManager


class JobRunner:
    """Manages execution of batch jobs and realtime monitors."""

    def __init__(self, config: CTSLiteConfig, db: DatabaseManager, storage: StorageManager):
        self.config = config
        self.db = db
        self.storage = storage

        self._executor = ProcessPoolExecutor(max_workers=config.max_workers)

        self._batch_adapters = {
            "cruise-control-analyzer": CruiseControlAnalyzerAdapter(),
            "rlog-to-csv": RlogToCsvAdapter(),
            "can-bitwatch": CanBitwatchAdapter(),
        }

        self._realtime_adapters = {
            "hybrid-rx-trace": HybridRxTraceAdapter(),
            "can-bus-check": CanBusCheckAdapter(),
            "panda-state": PandaStateAdapter(),
        }

        self._monitors: Dict[str, RealtimeAdapter] = {}
        self._monitor_queues: Dict[str, asyncio.Queue] = {}

        self._device_locks: Dict[str, threading.Lock] = {}

    def submit_batch_job(
        self, run_id: str, tool_id: str, params: Dict[str, Any], inputs: List[InputRef]
    ) -> Future:
        """Submit a batch job for execution."""

        if tool_id not in self._batch_adapters:
            raise ValueError(f"Unknown batch tool: {tool_id}")

        adapter = self._batch_adapters[tool_id]

        work_dir = self.storage.get_run_work_dir(run_id)
        log_path = self.storage.get_run_log_path(run_id)

        future = self._executor.submit(
            self._execute_batch_job, run_id, adapter, params, inputs, work_dir, log_path
        )

        return future

    def _execute_batch_job(
        self,
        run_id: str,
        adapter: BatchAdapter,
        params: Dict[str, Any],
        inputs: List[InputRef],
        work_dir: Path,
        log_path: Path,
    ) -> Dict[str, Any]:
        """Execute a batch job in a subprocess."""

        log_file = open(log_path, "w")

        def log_callback(event: Dict[str, Any]):
            """Callback to write log events."""
            event["ts"] = time.time()
            log_file.write(json.dumps(event) + "\n")
            log_file.flush()

        try:
            self.db.update_run_status(
                run_id, RunStatus.running.value, started_at=datetime.utcnow().isoformat()
            )

            log_callback({"event": "status", "status": "running"})

            result = adapter.execute(params, inputs, work_dir, log_callback)

            artifacts = []
            for artifact_path_str in result.get("artifacts", []):
                artifact_path = Path(artifact_path_str)
                if artifact_path.exists():
                    artifact_meta = self.storage.register_artifact(run_id, artifact_path)
                    artifact_id = str(uuid.uuid4())

                    self.db.create_artifact(
                        {
                            "id": artifact_id,
                            "run_id": run_id,
                            "name": artifact_meta["name"],
                            "media_type": artifact_meta["media_type"],
                            "size": artifact_meta["size"],
                            "sha256": artifact_meta["sha256"],
                            "path": artifact_meta["path"],
                            "created_at": datetime.utcnow().isoformat(),
                        }
                    )

                    artifacts.append(artifact_id)
                    log_callback(
                        {"event": "artifact", "name": artifact_meta["name"], "id": artifact_id}
                    )

            if result["return_code"] == 0:
                status = RunStatus.succeeded.value
                log_callback({"event": "status", "status": "succeeded"})
            else:
                status = RunStatus.failed.value
                log_callback({"event": "status", "status": "failed", "error": result.get("error")})

            self.db.update_run_status(
                run_id,
                status,
                finished_at=datetime.utcnow().isoformat(),
                error_message=result.get("error"),
            )

            return {
                "status": status,
                "artifacts": artifacts,
                "return_code": result["return_code"],
                "error": result.get("error"),
            }

        except Exception as e:
            error_msg = str(e)
            log_callback({"event": "error", "error": error_msg})

            self.db.update_run_status(
                run_id,
                RunStatus.failed.value,
                finished_at=datetime.utcnow().isoformat(),
                error_message=error_msg,
            )

            return {
                "status": RunStatus.failed.value,
                "error": error_msg,
                "return_code": -1,
            }

        finally:
            log_file.close()

    def start_monitor(self, monitor_id: str, tool_id: str, params: Dict[str, Any]) -> asyncio.Queue:
        """Start a realtime monitor."""

        if tool_id not in self._realtime_adapters:
            raise ValueError(f"Unknown monitor tool: {tool_id}")

        if monitor_id in self._monitors:
            raise ValueError(f"Monitor {monitor_id} is already running")

        device_key = self._get_device_key(tool_id)
        if device_key:
            if device_key not in self._device_locks:
                self._device_locks[device_key] = threading.Lock()

            if not self._device_locks[device_key].acquire(blocking=False):
                raise RuntimeError(f"Device {device_key} is already in use")

        try:
            adapter = self._realtime_adapters[tool_id]

            event_queue: asyncio.Queue[Dict[str, Any]] = asyncio.Queue(maxsize=1000)

            adapter.start(params, event_queue)

            self._monitors[monitor_id] = adapter
            self._monitor_queues[monitor_id] = event_queue

            self.db.update_monitor_status(
                monitor_id, MonitorStatus.running.value, started_at=datetime.utcnow().isoformat()
            )

            return event_queue

        except Exception:
            if device_key and device_key in self._device_locks:
                self._device_locks[device_key].release()
            raise

    def stop_monitor(self, monitor_id: str) -> None:
        """Stop a realtime monitor."""

        if monitor_id not in self._monitors:
            return

        adapter = self._monitors[monitor_id]
        tool_id = adapter.tool_id

        adapter.stop()

        del self._monitors[monitor_id]
        if monitor_id in self._monitor_queues:
            del self._monitor_queues[monitor_id]

        device_key = self._get_device_key(tool_id)
        if device_key and device_key in self._device_locks:
            self._device_locks[device_key].release()

        self.db.update_monitor_status(
            monitor_id, MonitorStatus.stopped.value, stopped_at=datetime.utcnow().isoformat()
        )

    def get_monitor_queue(self, monitor_id: str) -> Optional[asyncio.Queue]:
        """Get the event queue for a monitor."""
        return self._monitor_queues.get(monitor_id)

    def _get_device_key(self, tool_id: str) -> Optional[str]:
        """Get device key for locking (if tool requires exclusive hardware access)."""
        hardware_tools = {
            "hybrid-rx-trace": "panda",
            "can-bus-check": "can",
            "panda-state": "panda",
        }
        return hardware_tools.get(tool_id)

    def shutdown(self) -> None:
        """Shutdown the runner and clean up resources."""

        for monitor_id in list(self._monitors.keys()):
            self.stop_monitor(monitor_id)

        self._executor.shutdown(wait=True)
