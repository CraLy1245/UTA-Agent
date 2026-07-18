from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from fastapi import WebSocket, WebSocketDisconnect
from sqlalchemy import func, select

from services.agent.model_provider import (
    OpenAICompatibleProvider,
    ProviderConfig,
    ProviderConfigurationError,
)
from services.agent.tool_runtime import ToolResult, WorkspaceToolRuntime
from services.agent.usage_normalizer import UsageNormalizer
from services.api.app.core.config import get_settings
from services.api.app.db.models import Message, ModelSetting, ToolExecution, Turn
from services.api.app.db.session import SessionLocal
from services.survival.ledger import balance_context, balances, debit_completed_turn


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


@dataclass
class PendingToolCall:
    index: int
    id: str = ""
    name: str = ""
    argument_parts: list[str] = field(default_factory=list)

    @property
    def arguments_json(self) -> str:
        return "".join(self.argument_parts)

    def as_provider_message(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "type": "function",
            "function": {"name": self.name, "arguments": self.arguments_json},
        }


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


def _tool_runtime() -> WorkspaceToolRuntime:
    settings = get_settings()
    return WorkspaceToolRuntime(
        settings.workspace_path,
        max_read_bytes=settings.tool_read_max_bytes,
        max_list_entries=settings.tool_list_max_entries,
    )


def _tool_public_data(execution: ToolExecution) -> dict[str, object]:
    return {
        "id": execution.id,
        "provider_call_id": execution.provider_call_id,
        "call_sequence": execution.call_sequence,
        "tool_name": execution.tool_name,
        "arguments": execution.arguments,
        "status": execution.status,
        "result": execution.result,
        "error_message": execution.error_message,
        "started_at": execution.started_at.isoformat() if execution.started_at else None,
        "completed_at": (
            execution.completed_at.isoformat() if execution.completed_at else None
        ),
    }


def _parse_tool_arguments(raw: str) -> dict[str, Any]:
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError("tool arguments are not valid JSON") from exc
    if not isinstance(parsed, dict):
        raise ValueError("tool arguments must be a JSON object")
    return parsed


async def _execute_tool_call(
    *,
    websocket: WebSocket,
    turn: Turn,
    tool_runtime: WorkspaceToolRuntime,
    call: PendingToolCall,
    call_sequence: int,
) -> ToolResult:
    if not call.id or not call.name:
        raise RuntimeError("Provider returned a tool call without id or name")
    try:
        arguments = _parse_tool_arguments(call.arguments_json)
        parse_error: str | None = None
    except ValueError as exc:
        arguments = {}
        parse_error = str(exc)

    with SessionLocal() as db:
        execution = ToolExecution(
            id=str(uuid4()),
            conversation_id=turn.conversation_id,
            turn_id=turn.id,
            provider_call_id=call.id,
            call_sequence=call_sequence,
            tool_name=call.name,
            arguments_json=json.dumps(arguments, ensure_ascii=False),
            status="running",
            started_at=datetime.now(UTC),
        )
        db.add(execution)
        db.commit()
        db.refresh(execution)
        await websocket.send_json(
            websocket_event("tool.started", turn, {"tool": _tool_public_data(execution)})
        )

        if parse_error is not None:
            result = ToolResult(ok=False, data={"error": parse_error})
        else:
            settings = get_settings()
            try:
                result = await asyncio.wait_for(
                    asyncio.to_thread(tool_runtime.execute, call.name, arguments),
                    timeout=settings.tool_timeout_seconds,
                )
            except TimeoutError:
                result = ToolResult(ok=False, data={"error": "tool execution timed out"})

        execution.status = "completed" if result.ok else "failed"
        execution.result_json = result.model_content()
        execution.error_message = None if result.ok else str(result.data.get("error", "failed"))
        execution.completed_at = datetime.now(UTC)
        db.commit()
        db.refresh(execution)
        event_name = "tool.completed" if result.ok else "tool.failed"
        await websocket.send_json(
            websocket_event(event_name, turn, {"tool": _tool_public_data(execution)})
        )
        return result


async def _run_model_loop(
    *,
    websocket: WebSocket,
    turn: Turn,
    messages: list[dict[str, Any]],
    provider: Any,
    cancel_event: asyncio.Event,
    survival_context: str,
) -> tuple[str, list[dict[str, Any]]]:
    settings = get_settings()
    tools = _tool_runtime() if settings.tools_enabled else None
    tool_schemas = tools.schemas if tools is not None else []
    visible_content: list[str] = []
    field_shapes: set[str] = set()
    raw_usages: list[dict[str, Any]] = []
    call_sequence = 0

    messages.insert(
        0,
        {
            "role": "system",
            "content": (
                "You have three local workspace tools. Tool paths must always be relative to the "
                "configured workspace. Use tools when the user asks to inspect or modify workspace "
                "files, use tool results as evidence, and never claim a file operation succeeded "
                "unless the tool result says ok=true."
            ),
        },
    )
    messages.insert(1, {"role": "system", "content": survival_context})

    for _ in range(settings.max_model_loops):
        if cancel_event.is_set():
            raise asyncio.CancelledError
        pending_calls: dict[int, PendingToolCall] = {}
        iteration_content: list[str] = []
        iteration_input: int | None = None
        iteration_output: int | None = None
        iteration_raw_usage: dict[str, Any] | None = None
        async for provider_event in provider.stream(messages, tools=tool_schemas):
            if cancel_event.is_set():
                raise asyncio.CancelledError
            if provider_event.delta:
                iteration_content.append(provider_event.delta)
                visible_content.append(provider_event.delta)
                await websocket.send_json(
                    websocket_event(
                        "assistant.delta", turn, {"content": provider_event.delta}
                    )
                )
            for delta in provider_event.tool_calls:
                call = pending_calls.setdefault(delta.index, PendingToolCall(index=delta.index))
                if delta.id:
                    call.id = delta.id
                if delta.name:
                    call.name += delta.name
                if delta.arguments:
                    call.argument_parts.append(delta.arguments)
            if provider_event.field_shape:
                field_shapes.add(provider_event.field_shape)
            if provider_event.input_tokens is not None:
                iteration_input = provider_event.input_tokens
            if provider_event.output_tokens is not None:
                iteration_output = provider_event.output_tokens
            if provider_event.raw_usage is not None:
                iteration_raw_usage = provider_event.raw_usage

        if iteration_raw_usage is not None:
            raw_usages.append(iteration_raw_usage)
        elif iteration_input is not None or iteration_output is not None:
            fallback_usage: dict[str, Any] = {}
            if iteration_input is not None:
                fallback_usage["input_tokens"] = iteration_input
            if iteration_output is not None:
                fallback_usage["output_tokens"] = iteration_output
            raw_usages.append(fallback_usage)

        if pending_calls:
            ordered_calls = [pending_calls[index] for index in sorted(pending_calls)]
            messages.append(
                {
                    "role": "assistant",
                    "content": "".join(iteration_content) or None,
                    "tool_calls": [call.as_provider_message() for call in ordered_calls],
                }
            )
            if tools is None:
                raise RuntimeError("Provider requested a tool while local tools are disabled")
            for call in ordered_calls:
                call_sequence += 1
                result = await _execute_tool_call(
                    websocket=websocket,
                    turn=turn,
                    tool_runtime=tools,
                    call=call,
                    call_sequence=call_sequence,
                )
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": call.id,
                        "content": result.model_content(),
                    }
                )
            continue

        content = "".join(visible_content).strip()
        if not content:
            shape_summary = " | ".join(sorted(field_shapes))[:900]
            detail = f" (event fields: {shape_summary})" if shape_summary else ""
            normalized = UsageNormalizer.normalize(raw_usages)
            usage_detail = f" (usage: {normalized.as_dict()})" if raw_usages else ""
            raise RuntimeError(
                f"Provider completed without an assistant message{detail}{usage_detail}"
            )
        return content, raw_usages
    raise RuntimeError("Model exceeded the configured tool loop limit")


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
            messages: list[dict[str, Any]] = [
                {"role": message.role, "content": message.content} for message in history
            ]
            provider = _provider_for(setting)
            model_id = setting.model
            survival_context = balance_context(db)
            turn.status = "running"
            turn.started_at = datetime.now(UTC)
            db.commit()
            await websocket.send_json(websocket_event("turn.started", turn, {}))

        try:
            async with asyncio.timeout(get_settings().turn_timeout_seconds):
                content, raw_usages = await _run_model_loop(
                    websocket=websocket,
                    turn=turn,
                    messages=messages,
                    provider=provider,
                    cancel_event=cancel_event,
                    survival_context=survival_context,
                )
        except asyncio.CancelledError:
            with SessionLocal() as db:
                current_turn = db.get(Turn, turn_id)
                if current_turn is not None:
                    current_turn.status = "cancelled"
                    current_turn.completed_at = datetime.now(UTC)
                    db.commit()
                    await websocket.send_json(
                        websocket_event("assistant.cancelled", current_turn, {})
                    )
            return
        if cancel_event.is_set():
            with SessionLocal() as db:
                current_turn = db.get(Turn, turn_id)
                if current_turn is not None:
                    current_turn.status = "cancelled"
                    current_turn.completed_at = datetime.now(UTC)
                    db.commit()
                    await websocket.send_json(
                        websocket_event("assistant.cancelled", current_turn, {})
                    )
            return

        with SessionLocal() as db:
            db.connection().exec_driver_sql("BEGIN IMMEDIATE")
            current_turn = db.get(Turn, turn_id)
            if current_turn is None:
                raise RuntimeError("Turn disappeared before finalization")
            sequence = int(
                db.scalar(
                    select(func.max(Message.sequence)).where(
                        Message.conversation_id == current_turn.conversation_id
                    )
                )
                or 0
            ) + 1
            assistant_message = Message(
                id=str(uuid4()),
                conversation_id=current_turn.conversation_id,
                turn_id=current_turn.id,
                role="assistant",
                content=content,
                sequence=sequence,
            )
            completed_at = datetime.now(UTC)
            normalized_usage = UsageNormalizer.normalize(raw_usages)
            current_turn.status = "completed"
            current_turn.completed_at = completed_at
            current_turn.input_tokens = normalized_usage.input_tokens
            current_turn.output_tokens = normalized_usage.output_tokens
            db.add(assistant_message)
            tool_executions = list(
                db.scalars(
                    select(ToolExecution)
                    .where(ToolExecution.turn_id == current_turn.id)
                    .order_by(ToolExecution.call_sequence)
                )
            )
            tool_names = [execution.tool_name for execution in tool_executions]
            tool_outcomes = [
                {"name": execution.tool_name, "status": execution.status}
                for execution in tool_executions
            ]
            started_at = current_turn.started_at or current_turn.created_at
            completed_for_latency = (
                completed_at.replace(tzinfo=None)
                if started_at.tzinfo is None
                else completed_at
            )
            latency_ms = int((completed_for_latency - started_at).total_seconds() * 1000)
            _, debit_transactions = debit_completed_turn(
                db,
                turn=current_turn,
                model_id=model_id,
                normalized_usage=normalized_usage,
                raw_usages=raw_usages,
                tool_names=tool_names,
                tool_outcomes=tool_outcomes,
                latency_ms=latency_ms,
            )
            db.flush()
            account_snapshot = balances(db)
            db.commit()
            await websocket.send_json(
                websocket_event(
                    "usage.updated",
                    current_turn,
                    {
                        **normalized_usage.as_dict(),
                        "provider_raw_usage": raw_usages,
                    },
                )
            )
            await websocket.send_json(
                websocket_event(
                    "balance.updated",
                    current_turn,
                    {
                        "accounts": {
                            key: {
                                "balance_units": account.balance_units,
                                "initial_balance_units": account.initial_balance_units,
                            }
                            for key, account in account_snapshot.items()
                        },
                        "turn_change_units": {
                            transaction.account_type: transaction.amount_units
                            for transaction in debit_transactions
                        },
                    },
                )
            )
            await websocket.send_json(
                websocket_event(
                    "assistant.completed",
                    current_turn,
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
