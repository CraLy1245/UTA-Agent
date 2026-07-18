from services.agent.usage_normalizer import UsageNormalizer


def test_usage_normalizer_uses_totals_without_double_counting_details() -> None:
    normalized = UsageNormalizer.normalize(
        [
            {
                "prompt_tokens": 1_000,
                "completion_tokens": 300,
                "prompt_tokens_details": {"cached_tokens": 800},
                "completion_tokens_details": {"reasoning_tokens": 200},
                "cache_read_tokens": 800,
                "reasoning_tokens": 200,
            },
            {"input_tokens": 20, "output_tokens": 5},
        ]
    )

    assert normalized.input_tokens == 1_020
    assert normalized.output_tokens == 305
    assert normalized.usage_complete is True
    assert normalized.provider_call_count == 2


def test_usage_normalizer_handles_missing_provider_fields_without_inventing_usage() -> None:
    normalized = UsageNormalizer.normalize([{"prompt_tokens": 7}])

    assert normalized.input_tokens == 7
    assert normalized.output_tokens == 0
    assert normalized.usage_complete is False

    absent = UsageNormalizer.normalize([])
    assert absent.input_tokens == 0
    assert absent.output_tokens == 0
    assert absent.usage_complete is False
