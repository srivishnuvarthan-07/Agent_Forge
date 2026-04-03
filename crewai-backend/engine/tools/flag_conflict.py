"""
Flag conflict tool — writes a conflict record to SharedMemory for Critic agents.
"""
from __future__ import annotations
import json
from datetime import datetime, timezone
from crewai.tools import tool
from engine.memory.store import SharedMemory


@tool("flag_conflict")
def flag_conflict_tool(key: str, reason: str) -> str:
    """Flag a memory key as conflicted with a reason. Args: key, reason."""
    if not key or not key.strip():
        return "Error: key must be a non-empty string"
    if not reason or not reason.strip():
        return "Error: reason must be a non-empty string"

    ts = datetime.now(timezone.utc)
    ts_ms = int(ts.timestamp() * 1000)
    record_key = f"conflict_flag:{key}:{ts_ms}"
    record_value = json.dumps({
        "key": key,
        "reason": reason,
        "flagged_by": "critic",
        "timestamp_iso": ts.isoformat(),
    })

    try:
        memory = SharedMemory()
        memory.write(
            key=record_key,
            value=record_value,
            source_agent="critic",
            collection="work_in_progress",
            confidence=0.8,
        )
        return f"Conflict flagged for key '{key}'"
    except Exception as e:
        return f"Conflict write error: {e}"
