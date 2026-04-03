from datetime import datetime
from .manager import ConnectionManager
from . import events

class EventEmitter:
    def __init__(self, manager: ConnectionManager):
        self.manager = manager

    async def emit(self, workflow_id: str, event_type: str, payload: dict):
        message = {
            "type": event_type,
            "timestamp": datetime.utcnow().isoformat(),
            "payload": payload,
        }
        await self.manager.send_to_workflow(workflow_id, message)

    async def broadcast_system_status(self, status: str, details: dict):
        message = {
            "type": events.SYSTEM_STATUS,
            "timestamp": datetime.utcnow().isoformat(),
            "payload": {"status": status, **details},
        }
        await self.manager.broadcast_to_all(message)
