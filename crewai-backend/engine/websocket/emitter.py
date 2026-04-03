import json
import asyncio
from datetime import datetime, timezone
from enum import Enum


class EventType(str, Enum):
    agent_started       = "agent_started"
    agent_thinking      = "agent_thinking"
    agent_completed     = "agent_completed"
    agent_spawned       = "agent_spawned"
    agent_error         = "agent_error"
    memory_update       = "memory_update"
    conflict_detected   = "conflict_detected"
    conflict_resolved   = "conflict_resolved"
    crew_finished       = "crew_finished"


class EventEmitter:
    """
    Sends structured JSON events to all connected WebSocket clients via
    ConnectionManager, and keeps an in-memory log.
    Supports sync listeners via subscribe() for state tracking.
    """

    def __init__(self):
        self.log: list[dict] = []
        self._listeners: list = []

    def subscribe(self, fn) -> None:
        self._listeners.append(fn)

    def unsubscribe(self, fn) -> None:
        self._listeners = [l for l in self._listeners if l is not fn]

    def _notify_listeners(self, event: dict):
        for fn in self._listeners:
            try:
                fn(event)
            except Exception:
                pass

    async def _broadcast(self, event: dict):
        """Push event to all connected WebSocket clients."""
        # Import here to avoid circular import at module load
        from engine.websocket.manager import manager
        self.log.append(event)
        self._notify_listeners(event)
        await manager.broadcast(event)

    def emit(self, event_type: str, payload: dict):
        """Fire-and-forget emit — safe to call from sync or async context."""
        event = {
            "type": event_type,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            **payload,
        }
        try:
            loop = asyncio.get_running_loop()
            asyncio.ensure_future(self._broadcast(event), loop=loop)
        except RuntimeError:
            # No running loop — we're in a background thread, schedule safely
            self.log.append(event)
            self._notify_listeners(event)

    # ── Convenience helpers ───────────────────────────────────────────────────

    def agent_started(self, agent_id: str, role: str):
        self.emit(EventType.agent_started, {"agent_id": agent_id, "role": role})

    def agent_thinking(self, agent_id: str, message: str):
        self.emit(EventType.agent_thinking, {"agent_id": agent_id, "message": message})

    def agent_completed(self, agent_id: str, output: str):
        self.emit(EventType.agent_completed, {"agent_id": agent_id, "output": output})

    def agent_spawned(self, parent_id: str, new_agent: dict):
        self.emit(EventType.agent_spawned, {"parent_id": parent_id, "new_agent": new_agent})

    def agent_error(self, agent_id: str, error: str):
        self.emit(EventType.agent_error, {"agent_id": agent_id, "error": error})

    def memory_update(self, key: str, collection: str, source_agent: str):
        self.emit(EventType.memory_update, {"key": key, "collection": collection, "source_agent": source_agent})

    def conflict_detected(self, key: str, agent_a: str, agent_b: str, severity: str):
        self.emit(EventType.conflict_detected, {"key": key, "agent_a": agent_a, "agent_b": agent_b, "severity": severity})

    def conflict_resolved(self, key: str, resolved_by: str, resolution: str):
        self.emit(EventType.conflict_resolved, {"key": key, "resolved_by": resolved_by, "resolution": resolution})

    def crew_finished(self, crew_id: str, result: str):
        self.emit(EventType.crew_finished, {"crew_id": crew_id, "result": result})


# Shared singleton
emitter = EventEmitter()
