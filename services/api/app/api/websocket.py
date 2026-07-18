from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from services.agent.runtime import cancellation_registry, run_turn

router = APIRouter(tags=["streaming"])


@router.websocket("/ws/turns/{turn_id}")
async def stream_turn(websocket: WebSocket, turn_id: str) -> None:
    await websocket.accept()
    try:
        await run_turn(websocket, turn_id)
    except WebSocketDisconnect:
        await cancellation_registry.cancel(turn_id)
