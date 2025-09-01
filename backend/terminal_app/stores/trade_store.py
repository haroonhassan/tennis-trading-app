"""Trade execution store for terminal app."""

import asyncio
from typing import Dict, List, Optional, Callable
from decimal import Decimal
from collections import deque
from ..models import Trade, OrderSide


class TradeStore:
    """Store and manage trade executions."""
    
    def __init__(self, max_history: int = 500):
        self.trades: deque = deque(maxlen=max_history)
        self.pending_orders: Dict[str, Trade] = {}
        self._observers: List[Callable] = []
        self._lock = asyncio.Lock()
        self._trade_counter = 0
    
    async def add_trade(self, trade_data: Dict) -> Trade:
        """Add a new trade."""
        async with self._lock:
            self._trade_counter += 1
            trade_id = f"TRD_{self._trade_counter:06d}"
            
            trade = Trade(
                trade_id=trade_id,
                match_id=trade_data['match_id'],
                selection_id=trade_data['selection_id'],
                selection_name=trade_data['selection_name'],
                side=OrderSide[trade_data['side']],
                stake=Decimal(str(trade_data['stake'])),
                odds=Decimal(str(trade_data['odds'])),
                status=trade_data.get('status', 'EXECUTED')
            )
            
            if 'pnl' in trade_data:
                trade.pnl = Decimal(str(trade_data['pnl']))
            if 'commission' in trade_data:
                trade.commission = Decimal(str(trade_data['commission']))
            
            self.trades.append(trade)
            
            # If it's a pending order, add to pending dict
            if trade.status == 'PENDING':
                self.pending_orders[trade_id] = trade
            
            await self._notify_observers()
            return trade
    
    async def update_trade_status(self, trade_id: str, status: str, **kwargs) -> None:
        """Update trade status."""
        async with self._lock:
            # Check pending orders
            if trade_id in self.pending_orders:
                trade = self.pending_orders[trade_id]
                trade.status = status
                
                if status in ['EXECUTED', 'CANCELLED', 'REJECTED']:
                    del self.pending_orders[trade_id]
                
                if 'pnl' in kwargs:
                    trade.pnl = Decimal(str(kwargs['pnl']))
                if 'commission' in kwargs:
                    trade.commission = Decimal(str(kwargs['commission']))
                
                await self._notify_observers()
    
    def get_recent_trades(self, count: int = 50) -> List[Trade]:
        """Get recent trades."""
        return list(self.trades)[-count:]
    
    def get_pending_orders(self) -> List[Trade]:
        """Get all pending orders."""
        return list(self.pending_orders.values())
    
    def get_trades_by_match(self, match_id: str) -> List[Trade]:
        """Get trades for a specific match."""
        return [t for t in self.trades if t.match_id == match_id]
    
    def get_trade_stats(self) -> Dict:
        """Get trading statistics."""
        executed_trades = [t for t in self.trades if t.status == 'EXECUTED']
        
        if not executed_trades:
            return {
                'total_trades': 0,
                'winning_trades': 0,
                'losing_trades': 0,
                'win_rate': 0,
                'total_pnl': Decimal("0"),
                'avg_win': Decimal("0"),
                'avg_loss': Decimal("0")
            }
        
        winning_trades = [t for t in executed_trades if t.pnl and t.pnl > 0]
        losing_trades = [t for t in executed_trades if t.pnl and t.pnl < 0]
        
        total_pnl = sum(t.pnl for t in executed_trades if t.pnl)
        avg_win = sum(t.pnl for t in winning_trades) / len(winning_trades) if winning_trades else Decimal("0")
        avg_loss = sum(t.pnl for t in losing_trades) / len(losing_trades) if losing_trades else Decimal("0")
        
        return {
            'total_trades': len(executed_trades),
            'winning_trades': len(winning_trades),
            'losing_trades': len(losing_trades),
            'win_rate': len(winning_trades) / len(executed_trades) * 100 if executed_trades else 0,
            'total_pnl': total_pnl,
            'avg_win': avg_win,
            'avg_loss': avg_loss
        }
    
    def add_observer(self, callback: Callable) -> None:
        """Add an observer for trade changes."""
        self._observers.append(callback)
    
    async def _notify_observers(self) -> None:
        """Notify all observers of trade changes."""
        for observer in self._observers:
            if asyncio.iscoroutinefunction(observer):
                await observer()
            else:
                observer()