"""Match data store for terminal app."""

import asyncio
from typing import Dict, List, Optional, Callable
from datetime import datetime
from ..models import Match, PriceData


class MatchDataStore:
    """Store and manage match data with real-time updates."""
    
    def __init__(self):
        self.matches: Dict[str, Match] = {}
        self.prices: Dict[str, Dict[str, PriceData]] = {}  # match_id -> selection_id -> price
        self._observers: List[Callable] = []
        self._lock = asyncio.Lock()
    
    async def update_match(self, match_id: str, data: Dict) -> None:
        """Update match data."""
        async with self._lock:
            if match_id not in self.matches:
                self.matches[match_id] = Match(
                    match_id=match_id,
                    home_player=data.get('home_player', 'Player 1'),
                    away_player=data.get('away_player', 'Player 2')
                )
            
            match = self.matches[match_id]
            if 'score' in data:
                match.score = data['score']
            if 'serving' in data:
                match.serving = data['serving']
            if 'status' in data:
                match.status = data['status']
            match.last_update = datetime.now()
            
            await self._notify_observers()
    
    async def update_prices(self, match_id: str, selection_id: str, price_data: Dict) -> None:
        """Update price data for a selection."""
        async with self._lock:
            if match_id not in self.prices:
                self.prices[match_id] = {}
            
            if selection_id not in self.prices[match_id]:
                self.prices[match_id][selection_id] = PriceData(selection_id=selection_id)
            
            price = self.prices[match_id][selection_id]
            
            # Track previous prices for flash effects
            prev_back = price.back_price
            prev_lay = price.lay_price
            
            # Update prices
            if 'back_price' in price_data:
                price.back_price = price_data['back_price']
            if 'back_volume' in price_data:
                price.back_volume = price_data['back_volume']
            if 'lay_price' in price_data:
                price.lay_price = price_data['lay_price']
            if 'lay_volume' in price_data:
                price.lay_volume = price_data['lay_volume']
            if 'last_traded' in price_data:
                price.last_traded = price_data['last_traded']
            
            price.last_update = datetime.now()
            
            # Store price change direction for UI effects
            if prev_back and price.back_price:
                price_data['back_direction'] = 'up' if price.back_price > prev_back else 'down' if price.back_price < prev_back else None
            if prev_lay and price.lay_price:
                price_data['lay_direction'] = 'up' if price.lay_price > prev_lay else 'down' if price.lay_price < prev_lay else None
            
            await self._notify_observers()
    
    def get_match(self, match_id: str) -> Optional[Match]:
        """Get match by ID."""
        return self.matches.get(match_id)
    
    def get_all_matches(self) -> List[Match]:
        """Get all matches."""
        return list(self.matches.values())
    
    def get_prices(self, match_id: str) -> Dict[str, PriceData]:
        """Get all prices for a match."""
        return self.prices.get(match_id, {})
    
    def add_observer(self, callback: Callable) -> None:
        """Add an observer for data changes."""
        self._observers.append(callback)
    
    async def _notify_observers(self) -> None:
        """Notify all observers of data changes."""
        for observer in self._observers:
            if asyncio.iscoroutinefunction(observer):
                await observer()
            else:
                observer()