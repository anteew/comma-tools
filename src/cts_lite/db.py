"""SQLite database layer for CTS-Lite."""

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional

import aiosqlite
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from .config import CTSLiteConfig


class DatabaseManager:
    """Manages SQLite database operations for CTS-Lite."""

    def __init__(self, config: CTSLiteConfig):
        self.config = config
        self.db_path = config.state_db_path
        self._engine: Optional[Engine] = None

    @property
    def engine(self) -> Engine:
        """Get SQLAlchemy engine with proper configuration."""
        if self._engine is None:
            self._engine = create_engine(
                f"sqlite:///{self.db_path}",
                echo=False,
                connect_args={
                    "check_same_thread": False,
                    "timeout": 30,
                },
            )
            self._apply_pragmas()
        return self._engine

    def _apply_pragmas(self) -> None:
        """Apply SQLite PRAGMAs for optimal performance."""
        with self.engine.connect() as conn:
            conn.execute(text("PRAGMA journal_mode = WAL"))
            conn.execute(text("PRAGMA synchronous = NORMAL"))
            conn.execute(text("PRAGMA foreign_keys = ON"))
            conn.execute(text("PRAGMA busy_timeout = 5000"))
            conn.commit()

    def initialize_schema(self) -> None:
        """Create database tables if they don't exist."""
        schema_sql = """
        -- runs: batch jobs
        CREATE TABLE IF NOT EXISTS runs (
          id TEXT PRIMARY KEY,
          tool_id TEXT NOT NULL,
          version TEXT,
          status TEXT NOT NULL CHECK (status IN ('queued','running','succeeded','failed','canceled')),
          params_json TEXT NOT NULL,
          inputs_json TEXT NOT NULL,
          summary_json TEXT,
          error_message TEXT,
          log_path TEXT NOT NULL,
          work_dir TEXT NOT NULL,
          pid INTEGER,
          submitted_at TEXT NOT NULL,
          started_at TEXT,
          finished_at TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_runs_status ON runs(status);
        CREATE INDEX IF NOT EXISTS idx_runs_submitted_at ON runs(submitted_at);

        -- artifacts: outputs attached to runs
        CREATE TABLE IF NOT EXISTS artifacts (
          id TEXT PRIMARY KEY,
          run_id TEXT NOT NULL,
          name TEXT NOT NULL,
          media_type TEXT NOT NULL,
          schema_version TEXT,
          size INTEGER,
          sha256 TEXT,
          path TEXT NOT NULL,
          created_at TEXT NOT NULL,
          FOREIGN KEY (run_id) REFERENCES runs(id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_artifacts_run_id ON artifacts(run_id);

        -- monitors: realtime streaming sessions
        CREATE TABLE IF NOT EXISTS monitors (
          id TEXT PRIMARY KEY,
          tool_id TEXT NOT NULL,
          version TEXT,
          status TEXT NOT NULL CHECK (status IN ('starting','running','stopped','failed')),
          params_json TEXT NOT NULL,
          pid INTEGER,
          ws_token TEXT NOT NULL,
          started_at TEXT,
          stopped_at TEXT,
          last_heartbeat_at TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_monitors_status ON monitors(status);

        -- uploads: for web UI (optional)
        CREATE TABLE IF NOT EXISTS uploads (
          id TEXT PRIMARY KEY,
          state TEXT NOT NULL CHECK (state IN ('pending','completed','failed')),
          file_name TEXT NOT NULL,
          path TEXT NOT NULL,
          size INTEGER,
          sha256 TEXT,
          created_at TEXT NOT NULL,
          completed_at TEXT
        );

        -- settings/config (simple KV)
        CREATE TABLE IF NOT EXISTS settings (
          key TEXT PRIMARY KEY,
          value TEXT NOT NULL
        );
        """

        with self.engine.connect() as conn:
            for statement in schema_sql.split(";"):
                if statement.strip():
                    conn.execute(text(statement))
            conn.commit()

    @contextmanager
    def get_connection(self) -> Generator[sqlite3.Connection, None, None]:
        """Get a raw SQLite connection for simple operations."""
        conn = sqlite3.connect(str(self.db_path), timeout=30.0)
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            yield conn
        finally:
            conn.close()

    async def get_async_connection(self) -> aiosqlite.Connection:
        """Get an async SQLite connection."""
        conn = await aiosqlite.connect(str(self.db_path))
        await conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def create_run(self, run_data: Dict[str, Any]) -> None:
        """Create a new run record."""
        with self.get_connection() as conn:
            conn.execute(
                """
                INSERT INTO runs (id, tool_id, version, status, params_json, inputs_json,
                                log_path, work_dir, submitted_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    run_data["id"],
                    run_data["tool_id"],
                    run_data.get("version"),
                    run_data["status"],
                    run_data["params_json"],
                    run_data["inputs_json"],
                    run_data["log_path"],
                    run_data["work_dir"],
                    run_data["submitted_at"],
                ),
            )
            conn.commit()

    def get_run(self, run_id: str) -> Optional[Dict[str, Any]]:
        """Get a run by ID."""
        with self.get_connection() as conn:
            cursor = conn.execute("SELECT * FROM runs WHERE id = ?", (run_id,))
            row = cursor.fetchone()
            if row:
                columns = [desc[0] for desc in cursor.description]
                return dict(zip(columns, row))
        return None

    def update_run_status(self, run_id: str, status: str, **kwargs) -> None:
        """Update run status and optional fields."""
        fields = ["status = ?"]
        values = [status]

        for field, value in kwargs.items():
            if value is not None:
                fields.append(f"{field} = ?")
                values.append(value)

        values.append(run_id)

        with self.get_connection() as conn:
            conn.execute(f"UPDATE runs SET {', '.join(fields)} WHERE id = ?", values)
            conn.commit()

    def list_runs(self, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        """List runs with pagination."""
        with self.get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT * FROM runs 
                ORDER BY submitted_at DESC 
                LIMIT ? OFFSET ?
            """,
                (limit, offset),
            )
            columns = [desc[0] for desc in cursor.description]
            return [dict(zip(columns, row)) for row in cursor.fetchall()]

    def create_artifact(self, artifact_data: Dict[str, Any]) -> None:
        """Create a new artifact record."""
        with self.get_connection() as conn:
            conn.execute(
                """
                INSERT INTO artifacts (id, run_id, name, media_type, schema_version,
                                     size, sha256, path, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    artifact_data["id"],
                    artifact_data["run_id"],
                    artifact_data["name"],
                    artifact_data["media_type"],
                    artifact_data.get("schema_version"),
                    artifact_data.get("size"),
                    artifact_data.get("sha256"),
                    artifact_data["path"],
                    artifact_data["created_at"],
                ),
            )
            conn.commit()

    def get_artifacts_for_run(self, run_id: str) -> List[Dict[str, Any]]:
        """Get all artifacts for a run."""
        with self.get_connection() as conn:
            cursor = conn.execute("SELECT * FROM artifacts WHERE run_id = ?", (run_id,))
            columns = [desc[0] for desc in cursor.description]
            return [dict(zip(columns, row)) for row in cursor.fetchall()]

    def get_artifact(self, artifact_id: str) -> Optional[Dict[str, Any]]:
        """Get an artifact by ID."""
        with self.get_connection() as conn:
            cursor = conn.execute("SELECT * FROM artifacts WHERE id = ?", (artifact_id,))
            row = cursor.fetchone()
            if row:
                columns = [desc[0] for desc in cursor.description]
                return dict(zip(columns, row))
        return None

    def create_monitor(self, monitor_data: Dict[str, Any]) -> None:
        """Create a new monitor record."""
        with self.get_connection() as conn:
            conn.execute(
                """
                INSERT INTO monitors (id, tool_id, version, status, params_json, ws_token)
                VALUES (?, ?, ?, ?, ?, ?)
            """,
                (
                    monitor_data["id"],
                    monitor_data["tool_id"],
                    monitor_data.get("version"),
                    monitor_data["status"],
                    monitor_data["params_json"],
                    monitor_data["ws_token"],
                ),
            )
            conn.commit()

    def get_monitor(self, monitor_id: str) -> Optional[Dict[str, Any]]:
        """Get a monitor by ID."""
        with self.get_connection() as conn:
            cursor = conn.execute("SELECT * FROM monitors WHERE id = ?", (monitor_id,))
            row = cursor.fetchone()
            if row:
                columns = [desc[0] for desc in cursor.description]
                return dict(zip(columns, row))
        return None

    def update_monitor_status(self, monitor_id: str, status: str, **kwargs) -> None:
        """Update monitor status and optional fields."""
        fields = ["status = ?"]
        values = [status]

        for field, value in kwargs.items():
            if value is not None:
                fields.append(f"{field} = ?")
                values.append(value)

        values.append(monitor_id)

        with self.get_connection() as conn:
            conn.execute(f"UPDATE monitors SET {', '.join(fields)} WHERE id = ?", values)
            conn.commit()
