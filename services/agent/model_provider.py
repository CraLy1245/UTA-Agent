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
class ProviderStreamEvent:
    delta: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    field_shape: str | None = None


class OpenAICompatibleProvider:
    def __init__(self, config: ProviderConfig, client: httpx.AsyncClient | None = None) -> None:
        self.config = config
        self._client = client

    def _payload(self, messages: list[dict[str, str]], token_field: str) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": self.config.model,
            "messages": messages,
            "stream": True,
            "stream_options": {"include_usage": True},
            token_field: self.config.max_output_tokens,
        }
        if self.config.temperature is not None:
            payload["temperature"] = self.config.temperature
        return payload

    async def stream(
        self, messages: list[dict[str, str]]
    ) -> AsyncIterator[ProviderStreamEvent]:
        owns_client = self._client is None
        client = self._client or httpx.AsyncClient(timeout=self.config.timeout_seconds)
        try:
            response = await self._send(client, messages, "max_tokens")
            if response.status_code == 400:
                error_body = (await response.aread()).decode(errors="replace")[:1000]
                await response.aclose()
                if "max_tokens" in error_body:
                    response = await self._send(client, messages, "max_completion_tokens")
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
            raise ProviderError(
                f"Provider model discovery failed: {type(exc).__name__}"
            ) from exc
        finally:
            if owns_client:
                await client.aclose()

    async def _send(
        self, client: httpx.AsyncClient, messages: list[dict[str, str]], token_field: str
    ) -> httpx.Response:
        request = client.build_request(
            "POST",
            f"{self.config.base_url.rstrip('/')}/chat/completions",
            headers={
                "Authorization": f"Bearer {self.config.api_key}",
                "Accept": "text/event-stream",
                "Content-Type": "application/json",
            },
            json=self._payload(messages, token_field),
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
        if choices:
            choice = choices[0]
            content = OpenAICompatibleProvider._content_text(
                (choice.get("delta") or {}).get("content")
            )
            if content is None:
                # Some compatible gateways accept stream=true but return a
                # regular Chat Completion object in the response body.
                content = OpenAICompatibleProvider._content_text(
                    (choice.get("message") or {}).get("content")
                )
            if content is None:
                content = OpenAICompatibleProvider._content_text(choice.get("text"))
        if content is None:
            content = OpenAICompatibleProvider._content_text(payload.get("output_text"))
        if content is None and payload.get("type") == "response.output_text.delta":
            content = OpenAICompatibleProvider._content_text(payload.get("delta"))
        usage = payload.get("usage") or {}
        return ProviderStreamEvent(
            delta=content,
            input_tokens=usage.get("prompt_tokens") or usage.get("input_tokens"),
            output_tokens=usage.get("completion_tokens") or usage.get("output_tokens"),
            field_shape=OpenAICompatibleProvider._field_shape(payload),
        )

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
