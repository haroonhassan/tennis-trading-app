"""Data models for terminal trading app."""

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Optional, List, Dict, Any
from enum import Enum


class OrderSide(Enum):
    """Order side enumeration."""
    BACK = "BACK"
    LAY = "LAY"


class PositionStatus(Enum):
    """Position status enumeration."""
    OPEN = "OPEN"
    CLOSED = "CLOSED"
    PARTIALLY_CLOSED = "PARTIALLY_CLOSED"


class MessageType(Enum):
    """WebSocket message types."""
    PRICE_UPDATE = "price_update"
    POSITION_UPDATE = "position_update"
    TRADE_UPDATE = "trade_update"
    MATCH_UPDATE = "match_update"
    SCORE_UPDATE = "score_update"
    CONNECTION = "connection"
    ERROR = "error"
    RISK_UPDATE = "risk_update"


@dataclass
class Match:
    """Tennis match data."""
    match_id: str
    home_player: str
    away_player: str
    score: str = "0-0"
    serving: Optional[str] = None
    status: str = "IN_PLAY"
    tournament: str = ""
    surface: str = ""
    last_update: datetime = field(default_factory=datetime.now)


@dataclass
class PriceData:
    """Price and volume data."""
    selection_id: str
    back_price: Optional[Decimal] = None
    back_volume: Optional[Decimal] = None
    lay_price: Optional[Decimal] = None
    lay_volume: Optional[Decimal] = None
    last_traded: Optional[Decimal] = None
    total_matched: Optional[Decimal] = None
    last_update: datetime = field(default_factory=datetime.now)


@dataclass
class Position:
    """Trading position data."""
    position_id: str
    match_id: str
    selection_id: str
    selection_name: str
    side: OrderSide
    stake: Decimal
    odds: Decimal
    current_odds: Optional[Decimal] = None
    pnl: Decimal = Decimal("0")
    status: PositionStatus = PositionStatus.OPEN
    opened_at: datetime = field(default_factory=datetime.now)
    closed_at: Optional[datetime] = None


@dataclass
class Trade:
    """Trade execution data."""
    trade_id: str
    match_id: str
    selection_id: str
    selection_name: str
    side: OrderSide
    stake: Decimal
    odds: Decimal
    status: str
    executed_at: datetime = field(default_factory=datetime.now)
    pnl: Optional[Decimal] = None
    commission: Optional[Decimal] = None


@dataclass
class RiskMetrics:
    """Risk management metrics."""
    total_exposure: Decimal = Decimal("0")
    max_exposure: Decimal = Decimal("1000")
    daily_pnl: Decimal = Decimal("0")
    daily_loss_limit: Decimal = Decimal("-200")
    open_positions: int = 0
    max_positions: int = 20
    risk_score: int = 0  # 0-100
    trading_enabled: bool = True
    
    @property
    def exposure_used(self) -> float:
        """Calculate exposure usage percentage."""
        if self.max_exposure == 0:
            return 0
        return float(self.total_exposure / self.max_exposure * 100)
    
    @property
    def is_risk_exceeded(self) -> bool:
        """Check if any risk limits are exceeded."""
        return (self.total_exposure >= self.max_exposure or 
                self.daily_pnl <= self.daily_loss_limit or
                self.open_positions >= self.max_positions)