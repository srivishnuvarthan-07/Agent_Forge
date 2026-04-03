from fastapi import WebSocket
from typing import Optional


class ConnectionManager:
    def __init__(self, redis_manager=None):
        self.active_connections: dict = {}
        self.redis_manager = redis_manager

    async def initialize(self):
        """Subscribe to Redis broadcast channel if redis_manager is available."""
        if self.redis_manager:
            await self.redis_manager.subscribe("workflow:broadcast", self._on_redis_broadcast)

    async def _on_redis_broadcast(self, message: dict):
        """Handle messages received from Redis broadcast channel."""
        for conn in self.active_connections.values():
            try:
                await conn["socket"].send_json(message)
            except Exception:
                pass

    async def connect(self, websocket: WebSocket, workflow_id: str, client_type: str):
        await websocket.accept()
        self.active_connections[workflow_id] = {"socket": websocket, "type": client_type}

    async def disconnect(self, workflow_id: str):
        if workflow_id in self.active_connections:
            del self.active_connections[workflow_id]

    async def send_to_workflow(self, workflow_id: str, message: dict):
        conn = self.active_connections.get(workflow_id)
        if conn:
            await conn["socket"].send_json(message)

    async def broadcast_to_all(self, message: dict):
        for conn in self.active_connections.values():
            try:
                await conn["socket"].send_json(message)
            except Exception:
                pass
        if self.redis_manager:
            await self.redis_manager.publish("workflow:broadcast", message)
