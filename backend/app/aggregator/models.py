"""Models for data aggregation across providers."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
from enum import Enum

from ..providers.tennis_models import (
    TennisMatch,
    TennisScore,
    MatchStatistics,
    Player,
    MatchStatus
)


class DataQualityStatus(Enum):
    """Data quality status levels."""
    EXCELLENT = "excellent"  # < 100ms latency, recent update
    GOOD = "good"  # < 500ms latency, update within 30s
    FAIR = "fair"  # < 1s latency, update within 1min
    POOR = "poor"  # > 1s latency or stale data
    UNAVAILABLE = "unavailable"


@dataclass
class DataQuality:
    """Data quality indicators for a provider."""
    provider: str
    status: DataQualityStatus
    latency_ms: float
    last_update: datetime
    error_count: int = 0
    is_primary: bool = False
    confidence_score: float = 1.0  # 0-1 confidence in data accuracy
    
    @property
    def age_seconds(self) -> float:
        """Get age of data in seconds."""
        return (datetime.now() - self.last_update).total_seconds()
    
    def calculate_quality_score(self) -> float:
        """
        Calculate overall quality score (0-1).
        
        Returns:
            Quality score between 0 and 1
        """
        # Latency component (0-1)
        if self.latency_ms < 100:
            latency_score = 1.0
        elif self.latency_ms < 500:
            latency_score = 0.8
        elif self.latency_ms < 1000:
            latency_score = 0.6
        else:
            latency_score = 0.3
        
        # Freshness component (0-1)
        age = self.age_seconds
        if age < 10:
            freshness_score = 1.0
        elif age < 30:
            freshness_score = 0.8
        elif age < 60:
            freshness_score = 0.6
        else:
            freshness_score = 0.3
        
        # Error component (0-1)
        if self.error_count == 0:
            error_score = 1.0
        elif self.error_count < 3:
            error_score = 0.7
        else:
            error_score = 0.3
        
        # Weight the components
        quality = (
            latency_score * 0.3 +
            freshness_score * 0.4 +
            error_score * 0.2 +
            self.confidence_score * 0.1
        )
        
        # Bonus for primary provider
        if self.is_primary:
            quality = min(1.0, quality * 1.1)
        
        return quality


@dataclass
class ProviderPrice:
    """Price data from a specific provider."""
    provider: str
    player1_back: float  # Best back price for player 1
    player1_lay: float  # Best lay price for player 1
    player2_back: float  # Best back price for player 2
    player2_lay: float  # Best lay price for player 2
    
    # Optional volume data
    player1_back_volume: Optional[float] = None
    player1_lay_volume: Optional[float] = None
    player2_back_volume: Optional[float] = None
    player2_lay_volume: Optional[float] = None
    
    # Metadata
    timestamp: datetime = field(default_factory=datetime.now)
    market_id: Optional[str] = None
    is_suspended: bool = False
    
    @property
    def spread_player1(self) -> float:
        """Calculate spread for player 1."""
        return self.player1_lay - self.player1_back
    
    @property
    def spread_player2(self) -> float:
        """Calculate spread for player 2."""
        return self.player2_lay - self.player2_back
    
    @property
    def overround(self) -> float:
        """Calculate the overround (book percentage)."""
        if self.player1_back and self.player2_back:
            return (1/self.player1_back + 1/self.player2_back) * 100
        return 0


@dataclass
class PriceComparison:
    """Comparison of prices across providers."""
    match_id: str
    
    # Best prices across all providers
    best_back_player1: float
    best_back_player1_provider: str
    best_lay_player1: float
    best_lay_player1_provider: str
    
    best_back_player2: float
    best_back_player2_provider: str
    best_lay_player2: float
    best_lay_player2_provider: str
    
    # All provider prices
    provider_prices: Dict[str, ProviderPrice] = field(default_factory=dict)
    
    # Price movements
    player1_price_trend: str = "stable"  # "up", "down", "stable"
    player2_price_trend: str = "stable"
    
    timestamp: datetime = field(default_factory=datetime.now)
    
    def get_price_variance(self, player: int = 1) -> float:
        """
        Calculate price variance across providers.
        
        Args:
            player: 1 or 2
            
        Returns:
            Variance in prices
        """
        prices = []
        for provider_price in self.provider_prices.values():
            if player == 1 and provider_price.player1_back:
                prices.append(provider_price.player1_back)
            elif player == 2 and provider_price.player2_back:
                prices.append(provider_price.player2_back)
        
        if len(prices) < 2:
            return 0.0
        
        avg = sum(prices) / len(prices)
        variance = sum((p - avg) ** 2 for p in prices) / len(prices)
        return variance


@dataclass
class ArbitrageOpportunity:
    """Represents an arbitrage opportunity across providers."""
    match_id: str
    type: str  # "back_lay", "cross_provider", "sure_bet"
    
    # Opportunity details
    player: int  # 1 or 2
    back_provider: str
    back_price: float
    lay_provider: str
    lay_price: float
    
    # Profitability
    profit_percentage: float
    recommended_stake: Optional[float] = None
    expected_profit: Optional[float] = None
    
    # Risk assessment
    risk_level: str = "low"  # "low", "medium", "high"
    confidence: float = 1.0  # 0-1 confidence score
    
    # Timing
    discovered_at: datetime = field(default_factory=datetime.now)
    expires_at: Optional[datetime] = None
    
    def is_valid(self) -> bool:
        """Check if opportunity is still valid."""
        if self.expires_at and datetime.now() > self.expires_at:
            return False
        return self.profit_percentage > 0
    
    def calculate_stakes(self, total_stake: float) -> Tuple[float, float]:
        """
        Calculate optimal stakes for arbitrage.
        
        Args:
            total_stake: Total amount to stake
            
        Returns:
            Tuple of (back_stake, lay_stake)
        """
        # For back/lay arbitrage
        if self.type == "back_lay":
            back_stake = total_stake / (1 + self.back_price / self.lay_price)
            lay_stake = total_stake - back_stake
            return back_stake, lay_stake
        
        # For other types, return equal stakes for now
        return total_stake / 2, total_stake / 2


@dataclass
class UnifiedMatchState:
    """Unified match state aggregated from all providers."""
    
    # Match identification
    match_id: str  # Internal unified ID
    
    # Match information (best available data)
    match: TennisMatch
    
    # Optional fields
    provider_match_ids: Dict[str, str] = field(default_factory=dict)
    score: Optional[TennisScore] = None
    statistics: Optional[MatchStatistics] = None
    
    # Price comparison
    price_comparison: Optional[PriceComparison] = None
    
    # Historical price tracking
    price_history: List[PriceComparison] = field(default_factory=list)
    max_history_size: int = 100
    
    # Provider-specific data
    provider_data: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    
    # Data quality indicators
    data_quality: Dict[str, DataQuality] = field(default_factory=dict)
    
    # Arbitrage opportunities
    arbitrage_opportunities: List[ArbitrageOpportunity] = field(default_factory=list)
    
    # Metadata
    created_at: datetime = field(default_factory=datetime.now)
    last_updated: datetime = field(default_factory=datetime.now)
    update_count: int = 0
    
    def update_prices(self, provider: str, prices: ProviderPrice):
        """
        Update prices from a provider.
        
        Args:
            provider: Provider name
            prices: New price data
        """
        if not self.price_comparison:
            self.price_comparison = PriceComparison(
                match_id=self.match_id,
                best_back_player1=prices.player1_back,
                best_back_player1_provider=provider,
                best_lay_player1=prices.player1_lay,
                best_lay_player1_provider=provider,
                best_back_player2=prices.player2_back,
                best_back_player2_provider=provider,
                best_lay_player2=prices.player2_lay,
                best_lay_player2_provider=provider
            )
        
        # Update provider prices
        self.price_comparison.provider_prices[provider] = prices
        
        # Update best prices
        self._update_best_prices()
        
        # Track price movement
        self._track_price_movement()
        
        # Add to history
        self._add_to_history()
        
        # Update timestamp
        self.last_updated = datetime.now()
        self.update_count += 1
    
    def _update_best_prices(self):
        """Update best prices across all providers."""
        if not self.price_comparison:
            return
        
        # Find best back prices (highest)
        best_back_p1 = 0
        best_back_p1_provider = ""
        best_back_p2 = 0
        best_back_p2_provider = ""
        
        # Find best lay prices (lowest)
        best_lay_p1 = float('inf')
        best_lay_p1_provider = ""
        best_lay_p2 = float('inf')
        best_lay_p2_provider = ""
        
        for provider, prices in self.price_comparison.provider_prices.items():
            if not prices.is_suspended:
                # Player 1
                if prices.player1_back and prices.player1_back > best_back_p1:
                    best_back_p1 = prices.player1_back
                    best_back_p1_provider = provider
                
                if prices.player1_lay and prices.player1_lay < best_lay_p1:
                    best_lay_p1 = prices.player1_lay
                    best_lay_p1_provider = provider
                
                # Player 2
                if prices.player2_back and prices.player2_back > best_back_p2:
                    best_back_p2 = prices.player2_back
                    best_back_p2_provider = provider
                
                if prices.player2_lay and prices.player2_lay < best_lay_p2:
                    best_lay_p2 = prices.player2_lay
                    best_lay_p2_provider = provider
        
        # Update comparison
        if best_back_p1 > 0:
            self.price_comparison.best_back_player1 = best_back_p1
            self.price_comparison.best_back_player1_provider = best_back_p1_provider
        
        if best_lay_p1 < float('inf'):
            self.price_comparison.best_lay_player1 = best_lay_p1
            self.price_comparison.best_lay_player1_provider = best_lay_p1_provider
        
        if best_back_p2 > 0:
            self.price_comparison.best_back_player2 = best_back_p2
            self.price_comparison.best_back_player2_provider = best_back_p2_provider
        
        if best_lay_p2 < float('inf'):
            self.price_comparison.best_lay_player2 = best_lay_p2
            self.price_comparison.best_lay_player2_provider = best_lay_p2_provider
    
    def _track_price_movement(self):
        """Track price movement trends."""
        if len(self.price_history) < 2:
            return
        
        current = self.price_comparison
        previous = self.price_history[-1]
        
        # Player 1 trend
        if current.best_back_player1 > previous.best_back_player1:
            current.player1_price_trend = "up"
        elif current.best_back_player1 < previous.best_back_player1:
            current.player1_price_trend = "down"
        else:
            current.player1_price_trend = "stable"
        
        # Player 2 trend
        if current.best_back_player2 > previous.best_back_player2:
            current.player2_price_trend = "up"
        elif current.best_back_player2 < previous.best_back_player2:
            current.player2_price_trend = "down"
        else:
            current.player2_price_trend = "stable"
    
    def _add_to_history(self):
        """Add current price comparison to history."""
        if self.price_comparison:
            # Create a copy for history
            import copy
            history_entry = copy.deepcopy(self.price_comparison)
            self.price_history.append(history_entry)
            
            # Limit history size
            if len(self.price_history) > self.max_history_size:
                self.price_history.pop(0)
    
    def check_arbitrage(self) -> List[ArbitrageOpportunity]:
        """
        Check for arbitrage opportunities.
        
        Returns:
            List of arbitrage opportunities
        """
        opportunities = []
        
        if not self.price_comparison:
            return opportunities
        
        # Check for back/lay arbitrage on same player across providers
        for player in [1, 2]:
            if player == 1:
                best_back = self.price_comparison.best_back_player1
                best_back_provider = self.price_comparison.best_back_player1_provider
                best_lay = self.price_comparison.best_lay_player1
                best_lay_provider = self.price_comparison.best_lay_player1_provider
            else:
                best_back = self.price_comparison.best_back_player2
                best_back_provider = self.price_comparison.best_back_player2_provider
                best_lay = self.price_comparison.best_lay_player2
                best_lay_provider = self.price_comparison.best_lay_player2_provider
            
            # Check if we can back higher than we can lay
            if best_back > best_lay and best_back_provider != best_lay_provider:
                profit_pct = ((best_back - best_lay) / best_lay) * 100
                
                opportunity = ArbitrageOpportunity(
                    match_id=self.match_id,
                    type="back_lay",
                    player=player,
                    back_provider=best_back_provider,
                    back_price=best_back,
                    lay_provider=best_lay_provider,
                    lay_price=best_lay,
                    profit_percentage=profit_pct,
                    risk_level="low" if profit_pct > 2 else "medium",
                    confidence=0.9 if profit_pct > 1 else 0.7
                )
                opportunities.append(opportunity)
        
        # Check for sure bet opportunity (backing both players for guaranteed profit)
        if self.price_comparison.best_back_player1 and self.price_comparison.best_back_player2:
            overround = (
                1/self.price_comparison.best_back_player1 + 
                1/self.price_comparison.best_back_player2
            ) * 100
            
            if overround < 100:  # Sure bet exists
                profit_pct = 100 - overround
                
                opportunity = ArbitrageOpportunity(
                    match_id=self.match_id,
                    type="sure_bet",
                    player=0,  # Both players
                    back_provider=self.price_comparison.best_back_player1_provider,
                    back_price=self.price_comparison.best_back_player1,
                    lay_provider=self.price_comparison.best_back_player2_provider,
                    lay_price=self.price_comparison.best_back_player2,
                    profit_percentage=profit_pct,
                    risk_level="low",
                    confidence=0.95
                )
                opportunities.append(opportunity)
        
        self.arbitrage_opportunities = opportunities
        return opportunities
    
    def get_best_provider(self) -> Optional[str]:
        """
        Get the best provider based on data quality.
        
        Returns:
            Best provider name or None
        """
        if not self.data_quality:
            return None
        
        best_provider = None
        best_score = 0
        
        for provider, quality in self.data_quality.items():
            score = quality.calculate_quality_score()
            if score > best_score:
                best_score = score
                best_provider = provider
        
        return best_provider
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "match_id": self.match_id,
            "provider_match_ids": self.provider_match_ids,
            "match": {
                "tournament": self.match.tournament_name,
                "player1": self.match.player1.name,
                "player2": self.match.player2.name,
                "status": self.match.status.value,
                "surface": self.match.surface.value
            },
            "score": self.score.get_score_string() if self.score else None,
            "price_comparison": {
                "best_back_player1": self.price_comparison.best_back_player1,
                "best_back_player1_provider": self.price_comparison.best_back_player1_provider,
                "best_lay_player1": self.price_comparison.best_lay_player1,
                "best_lay_player1_provider": self.price_comparison.best_lay_player1_provider,
                "best_back_player2": self.price_comparison.best_back_player2,
                "best_back_player2_provider": self.price_comparison.best_back_player2_provider,
                "best_lay_player2": self.price_comparison.best_lay_player2,
                "best_lay_player2_provider": self.price_comparison.best_lay_player2_provider,
                "player1_trend": self.price_comparison.player1_price_trend,
                "player2_trend": self.price_comparison.player2_price_trend,
                "providers": list(self.price_comparison.provider_prices.keys())
            } if self.price_comparison else None,
            "arbitrage_opportunities": [
                {
                    "type": opp.type,
                    "player": opp.player,
                    "profit_percentage": opp.profit_percentage,
                    "risk_level": opp.risk_level
                }
                for opp in self.arbitrage_opportunities
            ],
            "data_quality": {
                provider: {
                    "status": quality.status.value,
                    "latency_ms": quality.latency_ms,
                    "age_seconds": quality.age_seconds,
                    "quality_score": quality.calculate_quality_score()
                }
                for provider, quality in self.data_quality.items()
            },
            "last_updated": self.last_updated.isoformat(),
            "update_count": self.update_count
        }