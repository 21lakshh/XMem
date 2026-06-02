from src.utils import billing


def test_pro_plan_has_india_and_global_prices() -> None:
    assert billing.plan_price("pro", "IN") == {
        "price_paise": 9_900,
        "currency": "INR",
    }
    assert billing.plan_price("pro", "GLOBAL") == {
        "price_paise": 300,
        "currency": "USD",
    }
    assert billing.PLANS["pro"]["monthly_credits"] == 5_000


def test_billing_region_defaults_to_india_and_unknowns_are_global() -> None:
    assert billing.normalize_billing_region(None) == billing.BILLING_REGION_IN
    assert billing.normalize_billing_region("india") == billing.BILLING_REGION_IN
    assert billing.normalize_billing_region("outside-india") == billing.BILLING_REGION_GLOBAL


def test_plan_price_options_are_serializable() -> None:
    assert billing.plan_price_options("pro") == {
        "IN": {"price_paise": 9_900, "currency": "INR"},
        "GLOBAL": {"price_paise": 300, "currency": "USD"},
    }
