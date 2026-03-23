"""WebSocket connection pool manager.

Manages active WebSocket connections and broadcasts pipeline events
(new scored events, heatmap updates) to all connected clients.
"""
from __future__ import annotations

import json
import logging
from typing import Any

from fastapi import WebSocket

logger = logging.getLogger("app.ws")


class ConnectionManager:
    def __init__(self) -> None:
        self._active: list[WebSocket] = []

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        self._active.append(ws)
        logger.info("WS client connected total=%d", len(self._active))

    def disconnect(self, ws: WebSocket) -> None:
        self._active = [c for c in self._active if c is not ws]
        logger.info("WS client disconnected total=%d", len(self._active))

    async def broadcast(self, event_type: str, data: Any) -> None:
        """Send a typed message to all connected clients."""
        payload = json.dumps({"type": event_type, "data": data})
        dead: list[WebSocket] = []
        for ws in list(self._active):
            try:
                await ws.send_text(payload)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)

    @property
    def connection_count(self) -> int:
        return len(self._active)


manager = ConnectionManager()
