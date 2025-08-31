"""Trade execution data models."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any, List
from decimal import Decimal


class OrderSide(Enum):
    """Order side (back or lay)."""
    BACK = "back"
    LAY = "lay"


class OrderType(Enum):
    """Order type."""
    LIMIT = "limit"  # Standard limit order
    MARKET = "market"  # Take best available price
    FILL_OR_KILL = "fill_or_kill"  # Complete fill or cancel
    ICEBERG = "iceberg"  # Hide order size


class OrderStatus(Enum):
    """Order status."""
    PENDING = "pending"
    SUBMITTED = "submitted"
    PARTIALLY_MATCHED = "partially_matched"
    MATCHED = "matched"
    CANCELLED = "cancelled"
    FAILED = "failed"
    EXPIRED = "expired"


class ExecutionStrategy(Enum):
    """Execution strategy."""
    AGGRESSIVE = "aggressive"  # Cross the spread immediately
    PASSIVE = "passive"  # Join the queue at best price
    ICEBERG = "iceberg"  # Hide large order size
    TWAP = "twap"  # Time-weighted average price
    SMART = "smart"  # Intelligent routing


class PersistenceType(Enum):
    """Order persistence type."""
    LAPSE = "lapse"  # Cancel at in-play
    PERSIST = "persist"  # Keep at in-play
    MARKET_ON_CLOSE = "market_on_close"  # Market order on close


@dataclass
class TradeInstruction:
    """Standardized trade instruction across all providers."""
    
    # Required fields
    market_id: str
    selection_id: str  # Runner ID or selection identifier
    side: OrderSide
    size: Decimal  # Stake amount
    
    # Optional fields
    price: Optional[Decimal] = None  # None for market orders
    order_type: OrderType = OrderType.LIMIT
    strategy: ExecutionStrategy = ExecutionStrategy.SMART
    persistence: PersistenceType = PersistenceType.LAPSE
    
    # Constraints
    min_fill_size: Optional[Decimal] = None  # For partial fills
    max_slippage: Optional[Decimal] = None  # Max price slippage allowed
    time_in_force: Optional[int] = None  # Seconds before auto-cancel
    
    # Metadata
    client_ref: Optional[str] = None  # Client reference
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def validate(self) -> bool:
        """Validate instruction parameters."""
        if self.size <= 0:
            raise ValueError("Size must be positive")
        
        if self.order_type == OrderType.LIMIT and not self.price:
            raise ValueError("Limit orders require a price")
        
        if self.price and self.price <= 0:
            raise ValueError("Price must be positive")
        
        if self.max_slippage and self.max_slippage < 0:
            raise ValueError("Max slippage cannot be negative")
        
        return True


@dataclass
class Order:
    """Pending order details."""
    
    # Identification
    order_id: str  # Internal order ID
    provider_order_id: Optional[str] = None  # Provider's order ID
    instruction: Optional[TradeInstruction] = None
    
    # Status
    status: OrderStatus = OrderStatus.PENDING
    provider: str = ""
    
    # Amounts
    requested_size: Decimal = Decimal("0")
    matched_size: Decimal = Decimal("0")
    remaining_size: Decimal = Decimal("0")
    cancelled_size: Decimal = Decimal("0")
    lapsed_size: Decimal = Decimal("0")
    
    # Prices
    requested_price: Optional[Decimal] = None
    average_matched_price: Optional[Decimal] = None
    
    # Timestamps
    created_at: datetime = field(default_factory=datetime.now)
    submitted_at: Optional[datetime] = None
    matched_at: Optional[datetime] = None
    cancelled_at: Optional[datetime] = None
    updated_at: datetime = field(default_factory=datetime.now)
    
    # Error handling
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    retry_count: int = 0
    
    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def is_complete(self) -> bool:
        """Check if order is complete."""
        return self.status in [
            OrderStatus.MATCHED,
            OrderStatus.CANCELLED,
            OrderStatus.FAILED,
            OrderStatus.EXPIRED
        ]
    
    @property
    def fill_percentage(self) -> Decimal:
        """Calculate fill percentage."""
        if self.requested_size == 0:
            return Decimal("0")
        return (self.matched_size / self.requested_size) * 100


@dataclass
class Bet:
    """Matched bet details."""
    
    # Identification
    bet_id: str  # Provider's bet ID
    order_id: str  # Related order ID
    market_id: str
    selection_id: str
    provider: str
    
    # Details
    side: OrderSide
    price: Decimal
    size: Decimal
    matched_date: datetime
    
    # Settlement
    is_settled: bool = False
    profit_loss: Optional[Decimal] = None
    commission: Optional[Decimal] = None
    settled_date: Optional[datetime] = None
    
    # Status
    is_void: bool = False
    void_reason: Optional[str] = None
    
    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def liability(self) -> Decimal:
        """Calculate liability for lay bets."""
        if self.side == OrderSide.LAY:
            return self.size * (self.price - 1)
        return self.size


@dataclass
class ExecutionReport:
    """Execution status report."""
    
    # Identification
    report_id: str
    order_id: str
    instruction: TradeInstruction
    
    # Status
    status: OrderStatus
    provider: str
    
    # Execution details
    executed_size: Decimal = Decimal("0")
    executed_price: Optional[Decimal] = None
    remaining_size: Decimal = Decimal("0")
    
    # Fills
    fills: List["Fill"] = field(default_factory=list)
    
    # Timing
    submitted_at: datetime = field(default_factory=datetime.now)
    executed_at: Optional[datetime] = None
    latency_ms: Optional[float] = None
    
    # Error handling
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    
    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def is_successful(self) -> bool:
        """Check if execution was successful."""
        return self.status in [OrderStatus.MATCHED, OrderStatus.PARTIALLY_MATCHED]
    
    @property
    def average_price(self) -> Optional[Decimal]:
        """Calculate average execution price."""
        if not self.fills:
            return self.executed_price
        
        total_value = sum(f.size * f.price for f in self.fills)
        total_size = sum(f.size for f in self.fills)
        
        if total_size == 0:
            return None
        
        return total_value / total_size


@dataclass
class Fill:
    """Individual fill in an order."""
    
    fill_id: str
    size: Decimal
    price: Decimal
    timestamp: datetime
    commission: Decimal = Decimal("0")
    
    @property
    def value(self) -> Decimal:
        """Calculate fill value."""
        return self.size * self.price


@dataclass
class TradingSession:
    """Trading session with statistics."""
    
    session_id: str
    provider: str
    started_at: datetime
    
    # Statistics
    total_orders: int = 0
    successful_orders: int = 0
    failed_orders: int = 0
    cancelled_orders: int = 0
    
    total_volume: Decimal = Decimal("0")
    total_matched: Decimal = Decimal("0")
    total_commission: Decimal = Decimal("0")
    
    # Current positions
    open_orders: List[Order] = field(default_factory=list)
    matched_bets: List[Bet] = field(default_factory=list)
    
    # Risk metrics
    max_exposure: Decimal = Decimal("0")
    current_exposure: Decimal = Decimal("0")
    
    # Metadata
    ended_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def success_rate(self) -> float:
        """Calculate order success rate."""
        if self.total_orders == 0:
            return 0.0
        return (self.successful_orders / self.total_orders) * 100
    
    @property
    def is_active(self) -> bool:
        """Check if session is active."""
        return self.ended_at is None


@dataclass
class RiskLimits:
    """Risk management limits."""
    
    # Order limits
    max_order_size: Decimal = Decimal("100")
    max_market_exposure: Decimal = Decimal("1000")
    max_selection_exposure: Decimal = Decimal("500")
    
    # Rate limits
    max_orders_per_minute: int = 10
    max_orders_per_market: int = 50
    
    # Price limits
    min_back_price: Decimal = Decimal("1.01")
    max_back_price: Decimal = Decimal("1000")
    min_lay_price: Decimal = Decimal("1.01")
    max_lay_price: Decimal = Decimal("1000")
    
    # Time limits
    min_time_to_start: int = 60  # Seconds before event start
    
    # Loss limits
    max_daily_loss: Decimal = Decimal("100")
    max_market_loss: Decimal = Decimal("50")
    
    def validate_order(self, instruction: TradeInstruction) -> tuple[bool, Optional[str]]:
        """
        Validate order against risk limits.
        
        Returns:
            Tuple of (is_valid, error_message)
        """
        # Check order size
        if instruction.size > self.max_order_size:
            return False, f"Order size {instruction.size} exceeds max {self.max_order_size}"
        
        # Check price limits
        if instruction.price:
            if instruction.side == OrderSide.BACK:
                if instruction.price < self.min_back_price or instruction.price > self.max_back_price:
                    return False, f"Back price {instruction.price} outside limits"
            else:  # LAY
                if instruction.price < self.min_lay_price or instruction.price > self.max_lay_price:
                    return False, f"Lay price {instruction.price} outside limits"
        
        return True, None


@dataclass
class TradeEvent:
    """Trading event for audit trail."""
    
    event_id: str
    event_type: str  # order_placed, order_matched, etc.
    timestamp: datetime
    
    # Related entities
    order_id: Optional[str] = None
    bet_id: Optional[str] = None
    market_id: Optional[str] = None
    
    # Event data
    provider: Optional[str] = None
    data: Dict[str, Any] = field(default_factory=dict)
    
    # User info
    user_id: Optional[str] = None
    ip_address: Optional[str] = None
    
    def to_audit_log(self) -> str:
        """Convert to audit log format."""
        return (
            f"[{self.timestamp.isoformat()}] "
            f"{self.event_type} "
            f"order={self.order_id} "
            f"provider={self.provider} "
            f"data={self.data}"
        )