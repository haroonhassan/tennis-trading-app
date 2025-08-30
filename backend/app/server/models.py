"""Server models for WebSocket and API communication."""

from enum import Enum
from typing import Any, Dict, Optional
from datetime import datetime
from pydantic import BaseModel


class MessageType(Enum):
    """WebSocket message types."""
    MATCH_UPDATE = "match_update"
    SCORE_UPDATE = "score_update"
    ODDS_UPDATE = "odds_update"
    PROVIDER_STATUS = "provider_status"
    ERROR = "error"
    PING = "ping"
    PONG = "pong"
    SUBSCRIPTION = "subscription"
    UNSUBSCRIPTION = "unsubscription"


class WebSocketMessage(BaseModel):
    """WebSocket message format."""
    type: MessageType
    data: Any
    timestamp: datetime
    provider: Optional[str] = None
    match_id: Optional[str] = None


class ProviderInfo(BaseModel):
    """Provider information."""
    name: str
    status: str
    is_primary: bool
    connected_at: Optional[datetime] = None
    last_update: Optional[datetime] = None
    error_count: int = 0
    last_error: Optional[str] = None


class MatchListResponse(BaseModel):
    """Response for match list endpoint."""
    matches: list
    total: int
    providers: list[str]
    timestamp: datetime


class MatchDetailResponse(BaseModel):
    """Response for match detail endpoint."""
    match: Dict[str, Any]
    score: Optional[Dict[str, Any]] = None
    statistics: Optional[Dict[str, Any]] = None
    providers: list[str]
    timestamp: datetime