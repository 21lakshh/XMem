"""Connector OAuth routes for external knowledge sources."""

from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Literal, Optional
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from src.api.dependencies import require_user
from src.config import settings


router = APIRouter(prefix="/api/connectors", tags=["Connectors"])

ConnectorId = Literal["notion", "google-drive"]
ConnectorState = Literal["connected", "not_connected", "pending"]

STATE_TTL_MINUTES = 10


class ConnectorDefinition(BaseModel):
    id: ConnectorId
    name: str
    description: str
    auth_url: str
    token_url: str
    scopes: List[str]
    docs_url: str


class ConnectorStatusResponse(BaseModel):
    id: ConnectorId
    name: str
    state: ConnectorState
    connected_at: Optional[datetime] = None
    scopes: List[str] = Field(default_factory=list)
    detail: str


class ConnectorListResponse(BaseModel):
    connectors: List[ConnectorStatusResponse]


class ConnectorStartResponse(BaseModel):
    connector_id: ConnectorId
    authorization_url: str
    state: str
    expires_at: datetime


class ConnectorDisconnectResponse(BaseModel):
    connector_id: ConnectorId
    disconnected: bool


class PendingOAuthState(BaseModel):
    connector_id: ConnectorId
    user_id: str
    expires_at: datetime


class StoredConnection(BaseModel):
    connector_id: ConnectorId
    user_id: str
    connected_at: datetime
    scopes: List[str]


CONNECTORS: Dict[ConnectorId, ConnectorDefinition] = {
    "notion": ConnectorDefinition(
        id="notion",
        name="Notion",
        description="Sync selected Notion pages and workspace notes into XMem memory.",
        auth_url="https://api.notion.com/v1/oauth/authorize",
        token_url="https://api.notion.com/v1/oauth/token",
        scopes=[],
        docs_url="https://developers.notion.com/docs/authorization",
    ),
    "google-drive": ConnectorDefinition(
        id="google-drive",
        name="Google Drive",
        description="Bring Google Drive docs and files into XMem as searchable memory.",
        auth_url="https://accounts.google.com/o/oauth2/v2/auth",
        token_url="https://oauth2.googleapis.com/token",
        scopes=[
            "https://www.googleapis.com/auth/drive.readonly",
            "https://www.googleapis.com/auth/documents.readonly",
        ],
        docs_url="https://developers.google.com/identity/protocols/oauth2",
    ),
}

_pending_states: Dict[str, PendingOAuthState] = {}
_connections: Dict[str, StoredConnection] = {}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _connection_key(user_id: str, connector_id: ConnectorId) -> str:
    return f"{user_id}:{connector_id}"


def _client_id(connector_id: ConnectorId) -> Optional[str]:
    if connector_id == "notion":
        return settings.notion_client_id
    return settings.google_drive_client_id


def _redirect_uri(connector_id: ConnectorId) -> str:
    if connector_id == "notion":
        return settings.notion_redirect_uri
    return settings.google_drive_redirect_uri


def _get_connector(connector_id: str) -> ConnectorDefinition:
    connector = CONNECTORS.get(connector_id)  # type: ignore[arg-type]
    if not connector:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unknown connector")
    return connector


def _status_for(user_id: str, connector: ConnectorDefinition) -> ConnectorStatusResponse:
    connection = _connections.get(_connection_key(user_id, connector.id))
    if connection:
        return ConnectorStatusResponse(
            id=connector.id,
            name=connector.name,
            state="connected",
            connected_at=connection.connected_at,
            scopes=connection.scopes,
            detail="Connected",
        )

    return ConnectorStatusResponse(
        id=connector.id,
        name=connector.name,
        state="not_connected",
        scopes=connector.scopes,
        detail="Not connected",
    )


def _build_authorization_url(connector: ConnectorDefinition, state: str) -> str:
    client_id = _client_id(connector.id)
    if not client_id:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"{connector.name} OAuth client ID is not configured",
        )

    params = {
        "client_id": client_id,
        "redirect_uri": _redirect_uri(connector.id),
        "response_type": "code",
        "state": state,
    }
    if connector.id == "google-drive":
        params.update(
            {
                "access_type": "offline",
                "include_granted_scopes": "true",
                "prompt": "consent",
                "scope": " ".join(connector.scopes),
            }
        )
    if connector.id == "notion":
        params["owner"] = "user"

    return f"{connector.auth_url}?{urlencode(params)}"


@router.get("", response_model=ConnectorListResponse)
async def list_connectors(current_user: dict = Depends(require_user)) -> ConnectorListResponse:
    user_id = str(current_user.get("id"))
    return ConnectorListResponse(
        connectors=[_status_for(user_id, connector) for connector in CONNECTORS.values()]
    )


@router.get("/{connector_id}/status", response_model=ConnectorStatusResponse)
async def connector_status(
    connector_id: str,
    current_user: dict = Depends(require_user),
) -> ConnectorStatusResponse:
    connector = _get_connector(connector_id)
    return _status_for(str(current_user.get("id")), connector)


@router.post("/{connector_id}/oauth/start", response_model=ConnectorStartResponse)
async def start_connector_oauth(
    connector_id: str,
    current_user: dict = Depends(require_user),
) -> ConnectorStartResponse:
    connector = _get_connector(connector_id)
    state = secrets.token_urlsafe(32)
    expires_at = _now() + timedelta(minutes=STATE_TTL_MINUTES)
    _pending_states[state] = PendingOAuthState(
        connector_id=connector.id,
        user_id=str(current_user.get("id")),
        expires_at=expires_at,
    )

    return ConnectorStartResponse(
        connector_id=connector.id,
        authorization_url=_build_authorization_url(connector, state),
        state=state,
        expires_at=expires_at,
    )


@router.get("/{connector_id}/oauth/callback")
async def connector_oauth_callback(
    connector_id: str,
    code: str = Query(..., min_length=1),
    state: str = Query(..., min_length=1),
) -> dict:
    connector = _get_connector(connector_id)
    pending = _pending_states.pop(state, None)
    if not pending or pending.connector_id != connector.id or pending.expires_at <= _now():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired connector authorization state",
        )

    # Token exchange and source ingestion are intentionally separate follow-up steps.
    # This callback validates the flow and records a pending connection marker only.
    _connections[_connection_key(pending.user_id, connector.id)] = StoredConnection(
        connector_id=connector.id,
        user_id=pending.user_id,
        connected_at=_now(),
        scopes=connector.scopes,
    )
    return {
        "status": "connected",
        "connector_id": connector.id,
        "detail": f"{connector.name} authorization received",
    }


@router.post("/{connector_id}/disconnect", response_model=ConnectorDisconnectResponse)
async def disconnect_connector(
    connector_id: str,
    current_user: dict = Depends(require_user),
) -> ConnectorDisconnectResponse:
    connector = _get_connector(connector_id)
    key = _connection_key(str(current_user.get("id")), connector.id)
    disconnected = _connections.pop(key, None) is not None
    return ConnectorDisconnectResponse(connector_id=connector.id, disconnected=disconnected)
