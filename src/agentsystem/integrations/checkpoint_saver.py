from __future__ import annotations

import os

from langgraph.checkpoint.memory import MemorySaver


def get_checkpoint_saver():
    db_url = os.getenv("POSTGRES_URL")
    if not db_url:
        return MemorySaver()
    try:
        from langgraph.checkpoint.postgres import PostgresSaver
    except Exception:
        return MemorySaver()
    saver = PostgresSaver.from_conn_string(db_url)
    saver.setup()
    return saver
