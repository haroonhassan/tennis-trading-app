"""Abstract base class for data providers."""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime
from dataclasses import dataclass
import logging


@dataclass
class Match:
    """Tennis match data model."""
    id: str
    event_name: str
    competition: str
    market_start_time: datetime
    status: str
    home_player: str
    away_player: str
    metadata: Dict[str, Any] = None


@dataclass
class PriceData:
    """Market price data model."""
    selection_id: str
    selection_name: str
    back_prices: List[Dict[str, float]]  # [{"price": x, "size": y}]
    lay_prices: List[Dict[str, float]]
    last_price_traded: Optional[float] = None
    total_matched: Optional[float] = None
    available_to_back: Optional[float] = None
    available_to_lay: Optional[float] = None


@dataclass
class Score:
    """Match score data model."""
    match_id: str
    home_score: Dict[str, Any]  # {"sets": 2, "games": 5, "points": "30"}
    away_score: Dict[str, Any]
    current_set: int
    server: Optional[str] = None
    timestamp: datetime = None


@dataclass
class MatchStats:
    """Match statistics data model."""
    match_id: str
    home_stats: Dict[str, Any]  # {"aces": 5, "double_faults": 2, etc.}
    away_stats: Dict[str, Any]
    timestamp: datetime = None


class BaseDataProvider(ABC):
    """Abstract base class for all betting data providers."""
    
    def __init__(self, logger: Optional[logging.Logger] = None):
        """Initialize the provider with optional logger."""
        self.logger = logger or logging.getLogger(self.__class__.__name__)
        self.is_authenticated = False
        self.session_token = None
        
    @abstractmethod
    def authenticate(self) -> bool:
        """
        Authenticate with the provider.
        
        Returns:
            bool: True if authentication successful, False otherwise
        """
        pass
    
    @abstractmethod
    def get_live_matches(self, sport: str = "tennis") -> List[Match]:
        """
        Get list of live matches.
        
        Args:
            sport: Sport to filter by (default: tennis)
            
        Returns:
            List of Match objects
        """
        pass
    
    @abstractmethod
    def subscribe_to_prices(
        self, 
        market_ids: List[str], 
        callback: Callable[[str, PriceData], None]
    ) -> bool:
        """
        Subscribe to real-time price updates for given markets.
        
        Args:
            market_ids: List of market IDs to subscribe to
            callback: Function to call with price updates (market_id, price_data)
            
        Returns:
            bool: True if subscription successful
        """
        pass
    
    @abstractmethod
    def unsubscribe_from_prices(self, market_ids: List[str]) -> bool:
        """
        Unsubscribe from price updates.
        
        Args:
            market_ids: List of market IDs to unsubscribe from
            
        Returns:
            bool: True if unsubscription successful
        """
        pass
    
    @abstractmethod
    def get_match_scores(self, match_id: str) -> Optional[Score]:
        """
        Get current score for a match.
        
        Args:
            match_id: Match identifier
            
        Returns:
            Score object or None if not available
        """
        pass
    
    @abstractmethod
    def get_match_stats(self, match_id: str) -> Optional[MatchStats]:
        """
        Get statistics for a match.
        
        Args:
            match_id: Match identifier
            
        Returns:
            MatchStats object or None if not available
        """
        pass
    
    @abstractmethod
    def get_account_balance(self) -> Dict[str, float]:
        """
        Get account balance information.
        
        Returns:
            Dictionary with balance information
        """
        pass
    
    @abstractmethod
    def place_bet(
        self,
        market_id: str,
        selection_id: str,
        side: str,  # "back" or "lay"
        price: float,
        size: float
    ) -> Dict[str, Any]:
        """
        Place a bet.
        
        Args:
            market_id: Market identifier
            selection_id: Selection identifier
            side: "back" or "lay"
            price: Requested price
            size: Stake amount
            
        Returns:
            Dictionary with bet placement result
        """
        pass
    
    @abstractmethod
    def cancel_bet(self, bet_id: str, size_reduction: Optional[float] = None) -> bool:
        """
        Cancel or reduce a bet.
        
        Args:
            bet_id: Bet identifier
            size_reduction: Optional partial cancel amount
            
        Returns:
            bool: True if cancellation successful
        """
        pass
    
    @abstractmethod
    def get_open_bets(self) -> List[Dict[str, Any]]:
        """
        Get list of open bets.
        
        Returns:
            List of open bet dictionaries
        """
        pass
    
    @abstractmethod
    def keep_alive(self) -> bool:
        """
        Keep the session alive.
        
        Returns:
            bool: True if session is still valid
        """
        pass
    
    def is_connected(self) -> bool:
        """Check if provider is connected and authenticated."""
        return self.is_authenticated
    
    def disconnect(self) -> None:
        """Disconnect from the provider."""
        self.is_authenticated = False
        self.session_token = None
        self.logger.info("Disconnected from provider")