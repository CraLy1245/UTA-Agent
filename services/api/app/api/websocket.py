from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from services.agent.runtime import cancellation_registry, run_turn
from services.memory.cognitive import cognitive_event_hub

router = APIRouter(tags=["streaming"])


@router.websocket("/ws/turns/{turn_id}")
async def stream_turn(websocket: WebSocket, turn_id: str) -> None:
    await websocket.accept()
    try:
        await run_turn(websocket, turn_id)
    except WebSocketDisconnect:
        await cancellation_registry.cancel(turn_id)


@router.websocket("/ws/cognitive-jobs")
async def stream_cognitive_jobs(websocket: WebSocket) -> None:
    await websocket.accept()
    queue = cognitive_event_hub.subscribe()
    try:
        while True:
            await websocket.send_json(await queue.get())
    except WebSocketDisconnect:
        pass
    finally:
        cognitive_event_hub.unsubscribe(queue)
