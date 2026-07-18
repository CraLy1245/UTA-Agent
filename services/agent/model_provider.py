from __future__ import annotations

import json
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any

import httpx


class ProviderError(RuntimeError):
    """A provider failure safe to expose without credentials or headers."""


class ProviderConfigurationError(ProviderError):
    pass


@dataclass(frozen=True)
class ProviderConfig:
    base_url: str
    api_key: str
    model: str
    timeout_seconds: int
    max_output_tokens: int
    temperature: float | None = None


@dataclass(frozen=True)
class ProviderToolCallDelta:
    index: int
    id: str | None = None
    name: str | None = None
    arguments: str = ""


@dataclass(frozen=True)
class ProviderStreamEvent:
    delta: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    field_shape: str | None = None
    raw_usage: dict[str, Any] | None = None
    tool_calls: tuple[ProviderToolCallDelta, ...] = ()


class OpenAICompatibleProvider:
    def __init__(self, config: ProviderConfig, client: httpx.AsyncClient | None = None) -> None:
        self.config = config
        self._client = client

    def _payload(
        self,
        messages: list[dict[str, Any]],
        token_field: str,
        tools: list[dict[str, Any]] | None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": self.config.model,
            "messages": messages,
            "stream": True,
            "stream_options": {"include_usage": True},
            token_field: self.config.max_output_tokens,
        }
        if self.config.temperature is not None:
            payload["temperature"] = self.config.temperature
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"
        return payload

    async def stream(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
    ) -> AsyncIterator[ProviderStreamEvent]:
        owns_client = self._client is None
        client = self._client or httpx.AsyncClient(timeout=self.config.timeout_seconds)
        try:
            response = await self._send(client, messages, "max_tokens", tools)
            if response.status_code == 400:
                error_body = (await response.aread()).decode(errors="replace")[:1000]
                await response.aclose()
                if "max_tokens" in error_body:
                    response = await self._send(client, messages, "max_completion_tokens", tools)
                else:
                    raise ProviderError(f"Provider rejected the request (HTTP 400): {error_body}")
            if response.is_error:
                error_body = (await response.aread()).decode(errors="replace")[:1000]
                status = response.status_code
                await response.aclose()
                raise ProviderError(f"Provider request failed (HTTP {status}): {error_body}")
            try:
                async for line in response.aiter_lines():
                    event = self._parse_line(line)
                    if event is not None:
                        yield event
            finally:
                await response.aclose()
        except httpx.TimeoutException as exc:
            raise ProviderError("Provider request timed out") from exc
        except httpx.HTTPError as exc:
            raise ProviderError(f"Provider connection failed: {type(exc).__name__}") from exc
        finally:
            if owns_client:
                await client.aclose()

    async def list_models(self) -> list[str]:
        owns_client = self._client is None
        client = self._client or httpx.AsyncClient(timeout=self.config.timeout_seconds)
        try:
            response = await client.get(
                f"{self.config.base_url.rstrip('/')}/models",
                headers={"Authorization": f"Bearer {self.config.api_key}"},
            )
            if response.is_error:
                body = response.text[:1000]
                raise ProviderError(
                    f"Provider model discovery failed (HTTP {response.status_code}): {body}"
                )
            payload = response.json()
            models = [
                item["id"]
                for item in payload.get("data", [])
                if isinstance(item, dict) and isinstance(item.get("id"), str)
            ]
            return sorted(set(models))
        except (httpx.HTTPError, json.JSONDecodeError) as exc:
            raise ProviderError(f"Provider model discovery failed: {type(exc).__name__}") from exc
        finally:
            if owns_client:
                await client.aclose()

    async def _send(
        self,
        client: httpx.AsyncClient,
        messages: list[dict[str, Any]],
        token_field: str,
        tools: list[dict[str, Any]] | None,
    ) -> httpx.Response:
        request = client.build_request(
            "POST",
            f"{self.config.base_url.rstrip('/')}/chat/completions",
            headers={
                "Authorization": f"Bearer {self.config.api_key}",
                "Accept": "text/event-stream",
                "Content-Type": "application/json",
            },
            json=self._payload(messages, token_field, tools),
        )
        return await client.send(request, stream=True)

    @staticmethod
    def _parse_line(line: str) -> ProviderStreamEvent | None:
        line = line.strip()
        if not line or line.startswith(":") or line in {"data: [DONE]", "[DONE]"}:
            return None
        raw = line.removeprefix("data:").strip()
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ProviderError("Provider returned an invalid streaming event") from exc
        choices = payload.get("choices") or []
        content = None
        tool_calls: tuple[ProviderToolCallDelta, ...] = ()
        if choices:
            choice = choices[0]
            message_part = choice.get("delta") or choice.get("message") or {}
            content = OpenAICompatibleProvider._content_text(message_part.get("content"))
            if content is None:
                # Some compatible gateways accept stream=true but return a
                # regular Chat Completion object in the response body.
                content = OpenAICompatibleProvider._content_text(
                    (choice.get("message") or {}).get("content")
                )
            if content is None:
                content = OpenAICompatibleProvider._content_text(choice.get("text"))
            tool_calls = OpenAICompatibleProvider._tool_call_deltas(message_part.get("tool_calls"))
        if content is None:
            content = OpenAICompatibleProvider._content_text(payload.get("output_text"))
        if content is None and payload.get("type") == "response.output_text.delta":
            content = OpenAICompatibleProvider._content_text(payload.get("delta"))
        raw_usage = payload.get("usage")
        usage = raw_usage if isinstance(raw_usage, dict) else {}
        return ProviderStreamEvent(
            delta=content,
            input_tokens=OpenAICompatibleProvider._usage_value(
                usage, "prompt_tokens", "input_tokens"
            ),
            output_tokens=OpenAICompatibleProvider._usage_value(
                usage, "completion_tokens", "output_tokens"
            ),
            field_shape=OpenAICompatibleProvider._field_shape(payload),
            raw_usage=usage or None,
            tool_calls=tool_calls,
        )

    @staticmethod
    def _usage_value(usage: dict[str, Any], *fields: str) -> int | None:
        for field in fields:
            value = usage.get(field)
            if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
                return value
        return None

    @staticmethod
    def _tool_call_deltas(value: object) -> tuple[ProviderToolCallDelta, ...]:
        if not isinstance(value, list):
            return ()
        deltas: list[ProviderToolCallDelta] = []
        for fallback_index, item in enumerate(value):
            if not isinstance(item, dict):
                continue
            function = item.get("function")
            if not isinstance(function, dict):
                function = {}
            raw_index = item.get("index", fallback_index)
            index = raw_index if isinstance(raw_index, int) else fallback_index
            call_id = item.get("id")
            name = function.get("name")
            arguments = function.get("arguments")
            deltas.append(
                ProviderToolCallDelta(
                    index=index,
                    id=call_id if isinstance(call_id, str) else None,
                    name=name if isinstance(name, str) else None,
                    arguments=arguments if isinstance(arguments, str) else "",
                )
            )
        return tuple(deltas)

    @staticmethod
    def _field_shape(payload: dict[str, Any]) -> str:
        sections = [f"root={','.join(sorted(payload))}"]
        choices = payload.get("choices")
        if isinstance(choices, list) and choices and isinstance(choices[0], dict):
            choice = choices[0]
            sections.append(f"choice={','.join(sorted(choice))}")
            for name in ("delta", "message"):
                value = choice.get(name)
                if isinstance(value, dict):
                    sections.append(f"{name}={','.join(sorted(value))}")
        return ";".join(sections)[:500]

    @staticmethod
    def _content_text(value: object) -> str | None:
        if isinstance(value, str):
            return value
        if not isinstance(value, list):
            return None
        parts: list[str] = []
        for part in value:
            if isinstance(part, str):
                parts.append(part)
            elif isinstance(part, dict):
                text = part.get("text")
                if isinstance(text, str):
                    parts.append(text)
        return "".join(parts) if parts else None
