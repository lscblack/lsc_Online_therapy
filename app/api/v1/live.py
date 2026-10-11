"""Realtime voice endpoints.

POST /v1/live/offer   JWT (Authorization: Bearer). Body {sdp, type="offer", language, voice?}
                      -> {session_id, type="answer", sdp, ice_servers}. 401 unauth, 429 over the
                      per-identity concurrent cap. Auth/cap are checked BEFORE any
                      RTCPeerConnection exists.
POST /v1/live/ice     JWT. Body {session_id, candidate: {candidate, sdpMid, sdpMLineIndex} | null}
                      (null = end of candidates) -> 204. 404 if not your session.
WS   /v1/live         Control channel. Query: session_id (required), token (access JWT).
                      Browsers/Flutter cannot always set WS headers, hence the query token; an
                      `Authorization: Bearer` header is also accepted. Bad auth closes with 4401,
                      unknown/foreign session 4404, second attach 4409.
                      Server -> client: JSON LiveSession events (state, transcript_partial/final,
                      answer, citations, safety_flags, barge_in, error).
                      Client -> server: {"type":"barge_in"} | {"type":"end"} | {"type":"ice", candidate}.
                      Disconnect or `end` tears the whole session down.
"""
import asyncio
import contextlib

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect, status
from pydantic import BaseModel, Field

from app.api.deps import current_user
from app.models import User
from app.realtime import signaling
from app.realtime.signaling import Runtime, get_runtime

router = APIRouter(tags=["live"])

WS_UNAUTHORIZED = 4401
WS_NOT_FOUND = 4404
WS_CONFLICT = 4409


class OfferIn(BaseModel):
    sdp: str = Field(min_length=1)
    type: str = "offer"
    language: str = "en"
    voice: str | None = None


class OfferOut(BaseModel):
    session_id: str
    type: str = "answer"
    sdp: str
    ice_servers: list[dict]


class IceIn(BaseModel):
    session_id: str
    candidate: dict | None = None


@router.post("/v1/live/offer", response_model=OfferOut)
async def offer(body: OfferIn, user: User = Depends(current_user),
                rt: Runtime = Depends(get_runtime)) -> OfferOut:
    # `current_user` has already run: no unauthenticated request reaches PC creation.
    if signaling.registry.at_cap(str(user.id)):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Too many concurrent live sessions")
    try:
        entry, answer = await signaling.create_session(
            rt, user, body.language, body.voice, body.sdp, body.type)
    except signaling.CapExceeded:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS,
                            "Too many concurrent live sessions") from None
    except Exception as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid offer") from e
    return OfferOut(session_id=entry.id, sdp=answer, ice_servers=rt.ice_servers(str(user.id)))


async def _add_ice(rt: Runtime, entry, candidate: dict | None) -> None:
    await entry.pc.addIceCandidate(None if candidate is None else rt.ice_candidate(candidate))
    entry.touch()


@router.post("/v1/live/ice", status_code=204)
async def ice(body: IceIn, user: User = Depends(current_user),
              rt: Runtime = Depends(get_runtime)) -> None:
    entry = signaling.registry.get(body.session_id)
    if entry is None or entry.identity != str(user.id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Unknown session")
    try:
        await _add_ice(rt, entry, body.candidate)
    except Exception as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid candidate") from e


def _ws_token(ws: WebSocket) -> str | None:
    tok = ws.query_params.get("token")
    if tok:
        return tok
    auth = ws.headers.get("authorization", "")
    return auth[7:] if auth.lower().startswith("bearer ") else None


@router.websocket("/v1/live")
async def live(ws: WebSocket, session_id: str = Query(default=""),
               rt: Runtime = Depends(get_runtime)) -> None:
    token = _ws_token(ws)
    try:
        user = await rt.ws_user(token) if token else None
    except HTTPException:
        user = None
    if user is None:
        await ws.close(code=WS_UNAUTHORIZED, reason="unauthorized")
        return
    entry = signaling.registry.get(session_id)
    if entry is None or entry.identity != str(user.id):
        await ws.close(code=WS_NOT_FOUND, reason="unknown_session")
        return
    if entry.ws_attached:
        await ws.close(code=WS_CONFLICT, reason="already_attached")
        return
    entry.ws_attached = True
    await ws.accept()

    async def pump_out() -> None:
        async for ev in entry.live.events():
            await ws.send_json(ev)
            entry.touch()

    async def pump_in() -> None:
        while True:
            msg = await ws.receive_json()
            entry.touch()
            kind = msg.get("type") if isinstance(msg, dict) else None
            if kind == "barge_in":
                await entry.live.barge_in()
            elif kind == "end":
                return
            elif kind == "ice":
                with contextlib.suppress(Exception):
                    await _add_ice(rt, entry, msg.get("candidate"))

    tasks = [asyncio.ensure_future(pump_out()), asyncio.ensure_future(pump_in())]
    try:
        await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
    finally:
        # Teardown is started first and runs in its own (shielded) task, so it completes even
        # if this handler is cancelled again while unwinding.
        closing = asyncio.ensure_future(entry.close())
        for t in tasks:
            t.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        await closing
        with contextlib.suppress(Exception):
            await ws.close()
