"""FastAPI application for CTS-Lite service."""

import asyncio
import json
import secrets
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import uvicorn
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from .config import CTSLiteConfig
from .db import DatabaseManager
from .models import (
    CreateRunRequest,
    CreateMonitorRequest,
    ExecRequest,
    HealthResponse,
    VersionResponse,
    Run,
    Monitor,
    RunStatus,
    MonitorStatus,
    InputRef,
    ArtifactRef,
    ToolCapability,
)
from .registry import registry
from .runner import JobRunner
from .storage import StorageManager


config = CTSLiteConfig()
config.ensure_directories()

db = DatabaseManager(config)
db.initialize_schema()

storage = StorageManager(config)
runner = JobRunner(config, db, storage)

app = FastAPI(
    title="CTS-Lite",
    description="comma-tools Local Service - HTTP API for automotive debugging tools",
    version="0.1.0",
    docs_url="/docs" if not config.api_key else None,  # Disable docs if auth enabled
)

if config.cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

security = HTTPBearer(auto_error=False) if config.api_key else None


def get_current_user(credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)):
    """Verify API key if authentication is enabled."""
    if not config.api_key:
        return None  # Auth disabled
    
    if not credentials or credentials.credentials != config.api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return credentials.credentials



@app.get("/v1/capabilities", response_model=List[ToolCapability])
async def get_capabilities():
    """Get capabilities of all available tools."""
    return registry.get_capabilities()


@app.post("/v1/runs", response_model=Run, status_code=201)
async def create_run(request: CreateRunRequest):
    """Create a new batch analyzer run."""
    
    try:
        tool_spec = registry.get(request.tool_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    
    if tool_spec.kind.value != "analyzer":
        raise HTTPException(status_code=400, detail=f"Tool {request.tool_id} is not an analyzer")
    
    run_id = str(uuid.uuid4())
    
    run_data = {
        "id": run_id,
        "tool_id": request.tool_id,
        "version": tool_spec.version,
        "status": RunStatus.queued.value,
        "params_json": json.dumps(request.params),
        "inputs_json": json.dumps([input_ref.model_dump() for input_ref in request.inputs]),
        "log_path": str(storage.get_run_log_path(run_id)),
        "work_dir": str(storage.get_run_work_dir(run_id)),
        "submitted_at": datetime.utcnow().isoformat(),
    }
    
    db.create_run(run_data)
    
    try:
        runner.submit_batch_job(run_id, request.tool_id, request.params, request.inputs)
    except Exception as e:
        db.update_run_status(run_id, RunStatus.failed.value, error_message=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to submit job: {e}")
    
    return await get_run(run_id)


@app.get("/v1/runs/{run_id}", response_model=Run)
async def get_run(run_id: str):
    """Get run status and details."""
    
    run_data = db.get_run(run_id)
    if not run_data:
        raise HTTPException(status_code=404, detail="Run not found")
    
    artifacts_data = db.get_artifacts_for_run(run_id)
    artifacts = []
    for artifact_data in artifacts_data:
        artifacts.append(ArtifactRef(
            id=artifact_data["id"],
            name=artifact_data["name"],
            media_type=artifact_data["media_type"],
            size=artifact_data["size"],
            sha256=artifact_data["sha256"],
            schema_version=artifact_data["schema_version"],
            download_uri=f"/v1/artifacts/{artifact_data['id']}/download"
        ))
    
    params = json.loads(run_data["params_json"])
    inputs = [InputRef(**input_data) for input_data in json.loads(run_data["inputs_json"])]
    outputs = json.loads(run_data["summary_json"]) if run_data["summary_json"] else None
    
    return Run(
        id=run_data["id"],
        tool_id=run_data["tool_id"],
        version=run_data["version"],
        status=RunStatus(run_data["status"]),
        submitted_at=datetime.fromisoformat(run_data["submitted_at"]),
        started_at=datetime.fromisoformat(run_data["started_at"]) if run_data["started_at"] else None,
        finished_at=datetime.fromisoformat(run_data["finished_at"]) if run_data["finished_at"] else None,
        params=params,
        inputs=inputs,
        outputs=outputs,
        artifacts=artifacts,
        logs_uri=f"/v1/runs/{run_id}/logs"
    )


@app.get("/v1/runs/{run_id}/logs")
async def get_run_logs(run_id: str):
    """Stream run logs via Server-Sent Events."""
    
    run_data = db.get_run(run_id)
    if not run_data:
        raise HTTPException(status_code=404, detail="Run not found")
    
    log_path = Path(run_data["log_path"])
    
    async def event_stream():
        """Generate SSE events from log file."""
        
        yield f"event: status\ndata: {json.dumps({'status': run_data['status']})}\n\n"
        
        if not log_path.exists():
            yield f"event: error\ndata: {json.dumps({'error': 'Log file not found'})}\n\n"
            return
        
        with open(log_path, "r") as f:
            while True:
                line = f.readline()
                if not line:
                    current_run = db.get_run(run_id)
                    if current_run and current_run["status"] in ("queued", "running"):
                        await asyncio.sleep(0.1)  # Wait for more data
                        continue
                    else:
                        break  # Run is complete
                
                try:
                    event_data = json.loads(line.strip())
                    event_type = event_data.get("event", "log")
                    yield f"event: {event_type}\ndata: {json.dumps(event_data)}\n\n"
                except json.JSONDecodeError:
                    yield f"event: log\ndata: {json.dumps({'line': line.strip()})}\n\n"
    
    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )


@app.delete("/v1/runs/{run_id}")
async def cancel_run(run_id: str):
    """Cancel a running job."""
    
    run_data = db.get_run(run_id)
    if not run_data:
        raise HTTPException(status_code=404, detail="Run not found")
    
    if run_data["status"] not in ("queued", "running"):
        raise HTTPException(status_code=400, detail="Run cannot be canceled")
    
    db.update_run_status(run_id, RunStatus.canceled.value, finished_at=datetime.utcnow().isoformat())
    
    return {"message": "Run canceled"}


@app.post("/v1/monitors", response_model=Monitor, status_code=201)
async def create_monitor(request: CreateMonitorRequest):
    """Start a new realtime monitor."""
    
    if not config.allow_hardware:
        raise HTTPException(status_code=403, detail="Hardware access is disabled")
    
    try:
        tool_spec = registry.get(request.tool_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    
    if tool_spec.kind.value != "monitor":
        raise HTTPException(status_code=400, detail=f"Tool {request.tool_id} is not a monitor")
    
    monitor_id = str(uuid.uuid4())
    ws_token = secrets.token_urlsafe(32)
    
    monitor_data = {
        "id": monitor_id,
        "tool_id": request.tool_id,
        "version": tool_spec.version,
        "status": MonitorStatus.starting.value,
        "params_json": json.dumps(request.params),
        "ws_token": ws_token,
    }
    
    db.create_monitor(monitor_data)
    
    try:
        runner.start_monitor(monitor_id, request.tool_id, request.params)
    except Exception as e:
        db.update_monitor_status(monitor_id, MonitorStatus.failed.value)
        raise HTTPException(status_code=500, detail=f"Failed to start monitor: {e}")
    
    return Monitor(
        id=monitor_id,
        tool_id=request.tool_id,
        version=tool_spec.version,
        status=MonitorStatus.running,
        params=request.params,
        stream_uri=f"/v1/monitors/{monitor_id}/stream?token={ws_token}"
    )


@app.get("/v1/monitors/{monitor_id}", response_model=Monitor)
async def get_monitor(monitor_id: str):
    """Get monitor status."""
    
    monitor_data = db.get_monitor(monitor_id)
    if not monitor_data:
        raise HTTPException(status_code=404, detail="Monitor not found")
    
    params = json.loads(monitor_data["params_json"])
    
    return Monitor(
        id=monitor_data["id"],
        tool_id=monitor_data["tool_id"],
        version=monitor_data["version"],
        status=MonitorStatus(monitor_data["status"]),
        params=params,
        stream_uri=f"/v1/monitors/{monitor_id}/stream?token={monitor_data['ws_token']}"
    )


@app.websocket("/v1/monitors/{monitor_id}/stream")
async def monitor_stream(websocket: WebSocket, monitor_id: str, token: str):
    """WebSocket stream for monitor events."""
    
    monitor_data = db.get_monitor(monitor_id)
    if not monitor_data or monitor_data["ws_token"] != token:
        await websocket.close(code=1008, reason="Invalid monitor or token")
        return
    
    await websocket.accept()
    
    event_queue = runner.get_monitor_queue(monitor_id)
    if not event_queue:
        await websocket.close(code=1011, reason="Monitor not running")
        return
    
    try:
        last_heartbeat = time.time()
        
        while True:
            try:
                now = time.time()
                if now - last_heartbeat >= 2.0:
                    await websocket.send_json({"event": "heartbeat", "ts": now})
                    last_heartbeat = now
                    
                    db.update_monitor_status(
                        monitor_id,
                        monitor_data["status"],
                        last_heartbeat_at=datetime.utcnow().isoformat()
                    )
                
                try:
                    event = await asyncio.wait_for(event_queue.get(), timeout=0.5)
                    await websocket.send_json(event)
                except asyncio.TimeoutError:
                    continue  # No event, continue to heartbeat check
                
            except WebSocketDisconnect:
                break
    
    except Exception as e:
        await websocket.close(code=1011, reason=f"Internal error: {e}")
    
    finally:
        runner.stop_monitor(monitor_id)


@app.delete("/v1/monitors/{monitor_id}")
async def stop_monitor(monitor_id: str):
    """Stop a monitor."""
    
    monitor_data = db.get_monitor(monitor_id)
    if not monitor_data:
        raise HTTPException(status_code=404, detail="Monitor not found")
    
    runner.stop_monitor(monitor_id)
    
    return {"message": "Monitor stopped"}


@app.get("/v1/artifacts/{artifact_id}/download")
async def download_artifact(artifact_id: str):
    """Download an artifact file."""
    
    artifact_data = db.get_artifact(artifact_id)
    if not artifact_data:
        raise HTTPException(status_code=404, detail="Artifact not found")
    
    artifact_path = Path(artifact_data["path"])
    if not artifact_path.exists():
        raise HTTPException(status_code=404, detail="Artifact file not found")
    
    return FileResponse(
        path=artifact_path,
        filename=artifact_data["name"],
        media_type=artifact_data["media_type"]
    )


@app.get("/v1/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    
    checks = {}
    status = "ok"
    
    try:
        with db.get_connection() as conn:
            conn.execute("SELECT 1").fetchone()
        checks["database"] = "ok"
    except Exception as e:
        checks["database"] = f"error: {e}"
        status = "error"
    
    try:
        disk_info = storage.get_disk_usage()
        if disk_info["free_gb"] < 1.0:  # Less than 1GB free
            checks["disk_space"] = f"low: {disk_info['free_gb']:.1f}GB free"
            status = "degraded"
        else:
            checks["disk_space"] = f"ok: {disk_info['free_gb']:.1f}GB free"
    except Exception as e:
        checks["disk_space"] = f"error: {e}"
        status = "error"
    
    if config.allow_hardware:
        checks["hardware_access"] = "enabled"
    else:
        checks["hardware_access"] = "disabled"
    
    return HealthResponse(
        status=status,
        checks=checks,
        timestamp=datetime.utcnow()
    )


@app.get("/v1/version", response_model=VersionResponse)
async def get_version():
    """Get version information."""
    
    tool_versions = {}
    for tool_spec in registry.list_tools():
        tool_versions[tool_spec.tool_id] = tool_spec.version
    
    return VersionResponse(
        service_version="0.1.0",
        tool_versions=tool_versions
    )


@app.get("/openapi.json")
async def get_openapi():
    """Get OpenAPI schema."""
    return app.openapi()


def cli_main():
    """CLI entry point for starting the service."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Start CTS-Lite service")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind to")
    parser.add_argument("--port", type=int, default=8080, help="Port to bind to")
    parser.add_argument("--workers", type=int, help="Number of worker processes")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload")
    
    args = parser.parse_args()
    
    if args.workers:
        config.max_workers = args.workers
    
    print(f"Starting CTS-Lite service on {args.host}:{args.port}")
    print(f"Data directory: {config.data_root}")
    print(f"Max workers: {config.max_workers}")
    print(f"Hardware access: {'enabled' if config.allow_hardware else 'disabled'}")
    
    if config.api_key:
        print("API key authentication: enabled")
    else:
        print("API key authentication: disabled")
    
    uvicorn.run(
        "cts_lite.main:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        access_log=True
    )


if __name__ == "__main__":
    cli_main()
