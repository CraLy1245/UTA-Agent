from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from uuid import uuid4

from fastapi import WebSocket, WebSocketDisconnect
from sqlalchemy import func, select

from services.agent.model_provider import (
    OpenAICompatibleProvider,
    ProviderConfig,
    ProviderConfigurationError,
)
from services.api.app.core.config import get_settings
from services.api.app.db.models import Message, ModelSetting, Turn
from services.api.app.db.session import SessionLocal


class CancellationRegistry:
    def __init__(self) -> None:
        self._events: dict[str, asyncio.Event] = {}
        self._lock = asyncio.Lock()

    async def register(self, turn_id: str) -> asyncio.Event:
        async with self._lock:
            if turn_id in self._events:
                raise RuntimeError("Turn is already running")
            event = asyncio.Event()
            self._events[turn_id] = event
            return event

    async def cancel(self, turn_id: str) -> bool:
        async with self._lock:
            event = self._events.get(turn_id)
            if event is None:
                return False
            event.set()
            return True

    async def remove(self, turn_id: str) -> None:
        async with self._lock:
            self._events.pop(turn_id, None)


cancellation_registry = CancellationRegistry()


def websocket_event(event: str, turn: Turn, data: dict[str, object]) -> dict[str, object]:
    return {
        "event": event,
        "conversation_id": turn.conversation_id,
        "turn_id": turn.id,
        "timestamp": datetime.now(UTC).isoformat(),
        "data": data,
    }


def _provider_for(setting: ModelSetting) -> OpenAICompatibleProvider:
    secret = get_settings().openai_api_key
    if secret is None or not secret.get_secret_value():
        raise ProviderConfigurationError(
            f"API key is not configured. Set {setting.api_key_env} and restart the backend."
        )
    if not setting.enabled:
        raise ProviderConfigurationError("The main model is disabled")
    return OpenAICompatibleProvider(
        ProviderConfig(
            base_url=setting.base_url,
            api_key=secret.get_secret_value(),
            model=setting.model,
            timeout_seconds=setting.timeout_seconds,
            max_output_tokens=setting.max_output_tokens,
            temperature=setting.temperature,
        )
    )


async def run_turn(websocket: WebSocket, turn_id: str) -> None:
    cancel_event = await cancellation_registry.register(turn_id)
    try:
        with SessionLocal() as db:
            turn = db.get(Turn, turn_id)
            if turn is None:
                await websocket.send_json({"event": "error", "data": {"message": "Turn not found"}})
                return
            if turn.status != "pending":
                await websocket.send_json(
                    websocket_event(
                        "error", turn, {"message": f"Turn cannot start from status {turn.status}"}
                    )
                )
                return
            setting = db.get(ModelSetting, "main")
            if setting is None:
                raise ProviderConfigurationError("Main model setting is missing")
            user_message = db.get(Message, turn.user_message_id)
            if user_message is None:
                raise RuntimeError("Turn user message is missing")
            history = list(
                db.scalars(
                    select(Message)
                    .where(
                        Message.conversation_id == turn.conversation_id,
                        Message.sequence <= user_message.sequence,
                    )
                    .order_by(Message.sequence)
                )
            )
            messages = [{"role": message.role, "content": message.content} for message in history]
            provider = _provider_for(setting)
            turn.status = "running"
            turn.started_at = datetime.now(UTC)
            db.commit()
            await websocket.send_json(websocket_event("turn.started", turn, {}))

            content_parts: list[str] = []
            field_shapes: set[str] = set()
            input_tokens: int | None = None
            output_tokens: int | None = None
            async for provider_event in provider.stream(messages):
                if cancel_event.is_set():
                    turn.status = "cancelled"
                    turn.completed_at = datetime.now(UTC)
                    db.commit()
                    await websocket.send_json(websocket_event("assistant.cancelled", turn, {}))
                    return
                if provider_event.delta:
                    content_parts.append(provider_event.delta)
                    await websocket.send_json(
                        websocket_event(
                            "assistant.delta", turn, {"content": provider_event.delta}
                        )
                    )
                if provider_event.field_shape:
                    field_shapes.add(provider_event.field_shape)
                if provider_event.input_tokens is not None:
                    input_tokens = provider_event.input_tokens
                if provider_event.output_tokens is not None:
                    output_tokens = provider_event.output_tokens

            if cancel_event.is_set():
                turn.status = "cancelled"
                turn.completed_at = datetime.now(UTC)
                db.commit()
                await websocket.send_json(websocket_event("assistant.cancelled", turn, {}))
                return
            content = "".join(content_parts).strip()
            if not content:
                shape_summary = " | ".join(sorted(field_shapes))[:900]
                detail = f" (event fields: {shape_summary})" if shape_summary else ""
                usage_detail = (
                    f" (usage: input={input_tokens}, output={output_tokens})"
                    if input_tokens is not None or output_tokens is not None
                    else ""
                )
                raise RuntimeError(
                    f"Provider completed without an assistant message{detail}{usage_detail}"
                )
            sequence = int(
                db.scalar(
                    select(func.max(Message.sequence)).where(
                        Message.conversation_id == turn.conversation_id
                    )
                )
                or 0
            ) + 1
            assistant_message = Message(
                id=str(uuid4()),
                conversation_id=turn.conversation_id,
                turn_id=turn.id,
                role="assistant",
                content=content,
                sequence=sequence,
            )
            turn.status = "completed"
            turn.completed_at = datetime.now(UTC)
            turn.input_tokens = input_tokens
            turn.output_tokens = output_tokens
            db.add(assistant_message)
            db.commit()
            if input_tokens is not None or output_tokens is not None:
                await websocket.send_json(
                    websocket_event(
                        "usage.updated",
                        turn,
                        {"input_tokens": input_tokens, "output_tokens": output_tokens},
                    )
                )
            await websocket.send_json(
                websocket_event(
                    "assistant.completed",
                    turn,
                    {
                        "message": {
                            "id": assistant_message.id,
                            "role": "assistant",
                            "content": content,
                            "sequence": sequence,
                        }
                    },
                )
            )
    except WebSocketDisconnect:
        with SessionLocal() as db:
            turn = db.get(Turn, turn_id)
            if turn is not None and turn.status == "running":
                turn.status = "cancelled"
                turn.completed_at = datetime.now(UTC)
                db.commit()
        raise
    except Exception as exc:
        with SessionLocal() as db:
            turn = db.get(Turn, turn_id)
            if turn is not None:
                turn.status = "failed"
                turn.error_message = str(exc)[:1000]
                turn.completed_at = datetime.now(UTC)
                db.commit()
                await websocket.send_json(
                    websocket_event("error", turn, {"message": turn.error_message})
                )
    finally:
        await cancellation_registry.remove(turn_id)
