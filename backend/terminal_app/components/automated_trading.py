"""Automated trading features for risk management."""

from decimal import Decimal
from typing import Dict, List, Optional, Callable
from datetime import datetime
from dataclasses import dataclass
from enum import Enum

from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.console import Group

from ..models import Position, Trade, OrderSide


class OrderType(Enum):
    """Types of automated orders."""
    STOP_LOSS = "stop_loss"
    TAKE_PROFIT = "take_profit"
    TRAILING_STOP = "trailing_stop"
    OCO = "one_cancels_other"  # One-Cancels-Other order
    ICEBERG = "iceberg"  # Large order split into smaller chunks


@dataclass
class AutomatedOrder:
    """Automated order configuration."""
    id: str
    position_id: str
    order_type: OrderType
    trigger_price: Decimal
    size: Decimal
    side: OrderSide
    status: str = "PENDING"
    created_at: datetime = None
    triggered_at: Optional[datetime] = None
    trail_amount: Optional[Decimal] = None  # For trailing stops
    trail_percent: Optional[Decimal] = None  # For percentage-based trailing
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()


class AutomatedTradingManager:
    """Manages automated trading features."""
    
    def __init__(self):
        self.automated_orders: Dict[str, AutomatedOrder] = {}
        self.position_monitors: Dict[str, List[AutomatedOrder]] = {}
        self.callbacks: Dict[str, Callable] = {}
        
        # Configuration
        self.config = {
            'auto_stop_loss': True,
            'default_stop_loss_pct': Decimal('10'),  # 10% stop loss
            'auto_take_profit': False,
            'default_take_profit_pct': Decimal('50'),  # 50% take profit
            'trailing_stop_enabled': False,
            'trailing_stop_distance': Decimal('5'),  # 5% trailing distance
            'partial_close_enabled': True,
            'partial_close_pct': Decimal('50')  # Close 50% at take profit
        }
    
    def create_stop_loss(self, position: Position, stop_price: Optional[Decimal] = None) -> AutomatedOrder:
        """Create a stop loss order for a position."""
        if stop_price is None:
            # Calculate default stop loss price
            if position.side == OrderSide.BACK:
                # For back bets, stop loss triggers when price drops
                stop_price = position.odds * (Decimal('1') - self.config['default_stop_loss_pct'] / Decimal('100'))
            else:
                # For lay bets, stop loss triggers when price rises
                stop_price = position.odds * (Decimal('1') + self.config['default_stop_loss_pct'] / Decimal('100'))
        
        order = AutomatedOrder(
            id=f"SL_{position.position_id}_{datetime.now().timestamp()}",
            position_id=position.position_id,
            order_type=OrderType.STOP_LOSS,
            trigger_price=stop_price,
            size=position.stake,
            side=OrderSide.LAY if position.side == OrderSide.BACK else OrderSide.BACK,
            status="PENDING"
        )
        
        self._add_order(order)
        return order
    
    def create_take_profit(self, position: Position, target_price: Optional[Decimal] = None) -> AutomatedOrder:
        """Create a take profit order for a position."""
        if target_price is None:
            # Calculate default take profit price
            if position.side == OrderSide.BACK:
                # For back bets, take profit when price rises
                target_price = position.odds * (Decimal('1') + self.config['default_take_profit_pct'] / Decimal('100'))
            else:
                # For lay bets, take profit when price drops
                target_price = position.odds * (Decimal('1') - self.config['default_take_profit_pct'] / Decimal('100'))
        
        # Determine size (full or partial)
        size = position.stake
        if self.config['partial_close_enabled']:
            size = position.stake * self.config['partial_close_pct'] / Decimal('100')
        
        order = AutomatedOrder(
            id=f"TP_{position.position_id}_{datetime.now().timestamp()}",
            position_id=position.position_id,
            order_type=OrderType.TAKE_PROFIT,
            trigger_price=target_price,
            size=size,
            side=OrderSide.LAY if position.side == OrderSide.BACK else OrderSide.BACK,
            status="PENDING"
        )
        
        self._add_order(order)
        return order
    
    def create_trailing_stop(self, position: Position, trail_amount: Optional[Decimal] = None) -> AutomatedOrder:
        """Create a trailing stop order."""
        if trail_amount is None:
            trail_amount = self.config['trailing_stop_distance']
        
        # Initial trigger price
        if position.side == OrderSide.BACK:
            trigger_price = position.current_odds - (position.current_odds * trail_amount / Decimal('100'))
        else:
            trigger_price = position.current_odds + (position.current_odds * trail_amount / Decimal('100'))
        
        order = AutomatedOrder(
            id=f"TS_{position.position_id}_{datetime.now().timestamp()}",
            position_id=position.position_id,
            order_type=OrderType.TRAILING_STOP,
            trigger_price=trigger_price,
            size=position.stake,
            side=OrderSide.LAY if position.side == OrderSide.BACK else OrderSide.BACK,
            status="PENDING",
            trail_percent=trail_amount
        )
        
        self._add_order(order)
        return order
    
    def create_oco_order(self, position: Position, stop_price: Decimal, target_price: Decimal) -> tuple[AutomatedOrder, AutomatedOrder]:
        """Create a One-Cancels-Other order pair (stop loss + take profit)."""
        stop_order = self.create_stop_loss(position, stop_price)
        take_profit_order = self.create_take_profit(position, target_price)
        
        # Link the orders
        stop_order.order_type = OrderType.OCO
        take_profit_order.order_type = OrderType.OCO
        
        return stop_order, take_profit_order
    
    def update_trailing_stop(self, order: AutomatedOrder, current_price: Decimal):
        """Update trailing stop trigger price based on favorable price movement."""
        if order.order_type != OrderType.TRAILING_STOP or order.status != "PENDING":
            return
        
        position_id = order.position_id
        # Assuming we have position info (would need to be passed or looked up)
        
        if order.side == OrderSide.LAY:  # Closing a back bet
            # Trail up as price increases
            new_trigger = current_price - (current_price * order.trail_percent / Decimal('100'))
            if new_trigger > order.trigger_price:
                order.trigger_price = new_trigger
        else:  # Closing a lay bet
            # Trail down as price decreases
            new_trigger = current_price + (current_price * order.trail_percent / Decimal('100'))
            if new_trigger < order.trigger_price:
                order.trigger_price = new_trigger
    
    def check_triggers(self, positions: List[Position], current_prices: Dict[str, Decimal]) -> List[AutomatedOrder]:
        """Check if any automated orders should be triggered."""
        triggered = []
        
        for order in self.automated_orders.values():
            if order.status != "PENDING":
                continue
            
            # Find the position
            position = next((p for p in positions if p.position_id == order.position_id), None)
            if not position:
                continue
            
            # Get current price for the selection
            current_price = current_prices.get(position.selection_name, position.current_odds)
            
            # Update trailing stops
            if order.order_type == OrderType.TRAILING_STOP:
                self.update_trailing_stop(order, current_price)
            
            # Check trigger conditions
            should_trigger = False
            
            if order.order_type in [OrderType.STOP_LOSS, OrderType.TRAILING_STOP]:
                if position.side == OrderSide.BACK:
                    # Trigger if price falls below stop
                    should_trigger = current_price <= order.trigger_price
                else:
                    # Trigger if price rises above stop
                    should_trigger = current_price >= order.trigger_price
            
            elif order.order_type == OrderType.TAKE_PROFIT:
                if position.side == OrderSide.BACK:
                    # Trigger if price rises above target
                    should_trigger = current_price >= order.trigger_price
                else:
                    # Trigger if price falls below target
                    should_trigger = current_price <= order.trigger_price
            
            if should_trigger:
                order.status = "TRIGGERED"
                order.triggered_at = datetime.now()
                triggered.append(order)
                
                # Handle OCO orders
                if order.order_type == OrderType.OCO:
                    self._cancel_paired_oco_orders(order)
        
        return triggered
    
    def _add_order(self, order: AutomatedOrder):
        """Add an automated order to the manager."""
        self.automated_orders[order.id] = order
        
        # Track by position
        if order.position_id not in self.position_monitors:
            self.position_monitors[order.position_id] = []
        self.position_monitors[order.position_id].append(order)
    
    def _cancel_paired_oco_orders(self, triggered_order: AutomatedOrder):
        """Cancel other OCO orders for the same position."""
        if triggered_order.position_id in self.position_monitors:
            for order in self.position_monitors[triggered_order.position_id]:
                if order.id != triggered_order.id and order.order_type == OrderType.OCO:
                    order.status = "CANCELLED"
    
    def cancel_order(self, order_id: str):
        """Cancel an automated order."""
        if order_id in self.automated_orders:
            self.automated_orders[order_id].status = "CANCELLED"
    
    def cancel_position_orders(self, position_id: str):
        """Cancel all automated orders for a position."""
        if position_id in self.position_monitors:
            for order in self.position_monitors[position_id]:
                order.status = "CANCELLED"
    
    def get_position_orders(self, position_id: str) -> List[AutomatedOrder]:
        """Get all automated orders for a position."""
        return self.position_monitors.get(position_id, [])
    
    def create_panel(self) -> Panel:
        """Create automated orders panel."""
        active_orders = [o for o in self.automated_orders.values() if o.status == "PENDING"]
        
        if not active_orders:
            return Panel(
                Text("No active automated orders", style="dim"),
                title="🤖 Automated Orders",
                border_style="blue"
            )
        
        table = Table(show_header=True, box=None)
        table.add_column("Type", style="cyan", width=12)
        table.add_column("Position", style="white", width=15)
        table.add_column("Trigger", justify="right", style="yellow")
        table.add_column("Size", justify="right")
        table.add_column("Status", justify="center")
        
        for order in active_orders[:10]:  # Show up to 10
            # Style based on order type
            type_style = {
                OrderType.STOP_LOSS: "red",
                OrderType.TAKE_PROFIT: "green",
                OrderType.TRAILING_STOP: "yellow",
                OrderType.OCO: "magenta"
            }.get(order.order_type, "white")
            
            table.add_row(
                Text(order.order_type.value, style=type_style),
                order.position_id[:12] + "...",
                f"£{order.trigger_price:.2f}",
                f"£{order.size:.2f}",
                Text("●", style="green") + " Active"
            )
        
        return Panel(table, title="🤖 Automated Orders", border_style="blue")


class SmartExecutor:
    """Smart order execution with advanced strategies."""
    
    def __init__(self):
        self.strategies = {
            'MARKET': self._execute_market,
            'LIMIT': self._execute_limit,
            'ICEBERG': self._execute_iceberg,
            'TWAP': self._execute_twap,  # Time-Weighted Average Price
            'VWAP': self._execute_vwap   # Volume-Weighted Average Price
        }
    
    async def execute_order(self, order: Dict, strategy: str = 'MARKET') -> List[Trade]:
        """Execute an order using the specified strategy."""
        if strategy not in self.strategies:
            strategy = 'MARKET'
        
        return await self.strategies[strategy](order)
    
    async def _execute_market(self, order: Dict) -> List[Trade]:
        """Execute at market price immediately."""
        # This would connect to the actual trading API
        trades = []
        # Implementation would execute the trade
        return trades
    
    async def _execute_limit(self, order: Dict) -> List[Trade]:
        """Execute at specified limit price."""
        trades = []
        # Implementation would place limit order
        return trades
    
    async def _execute_iceberg(self, order: Dict) -> List[Trade]:
        """Split large order into smaller chunks."""
        total_size = order['size']
        chunk_size = Decimal('10')  # Default chunk size
        trades = []
        
        remaining = total_size
        while remaining > 0:
            current_chunk = min(chunk_size, remaining)
            # Execute chunk
            chunk_order = order.copy()
            chunk_order['size'] = current_chunk
            chunk_trades = await self._execute_market(chunk_order)
            trades.extend(chunk_trades)
            remaining -= current_chunk
        
        return trades
    
    async def _execute_twap(self, order: Dict) -> List[Trade]:
        """Execute over time period with equal time intervals."""
        trades = []
        # Implementation would split order over time
        return trades
    
    async def _execute_vwap(self, order: Dict) -> List[Trade]:
        """Execute based on volume patterns."""
        trades = []
        # Implementation would execute based on volume
        return trades