from __future__ import annotations

from types import SimpleNamespace

from src.billing.pricing import CreditConverter, UsageCostCalculator, UsageNormalizer


def test_openai_cached_and_reasoning_tokens_are_priced_without_double_counting_output():
    response = SimpleNamespace(
        usage_metadata={
            "input_tokens": 2000,
            "output_tokens": 500,
            "total_tokens": 2500,
            "input_token_details": {"cache_read": 1200},
            "output_token_details": {"reasoning": 200},
        },
        response_metadata={},
    )
    usage = UsageNormalizer().normalize(
        provider="openai",
        model="gpt-4.1-mini",
        agent="classifier",
        response=response,
    )
    cost = UsageCostCalculator(
        converter=CreditConverter(
            usd_to_inr_rate=85.0, credit_value_paise=2.0, markup_multiplier=2.0
        )
    ).calculate(usage)

    assert usage.input_tokens == 2000
    assert usage.cached_input_tokens == 1200
    assert usage.thinking_tokens == 200
    assert cost is not None
    # 800 uncached input at $0.40/MTok + 1200 cached at $0.10/MTok + 500 output at $1.60/MTok.
    assert round(cost.total_cost_usd, 8) == 0.00124
    assert cost.charged_credits == 11


def test_gemini_thinking_tokens_are_added_to_output_cost():
    response = SimpleNamespace(
        usage_metadata={},
        response_metadata={
            "usage_metadata": {
                "prompt_token_count": 1000,
                "candidates_token_count": 200,
                "thoughts_token_count": 300,
                "total_token_count": 1500,
            }
        },
    )
    usage = UsageNormalizer().normalize(
        provider="gemini",
        model="gemini-2.5-flash",
        response=response,
    )
    cost = UsageCostCalculator().calculate(usage)

    assert usage.thinking_tokens == 300
    assert cost is not None
    # 1000 input at $0.30/MTok + 500 output/thinking at $2.50/MTok.
    assert round(cost.total_cost_usd, 8) == 0.00155


def test_claude_cache_creation_and_cache_read_tokens_use_cache_rates():
    response = SimpleNamespace(
        usage_metadata={
            "input_tokens": 1000,
            "cache_creation_input_tokens": 500,
            "cache_read_input_tokens": 2000,
            "output_tokens": 400,
        },
        response_metadata={},
    )
    usage = UsageNormalizer().normalize(
        provider="claude",
        model="claude-3-5-sonnet",
        response=response,
    )
    cost = UsageCostCalculator().calculate(usage)

    assert cost is not None
    # 1000 input at $3 + 500 cache write at $3.75 + 2000 cache read at $0.30 + 400 output at $15, all per MTok.
    assert round(cost.total_cost_usd, 8) == 0.011475


def test_openrouter_model_prefixes_resolve_to_underlying_provider_pricing():
    response = SimpleNamespace(
        usage_metadata={
            "input_tokens": 1000,
            "output_tokens": 100,
            "total_tokens": 1100,
        },
        response_metadata={},
    )

    usage = UsageNormalizer().normalize(
        provider="openai",
        model="anthropic/claude-3.5-sonnet",
        response=response,
    )
    cost = UsageCostCalculator().calculate(usage)

    assert usage.provider == "claude"
    assert cost is not None
    assert cost.provider == "claude"
    # 1000 input at $3/MTok + 100 output at $15/MTok.
    assert round(cost.total_cost_usd, 8) == 0.0045
