from __future__ import annotations

import os
import re
from collections.abc import Mapping, Sequence
from typing import Any

REDACTED = "[REDACTED]"

_SECRET_PATTERNS = (
    re.compile(r"(?i)(authorization\s*[:=]\s*bearer\s+)[^\s,;\"']+"),
    re.compile(
        r"(?i)((?:api[_-]?key|access[_-]?token|secret)\s*[\"']?\s*[:=]\s*[\"']?)"
        r"([^\s,;\"'}]+)"
    ),
    re.compile(r"\bsk-[A-Za-z0-9_-]{8,}\b"),
)


def redact_text(value: str, *, secrets: Sequence[str] = ()) -> str:
    """Remove credentials from text without retaining a copy of those credentials."""
    result = value
    environment_secrets = (
        os.getenv("OPENAI_API_KEY", ""),
        os.getenv("SURVIVAL_AGENT_OPENAI_API_KEY", ""),
    )
    for secret in (*secrets, *environment_secrets):
        if secret:
            result = result.replace(secret, REDACTED)
    result = _SECRET_PATTERNS[0].sub(rf"\1{REDACTED}", result)
    result = _SECRET_PATTERNS[1].sub(rf"\1{REDACTED}", result)
    result = _SECRET_PATTERNS[2].sub(REDACTED, result)
    return result


def redact_value(value: Any, *, secrets: Sequence[str] = ()) -> Any:
    if isinstance(value, str):
        return redact_text(value, secrets=secrets)
    if isinstance(value, Mapping):
        sanitized: dict[str, Any] = {}
        for key, item in value.items():
            key_text = str(key)
            if re.search(r"(?i)(authorization|api[_-]?key|access[_-]?token|secret)", key_text):
                sanitized[key_text] = REDACTED
            else:
                sanitized[key_text] = redact_value(item, secrets=secrets)
        return sanitized
    if isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray)):
        return [redact_value(item, secrets=secrets) for item in value]
    return value
