from __future__ import annotations

from collections import defaultdict

from fastapi import WebSocket


class WSHub:
    """Minimal in-process pub/sub for streaming chain events to connected clients.

    Single-process only (matches Phase 0/1 scope) — fine for local dev; a multi-worker
    deployment would need this backed by something shared (Redis pub/sub, etc.), which is
    Phase 5 platform scope, not now.
    """

    def __init__(self) -> None:
        self._connections: dict[str, set[WebSocket]] = defaultdict(set)

    async def connect(self, campaign_id: str, ws: WebSocket) -> None:
        await ws.accept()
        self._connections[campaign_id].add(ws)

    def disconnect(self, campaign_id: str, ws: WebSocket) -> None:
        self._connections[campaign_id].discard(ws)

    async def broadcast(self, campaign_id: str, message: dict) -> None:
        dead: list[WebSocket] = []
        for ws in self._connections.get(campaign_id, set()):
            try:
                await ws.send_json(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(campaign_id, ws)


ws_hub = WSHub()
