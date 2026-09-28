from __future__ import annotations

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from storybard.core.ws_hub import ws_hub

router = APIRouter(tags=["ws"])


@router.websocket("/campaigns/{campaign_id}/stream")
async def campaign_stream(websocket: WebSocket, campaign_id: str) -> None:
    await ws_hub.connect(campaign_id, websocket)
    try:
        while True:
            # Client doesn't need to send anything; keep the connection open and just
            # drain whatever it sends (e.g. pings) so disconnects are detected promptly.
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        ws_hub.disconnect(campaign_id, websocket)
