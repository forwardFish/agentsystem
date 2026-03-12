from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class MemoryTaskCheckpointSaver:
    store: dict[str, dict[str, Any]] = field(default_factory=dict)

    def save(self, task_id: str, state: str, workspace_path: str, metadata: dict[str, Any] | None = None) -> None:
        self.store[task_id] = {
            "task_id": task_id,
            "state": state,
            "workspace_path": workspace_path,
            "checkpoint_time": datetime.now(timezone.utc).isoformat(),
            "metadata": metadata or {},
        }

    def load(self, task_id: str) -> dict[str, Any] | None:
        return self.store.get(task_id)

    def list_all(self) -> list[dict[str, Any]]:
        return sorted(self.store.values(), key=lambda item: item["checkpoint_time"], reverse=True)


class PostgresCheckpointSaver:
    def __init__(self, config: dict[str, Any]):
        postgres = config.get("postgres", {})
        try:
            import psycopg2
            from psycopg2.extras import Json, RealDictCursor
        except ImportError as exc:
            raise RuntimeError("psycopg2 is required for PostgresCheckpointSaver") from exc

        self._json_adapter = Json
        self._cursor_factory = RealDictCursor
        self.conn = psycopg2.connect(
            host=postgres["host"],
            port=postgres["port"],
            user=postgres["user"],
            password=postgres["password"],
            dbname=postgres["dbname"],
            connect_timeout=2,
        )
        self._init_table()

    def _init_table(self) -> None:
        with self.conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS task_checkpoints (
                    task_id TEXT PRIMARY KEY,
                    state TEXT NOT NULL,
                    workspace_path TEXT NOT NULL,
                    checkpoint_time TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
                    metadata JSONB
                )
                """
            )
        self.conn.commit()

    def save(self, task_id: str, state: str, workspace_path: str, metadata: dict[str, Any] | None = None) -> None:
        with self.conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO task_checkpoints (task_id, state, workspace_path, metadata)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (task_id) DO UPDATE SET
                    state = EXCLUDED.state,
                    workspace_path = EXCLUDED.workspace_path,
                    checkpoint_time = CURRENT_TIMESTAMP,
                    metadata = EXCLUDED.metadata
                """,
                (task_id, state, workspace_path, self._json_adapter(metadata or {})),
            )
        self.conn.commit()

    def load(self, task_id: str) -> dict[str, Any] | None:
        with self.conn.cursor(cursor_factory=self._cursor_factory) as cur:
            cur.execute(
                """
                SELECT task_id, state, workspace_path, checkpoint_time, metadata
                FROM task_checkpoints
                WHERE task_id = %s
                """,
                (task_id,),
            )
            row = cur.fetchone()
        if not row:
            return None
        return {
            "task_id": row["task_id"],
            "state": row["state"],
            "workspace_path": row["workspace_path"],
            "checkpoint_time": row["checkpoint_time"].isoformat(),
            "metadata": row["metadata"] or {},
        }

    def list_all(self) -> list[dict[str, Any]]:
        with self.conn.cursor(cursor_factory=self._cursor_factory) as cur:
            cur.execute(
                """
                SELECT task_id, state, workspace_path, checkpoint_time, metadata
                FROM task_checkpoints
                ORDER BY checkpoint_time DESC
                """
            )
            rows = cur.fetchall()
        return [
            {
                "task_id": row["task_id"],
                "state": row["state"],
                "workspace_path": row["workspace_path"],
                "checkpoint_time": row["checkpoint_time"].isoformat(),
                "metadata": row["metadata"] or {},
            }
            for row in rows
        ]

    def delete(self, task_id: str) -> None:
        with self.conn.cursor() as cur:
            cur.execute("DELETE FROM task_checkpoints WHERE task_id = %s", (task_id,))
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()


def build_task_checkpoint_saver(config: dict[str, Any]) -> PostgresCheckpointSaver | MemoryTaskCheckpointSaver:
    postgres = config.get("postgres", {})
    required = ("host", "port", "user", "password", "dbname")
    if not all(postgres.get(key) for key in required):
        return MemoryTaskCheckpointSaver()
    try:
        return PostgresCheckpointSaver(config)
    except Exception:
        return MemoryTaskCheckpointSaver()
