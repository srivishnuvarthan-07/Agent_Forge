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
    Sends structured JSON events over WebSocket.
    Falls back to in-memory log when no connection is active.
    Supports sync listeners via subscribe() for state tracking.
    """

    def __init__(self):
        self._ws = None
        self.log: list[dict] = []
        self._listeners: list = []  # list of callables: fn(event: dict)

    def subscribe(self, fn) -> None:
        """Register a sync callable that receives every emitted event dict."""
        self._listeners.append(fn)

    def unsubscribe(self, fn) -> None:
        """Remove a previously registered listener."""
        self._listeners = [l for l in self._listeners if l is not fn]

    async def connect(self, websocket_url: str):
        """Establish a WebSocket client connection."""
        try:
            import websockets
            self._ws = await websockets.connect(websocket_url)
        except ImportError:
            raise RuntimeError("websockets package not installed. Run: pip install websockets")

    async def disconnect(self):
        if self._ws:
            await self._ws.close()
            self._ws = None

    async def _send(self, event: dict):
        self.log.append(event)
        # Notify sync listeners (state trackers, job store updaters)
        for fn in self._listeners:
            try:
                fn(event)
            except Exception:
                pass
        if self._ws:
            try:
                await self._ws.send(json.dumps(event))
            except Exception:
                pass  # connection dropped — event already in log

    def emit(self, event_type: str, payload: dict):
        """Fire-and-forget emit — safe to call from sync or async context."""
        event = {
            "type": event_type,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            **payload,
        }
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.ensure_future(self._send(event))
            else:
                loop.run_until_complete(self._send(event))
        except RuntimeError:
            self.log.append(event)

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


# Shared singleton — imported by other modules
emitter = EventEmitter()
