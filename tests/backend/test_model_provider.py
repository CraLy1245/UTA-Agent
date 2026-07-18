import json

import httpx
import pytest

from services.agent.model_provider import OpenAICompatibleProvider, ProviderConfig


@pytest.mark.asyncio
async def test_openai_compatible_provider_streams_content_and_usage() -> None:
    seen_request: httpx.Request | None = None

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal seen_request
        seen_request = request
        body = "\n".join(
            [
                'data: {"choices":[{"delta":{"content":"你"}}]}',
                'data: {"choices":[{"delta":{"content":"好"}}]}',
                'data: {"choices":[],"usage":{"prompt_tokens":7,"completion_tokens":2}}',
                "data: [DONE]",
                "",
            ]
        )
        return httpx.Response(200, text=body, headers={"content-type": "text/event-stream"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = OpenAICompatibleProvider(
            ProviderConfig(
                base_url="https://provider.example/v1",
                api_key="test-secret",
                model="test-model",
                timeout_seconds=30,
                max_output_tokens=100,
            ),
            client=client,
        )
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "read_file",
                    "description": "Read a file",
                    "parameters": {"type": "object"},
                },
            }
        ]
        events = [
            event
            async for event in provider.stream([{"role": "user", "content": "hi"}], tools=tools)
        ]

    assert "".join(event.delta or "" for event in events) == "你好"
    assert events[-1].input_tokens == 7
    assert events[-1].output_tokens == 2
    assert seen_request is not None
    assert seen_request.headers["authorization"] == "Bearer test-secret"
    request_payload = json.loads(seen_request.content)
    assert request_payload["max_tokens"] == 100
    assert request_payload["tools"] == tools
    assert request_payload["tool_choice"] == "auto"


@pytest.mark.asyncio
async def test_openai_compatible_provider_discovers_models_without_exposing_key() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["authorization"] == "Bearer test-secret"
        return httpx.Response(200, json={"data": [{"id": "model-b"}, {"id": "model-a"}]})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = OpenAICompatibleProvider(
            ProviderConfig(
                base_url="https://provider.example/v1",
                api_key="test-secret",
                model="unused",
                timeout_seconds=30,
                max_output_tokens=100,
            ),
            client=client,
        )
        models = await provider.list_models()

    assert models == ["model-a", "model-b"]


def test_parse_non_stream_chat_completion_from_compatible_gateway() -> None:
    event = OpenAICompatibleProvider._parse_line(
        'data: {"choices":[{"message":{"role":"assistant","content":"done"}}]}'
    )

    assert event is not None
    assert event.delta == "done"


def test_parse_content_parts() -> None:
    event = OpenAICompatibleProvider._parse_line(
        'data: {"choices":[{"delta":{"content":[{"type":"text","text":"hello"},'
        '{"type":"text","text":" world"}]}}]}'
    )

    assert event is not None
    assert event.delta == "hello world"


def test_event_field_shape_contains_names_but_not_values() -> None:
    event = OpenAICompatibleProvider._parse_line(
        'data: {"id":"secret-value","choices":[{"delta":{"reasoning":"private"}}]}'
    )

    assert event is not None
    assert event.field_shape == "root=choices,id;choice=delta;delta=reasoning"
    assert "secret-value" not in event.field_shape
    assert "private" not in event.field_shape


def test_parse_streaming_tool_call_deltas() -> None:
    first = OpenAICompatibleProvider._parse_line(
        'data: {"choices":[{"delta":{"tool_calls":[{"index":0,"id":"call-1",'
        '"type":"function","function":{"name":"read_file","arguments":""}}]}}]}'
    )
    second = OpenAICompatibleProvider._parse_line(
        'data: {"choices":[{"delta":{"tool_calls":[{"index":0,'
        '"function":{"arguments":"{\\"path\\":\\"notes.txt\\"}"}}]}}]}'
    )

    assert first is not None and second is not None
    assert first.tool_calls[0].id == "call-1"
    assert first.tool_calls[0].name == "read_file"
    assert second.tool_calls[0].arguments == '{"path":"notes.txt"}'
