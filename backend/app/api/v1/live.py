"""Realtime voice endpoints.

POST /v1/live/offer   JWT (Authorization: Bearer). Body {sdp, type="offer", language, voice?}
                      -> {session_id, type="answer", sdp, ice_servers}. 401 unauth, 429 over the
                      per-identity concurrent cap. Auth/cap are checked BEFORE any
                      RTCPeerConnection exists.
POST /v1/live/ice     JWT. Body {session_id, candidate: {candidate, sdpMid, sdpMLineIndex} | null}
                      (null = end of candidates) -> 204. 404 if not your session.
WS   /v1/live         Control channel. Query: session_id (required), ticket (the `ws_ticket` from
                      /offer: single-use, ~60s, bound to the session; the access JWT is NOT put
                      in the URL). An `Authorization: Bearer` header is accepted as a fallback.
                      The socket is accepted first, then closed with an app code so clients can
                      tell failures apart: 4401 unauthorized, 4404 unknown/foreign session,
                      4409 already attached.
                      Server -> client: JSON LiveSession events (state, transcript_partial/final,
                      answer, citations, safety_flags, barge_in, error).
                      Client -> server: {"type":"barge_in"} | {"type":"end"} | {"type":"ice", candidate}.
                      Disconnect or `end` tears the whole session down.
"""
import asyncio
import contextlib
import logging

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect, status
from pydantic import BaseModel, Field

from app.api.deps import current_user
from app.models import User
from app.realtime import signaling
from app.realtime.signaling import Runtime, get_runtime

logger = logging.getLogger(__name__)

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
    ws_ticket: str  # single-use, ~60s, bound to session_id; pass as ?ticket= on the WS


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
    except ImportError as e:  # aiortc/av (realtime extra) not installed
        logger.warning("realtime unavailable: %s", e)
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE,
                            "Realtime voice unavailable (install the realtime extra: "
                            "pip install '.[realtime]')") from e
    except (ValueError, KeyError, TypeError) as e:  # malformed SDP; anything else is a real 500
        logger.warning("rejected offer: %s", type(e).__name__)
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid offer") from e
    return OfferOut(session_id=entry.id, sdp=answer, ice_servers=rt.ice_servers(str(user.id)),
                    ws_ticket=signaling.issue_ticket(entry.id, str(user.id)))


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


def _bearer(ws: WebSocket) -> str | None:
    auth = ws.headers.get("authorization", "")
    return auth[7:] if auth.lower().startswith("bearer ") else None


async def _reject(ws: WebSocket, code: int, reason: str) -> None:
    # Accept first: closing before accept becomes an HTTP 403 and the app code never arrives.
    await ws.accept()
    await ws.close(code=code, reason=reason)


@router.websocket("/v1/live")
async def live(ws: WebSocket, session_id: str = Query(default=""),
               rt: Runtime = Depends(get_runtime)) -> None:
    ticket = ws.query_params.get("ticket")
    identity: str | None = None
    if ticket:
        identity = signaling.consume_ticket(ticket, session_id)
    else:
        token = _bearer(ws)
        if token:
            try:
                identity = str((await rt.ws_user(token)).id)
            except HTTPException:
                identity = None
    if identity is None:
        await _reject(ws, WS_UNAUTHORIZED, "unauthorized")
        return
    entry = signaling.registry.get(session_id)
    if entry is None or entry.identity != identity:
        await _reject(ws, WS_NOT_FOUND, "unknown_session")
        return
    if entry.ws_attached:
        await _reject(ws, WS_CONFLICT, "already_attached")
        return
    entry.ws_attached = True
    try:
        await ws.accept()
    except BaseException:
        entry.ws_attached = False
        raise

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
