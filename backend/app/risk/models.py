"""Risk management data models for position tracking and P&L calculation."""

from typing import Dict, List, Optional, Any
from decimal import Decimal
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field


class PositionStatus(str, Enum):
    """Position status."""
    OPEN = "open"
    CLOSED = "closed"
    PARTIALLY_CLOSED = "partially_closed"


class PositionSide(str, Enum):
    """Position side."""
    LONG = "long"  # Back bet
    SHORT = "short"  # Lay bet


class Position(BaseModel):
    """Individual position in a market."""
    position_id: str = Field(..., description="Unique position identifier")
    market_id: str = Field(..., description="Market identifier")
    selection_id: str = Field(..., description="Selection/runner identifier")
    side: PositionSide = Field(..., description="Position side (long/short)")
    
    # Entry details
    entry_price: Decimal = Field(..., description="Average entry price")
    entry_size: Decimal = Field(..., description="Total size entered")
    entry_time: datetime = Field(..., description="Position entry time")
    
    # Current state
    current_size: Decimal = Field(..., description="Current open size")
    exit_price: Optional[Decimal] = Field(None, description="Average exit price")
    exit_size: Decimal = Field(default=Decimal("0"), description="Total size exited")
    last_update: datetime = Field(..., description="Last update time")
    
    # P&L
    realized_pnl: Decimal = Field(default=Decimal("0"), description="Realized P&L")
    unrealized_pnl: Decimal = Field(default=Decimal("0"), description="Unrealized P&L")
    commission: Decimal = Field(default=Decimal("0"), description="Commission paid")
    
    # Status
    status: PositionStatus = Field(..., description="Position status")
    
    # Metadata
    provider: str = Field(..., description="Data provider")
    strategy: Optional[str] = Field(None, description="Strategy name")
    tags: List[str] = Field(default_factory=list, description="Position tags")
    
    class Config:
        use_enum_values = True


class MarketExposure(BaseModel):
    """Market exposure summary."""
    market_id: str = Field(..., description="Market identifier")
    market_name: str = Field(..., description="Market name")
    
    # Exposure by selection
    selection_exposures: Dict[str, Decimal] = Field(
        default_factory=dict,
        description="Max loss by selection ID"
    )
    
    # Net exposure
    net_back_exposure: Decimal = Field(..., description="Total back bet exposure")
    net_lay_liability: Decimal = Field(..., description="Total lay bet liability")
    max_loss: Decimal = Field(..., description="Maximum possible loss")
    
    # Position counts
    open_positions: int = Field(..., description="Number of open positions")
    total_stake: Decimal = Field(..., description="Total amount staked")
    
    # Hedge requirements
    hedge_required: bool = Field(default=False, description="Whether hedging is needed")
    hedge_amount: Optional[Decimal] = Field(None, description="Amount to hedge")
    hedge_selection: Optional[str] = Field(None, description="Selection to hedge on")
    hedge_price: Optional[Decimal] = Field(None, description="Suggested hedge price")


class RiskMetrics(BaseModel):
    """Risk metrics for a portfolio."""
    timestamp: datetime = Field(..., description="Calculation timestamp")
    
    # Portfolio metrics
    total_exposure: Decimal = Field(..., description="Total portfolio exposure")
    max_drawdown: Decimal = Field(..., description="Maximum drawdown")
    var_95: Decimal = Field(..., description="Value at Risk (95% confidence)")
    expected_value: Decimal = Field(..., description="Expected value")
    
    # Position metrics
    num_open_positions: int = Field(..., description="Number of open positions")
    num_markets: int = Field(..., description="Number of active markets")
    largest_position: Decimal = Field(..., description="Largest position size")
    concentration_risk: Decimal = Field(..., description="Position concentration (0-1)")
    
    # Greeks (for options-like analysis)
    portfolio_delta: Decimal = Field(..., description="Portfolio delta")
    portfolio_gamma: Decimal = Field(..., description="Portfolio gamma")
    portfolio_theta: Decimal = Field(..., description="Portfolio theta (time decay)")
    
    # Risk limits
    exposure_limit_used: Decimal = Field(..., description="% of exposure limit used")
    position_limit_used: Decimal = Field(..., description="% of position limit used")
    loss_limit_used: Decimal = Field(..., description="% of daily loss limit used")
    
    # Alerts
    risk_score: Decimal = Field(..., description="Overall risk score (0-100)")
    alerts: List[str] = Field(default_factory=list, description="Active risk alerts")


class PnLStatement(BaseModel):
    """P&L statement for a period."""
    period_start: datetime = Field(..., description="Period start time")
    period_end: datetime = Field(..., description="Period end time")
    
    # P&L breakdown
    gross_pnl: Decimal = Field(..., description="Gross P&L before costs")
    commission: Decimal = Field(..., description="Total commission")
    net_pnl: Decimal = Field(..., description="Net P&L after costs")
    
    # Realized vs unrealized
    realized_pnl: Decimal = Field(..., description="Realized P&L")
    unrealized_pnl: Decimal = Field(..., description="Unrealized P&L")
    
    # By market
    pnl_by_market: Dict[str, Decimal] = Field(
        default_factory=dict,
        description="P&L breakdown by market"
    )
    
    # By strategy
    pnl_by_strategy: Dict[str, Decimal] = Field(
        default_factory=dict,
        description="P&L breakdown by strategy"
    )
    
    # Statistics
    num_trades: int = Field(..., description="Number of trades")
    win_rate: Decimal = Field(..., description="Win rate percentage")
    avg_win: Decimal = Field(..., description="Average winning trade")
    avg_loss: Decimal = Field(..., description="Average losing trade")
    sharpe_ratio: Optional[Decimal] = Field(None, description="Sharpe ratio")
    
    # Turnover
    total_volume: Decimal = Field(..., description="Total volume traded")
    total_stake: Decimal = Field(..., description="Total amount staked")


class ExposureReport(BaseModel):
    """Comprehensive exposure report."""
    timestamp: datetime = Field(..., description="Report timestamp")
    account_balance: Decimal = Field(..., description="Current account balance")
    available_balance: Decimal = Field(..., description="Available for trading")
    
    # Market exposures
    market_exposures: List[MarketExposure] = Field(
        default_factory=list,
        description="Exposure by market"
    )
    
    # Aggregate exposure
    total_exposure: Decimal = Field(..., description="Total exposure across markets")
    total_liability: Decimal = Field(..., description="Total potential liability")
    net_exposure: Decimal = Field(..., description="Net exposure (backs - lays)")
    
    # Risk metrics
    risk_metrics: RiskMetrics = Field(..., description="Current risk metrics")
    
    # P&L
    daily_pnl: PnLStatement = Field(..., description="Today's P&L")
    open_pnl: Decimal = Field(..., description="Open P&L across all positions")
    
    # Limits
    exposure_limit: Decimal = Field(..., description="Maximum exposure limit")
    exposure_limit_remaining: Decimal = Field(..., description="Remaining exposure")
    daily_loss_limit: Decimal = Field(..., description="Daily loss limit")
    daily_loss_limit_remaining: Decimal = Field(..., description="Remaining loss limit")
    
    # Warnings
    warnings: List[str] = Field(default_factory=list, description="Risk warnings")
    breaches: List[str] = Field(default_factory=list, description="Limit breaches")


class HedgeInstruction(BaseModel):
    """Instruction for hedging a position."""
    market_id: str = Field(..., description="Market to hedge in")
    selection_id: str = Field(..., description="Selection to bet on")
    side: PositionSide = Field(..., description="Hedge side")
    size: Decimal = Field(..., description="Hedge size")
    price: Decimal = Field(..., description="Target price")
    reason: str = Field(..., description="Reason for hedge")
    urgency: str = Field(..., description="Urgency level (low/medium/high/critical)")
    
    # Optional parameters
    min_price: Optional[Decimal] = Field(None, description="Minimum acceptable price")
    max_price: Optional[Decimal] = Field(None, description="Maximum acceptable price")
    time_limit: Optional[int] = Field(None, description="Seconds to execute")


class RiskAlert(BaseModel):
    """Risk alert notification."""
    alert_id: str = Field(..., description="Alert identifier")
    timestamp: datetime = Field(..., description="Alert time")
    severity: str = Field(..., description="Severity (info/warning/critical)")
    category: str = Field(..., description="Alert category")
    message: str = Field(..., description="Alert message")
    
    # Context
    market_id: Optional[str] = Field(None, description="Related market")
    position_id: Optional[str] = Field(None, description="Related position")
    metric_name: Optional[str] = Field(None, description="Metric that triggered alert")
    metric_value: Optional[Decimal] = Field(None, description="Metric value")
    threshold: Optional[Decimal] = Field(None, description="Threshold breached")
    
    # Actions
    suggested_action: Optional[str] = Field(None, description="Suggested action")
    auto_action_taken: Optional[str] = Field(None, description="Automatic action taken")
    requires_confirmation: bool = Field(default=False, description="Needs user confirmation")


class PositionUpdate(BaseModel):
    """Position update event."""
    timestamp: datetime = Field(..., description="Update time")
    position_id: str = Field(..., description="Position identifier")
    update_type: str = Field(..., description="Update type (open/partial_close/close/adjust)")
    
    # Changes
    size_change: Optional[Decimal] = Field(None, description="Size change")
    price: Optional[Decimal] = Field(None, description="Execution price")
    pnl_impact: Optional[Decimal] = Field(None, description="P&L impact")
    
    # New state
    new_size: Decimal = Field(..., description="New position size")
    new_avg_price: Decimal = Field(..., description="New average price")
    new_pnl: Decimal = Field(..., description="New total P&L")
    
    # Source
    source: str = Field(..., description="Update source (trade/market/manual)")
    order_id: Optional[str] = Field(None, description="Related order ID")