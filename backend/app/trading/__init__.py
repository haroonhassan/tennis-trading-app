"""Trading execution module for tennis trading system."""

from .models import (
    TradeInstruction,
    Order,
    Bet,
    ExecutionReport,
    Fill,
    OrderSide,
    OrderType,
    OrderStatus,
    ExecutionStrategy,
    PersistenceType,
    RiskLimits,
    TradeEvent,
    TradingSession
)

from .executor import TradeExecutor
from .strategies import (
    BaseExecutionStrategy,
    AggressiveStrategy,
    PassiveStrategy,
    IcebergStrategy,
    TWAPStrategy,
    SmartStrategy,
    ExecutionStrategyFactory
)
from .audit import TradeAuditLogger, TradeEventBus

__all__ = [
    # Models
    "TradeInstruction",
    "Order",
    "Bet",
    "ExecutionReport",
    "Fill",
    "OrderSide",
    "OrderType",
    "OrderStatus",
    "ExecutionStrategy",
    "PersistenceType",
    "RiskLimits",
    "TradeEvent",
    "TradingSession",
    
    # Executor
    "TradeExecutor",
    
    # Strategies
    "BaseExecutionStrategy",
    "AggressiveStrategy",
    "PassiveStrategy",
    "IcebergStrategy",
    "TWAPStrategy",
    "SmartStrategy",
    "ExecutionStrategyFactory",
    
    # Audit
    "TradeAuditLogger",
    "TradeEventBus"
]