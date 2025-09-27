"""Monitor management endpoints and runtime."""

from __future__ import annotations

import asyncio
import json
import logging
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, AsyncIterator, Dict, List, Optional, Set

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect

from .config import Config

logger = logging.getLogger(__name__)
router = APIRouter()


MONITOR_MODULES: Dict[str, str] = {
    "hybrid_rx_trace": "comma_tools.monitors.hybrid_rx_trace",
    "can_bus_check": "comma_tools.monitors.can_bus_check",
    "can_hybrid_rx_check": "comma_tools.monitors.can_hybrid_rx_check",
}


@dataclass
class MonitorContext:
    id: str
    tool_id: str
    params: Dict[str, Any] = field(default_factory=dict)
    process: Optional[asyncio.subprocess.Process] = None
    queue: asyncio.Queue[str] = field(default_factory=asyncio.Queue)
    clients: Set[WebSocket] = field(default_factory=set)
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    stopped_at: Optional[datetime] = None
    status: str = "starting"


class MonitorManager:
    def __init__(self, config: Config):
        self.config = config
        self.monitors: Dict[str, MonitorContext] = {}

    def _build_command(self, tool_id: str, params: Dict[str, Any]) -> List[str]:
        module = MONITOR_MODULES.get(tool_id)
        if not module:
            raise ValueError(f"Unknown monitor tool_id '{tool_id}'")

        cmd = [sys.executable, "-u", "-m", module]
        # Current monitors do not accept CLI args; keep for future extension.
        for key, value in params.items():
            if isinstance(value, bool):
                if value:
                    cmd.append(f"--{key.replace('_', '-')}")
            elif isinstance(value, list):
                cmd.append(f"--{key.replace('_', '-')}")
                cmd.extend(str(v) for v in value)
            else:
                cmd.extend([f"--{key.replace('_', '-')}", str(value)])
        return cmd

    async def start(self, tool_id: str, params: Dict[str, Any]) -> MonitorContext:
        import uuid

        monitor_id = str(uuid.uuid4())
        ctx = MonitorContext(id=monitor_id, tool_id=tool_id, params=params)
        self.monitors[monitor_id] = ctx

        cmd = self._build_command(tool_id, params)
        logger.info(f"Starting monitor {tool_id} as {monitor_id}: {' '.join(cmd)}")
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            ctx.process = proc
            ctx.status = "running"

            # Reader tasks
            asyncio.create_task(self._read_stream(ctx, proc.stdout, source="stdout"))
            asyncio.create_task(self._read_stream(ctx, proc.stderr, source="stderr"))
            asyncio.create_task(self._watch_process(ctx))
            return ctx
        except FileNotFoundError as e:
            ctx.status = "failed"
            ctx.stopped_at = datetime.now(timezone.utc)
            raise RuntimeError(f"Failed to start monitor (dependency missing?): {e}")

    async def _watch_process(self, ctx: MonitorContext) -> None:
        assert ctx.process is not None
        await ctx.process.wait()
        rc = ctx.process.returncode
        ctx.status = "stopped" if rc == 0 else "failed"
        ctx.stopped_at = datetime.now(timezone.utc)
        await ctx.queue.put(json.dumps({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "type": "status",
            "data": {"status": ctx.status, "return_code": rc},
        }))
        await self._broadcast(ctx)

    async def _read_stream(self, ctx: MonitorContext, stream: Optional[asyncio.StreamReader], *, source: str) -> None:
        if stream is None:
            return
        while True:
            try:
                line = await stream.readline()
                if not line:
                    break
                text = line.decode(errors="replace").rstrip("\n")
                event = {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "type": source,
                    "data": text,
                }
                await ctx.queue.put(json.dumps(event))
                await self._broadcast(ctx)
            except Exception:
                break

    async def _broadcast(self, ctx: MonitorContext) -> None:
        # Drain queue and send to all connected clients
        pending: List[str] = []
        while not ctx.queue.empty():
            try:
                pending.append(ctx.queue.get_nowait())
            except asyncio.QueueEmpty:
                break
        if not pending:
            return
        to_remove: Set[WebSocket] = set()
        for ws in ctx.clients:
            for payload in pending:
                try:
                    await ws.send_text(payload)
                except Exception:
                    to_remove.add(ws)
                    break
        for ws in to_remove:
            try:
                ctx.clients.remove(ws)
            except KeyError:
                pass

    async def stop(self, monitor_id: str) -> bool:
        ctx = self.monitors.get(monitor_id)
        if not ctx:
            return False
        if ctx.process and ctx.status == "running":
            try:
                ctx.process.terminate()
            except ProcessLookupError:
                pass
        ctx.status = "stopping"
        return True

    def status(self, monitor_id: str) -> Dict[str, Any]:
        ctx = self.monitors.get(monitor_id)
        if not ctx:
            raise KeyError("Monitor not found")
        uptime = None
        if ctx.started_at:
            ref = ctx.stopped_at or datetime.now(timezone.utc)
            uptime = str(ref - ctx.started_at)
        return {
            "id": ctx.id,
            "tool_id": ctx.tool_id,
            "status": ctx.status,
            "started_at": ctx.started_at,
            "stopped_at": ctx.stopped_at,
            "uptime": uptime,
        }

    def list(self) -> List[Dict[str, Any]]:
        return [self.status(mid) for mid in list(self.monitors.keys())]


_manager: Optional[MonitorManager] = None


def get_manager() -> MonitorManager:
    global _manager
    if _manager is None:
        _manager = MonitorManager(Config.from_env())
    return _manager


@router.post("/monitors")
async def start_monitor(payload: Dict[str, Any], manager: MonitorManager = Depends(get_manager)) -> Dict[str, Any]:
    tool_id = payload.get("tool_id")
    params = payload.get("params") or {}
    if not tool_id:
        raise HTTPException(status_code=400, detail="tool_id required")
    try:
        ctx = await manager.start(tool_id, params)
        return {"monitor_id": ctx.id, "status": ctx.status}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/monitors")
async def list_monitors(manager: MonitorManager = Depends(get_manager)) -> List[Dict[str, Any]]:
    return manager.list()


@router.get("/monitors/{monitor_id}/status")
async def get_monitor_status(monitor_id: str, manager: MonitorManager = Depends(get_manager)) -> Dict[str, Any]:
    try:
        return manager.status(monitor_id)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/monitors/{monitor_id}")
async def stop_monitor(monitor_id: str, manager: MonitorManager = Depends(get_manager)) -> Dict[str, Any]:
    stopped = await manager.stop(monitor_id)
    if not stopped:
        raise HTTPException(status_code=404, detail="Monitor not found")
    return {"monitor_id": monitor_id, "status": "stopping"}


@router.websocket("/monitors/{monitor_id}/stream")
async def stream_monitor(websocket: WebSocket, monitor_id: str, manager: MonitorManager = Depends(get_manager)) -> None:
    await websocket.accept()
    try:
        ctx = manager.monitors.get(monitor_id)
        if not ctx:
            await websocket.send_text(json.dumps({"error": "monitor not found"}))
            await websocket.close()
            return
        ctx.clients.add(websocket)

        # Send initial status
        await websocket.send_text(
            json.dumps({
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "type": "status",
                "data": {"status": ctx.status},
            })
        )

        # Keep connection alive and rely on broadcast to push data
        while True:
            try:
                # Just wait for client ping/close
                await asyncio.sleep(5)
            except asyncio.CancelledError:
                break
    except WebSocketDisconnect:
        pass
    finally:
        ctx = manager.monitors.get(monitor_id)
        if ctx and websocket in ctx.clients:
            ctx.clients.remove(websocket)

