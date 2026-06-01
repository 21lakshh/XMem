from __future__ import annotations

import pytest

fastapi = pytest.importorskip("fastapi")
testclient = pytest.importorskip("fastapi.testclient")

from src.api.routes import billing


def test_subscription_verify_checks_signature_before_checkout_lookup(monkeypatch):
    class Store:
        def get_checkout(self, checkout_id):
            raise AssertionError("checkout lookup should not run before signature verification")

    class Service:
        store = Store()

    async def fake_auth():
        return {"id": "user-1"}

    monkeypatch.setattr(billing, "get_default_billing_service", lambda: Service())
    monkeypatch.setattr(billing, "verify_subscription_signature", lambda *args: False)

    app = fastapi.FastAPI()
    app.dependency_overrides[billing.require_auth] = fake_auth
    app.include_router(billing.router)

    response = testclient.TestClient(app).post(
        "/api/billing/razorpay/verify",
        json={
            "package_id": "pro",
            "razorpay_payment_id": "pay_1",
            "razorpay_signature": "bad",
            "razorpay_subscription_id": "sub_1",
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid Razorpay signature"
