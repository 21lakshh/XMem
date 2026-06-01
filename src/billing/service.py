from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any, Mapping, Optional

from src.billing.metering import estimate_required_credits as _estimate_required_credits
from src.billing.store import BillingStore, get_default_billing_store, utc_now
from src.billing.types import BillingSummary, CreditEstimate, CreditLotPublic, PlanPublic, ReservationResult, TopUpPackPublic
from src.utils import billing as billing_config

logger = logging.getLogger("xmem.billing.service")


def _user_id(user: Mapping[str, Any]) -> str:
    user_id = user.get("id") or user.get("_id") or user.get("sub")
    if not user_id:
        raise ValueError("Authenticated user is missing an id")
    return str(user_id)


def public_plans() -> list[PlanPublic]:
    return [
        PlanPublic(
            id=plan_id,
            name=str(plan["name"]),
            price_paise=int(plan.get("price_paise") or 0),
            currency=str(plan.get("currency") or "INR"),
            monthly_credits=int(plan.get("monthly_credits") or 0),
            trial_credits=int(plan.get("trial_credits") or 0),
            trial_days=int(plan.get("trial_days") or 0),
            nominal_paise_per_credit=billing_config.nominal_paise_per_credit(plan_id),
        )
        for plan_id, plan in billing_config.PLANS.items()
    ]


def public_topups() -> list[TopUpPackPublic]:
    return [
        TopUpPackPublic(
            id=pack_id,
            price_paise=int(pack["price_paise"]),
            currency=str(pack.get("currency") or "INR"),
            credits=int(pack["credits"]),
        )
        for pack_id, pack in billing_config.TOP_UP_PACKS.items()
    ]


class BillingService:
    def __init__(self, store: Optional[BillingStore] = None) -> None:
        self.store = store or get_default_billing_store()

    def ensure_billing_account(self, user: Mapping[str, Any]) -> dict[str, Any]:
        owner_id = _user_id(user)
        account = self.store.ensure_account(owner_id=owner_id)
        free_plan = billing_config.PLANS["free"]
        trial_credits = int(free_plan.get("trial_credits") or 0)
        trial_days = int(free_plan.get("trial_days") or 30)
        if trial_credits > 0:
            self.store.grant_credits(
                account_id=account["id"],
                amount=trial_credits,
                source="free_trial",
                expires_at=utc_now() + timedelta(days=trial_days),
                idempotency_key=f"free_trial:{owner_id}",
                metadata={"plan_id": "free", "trial_days": trial_days},
            )
        return account

    def estimate_required_credits(
        self,
        job_type: str,
        payload: Mapping[str, Any],
        *,
        include_reservation_buffer: bool = True,
    ) -> CreditEstimate:
        return _estimate_required_credits(
            job_type,
            payload,
            include_reservation_buffer=include_reservation_buffer,
        )

    def reserve_credits(
        self,
        account_id: str,
        job_id: str,
        estimated_credits: int,
        *,
        metadata: Optional[dict[str, Any]] = None,
    ) -> ReservationResult:
        reservation = self.store.reserve_credits(
            account_id=account_id,
            job_id=job_id,
            amount=estimated_credits,
            metadata=metadata,
        )
        wallet = self.store.get_wallet(account_id)
        return ReservationResult(
            reservation_id=reservation["id"],
            billing_account_id=account_id,
            job_id=job_id,
            reserved_credits=int(reservation.get("reserved_credits") or 0),
            status=reservation.get("status", "active"),
            available_credits=int(wallet.get("available_credits") or 0),
            created=bool(reservation.get("created")),
        )

    def reserve_job_credits(
        self,
        *,
        user: Mapping[str, Any],
        job_id: str,
        job_type: str,
        payload: Mapping[str, Any],
    ) -> tuple[dict[str, Any], CreditEstimate, ReservationResult]:
        account = self.ensure_billing_account(user)
        estimate = self.estimate_required_credits(job_type, payload)
        reservation = self.reserve_credits(
            account["id"],
            job_id,
            estimate.reserved_credits,
            metadata={
                "job_type": job_type,
                "billable_credits": estimate.billable_credits,
                "content_tokens": estimate.content_tokens,
            },
        )
        return account, estimate, reservation

    def commit_job_debit(
        self,
        account_id: str,
        job_id: str,
        final_credits: int,
        *,
        metadata: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        return self.store.commit_debit(
            account_id=account_id,
            job_id=job_id,
            final_amount=final_credits,
            metadata=metadata,
        )

    def release_job_reservation(
        self,
        account_id: str,
        job_id: str,
        *,
        metadata: Optional[dict[str, Any]] = None,
    ) -> Optional[dict[str, Any]]:
        return self.store.release_reservation(
            account_id=account_id,
            job_id=job_id,
            metadata=metadata,
        )

    def commit_job_billing(self, job: Mapping[str, Any], result: Mapping[str, Any]) -> dict[str, Any]:
        payload = job.get("payload") if isinstance(job.get("payload"), Mapping) else {}
        account_id = payload.get("billing_account_id")
        if not account_id:
            return dict(result)
        job_type = str(job.get("job_type") or payload.get("job_type") or "memory_ingest")
        estimate = self.estimate_required_credits(
            job_type,
            payload,
            include_reservation_buffer=False,
        )
        self.commit_job_debit(
            str(account_id),
            str(job["job_id"]),
            estimate.billable_credits,
            metadata={
                "job_type": job_type,
                "content_tokens": estimate.content_tokens,
                "multiplier": estimate.multiplier,
            },
        )
        enriched = dict(result)
        enriched["billing"] = {
            "billing_account_id": account_id,
            "billable_credits": estimate.billable_credits,
            "content_tokens": estimate.content_tokens,
            "multiplier": estimate.multiplier,
        }
        return enriched

    def release_job_billing(self, job: Mapping[str, Any], reason: str = "job_not_completed") -> None:
        payload = job.get("payload") if isinstance(job.get("payload"), Mapping) else {}
        account_id = payload.get("billing_account_id")
        if not account_id:
            return
        self.release_job_reservation(
            str(account_id),
            str(job["job_id"]),
            metadata={"reason": reason},
        )

    def grant_pro_subscription(
        self,
        *,
        user_id: str,
        payment_id: str,
        subscription_id: str,
        period_end=None,
    ) -> dict[str, Any]:
        account = self.store.ensure_account(owner_id=user_id)
        plan = billing_config.PLANS["pro"]
        expires_at = period_end or (utc_now() + timedelta(days=30))
        self.store.update_account(
            account["id"],
            {
                "plan_id": "pro",
                "status": "active",
                "razorpay_subscription_id": subscription_id,
                "current_period_end": expires_at,
            },
        )
        return self.store.grant_credits(
            account_id=account["id"],
            amount=int(plan["monthly_credits"]),
            source="pro_monthly",
            expires_at=expires_at,
            idempotency_key=f"pro_grant:{subscription_id}:{payment_id}",
            metadata={"payment_id": payment_id, "subscription_id": subscription_id},
        )

    def grant_topup(
        self,
        *,
        user_id: str,
        pack_id: str,
        payment_id: str,
        order_id: str,
    ) -> dict[str, Any]:
        pack = billing_config.TOP_UP_PACKS[pack_id]
        account = self.store.ensure_account(owner_id=user_id)
        return self.store.grant_credits(
            account_id=account["id"],
            amount=int(pack["credits"]),
            source=pack_id,
            expires_at=utc_now() + timedelta(days=billing_config.TOP_UP_EXPIRY_DAYS),
            idempotency_key=f"topup_grant:{order_id}:{payment_id}",
            metadata={"payment_id": payment_id, "order_id": order_id, "pack_id": pack_id},
        )

    def get_billing_summary(self, user: Mapping[str, Any]) -> BillingSummary:
        account = self.ensure_billing_account(user)
        wallet = self.store.get_wallet(account["id"])
        plan_id = str(account.get("plan_id") or "free")
        plan = billing_config.PLANS.get(plan_id, billing_config.PLANS["free"])
        lots = [
            CreditLotPublic(
                id=str(lot["id"]),
                source=str(lot.get("source") or ""),
                remaining_credits=int(lot.get("remaining_credits") or 0),
                expires_at=lot.get("expires_at"),
            )
            for lot in self.store.active_lots(account["id"])
        ]
        return BillingSummary(
            billing_account_id=account["id"],
            owner_type=str(account.get("owner_type") or "user"),
            owner_id=str(account.get("owner_id")),
            plan_id=plan_id,
            plan_name=str(plan.get("name") or plan_id),
            status=str(account.get("status") or "trialing"),
            currency=str(plan.get("currency") or "INR"),
            available_credits=int(wallet.get("available_credits") or 0),
            reserved_credits=int(wallet.get("reserved_credits") or 0),
            current_period_start=account.get("current_period_start"),
            current_period_end=account.get("current_period_end"),
            credit_lots=lots,
        )

    def list_ledger(self, user: Mapping[str, Any], limit: int = 100) -> list[dict[str, Any]]:
        account = self.ensure_billing_account(user)
        return self.store.list_ledger(account["id"], limit=limit)

    def record_usage_event(self, **event: Any) -> None:
        self.store.record_usage_event(event)


_default_service: Optional[BillingService] = None


def get_default_billing_service() -> BillingService:
    global _default_service
    if _default_service is None:
        _default_service = BillingService()
    return _default_service


def ensure_billing_account(user: Mapping[str, Any]) -> dict[str, Any]:
    return get_default_billing_service().ensure_billing_account(user)


def estimate_required_credits(job_type: str, payload: Mapping[str, Any]) -> CreditEstimate:
    return get_default_billing_service().estimate_required_credits(job_type, payload)


def reserve_credits(account_id: str, job_id: str, estimated_credits: int) -> ReservationResult:
    return get_default_billing_service().reserve_credits(account_id, job_id, estimated_credits)


def reserve_job_credits(
    *,
    user: Mapping[str, Any],
    job_id: str,
    job_type: str,
    payload: Mapping[str, Any],
) -> tuple[dict[str, Any], CreditEstimate, ReservationResult]:
    return get_default_billing_service().reserve_job_credits(
        user=user,
        job_id=job_id,
        job_type=job_type,
        payload=payload,
    )


def commit_job_debit(account_id: str, job_id: str, final_credits: int) -> dict[str, Any]:
    return get_default_billing_service().commit_job_debit(account_id, job_id, final_credits)


def release_job_reservation(account_id: str, job_id: str) -> Optional[dict[str, Any]]:
    return get_default_billing_service().release_job_reservation(account_id, job_id)


def commit_job_billing(job: Mapping[str, Any], result: Mapping[str, Any]) -> dict[str, Any]:
    return get_default_billing_service().commit_job_billing(job, result)


def release_job_billing(job: Mapping[str, Any], reason: str = "job_not_completed") -> None:
    get_default_billing_service().release_job_billing(job, reason)


def get_billing_summary(user: Mapping[str, Any]) -> BillingSummary:
    return get_default_billing_service().get_billing_summary(user)


def record_usage_event(**event: Any) -> None:
    get_default_billing_service().record_usage_event(**event)
