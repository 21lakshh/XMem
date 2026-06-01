from __future__ import annotations

import json

import pytest

pytest.importorskip("fastapi")

from src.api.routes import billing
from src.billing.types import VerifyPaymentRequest


@pytest.mark.asyncio
async def test_subscription_verify_checks_signature_before_checkout_lookup(monkeypatch):
    class Store:
        def get_checkout(self, checkout_id):
            raise AssertionError("checkout lookup should not run before signature verification")

    class Service:
        store = Store()

    monkeypatch.setattr(billing, "get_default_billing_service", lambda: Service())
    monkeypatch.setattr(billing, "verify_subscription_signature", lambda *args: False)

    with pytest.raises(billing.HTTPException) as exc:
        await billing.verify_razorpay_payment(
            VerifyPaymentRequest(
                package_id="pro",
                razorpay_payment_id="pay_1",
                razorpay_signature="bad",
                razorpay_subscription_id="sub_1",
            ),
            current_user={"id": "user-1"},
        )

    assert exc.value.status_code == 400
    assert exc.value.detail == "Invalid Razorpay signature"


@pytest.mark.asyncio
async def test_webhook_without_payment_id_does_not_grant_with_event_id(monkeypatch):
    events = []

    class Store:
        def has_payment_event(self, event_id):
            return False

        def mark_payment_event(self, event_id, payload):
            events.append((event_id, payload["event"]))
            return True

    class Service:
        store = Store()

        def grant_pro_subscription(self, **kwargs):
            raise AssertionError("webhook without payment id must not grant credits")

    class Request:
        headers = {"x-razorpay-signature": "valid", "x-razorpay-event-id": "evt_1"}

        async def body(self):
            return json.dumps(
                {
                    "id": "evt_1",
                    "event": "subscription.charged",
                    "payload": {
                        "subscription": {
                            "entity": {
                                "id": "sub_1",
                                "notes": {"user_id": "user-1", "package_id": "pro"},
                            }
                        }
                    },
                }
            ).encode("utf-8")

    monkeypatch.setattr(billing, "get_default_billing_service", lambda: Service())
    monkeypatch.setattr(billing, "verify_webhook_signature", lambda body, signature: True)

    response = await billing.razorpay_webhook(Request())

    assert response == {"status": "ok"}
    assert events == [("evt_1", "subscription.charged")]
