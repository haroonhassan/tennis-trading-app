"""Position tracking store for terminal app."""

import asyncio
from typing import Dict, List, Optional, Callable
from decimal import Decimal
from datetime import datetime
from ..models import Position, PositionStatus, OrderSide


class PositionStore:
    """Store and manage trading positions."""
    
    def __init__(self):
        self.positions: Dict[str, Position] = {}
        self._observers: List[Callable] = []
        self._lock = asyncio.Lock()
        self._position_counter = 0
    
    async def add_position(self, position_data: Dict) -> Position:
        """Add a new position."""
        async with self._lock:
            self._position_counter += 1
            position_id = f"POS_{self._position_counter:06d}"
            
            position = Position(
                position_id=position_id,
                match_id=position_data['match_id'],
                selection_id=position_data['selection_id'],
                selection_name=position_data['selection_name'],
                side=OrderSide[position_data['side']],
                stake=Decimal(str(position_data['stake'])),
                odds=Decimal(str(position_data['odds']))
            )
            
            self.positions[position_id] = position
            await self._notify_observers()
            return position
    
    async def update_position(self, position_id: str, updates: Dict) -> None:
        """Update an existing position."""
        async with self._lock:
            if position_id in self.positions:
                position = self.positions[position_id]
                
                if 'current_odds' in updates:
                    position.current_odds = Decimal(str(updates['current_odds']))
                    # Calculate P&L
                    position.pnl = self._calculate_pnl(position)
                
                if 'status' in updates:
                    position.status = PositionStatus[updates['status']]
                    if position.status == PositionStatus.CLOSED:
                        position.closed_at = datetime.now()
                
                await self._notify_observers()
    
    async def close_position(self, position_id: str, closing_odds: Decimal) -> None:
        """Close a position at given odds."""
        async with self._lock:
            if position_id in self.positions:
                position = self.positions[position_id]
                position.current_odds = closing_odds
                position.pnl = self._calculate_pnl(position)
                position.status = PositionStatus.CLOSED
                position.closed_at = datetime.now()
                await self._notify_observers()
    
    def _calculate_pnl(self, position: Position) -> Decimal:
        """Calculate P&L for a position."""
        if not position.current_odds:
            return Decimal("0")
        
        if position.side == OrderSide.BACK:
            # Back bet P&L
            if position.current_odds < position.odds:
                # Can lay at lower odds for profit
                return position.stake * (position.odds - position.current_odds) / position.current_odds
            else:
                # Would need to lay at higher odds for loss
                return -position.stake * (position.current_odds - position.odds) / position.current_odds
        else:
            # Lay bet P&L
            if position.current_odds > position.odds:
                # Can back at higher odds for profit
                return position.stake * (position.current_odds - position.odds) / position.odds
            else:
                # Would need to back at lower odds for loss
                return -position.stake * (position.odds - position.current_odds) / position.odds
    
    def get_position(self, position_id: str) -> Optional[Position]:
        """Get position by ID."""
        return self.positions.get(position_id)
    
    def get_open_positions(self) -> List[Position]:
        """Get all open positions."""
        return [p for p in self.positions.values() if p.status == PositionStatus.OPEN]
    
    def get_positions_by_match(self, match_id: str) -> List[Position]:
        """Get all positions for a match."""
        return [p for p in self.positions.values() if p.match_id == match_id]
    
    def get_total_pnl(self) -> Decimal:
        """Calculate total P&L across all positions."""
        return sum(p.pnl for p in self.positions.values())
    
    def get_realized_pnl(self) -> Decimal:
        """Calculate realized P&L from closed positions."""
        return sum(p.pnl for p in self.positions.values() 
                  if p.status == PositionStatus.CLOSED)
    
    def get_unrealized_pnl(self) -> Decimal:
        """Calculate unrealized P&L from open positions."""
        return sum(p.pnl for p in self.positions.values() 
                  if p.status == PositionStatus.OPEN)
    
    def add_observer(self, callback: Callable) -> None:
        """Add an observer for position changes."""
        self._observers.append(callback)
    
    async def _notify_observers(self) -> None:
        """Notify all observers of position changes."""
        for observer in self._observers:
            if asyncio.iscoroutinefunction(observer):
                await observer()
            else:
                observer()