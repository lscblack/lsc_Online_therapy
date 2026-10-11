"""RESERVED: full-duplex realtime voice is a future sub-project. This stub never works."""
from fastapi import APIRouter, WebSocket

router = APIRouter(tags=["live"])

NOT_AVAILABLE = "Not yet available (realtime voice is a future sub-project)."
WS_CLOSE_CODE = 4501  # application-defined: feature not implemented


@router.websocket("/v1/live")
async def live(ws: WebSocket) -> None:
    await ws.accept()
    await ws.send_json({"error": "not_available", "detail": NOT_AVAILABLE})
    await ws.close(code=WS_CLOSE_CODE, reason="not_available")
