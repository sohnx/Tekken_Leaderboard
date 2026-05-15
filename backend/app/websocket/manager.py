# app/websocket/manager.py
import json
import logging
from datetime import datetime
from typing import Set
from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manages all active WebSocket connections for the leaderboard."""

    def __init__(self):
        self.active_connections: Set[WebSocket] = set()

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.add(websocket)
        logger.info(f"WebSocket connected. Total connections: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        self.active_connections.discard(websocket)
        logger.info(f"WebSocket disconnected. Total connections: {len(self.active_connections)}")

    async def broadcast(self, message: dict):
        """Broadcast a message to all connected clients."""
        if not self.active_connections:
            return

        data = json.dumps(message, default=str)
        dead = set()

        for connection in self.active_connections:
            try:
                await connection.send_text(data)
            except Exception as e:
                logger.warning(f"Failed to send to WebSocket: {e}")
                dead.add(connection)

        # Clean up dead connections
        for conn in dead:
            self.active_connections.discard(conn)

    async def broadcast_leaderboard(self, leaderboard_data: dict):
        """Broadcast leaderboard update to all clients."""
        message = {
            "type": "leaderboard_update",
            "data": leaderboard_data,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        await self.broadcast(message)

    async def broadcast_match_event(self, event_type: str, data: dict):
        """Broadcast match events (new match, result, undo, etc.)."""
        message = {
            "type": event_type,
            "data": data,
            "timestamp": datetime.utcnow().isoformat()
        }
        await self.broadcast(message)

    @property
    def connection_count(self) -> int:
        return len(self.active_connections)


# Singleton instance
manager = ConnectionManager()