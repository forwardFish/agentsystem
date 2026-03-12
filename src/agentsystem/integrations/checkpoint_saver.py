from __future__ import annotations

import os

from langgraph.checkpoint.memory import MemorySaver


def _build_conn_string(config: dict | None = None) -> str | None:
    if os.getenv("POSTGRES_URL"):
        return os.getenv("POSTGRES_URL")
    if not config:
        return None
    postgres = config.get("postgres", {})
    url = postgres.get("url")
    if url:
        return url
    required = ("host", "port", "user", "password", "dbname")
    if not all(postgres.get(key) for key in required):
        return None
    return (
        f"postgresql://{postgres['user']}:{postgres['password']}"
        f"@{postgres['host']}:{postgres['port']}/{postgres['dbname']}"
    )


def get_checkpoint_saver(config: dict | None = None):
    db_url = _build_conn_string(config)
    if not db_url:
        return MemorySaver()
    try:
        from langgraph.checkpoint.postgres import PostgresSaver
    except Exception:
        return MemorySaver()
    try:
        saver = PostgresSaver.from_conn_string(db_url)
        saver.setup()
        return saver
    except Exception:
        return MemorySaver()
