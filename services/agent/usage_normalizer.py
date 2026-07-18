from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class NormalizedUsage:
    input_tokens: int
    output_tokens: int
    usage_complete: bool
    provider_call_count: int

    def as_dict(self) -> dict[str, int | bool]:
        return asdict(self)


class UsageNormalizer:
    """Normalize OpenAI-compatible usage without double-counting detail fields."""

    INPUT_FIELDS = ("prompt_tokens", "input_tokens")
    OUTPUT_FIELDS = ("completion_tokens", "output_tokens")

    @classmethod
    def normalize(cls, raw_usages: list[dict[str, Any]]) -> NormalizedUsage:
        input_total = 0
        output_total = 0
        complete = bool(raw_usages)
        for usage in raw_usages:
            input_value = cls._first_non_negative_int(usage, cls.INPUT_FIELDS)
            output_value = cls._first_non_negative_int(usage, cls.OUTPUT_FIELDS)
            if input_value is None or output_value is None:
                complete = False
            input_total += input_value or 0
            output_total += output_value or 0
        return NormalizedUsage(
            input_tokens=input_total,
            output_tokens=output_total,
            usage_complete=complete,
            provider_call_count=len(raw_usages),
        )

    @staticmethod
    def _first_non_negative_int(
        usage: dict[str, Any], fields: tuple[str, ...]
    ) -> int | None:
        for field in fields:
            value = usage.get(field)
            if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
                return value
        return None
