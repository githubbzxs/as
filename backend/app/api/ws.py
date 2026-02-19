from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect

from app.core.auth import AuthError, decode_access_token
from app.core.settings import Settings, get_settings

router = APIRouter(tags=["ws"])


@router.websocket("/ws/stream")
async def stream_ws(websocket: WebSocket, settings: Settings = Depends(get_settings)):
    container = websocket.app.state.container
    token = websocket.query_params.get("token", "")
    try:
        decode_access_token(settings, token)
    except AuthError:
        await websocket.close(code=4401)
        return

    await websocket.accept()
    queue = container.event_bus.subscribe()
    try:
        await websocket.send_json({"type": "hello", "payload": {"message": "connected"}})
        while True:
            try:
                event = await asyncio.wait_for(queue.get(), timeout=30.0)
                await websocket.send_json(event)
            except asyncio.TimeoutError:
                await websocket.send_json({"type": "ping", "payload": {}})
    except WebSocketDisconnect:
        pass
    finally:
        container.event_bus.unsubscribe(queue)
