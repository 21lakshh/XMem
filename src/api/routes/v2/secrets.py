from __future__ import annotations

import base64
import hashlib
import os
from datetime import datetime, timezone
from typing import Any, Dict

from cryptography.fernet import Fernet, InvalidToken

from src.config import settings
from src.jobs.durable import get_default_job_store

_IN_MEMORY_SECRETS: Dict[str, Dict[str, Any]] = {}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _fernet() -> Fernet:
    configured = os.getenv("XMEM_SECRET_ENCRYPTION_KEY", "").strip()
    if configured:
        return Fernet(configured.encode("utf-8"))
    digest = hashlib.sha256(settings.jwt_secret_key.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def _collection():
    store = get_default_job_store()
    db = getattr(store, "_db", None)
    if db is None:
        return None
    collection = db["durable_job_secrets"]
    collection.create_index([("secret_ref", 1)], unique=True)
    collection.create_index([("job_id", 1)])
    return collection


def scanner_pat_secret_ref(job_id: str) -> str:
    return f"scanner_pat:{job_id}"


def store_scanner_pat(job_id: str, pat: str) -> str:
    secret_ref = scanner_pat_secret_ref(job_id)
    ciphertext = _fernet().encrypt(pat.encode("utf-8")).decode("utf-8")
    doc = {
        "secret_ref": secret_ref,
        "job_id": job_id,
        "kind": "github_pat",
        "ciphertext": ciphertext,
        "updated_at": _now(),
    }
    collection = _collection()
    if collection is None:
        _IN_MEMORY_SECRETS[secret_ref] = doc
    else:
        collection.update_one(
            {"secret_ref": secret_ref},
            {"$set": doc, "$setOnInsert": {"created_at": _now()}},
            upsert=True,
        )
    return secret_ref


def resolve_scanner_pat(secret_ref: str) -> str:
    if not secret_ref:
        return ""
    collection = _collection()
    doc = _IN_MEMORY_SECRETS.get(secret_ref) if collection is None else collection.find_one({"secret_ref": secret_ref})
    if not doc:
        return ""
    try:
        return _fernet().decrypt(str(doc["ciphertext"]).encode("utf-8")).decode("utf-8")
    except (InvalidToken, KeyError) as exc:
        raise ValueError("Scanner credential could not be decrypted.") from exc
