"""Universal data models for provider-agnostic streaming."""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from datetime import datetime
from enum import Enum


class StreamStatus(Enum):
    """Stream connection status."""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    RECONNECTING = "reconnecting"
    ERROR = "error"


class MessageType(Enum):
    """Types of streaming messages."""
    CONNECTION = "connection"
    SUBSCRIPTION = "subscription"
    HEARTBEAT = "heartbeat"
    MARKET_CHANGE = "market_change"
    ORDER_CHANGE = "order_change"
    ERROR = "error"
    STATUS = "status"


class Side(Enum):
    """Betting side."""
    BACK = "back"
    LAY = "lay"


@dataclass
class PriceVolume:
    """Price and volume tuple."""
    price: float
    volume: float
    
    def __repr__(self):
        return f"{self.price}@{self.volume:.2f}"


@dataclass
class RunnerPrices:
    """Prices for a single runner/selection."""
    runner_id: str
    runner_name: Optional[str] = None
    back_prices: List[PriceVolume] = field(default_factory=list)
    lay_prices: List[PriceVolume] = field(default_factory=list)
    last_traded_price: Optional[float] = None
    total_matched: Optional[float] = None
    available_to_back: Optional[float] = None
    available_to_lay: Optional[float] = None
    line: Optional[float] = None  # For handicap/total markets
    
    @property
    def best_back(self) -> Optional[PriceVolume]:
        """Get best back price (highest)."""
        return self.back_prices[0] if self.back_prices else None
    
    @property
    def best_lay(self) -> Optional[PriceVolume]:
        """Get best lay price (lowest)."""
        return self.lay_prices[0] if self.lay_prices else None


@dataclass
class MarketPrices:
    """Market prices snapshot."""
    market_id: str
    market_name: Optional[str] = None
    event_name: Optional[str] = None
    runners: Dict[str, RunnerPrices] = field(default_factory=dict)
    total_matched: Optional[float] = None
    total_available: Optional[float] = None
    in_play: bool = False
    timestamp: datetime = field(default_factory=datetime.now)
    
    def get_runner(self, runner_id: str) -> Optional[RunnerPrices]:
        """Get runner prices by ID."""
        return self.runners.get(runner_id)


@dataclass
class StreamMessage:
    """Universal streaming message format."""
    type: MessageType
    timestamp: datetime
    provider: str
    data: Any = None
    market_id: Optional[str] = None
    error: Optional[str] = None
    raw_message: Optional[Dict] = None
    
    @classmethod
    def connection_message(cls, provider: str, status: str, **kwargs):
        """Create a connection status message."""
        return cls(
            type=MessageType.CONNECTION,
            timestamp=datetime.now(),
            provider=provider,
            data={"status": status, **kwargs}
        )
    
    @classmethod
    def heartbeat_message(cls, provider: str):
        """Create a heartbeat message."""
        return cls(
            type=MessageType.HEARTBEAT,
            timestamp=datetime.now(),
            provider=provider
        )
    
    @classmethod
    def market_change_message(cls, provider: str, market_prices: MarketPrices, raw=None):
        """Create a market change message."""
        return cls(
            type=MessageType.MARKET_CHANGE,
            timestamp=datetime.now(),
            provider=provider,
            market_id=market_prices.market_id,
            data=market_prices,
            raw_message=raw
        )
    
    @classmethod
    def error_message(cls, provider: str, error: str, **kwargs):
        """Create an error message."""
        return cls(
            type=MessageType.ERROR,
            timestamp=datetime.now(),
            provider=provider,
            error=error,
            data=kwargs
        )


@dataclass
class StreamConfig:
    """Configuration for streaming connection."""
    conflate_ms: int = 120  # Conflation rate in milliseconds
    heartbeat_ms: int = 5000  # Heartbeat interval
    buffer_size: int = 1024  # Read buffer size
    auto_reconnect: bool = True
    max_reconnect_attempts: int = 5
    reconnect_interval: int = 5  # Seconds between reconnect attempts
    
    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            "conflate_ms": self.conflate_ms,
            "heartbeat_ms": self.heartbeat_ms,
            "buffer_size": self.buffer_size,
            "auto_reconnect": self.auto_reconnect,
            "max_reconnect_attempts": self.max_reconnect_attempts,
            "reconnect_interval": self.reconnect_interval
        }