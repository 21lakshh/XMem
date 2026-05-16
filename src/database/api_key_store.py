"""API Key management store for MongoDB."""

import hashlib
import logging
import secrets
import string
import time
from collections import OrderedDict
from datetime import datetime
from threading import RLock
from typing import List, Optional, Dict, Any

from src.config import settings

logger = logging.getLogger("xmem.database.api_key_store")

# API key prefix for identification
API_KEY_PREFIX = "xmem_"
API_KEY_LENGTH = 48  # Total length including prefix

# In-memory fallback
_in_memory_api_keys: Dict[str, Dict[str, Any]] = {}

VALIDATION_CACHE_TTL_SECONDS = 120
VALIDATION_CACHE_MAX_SIZE = 2048
_validation_cache: OrderedDict[str, tuple[float, Dict[str, Any]]] = OrderedDict()
_validation_cache_lock = RLock()


class APIKeyStore:
    """MongoDB-backed storage for API key management with in-memory fallback."""

    def __init__(
        self,
        uri: str = None,
        database: str = None,
    ) -> None:
        self._uri = uri or settings.mongodb_uri
        self._database = database or settings.mongodb_database
        self._client = None
        self._db = None
        self.api_keys = None
        self._connected = False
        self._in_memory = False

        # Try to connect
        self._try_connect()

    def _try_connect(self) -> None:
        """Attempt to connect to configured store, fall back to memory if unavailable."""
        provider = (settings.app_store_provider or "mongo").strip().lower()
        if provider == "memory":
            self._connected = False
            self._in_memory = True
            self.api_keys = None
            logger.info("Using in-memory API key storage")
            return
        if provider == "postgres":
            self._try_connect_postgres()
            return

        try:
            from pymongo import MongoClient

            self._client = MongoClient(self._uri, serverSelectionTimeoutMS=5000)
            self._client.admin.command('ping')
            self._db = self._client[self._database]
            self.api_keys = self._db["api_keys"]
            self._connected = True
            self._in_memory = False
            logger.info("Connected to MongoDB for API key storage")
            self._ensure_indexes()
        except Exception as e:
            logger.warning(f"MongoDB connection failed, using in-memory storage: {e}")
            self._connected = False
            self._in_memory = True
            self.api_keys = None

    def _try_connect_postgres(self) -> None:
        """Attempt to connect to Postgres for local API key metadata."""
        try:
            import psycopg
            from psycopg.rows import dict_row

            self._client = psycopg.connect(settings.app_postgres_url or settings.pgvector_url)
            self._client.autocommit = True
            self._pg_row_factory = dict_row
            self._connected = True
            self._in_memory = False
            self._backend = "postgres"
            self._ensure_postgres_schema()
            logger.info("Connected to Postgres for API key storage")
        except Exception as e:
            logger.warning(f"Postgres connection failed, using in-memory API key storage: {e}")
            self._connected = False
            self._in_memory = True
            self.api_keys = None

    def _ensure_postgres_schema(self) -> None:
        with self._client.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS api_keys (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    key_hash TEXT UNIQUE NOT NULL,
                    key_prefix TEXT NOT NULL,
                    name TEXT NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL,
                    last_used TIMESTAMPTZ,
                    is_active BOOLEAN NOT NULL DEFAULT TRUE
                )
                """
            )
            cur.execute("CREATE INDEX IF NOT EXISTS api_keys_user_id_idx ON api_keys(user_id)")
            cur.execute("CREATE INDEX IF NOT EXISTS api_keys_active_idx ON api_keys(is_active)")

    def _is_postgres(self) -> bool:
        return getattr(self, "_backend", "") == "postgres"

    def _ensure_indexes(self) -> None:
        """Create necessary indexes for the api_keys collection."""
        if not self._connected:
            return
        try:
            from pymongo import ASCENDING
            self.api_keys.create_index([("user_id", ASCENDING)])
            self.api_keys.create_index([("key_hash", ASCENDING)], unique=True)
            self.api_keys.create_index([("is_active", ASCENDING)])
        except Exception as e:
            logger.warning(f"Failed to create indexes: {e}")

    def _generate_api_key(self) -> str:
        """Generate a new secure API key."""
        alphabet = string.ascii_letters + string.digits
        random_part = "".join(secrets.choice(alphabet) for _ in range(API_KEY_LENGTH - len(API_KEY_PREFIX)))
        return f"{API_KEY_PREFIX}{random_part}"

    def _hash_key(self, key: str) -> str:
        """Create SHA-256 hash of the API key."""
        return hashlib.sha256(key.encode()).hexdigest()

    def _clear_validation_cache(self) -> None:
        """Clear cached API key validation results."""
        with _validation_cache_lock:
            _validation_cache.clear()

    def _get_cached_validation(self, key_hash: str) -> Optional[Dict[str, Any]]:
        """Return a cached validation result when it is still fresh."""
        with _validation_cache_lock:
            cached = _validation_cache.get(key_hash)
            if not cached:
                return None

            expires_at, key_doc = cached
            if expires_at <= time.monotonic():
                _validation_cache.pop(key_hash, None)
                return None

            result = dict(key_doc)

        result["last_used"] = datetime.utcnow()
        return result

    def _cache_validation(self, key_hash: str, key_doc: Dict[str, Any]) -> None:
        """Cache a sanitized active API key document."""
        with _validation_cache_lock:
            if key_hash in _validation_cache:
                _validation_cache.pop(key_hash, None)
            while len(_validation_cache) >= VALIDATION_CACHE_MAX_SIZE:
                _validation_cache.popitem(last=False)

            _validation_cache[key_hash] = (
                time.monotonic() + VALIDATION_CACHE_TTL_SECONDS,
                dict(key_doc),
            )

    def create_api_key(
        self,
        user_id: str,
        name: str = "Default",
    ) -> Dict[str, Any]:
        """Create a new API key for a user."""
        key = self._generate_api_key()
        key_hash = self._hash_key(key)
        key_prefix = key[:8]
        now = datetime.utcnow()

        if self._in_memory:
            key_id = f"mem_{len(_in_memory_api_keys)}"
            key_doc = {
                "_id": key_id,
                "user_id": user_id,
                "key_hash": key_hash,
                "key_prefix": key_prefix,
                "name": name,
                "created_at": now,
                "last_used": None,
                "is_active": True,
            }
            _in_memory_api_keys[key_id] = key_doc
            logger.info(f"Created new API key (memory) for user {user_id}")
            return {
                "key": key,
                "key_id": key_id,
                "name": name,
                "created_at": now,
            }

        if self._is_postgres():
            import uuid

            key_id = str(uuid.uuid4())
            with self._client.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO api_keys(id, user_id, key_hash, key_prefix, name, created_at, is_active)
                    VALUES (%s, %s, %s, %s, %s, %s, TRUE)
                    """,
                    (key_id, user_id, key_hash, key_prefix, name, now),
                )
            logger.info(f"Created new API key (postgres) for user {user_id}")
            return {
                "key": key,
                "key_id": key_id,
                "name": name,
                "created_at": now,
            }

        try:
            key_doc = {
                "user_id": user_id,
                "key_hash": key_hash,
                "key_prefix": key_prefix,
                "name": name,
                "created_at": now,
                "last_used": None,
                "is_active": True,
            }
            result = self.api_keys.insert_one(key_doc)
            logger.info(f"Created new API key for user {user_id}")
            return {
                "key": key,
                "key_id": str(result.inserted_id),
                "name": name,
                "created_at": now,
            }
        except Exception as e:
            logger.error(f"Database error creating API key: {e}")
            self._in_memory = True
            return self.create_api_key(user_id, name)

    def get_user_api_keys(self, user_id: str, include_inactive: bool = False) -> List[Dict[str, Any]]:
        """Get all API keys for a user."""
        if self._in_memory:
            keys = [
                {**k, "id": str(k["_id"])}
                for k in _in_memory_api_keys.values()
                if k["user_id"] == user_id and (include_inactive or k.get("is_active", True))
            ]
            for key in keys:
                key.pop("key_hash", None)
            return keys

        if self._is_postgres():
            query = "SELECT * FROM api_keys WHERE user_id = %s"
            params: list[Any] = [user_id]
            if not include_inactive:
                query += " AND is_active = TRUE"
            query += " ORDER BY created_at ASC"
            with self._client.cursor(row_factory=self._pg_row_factory) as cur:
                cur.execute(query, params)
                keys = [dict(row) for row in cur.fetchall()]
            for key_doc in keys:
                key_doc.pop("key_hash", None)
            return keys

        try:
            from pymongo import ASCENDING
            query = {"user_id": user_id}
            if not include_inactive:
                query["is_active"] = True

            keys = list(self.api_keys.find(query).sort("created_at", ASCENDING))
            for key in keys:
                key.pop("key_hash", None)
                key["id"] = str(key.pop("_id"))
            return keys
        except Exception as e:
            logger.error(f"Database error getting API keys: {e}")
            return []

    def validate_api_key(self, key: str) -> Optional[Dict[str, Any]]:
        """Validate an API key and return associated user info."""
        key_hash = self._hash_key(key)

        if self._in_memory:
            for key_doc in _in_memory_api_keys.values():
                if key_doc.get("key_hash") == key_hash and key_doc.get("is_active", True):
                    key_doc["last_used"] = datetime.utcnow()
                    result = {**key_doc, "id": str(key_doc["_id"])}
                    result.pop("key_hash", None)
                    return result
            return None

        cached_doc = self._get_cached_validation(key_hash)
        if cached_doc:
            return cached_doc

        if self._is_postgres():
            now = datetime.utcnow()
            with self._client.cursor(row_factory=self._pg_row_factory) as cur:
                cur.execute(
                    "SELECT * FROM api_keys WHERE key_hash = %s AND is_active = TRUE",
                    (key_hash,),
                )
                row = cur.fetchone()
                if not row:
                    return None
                cur.execute(
                    "UPDATE api_keys SET last_used = %s WHERE id = %s",
                    (now, row["id"]),
                )
            key_doc = dict(row)
            key_doc["last_used"] = now
            key_doc.pop("key_hash", None)
            self._cache_validation(key_hash, key_doc)
            return key_doc

        try:
            key_doc = self.api_keys.find_one({
                "key_hash": key_hash,
                "is_active": True,
            })
            if key_doc:
                now = datetime.utcnow()
                self.api_keys.update_one(
                    {"_id": key_doc["_id"]},
                    {"$set": {"last_used": now}}
                )
                key_doc = {
                    **key_doc,
                    "id": str(key_doc["_id"]),
                    "last_used": now,
                }
                key_doc.pop("_id", None)
                key_doc.pop("key_hash", None)
                self._cache_validation(key_hash, key_doc)
            return dict(key_doc) if key_doc else None
        except Exception as e:
            logger.error(f"Database error validating API key: {e}")
            return None

    def revoke_api_key(self, user_id: str, key_id: str) -> bool:
        """Revoke (deactivate) an API key."""
        if self._in_memory:
            if key_id in _in_memory_api_keys:
                if _in_memory_api_keys[key_id].get("user_id") == user_id:
                    _in_memory_api_keys[key_id]["is_active"] = False
                    self._clear_validation_cache()
                    return True
            return False

        if self._is_postgres():
            with self._client.cursor() as cur:
                cur.execute(
                    "UPDATE api_keys SET is_active = FALSE WHERE id = %s AND user_id = %s",
                    (key_id, user_id),
                )
                success = cur.rowcount > 0
            if success:
                self._clear_validation_cache()
            return success

        try:
            from bson import ObjectId
            result = self.api_keys.update_one(
                {"_id": ObjectId(key_id), "user_id": user_id},
                {"$set": {"is_active": False}}
            )
            success = result.modified_count > 0
            if success:
                self._clear_validation_cache()
            return success
        except Exception as e:
            logger.error(f"Failed to revoke API key {key_id}: {e}")
            return False

    def update_api_key_name(
        self,
        user_id: str,
        key_id: str,
        new_name: str,
    ) -> bool:
        """Update the name of an API key."""
        if self._in_memory:
            if key_id in _in_memory_api_keys:
                if _in_memory_api_keys[key_id].get("user_id") == user_id:
                    _in_memory_api_keys[key_id]["name"] = new_name
                    self._clear_validation_cache()
                    return True
            return False

        if self._is_postgres():
            with self._client.cursor() as cur:
                cur.execute(
                    "UPDATE api_keys SET name = %s WHERE id = %s AND user_id = %s",
                    (new_name, key_id, user_id),
                )
                success = cur.rowcount > 0
            if success:
                self._clear_validation_cache()
            return success

        try:
            from bson import ObjectId
            result = self.api_keys.update_one(
                {"_id": ObjectId(key_id), "user_id": user_id},
                {"$set": {"name": new_name}}
            )
            success = result.modified_count > 0
            if success:
                self._clear_validation_cache()
            return success
        except Exception as e:
            logger.error(f"Failed to update API key name {key_id}: {e}")
            return False

    def close(self) -> None:
        """Close the MongoDB connection."""
        if self._client:
            self._client.close()
