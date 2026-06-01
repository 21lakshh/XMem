from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Iterable, Optional

from src.config import settings

logger = logging.getLogger("xmem.billing.store")

_memory_accounts: dict[str, dict[str, Any]] = {}
_memory_wallets: dict[str, dict[str, Any]] = {}
_memory_lots: dict[str, dict[str, Any]] = {}
_memory_ledger: dict[str, dict[str, Any]] = {}
_memory_reservations: dict[str, dict[str, Any]] = {}
_memory_usage_events: list[dict[str, Any]] = []
_memory_payments: dict[str, dict[str, Any]] = {}


class BillingStoreError(RuntimeError):
    pass


class InsufficientCredits(BillingStoreError):
    def __init__(self, required: int, available: int) -> None:
        super().__init__(
            f"Insufficient credits: required {required}, available {available}."
        )
        self.required = required
        self.available = available


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _without_id(doc: Optional[dict[str, Any]]) -> Optional[dict[str, Any]]:
    if not doc:
        return None
    result = dict(doc)
    result.pop("_id", None)
    return result


def _is_expired(doc: dict[str, Any], now: Optional[datetime] = None) -> bool:
    expires_at = doc.get("expires_at")
    if not expires_at:
        return False
    now = now or utc_now()
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    return expires_at <= now


class BillingStore:
    """Mongo-backed credit ledger with in-memory fallback for local development."""

    def __init__(self, uri: Optional[str] = None, database: Optional[str] = None) -> None:
        self._uri = uri or settings.mongodb_uri
        self._database = database or settings.mongodb_database
        self._client = None
        self._db = None
        self._connected = False
        self._in_memory = False
        self._try_connect()

    def _requires_durable_storage(self) -> bool:
        return settings.environment.lower() in {"production", "prod"}

    def _enable_memory_fallback(self, error: Exception) -> None:
        message = f"Billing store connection failed: {error}"
        if self._requires_durable_storage():
            logger.error("%s; refusing in-memory fallback in production", message)
            raise RuntimeError(
                "MongoDB is required for billing storage when ENVIRONMENT=production"
            ) from error
        logger.warning("%s; using in-memory billing storage", message)
        self._connected = False
        self._in_memory = True

    def _try_connect(self) -> None:
        provider = (settings.app_store_provider or "mongo").strip().lower()
        if provider == "memory":
            self._in_memory = True
            return
        if provider == "postgres":
            self._enable_memory_fallback(
                RuntimeError("Postgres billing storage is not implemented")
            )
            return
        try:
            from pymongo import ASCENDING, MongoClient

            self._client = MongoClient(self._uri, serverSelectionTimeoutMS=5000)
            self._client.admin.command("ping")
            self._db = self._client[self._database]
            self.accounts = self._db["billing_accounts"]
            self.wallets = self._db["credit_wallets"]
            self.lots = self._db["credit_lots"]
            self.ledger = self._db["credit_ledger"]
            self.reservations = self._db["credit_reservations"]
            self.usage_events = self._db["usage_events"]
            self.payments = self._db["billing_payments"]

            self.accounts.create_index([("id", ASCENDING)], unique=True)
            self.accounts.create_index([("owner_type", ASCENDING), ("owner_id", ASCENDING)], unique=True)
            self.accounts.create_index([("razorpay_subscription_id", ASCENDING)])
            self.wallets.create_index([("billing_account_id", ASCENDING)], unique=True)
            self.lots.create_index([("id", ASCENDING)], unique=True)
            self.lots.create_index([("billing_account_id", ASCENDING), ("expires_at", ASCENDING)])
            self.ledger.create_index([("id", ASCENDING)], unique=True)
            self.ledger.create_index([("idempotency_key", ASCENDING)], unique=True)
            self.ledger.create_index([("billing_account_id", ASCENDING), ("created_at", ASCENDING)])
            self.reservations.create_index([("id", ASCENDING)], unique=True)
            self.reservations.create_index([("job_id", ASCENDING)], unique=True)
            self.payments.create_index([("id", ASCENDING)], unique=True, sparse=True)
            self.payments.create_index([("razorpay_event_id", ASCENDING)], unique=True, sparse=True)
            self.payments.create_index([("razorpay_payment_id", ASCENDING)], unique=True, sparse=True)

            self._connected = True
            self._in_memory = False
        except Exception as exc:
            self._enable_memory_fallback(exc)

    def ensure_account(
        self,
        *,
        owner_id: str,
        owner_type: str = "user",
        plan_id: str = "free",
        status: str = "trialing",
    ) -> dict[str, Any]:
        now = utc_now()
        if self._in_memory:
            key = f"{owner_type}:{owner_id}"
            account = _memory_accounts.get(key)
            if account:
                return dict(account)
            account = {
                "id": uuid.uuid4().hex,
                "owner_type": owner_type,
                "owner_id": owner_id,
                "plan_id": plan_id,
                "status": status,
                "created_at": now,
                "updated_at": now,
            }
            _memory_accounts[key] = account
            _memory_wallets[account["id"]] = {
                "billing_account_id": account["id"],
                "available_credits": 0,
                "reserved_credits": 0,
                "updated_at": now,
            }
            return dict(account)

        from pymongo import ReturnDocument

        doc = self.accounts.find_one_and_update(
            {"owner_type": owner_type, "owner_id": owner_id},
            {
                "$setOnInsert": {
                    "id": uuid.uuid4().hex,
                    "owner_type": owner_type,
                    "owner_id": owner_id,
                    "plan_id": plan_id,
                    "status": status,
                    "created_at": now,
                },
                "$set": {"updated_at": now},
            },
            upsert=True,
            return_document=ReturnDocument.AFTER,
        )
        account = _without_id(doc) or {}
        self.wallets.update_one(
            {"billing_account_id": account["id"]},
            {
                "$setOnInsert": {
                    "billing_account_id": account["id"],
                    "available_credits": 0,
                    "reserved_credits": 0,
                },
                "$set": {"updated_at": now},
            },
            upsert=True,
        )
        return account

    def get_account(self, account_id: str) -> Optional[dict[str, Any]]:
        if self._in_memory:
            for account in _memory_accounts.values():
                if account["id"] == account_id:
                    return dict(account)
            return None
        return _without_id(self.accounts.find_one({"id": account_id}))

    def update_account(self, account_id: str, updates: dict[str, Any]) -> None:
        updates = {**updates, "updated_at": utc_now()}
        if self._in_memory:
            for account in _memory_accounts.values():
                if account["id"] == account_id:
                    account.update(updates)
                    return
            return
        self.accounts.update_one({"id": account_id}, {"$set": updates})

    def get_wallet(self, account_id: str) -> dict[str, Any]:
        if self._in_memory:
            return dict(
                _memory_wallets.setdefault(
                    account_id,
                    {
                        "billing_account_id": account_id,
                        "available_credits": 0,
                        "reserved_credits": 0,
                        "updated_at": utc_now(),
                    },
                )
            )
        wallet = self.wallets.find_one({"billing_account_id": account_id})
        if not wallet:
            self.wallets.update_one(
                {"billing_account_id": account_id},
                {
                    "$setOnInsert": {
                        "billing_account_id": account_id,
                        "available_credits": 0,
                        "reserved_credits": 0,
                    },
                    "$set": {"updated_at": utc_now()},
                },
                upsert=True,
            )
            wallet = self.wallets.find_one({"billing_account_id": account_id})
        return _without_id(wallet) or {}

    def _insert_ledger(self, entry: dict[str, Any]) -> Optional[dict[str, Any]]:
        if self._in_memory:
            key = entry["idempotency_key"]
            if key in _memory_ledger:
                return dict(_memory_ledger[key])
            _memory_ledger[key] = dict(entry)
            return None
        try:
            self.ledger.insert_one(entry)
            return None
        except Exception as exc:
            if exc.__class__.__name__ != "DuplicateKeyError":
                raise
            return _without_id(self.ledger.find_one({"idempotency_key": entry["idempotency_key"]}))

    def grant_credits(
        self,
        *,
        account_id: str,
        amount: int,
        source: str,
        expires_at: Optional[datetime],
        idempotency_key: str,
        metadata: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        if amount <= 0:
            raise ValueError("Credit grant amount must be positive")
        now = utc_now()
        ledger_entry = {
            "id": uuid.uuid4().hex,
            "billing_account_id": account_id,
            "type": "grant",
            "amount": amount,
            "source": source,
            "expires_at": expires_at,
            "idempotency_key": idempotency_key,
            "metadata": metadata or {},
            "created_at": now,
        }
        duplicate = self._insert_ledger(ledger_entry)
        if duplicate:
            return duplicate

        lot = {
            "id": uuid.uuid4().hex,
            "billing_account_id": account_id,
            "source": source,
            "remaining_credits": amount,
            "ledger_id": ledger_entry["id"],
            "expires_at": expires_at,
            "created_at": now,
            "updated_at": now,
        }
        if self._in_memory:
            _memory_lots[lot["id"]] = lot
            wallet = _memory_wallets.setdefault(
                account_id,
                {"billing_account_id": account_id, "available_credits": 0, "reserved_credits": 0},
            )
            wallet["available_credits"] += amount
            wallet["updated_at"] = now
            return dict(ledger_entry)

        self.lots.insert_one(lot)
        self.wallets.update_one(
            {"billing_account_id": account_id},
            {"$inc": {"available_credits": amount}, "$set": {"updated_at": now}},
            upsert=True,
        )
        return ledger_entry

    def reserve_credits(
        self,
        *,
        account_id: str,
        job_id: str,
        amount: int,
        metadata: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        if amount <= 0:
            raise ValueError("Reservation amount must be positive")
        existing = self.get_reservation(job_id)
        if existing and existing.get("status") in {"active", "committed"}:
            if existing.get("billing_account_id") != account_id:
                raise BillingStoreError(
                    f"Reservation for job {job_id} belongs to a different billing account"
                )
            return existing

        now = utc_now()
        if self._in_memory:
            if existing and existing.get("billing_account_id") != account_id:
                raise BillingStoreError(
                    f"Reservation for job {job_id} belongs to a different billing account"
                )
            wallet = self.get_wallet(account_id)
            if int(wallet.get("available_credits") or 0) < amount:
                raise InsufficientCredits(amount, int(wallet.get("available_credits") or 0))
            _memory_wallets[account_id]["available_credits"] -= amount
            _memory_wallets[account_id]["reserved_credits"] += amount
            version = int((existing or {}).get("version") or 0) + 1
            reservation = {
                "id": (existing or {}).get("id") or uuid.uuid4().hex,
                "billing_account_id": account_id,
                "job_id": job_id,
                "reserved_credits": amount,
                "status": "active",
                "version": version,
                "metadata": metadata or {},
                "created_at": (existing or {}).get("created_at") or now,
                "updated_at": now,
            }
            _memory_reservations[job_id] = reservation
            self._insert_ledger(
                {
                    "id": uuid.uuid4().hex,
                    "billing_account_id": account_id,
                    "type": "reserve",
                    "amount": amount,
                    "job_id": job_id,
                    "idempotency_key": f"reserve:{job_id}:{version}",
                    "metadata": metadata or {},
                    "created_at": now,
                }
            )
            return dict(reservation)

        from pymongo import ReturnDocument

        if existing:
            if existing.get("billing_account_id") != account_id:
                raise BillingStoreError(
                    f"Reservation for job {job_id} belongs to a different billing account"
                )
            reserved_doc = self.reservations.find_one_and_update(
                {
                    "job_id": job_id,
                    "billing_account_id": account_id,
                    "status": {"$nin": ["active", "committed", "reserving"]},
                },
                {
                    "$set": {
                        "status": "reserving",
                        "reserved_credits": amount,
                        "metadata": metadata or {},
                        "updated_at": now,
                    },
                    "$inc": {"version": 1},
                },
                return_document=ReturnDocument.AFTER,
            )
            if not reserved_doc:
                current = self.get_reservation(job_id)
                if (
                    current
                    and current.get("billing_account_id") == account_id
                    and current.get("status") != "reserving"
                ):
                    return current
                raise BillingStoreError(f"Reservation for job {job_id} is already active")
            reservation = _without_id(reserved_doc) or {}
            version = int(reservation.get("version") or 1)
        else:
            reservation = {
                "id": uuid.uuid4().hex,
                "billing_account_id": account_id,
                "job_id": job_id,
                "reserved_credits": amount,
                "status": "reserving",
                "version": 1,
                "metadata": metadata or {},
                "created_at": now,
                "updated_at": now,
            }
            try:
                self.reservations.insert_one(reservation)
            except Exception as exc:
                if exc.__class__.__name__ != "DuplicateKeyError":
                    raise
                current = self.get_reservation(job_id)
                if (
                    current
                    and current.get("billing_account_id") == account_id
                    and current.get("status") != "reserving"
                ):
                    return current
                if current and current.get("billing_account_id") == account_id:
                    raise BillingStoreError(
                        f"Reservation for job {job_id} is already being created"
                    ) from exc
                raise BillingStoreError(
                    f"Reservation for job {job_id} belongs to a different billing account"
                ) from exc
            version = 1

        wallet = self.wallets.find_one_and_update(
            {"billing_account_id": account_id, "available_credits": {"$gte": amount}},
            {
                "$inc": {"available_credits": -amount, "reserved_credits": amount},
                "$set": {"updated_at": now},
            },
            return_document=True,
        )
        if not wallet:
            self.reservations.update_one(
                {"job_id": job_id, "status": "reserving"},
                {"$set": {"status": "released", "updated_at": now}},
            )
            current = self.get_wallet(account_id)
            raise InsufficientCredits(amount, int(current.get("available_credits") or 0))

        self.reservations.update_one(
            {"job_id": job_id, "billing_account_id": account_id, "status": "reserving"},
            {"$set": {"status": "active", "updated_at": now}},
        )
        reservation = self.get_reservation(job_id) or reservation
        self._insert_ledger(
            {
                "id": uuid.uuid4().hex,
                "billing_account_id": account_id,
                "type": "reserve",
                "amount": amount,
                "job_id": job_id,
                "idempotency_key": f"reserve:{job_id}:{version}",
                "metadata": metadata or {},
                "created_at": now,
            }
        )
        return reservation

    def get_reservation(self, job_id: str) -> Optional[dict[str, Any]]:
        if self._in_memory:
            reservation = _memory_reservations.get(job_id)
            return dict(reservation) if reservation else None
        return _without_id(self.reservations.find_one({"job_id": job_id}))

    def commit_debit(
        self,
        *,
        account_id: str,
        job_id: str,
        final_amount: int,
        metadata: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        if final_amount <= 0:
            raise ValueError("Debit amount must be positive")
        duplicate = self.find_ledger_by_key(f"debit:{job_id}")
        if duplicate:
            return duplicate
        now = utc_now()
        reservation = self._claim_reservation_for_commit(account_id, job_id, final_amount, now)
        if reservation.get("type") == "debit":
            return reservation
        reserved = int(reservation.get("reserved_credits") or 0)
        extra = max(final_amount - reserved, 0)
        refund = max(reserved - final_amount, 0)

        try:
            if extra and self._in_memory:
                wallet = self.get_wallet(account_id)
                if int(wallet.get("available_credits") or 0) < extra:
                    raise InsufficientCredits(extra, int(wallet.get("available_credits") or 0))
                _memory_wallets[account_id]["available_credits"] -= extra
            elif extra:
                wallet = self.wallets.find_one_and_update(
                    {"billing_account_id": account_id, "available_credits": {"$gte": extra}},
                    {"$inc": {"available_credits": -extra}, "$set": {"updated_at": now}},
                    return_document=True,
                )
                if not wallet:
                    current = self.get_wallet(account_id)
                    raise InsufficientCredits(extra, int(current.get("available_credits") or 0))

            self._consume_lots(account_id, final_amount)
            if self._in_memory:
                _memory_wallets[account_id]["reserved_credits"] -= reserved
                _memory_wallets[account_id]["available_credits"] += refund
                _memory_wallets[account_id]["updated_at"] = now
                _memory_reservations[job_id]["status"] = "committed"
                _memory_reservations[job_id]["final_credits"] = final_amount
                _memory_reservations[job_id]["updated_at"] = now
            else:
                self.wallets.update_one(
                    {"billing_account_id": account_id},
                    {
                        "$inc": {"reserved_credits": -reserved, "available_credits": refund},
                        "$set": {"updated_at": now},
                    },
                )
                self.reservations.update_one(
                    {"job_id": job_id, "billing_account_id": account_id},
                    {
                        "$set": {
                            "status": "committed",
                            "final_credits": final_amount,
                            "updated_at": now,
                        }
                    },
                )
        except Exception:
            self._release_commit_claim(account_id, job_id)
            raise

        entry = {
            "id": uuid.uuid4().hex,
            "billing_account_id": account_id,
            "type": "debit",
            "amount": -final_amount,
            "job_id": job_id,
            "idempotency_key": f"debit:{job_id}",
            "metadata": metadata or {},
            "created_at": now,
        }
        self._insert_ledger(entry)
        if refund:
            self._insert_ledger(
                {
                    "id": uuid.uuid4().hex,
                    "billing_account_id": account_id,
                    "type": "refund",
                    "amount": refund,
                    "job_id": job_id,
                    "idempotency_key": f"refund:{job_id}",
                    "metadata": {"reason": "unused_reservation"},
                    "created_at": now,
                }
            )
        return entry

    def _claim_reservation_for_commit(
        self,
        account_id: str,
        job_id: str,
        final_amount: int,
        now: datetime,
    ) -> dict[str, Any]:
        if self._in_memory:
            reservation = self.get_reservation(job_id)
            if not reservation:
                raise BillingStoreError(f"No credit reservation exists for job {job_id}")
            if reservation.get("billing_account_id") != account_id:
                raise BillingStoreError(
                    f"Reservation for job {job_id} belongs to a different billing account"
                )
            if reservation.get("status") == "committed":
                existing = self.find_ledger_by_key(f"debit:{job_id}")
                if existing:
                    return existing
                raise BillingStoreError(f"Reservation for job {job_id} is already committed")
            if reservation.get("status") != "active":
                raise BillingStoreError(f"Reservation for job {job_id} is not active")
            _memory_reservations[job_id]["status"] = "committing"
            _memory_reservations[job_id]["final_credits"] = final_amount
            _memory_reservations[job_id]["updated_at"] = now
            return reservation

        from pymongo import ReturnDocument

        reservation = self.reservations.find_one_and_update(
            {"job_id": job_id, "billing_account_id": account_id, "status": "active"},
            {
                "$set": {
                    "status": "committing",
                    "final_credits": final_amount,
                    "updated_at": now,
                }
            },
            return_document=ReturnDocument.BEFORE,
        )
        if reservation:
            return _without_id(reservation) or {}

        existing = self.find_ledger_by_key(f"debit:{job_id}")
        if existing:
            return existing
        current = self.get_reservation(job_id)
        if current and current.get("billing_account_id") != account_id:
            raise BillingStoreError(
                f"Reservation for job {job_id} belongs to a different billing account"
            )
        raise BillingStoreError(f"Reservation for job {job_id} is not active")

    def _release_commit_claim(self, account_id: str, job_id: str) -> None:
        if self._in_memory:
            reservation = _memory_reservations.get(job_id)
            if reservation and reservation.get("billing_account_id") == account_id:
                reservation["status"] = "active"
                reservation.pop("final_credits", None)
                reservation["updated_at"] = utc_now()
            return
        self.reservations.update_one(
            {"job_id": job_id, "billing_account_id": account_id, "status": "committing"},
            {
                "$set": {"status": "active", "updated_at": utc_now()},
                "$unset": {"final_credits": ""},
            },
        )

    def release_reservation(
        self,
        *,
        account_id: str,
        job_id: str,
        metadata: Optional[dict[str, Any]] = None,
    ) -> Optional[dict[str, Any]]:
        reservation = self.get_reservation(job_id)
        if not reservation or reservation.get("status") != "active":
            return reservation
        now = utc_now()
        amount = int(reservation.get("reserved_credits") or 0)
        if self._in_memory:
            _memory_wallets[account_id]["available_credits"] += amount
            _memory_wallets[account_id]["reserved_credits"] -= amount
            _memory_wallets[account_id]["updated_at"] = now
            _memory_reservations[job_id]["status"] = "released"
            _memory_reservations[job_id]["updated_at"] = now
        else:
            self.wallets.update_one(
                {"billing_account_id": account_id},
                {
                    "$inc": {"available_credits": amount, "reserved_credits": -amount},
                    "$set": {"updated_at": now},
                },
            )
            self.reservations.update_one(
                {"job_id": job_id}, {"$set": {"status": "released", "updated_at": now}}
            )
        self._insert_ledger(
            {
                "id": uuid.uuid4().hex,
                "billing_account_id": account_id,
                "type": "release",
                "amount": amount,
                "job_id": job_id,
                "idempotency_key": f"release:{job_id}:{reservation.get('version', 1)}",
                "metadata": metadata or {},
                "created_at": now,
            }
        )
        return self.get_reservation(job_id)

    def _consume_lots(self, account_id: str, amount: int) -> None:
        remaining = amount
        now = utc_now()
        while remaining > 0:
            lots = list(self.active_lots(account_id))
            if not lots:
                break
            progressed = False
            for lot in lots:
                if remaining <= 0:
                    break
                take = min(remaining, int(lot.get("remaining_credits") or 0))
                if take <= 0:
                    continue
                if self._in_memory:
                    _memory_lots[lot["id"]]["remaining_credits"] -= take
                    _memory_lots[lot["id"]]["updated_at"] = now
                    remaining -= take
                    progressed = True
                    continue
                result = self.lots.update_one(
                    {"id": lot["id"], "remaining_credits": {"$gte": take}},
                    {
                        "$inc": {"remaining_credits": -take},
                        "$set": {"updated_at": now},
                    },
                )
                if getattr(result, "modified_count", 0) == 1:
                    remaining -= take
                    progressed = True
            if not progressed:
                break
        if remaining > 0:
            raise BillingStoreError(
                f"Wallet had credits but credit lots were short by {remaining}"
            )

    def active_lots(self, account_id: str) -> Iterable[dict[str, Any]]:
        now = utc_now()
        if self._in_memory:
            lots = [
                dict(lot)
                for lot in _memory_lots.values()
                if lot["billing_account_id"] == account_id
                and int(lot.get("remaining_credits") or 0) > 0
                and not _is_expired(lot, now)
            ]
            return sorted(lots, key=lambda item: item.get("expires_at") or datetime.max.replace(tzinfo=timezone.utc))
        cursor = self.lots.find(
            {
                "billing_account_id": account_id,
                "remaining_credits": {"$gt": 0},
                "$or": [{"expires_at": None}, {"expires_at": {"$gt": now}}],
            }
        ).sort("expires_at", 1)
        return [_without_id(lot) or {} for lot in cursor]

    def find_ledger_by_key(self, idempotency_key: str) -> Optional[dict[str, Any]]:
        if self._in_memory:
            entry = _memory_ledger.get(idempotency_key)
            return dict(entry) if entry else None
        return _without_id(self.ledger.find_one({"idempotency_key": idempotency_key}))

    def list_ledger(self, account_id: str, limit: int = 100) -> list[dict[str, Any]]:
        if self._in_memory:
            entries = [
                dict(entry)
                for entry in _memory_ledger.values()
                if entry.get("billing_account_id") == account_id
            ]
            return sorted(entries, key=lambda item: item["created_at"], reverse=True)[:limit]
        return [
            _without_id(entry) or {}
            for entry in self.ledger.find({"billing_account_id": account_id})
            .sort("created_at", -1)
            .limit(limit)
        ]

    def record_usage_event(self, event: dict[str, Any]) -> None:
        payload = {"id": uuid.uuid4().hex, "created_at": utc_now(), **event}
        if self._in_memory:
            _memory_usage_events.append(payload)
            return
        self.usage_events.insert_one(payload)

    def save_checkout(self, checkout_id: str, payload: dict[str, Any]) -> None:
        now = utc_now()
        doc = {"id": checkout_id, **payload, "updated_at": now}
        if self._in_memory:
            _memory_payments[checkout_id] = doc
            return
        self.payments.update_one({"id": checkout_id}, {"$set": doc, "$setOnInsert": {"created_at": now}}, upsert=True)

    def get_checkout(self, checkout_id: str) -> Optional[dict[str, Any]]:
        if self._in_memory:
            return dict(_memory_payments[checkout_id]) if checkout_id in _memory_payments else None
        return _without_id(self.payments.find_one({"id": checkout_id}))

    def mark_payment_event(self, event_id: str, payload: dict[str, Any]) -> bool:
        if not event_id:
            event_id = uuid.uuid4().hex
        now = utc_now()
        if self._in_memory:
            if event_id in _memory_payments:
                return False
            _memory_payments[event_id] = {"razorpay_event_id": event_id, **payload, "created_at": now}
            return True
        try:
            self.payments.insert_one({"razorpay_event_id": event_id, **payload, "created_at": now})
            return True
        except Exception as exc:
            if exc.__class__.__name__ == "DuplicateKeyError":
                return False
            raise


_default_store: Optional[BillingStore] = None


def get_default_billing_store() -> BillingStore:
    global _default_store
    if _default_store is None:
        _default_store = BillingStore()
    return _default_store
