"""Data aggregation service for merging multi-provider tennis data."""

import asyncio
import logging
import time
from typing import Dict, List, Optional, Any, Callable, Set
from datetime import datetime, timedelta
from collections import defaultdict

from .models import (
    UnifiedMatchState,
    ProviderPrice,
    ArbitrageOpportunity,
    DataQuality,
    DataQualityStatus,
    PriceComparison
)
from .match_matcher import MatchMatcher
from ..providers.tennis_models import TennisMatch, TennisScore, MatchStatistics
from ..server.provider_manager import ProviderManager


class AggregatorService:
    """
    Service for aggregating data from multiple providers.
    
    Maintains unified match state, identifies arbitrage opportunities,
    and tracks data quality across providers.
    """
    
    def __init__(
        self,
        provider_manager: ProviderManager,
        logger: Optional[logging.Logger] = None
    ):
        """
        Initialize aggregator service.
        
        Args:
            provider_manager: Provider manager instance
            logger: Optional logger
        """
        self.provider_manager = provider_manager
        self.logger = logger or logging.getLogger(__name__)
        
        # Match matching
        self.match_matcher = MatchMatcher(self.logger)
        
        # Unified match states
        self.unified_matches: Dict[str, UnifiedMatchState] = {}
        
        # Provider to unified ID mapping
        self.provider_match_map: Dict[str, Dict[str, str]] = defaultdict(dict)
        
        # Arbitrage tracking
        self.active_arbitrage: List[ArbitrageOpportunity] = []
        self.arbitrage_history: List[ArbitrageOpportunity] = []
        self.max_history_size = 1000
        
        # Update callbacks
        self._update_callbacks: List[Callable] = []
        
        # Monitoring
        self._running = False
        self._monitor_task: Optional[asyncio.Task] = None
        
        # Performance tracking
        self.update_latencies: Dict[str, List[float]] = defaultdict(list)
        self.max_latency_samples = 100
    
    async def initialize(self):
        """Initialize the aggregator service."""
        self.logger.info("Initializing aggregator service...")
        
        # Get initial matches from all providers
        await self.refresh_all_matches()
        
        self.logger.info(f"Initialized with {len(self.unified_matches)} unified matches")
    
    async def refresh_all_matches(self):
        """Refresh matches from all providers and unify them."""
        start_time = time.time()
        
        # Get matches from all providers
        all_provider_matches = []
        
        for provider_name, provider_info in self.provider_manager.providers.items():
            if provider_info.service:
                try:
                    matches = provider_info.service.get_matches()
                    for match in matches:
                        all_provider_matches.append((provider_name, match))
                    
                    # Track latency
                    latency = (time.time() - start_time) * 1000
                    self._track_latency(provider_name, latency)
                    
                except Exception as e:
                    self.logger.error(f"Error getting matches from {provider_name}: {e}")
        
        # Match and unify
        await self._unify_matches(all_provider_matches)
        
        # Check for arbitrage opportunities
        await self._check_all_arbitrage()
        
        # Notify callbacks
        await self._notify_updates("full_refresh")
    
    async def _unify_matches(self, provider_matches: List[Tuple[str, TennisMatch]]):
        """
        Unify matches from different providers.
        
        Args:
            provider_matches: List of (provider, match) tuples
        """
        # Clear previous mappings
        self.provider_match_map.clear()
        
        # Process each match
        for provider, match in provider_matches:
            # Find unified ID using matcher
            unified_id = self.match_matcher.find_match(match, provider, provider_matches)
            
            # Update mapping
            self.provider_match_map[provider][match.id] = unified_id
            
            # Create or update unified match state
            if unified_id not in self.unified_matches:
                # Create new unified match
                unified_match = UnifiedMatchState(
                    match_id=unified_id,
                    match=match
                )
                self.unified_matches[unified_id] = unified_match
            
            # Add provider match ID
            unified_match = self.unified_matches[unified_id]
            unified_match.provider_match_ids[provider] = match.id
            
            # Update match info if this is primary provider or better quality
            if self._should_update_match_info(unified_match, provider, match):
                unified_match.match = match
            
            # Update data quality
            await self._update_data_quality(unified_match, provider)
    
    def _should_update_match_info(
        self,
        unified_match: UnifiedMatchState,
        provider: str,
        match: TennisMatch
    ) -> bool:
        """
        Determine if match info should be updated from this provider.
        
        Args:
            unified_match: Unified match state
            provider: Provider name
            match: New match data
            
        Returns:
            True if should update
        """
        # Always update if no quality data yet
        if not unified_match.data_quality:
            return True
        
        # Update if this is the primary provider
        if provider == self.provider_manager.primary_provider:
            return True
        
        # Update if current provider has better quality
        if provider in unified_match.data_quality:
            provider_quality = unified_match.data_quality[provider]
            current_best = unified_match.get_best_provider()
            
            if current_best and current_best in unified_match.data_quality:
                best_quality = unified_match.data_quality[current_best]
                if provider_quality.calculate_quality_score() > best_quality.calculate_quality_score():
                    return True
        
        return False
    
    async def update_match_prices(
        self,
        provider: str,
        match_id: str,
        prices: Dict[str, float]
    ):
        """
        Update prices for a match from a provider.
        
        Args:
            provider: Provider name
            match_id: Provider's match ID
            prices: Price data dictionary
        """
        # Find unified match
        unified_id = self.provider_match_map.get(provider, {}).get(match_id)
        if not unified_id or unified_id not in self.unified_matches:
            self.logger.warning(f"No unified match found for {provider}:{match_id}")
            return
        
        unified_match = self.unified_matches[unified_id]
        
        # Create provider price
        provider_price = ProviderPrice(
            provider=provider,
            player1_back=prices.get("player1_back", 0),
            player1_lay=prices.get("player1_lay", 0),
            player2_back=prices.get("player2_back", 0),
            player2_lay=prices.get("player2_lay", 0),
            player1_back_volume=prices.get("player1_back_volume"),
            player1_lay_volume=prices.get("player1_lay_volume"),
            player2_back_volume=prices.get("player2_back_volume"),
            player2_lay_volume=prices.get("player2_lay_volume"),
            market_id=prices.get("market_id"),
            is_suspended=prices.get("is_suspended", False)
        )
        
        # Update unified match
        unified_match.update_prices(provider, provider_price)
        
        # Check for arbitrage
        opportunities = unified_match.check_arbitrage()
        if opportunities:
            await self._handle_arbitrage_opportunities(unified_match, opportunities)
        
        # Update data quality
        await self._update_data_quality(unified_match, provider)
        
        # Notify updates
        await self._notify_updates("price_update", unified_match)
    
    async def update_match_score(
        self,
        provider: str,
        match_id: str,
        score: TennisScore
    ):
        """
        Update score for a match from a provider.
        
        Args:
            provider: Provider name
            match_id: Provider's match ID
            score: Score data
        """
        # Find unified match
        unified_id = self.provider_match_map.get(provider, {}).get(match_id)
        if not unified_id or unified_id not in self.unified_matches:
            return
        
        unified_match = self.unified_matches[unified_id]
        
        # Update score if this provider has good quality
        if self._should_update_match_info(unified_match, provider, unified_match.match):
            unified_match.score = score
            unified_match.last_updated = datetime.now()
        
        # Notify updates
        await self._notify_updates("score_update", unified_match)
    
    async def update_match_statistics(
        self,
        provider: str,
        match_id: str,
        statistics: MatchStatistics
    ):
        """
        Update statistics for a match from a provider.
        
        Args:
            provider: Provider name
            match_id: Provider's match ID
            statistics: Statistics data
        """
        # Find unified match
        unified_id = self.provider_match_map.get(provider, {}).get(match_id)
        if not unified_id or unified_id not in self.unified_matches:
            return
        
        unified_match = self.unified_matches[unified_id]
        
        # Update statistics if this provider has good quality
        if self._should_update_match_info(unified_match, provider, unified_match.match):
            unified_match.statistics = statistics
            unified_match.last_updated = datetime.now()
        
        # Notify updates
        await self._notify_updates("statistics_update", unified_match)
    
    async def _update_data_quality(self, unified_match: UnifiedMatchState, provider: str):
        """
        Update data quality indicators for a provider.
        
        Args:
            unified_match: Unified match state
            provider: Provider name
        """
        # Get latency
        latencies = self.update_latencies.get(provider, [])
        avg_latency = sum(latencies) / len(latencies) if latencies else 1000
        
        # Determine quality status
        if avg_latency < 100:
            status = DataQualityStatus.EXCELLENT
        elif avg_latency < 500:
            status = DataQualityStatus.GOOD
        elif avg_latency < 1000:
            status = DataQualityStatus.FAIR
        else:
            status = DataQualityStatus.POOR
        
        # Get provider info
        provider_info = self.provider_manager.providers.get(provider)
        error_count = provider_info.error_count if provider_info else 0
        
        # Create quality indicator
        quality = DataQuality(
            provider=provider,
            status=status,
            latency_ms=avg_latency,
            last_update=datetime.now(),
            error_count=error_count,
            is_primary=(provider == self.provider_manager.primary_provider)
        )
        
        unified_match.data_quality[provider] = quality
    
    def _track_latency(self, provider: str, latency_ms: float):
        """
        Track latency for a provider.
        
        Args:
            provider: Provider name
            latency_ms: Latency in milliseconds
        """
        latencies = self.update_latencies[provider]
        latencies.append(latency_ms)
        
        # Limit sample size
        if len(latencies) > self.max_latency_samples:
            latencies.pop(0)
    
    async def _check_all_arbitrage(self):
        """Check all unified matches for arbitrage opportunities."""
        self.active_arbitrage.clear()
        
        for unified_match in self.unified_matches.values():
            opportunities = unified_match.check_arbitrage()
            if opportunities:
                self.active_arbitrage.extend(opportunities)
                await self._handle_arbitrage_opportunities(unified_match, opportunities)
    
    async def _handle_arbitrage_opportunities(
        self,
        unified_match: UnifiedMatchState,
        opportunities: List[ArbitrageOpportunity]
    ):
        """
        Handle discovered arbitrage opportunities.
        
        Args:
            unified_match: Unified match with opportunity
            opportunities: List of opportunities
        """
        for opportunity in opportunities:
            # Log opportunity
            self.logger.info(
                f"Arbitrage opportunity found for {unified_match.match_id}: "
                f"Type={opportunity.type}, Profit={opportunity.profit_percentage:.2f}%, "
                f"Risk={opportunity.risk_level}"
            )
            
            # Add to history
            self.arbitrage_history.append(opportunity)
            if len(self.arbitrage_history) > self.max_history_size:
                self.arbitrage_history.pop(0)
            
            # Notify callbacks
            await self._notify_arbitrage(unified_match, opportunity)
    
    async def _notify_updates(self, update_type: str, unified_match: Optional[UnifiedMatchState] = None):
        """
        Notify callbacks of updates.
        
        Args:
            update_type: Type of update
            unified_match: Updated match (optional)
        """
        for callback in self._update_callbacks:
            try:
                await callback({
                    "type": update_type,
                    "match": unified_match.to_dict() if unified_match else None,
                    "timestamp": datetime.now().isoformat()
                })
            except Exception as e:
                self.logger.error(f"Error in update callback: {e}")
    
    async def _notify_arbitrage(
        self,
        unified_match: UnifiedMatchState,
        opportunity: ArbitrageOpportunity
    ):
        """
        Notify callbacks of arbitrage opportunity.
        
        Args:
            unified_match: Match with opportunity
            opportunity: Arbitrage opportunity
        """
        for callback in self._update_callbacks:
            try:
                await callback({
                    "type": "arbitrage_alert",
                    "match": unified_match.to_dict(),
                    "opportunity": {
                        "type": opportunity.type,
                        "player": opportunity.player,
                        "back_provider": opportunity.back_provider,
                        "back_price": opportunity.back_price,
                        "lay_provider": opportunity.lay_provider,
                        "lay_price": opportunity.lay_price,
                        "profit_percentage": opportunity.profit_percentage,
                        "risk_level": opportunity.risk_level
                    },
                    "timestamp": datetime.now().isoformat()
                })
            except Exception as e:
                self.logger.error(f"Error in arbitrage callback: {e}")
    
    def add_update_callback(self, callback: Callable):
        """
        Add update callback.
        
        Args:
            callback: Async callback function
        """
        self._update_callbacks.append(callback)
    
    async def start_monitoring(self, interval: int = 10):
        """
        Start monitoring for updates.
        
        Args:
            interval: Update interval in seconds
        """
        if self._running:
            return
        
        self._running = True
        self._monitor_task = asyncio.create_task(self._monitor_loop(interval))
        self.logger.info(f"Started aggregator monitoring (interval={interval}s)")
    
    async def stop_monitoring(self):
        """Stop monitoring."""
        self._running = False
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
        
        self.logger.info("Stopped aggregator monitoring")
    
    async def _monitor_loop(self, interval: int):
        """
        Main monitoring loop.
        
        Args:
            interval: Update interval in seconds
        """
        while self._running:
            try:
                # Refresh all matches
                await self.refresh_all_matches()
                
                # Update prices for live matches
                for unified_id, unified_match in self.unified_matches.items():
                    if unified_match.match.is_live():
                        # Get prices from each provider
                        for provider, match_id in unified_match.provider_match_ids.items():
                            provider_info = self.provider_manager.providers.get(provider)
                            if provider_info and provider_info.service:
                                try:
                                    # This would need actual price fetching method
                                    # For now, we'll skip actual price updates
                                    pass
                                except Exception as e:
                                    self.logger.error(f"Error updating prices from {provider}: {e}")
                
                # Wait for next interval
                await asyncio.sleep(interval)
                
            except Exception as e:
                self.logger.error(f"Error in aggregator monitor loop: {e}")
                await asyncio.sleep(interval)
    
    def get_unified_matches(
        self,
        status: Optional[str] = None,
        with_arbitrage: bool = False
    ) -> List[UnifiedMatchState]:
        """
        Get unified matches.
        
        Args:
            status: Filter by status
            with_arbitrage: Only return matches with arbitrage opportunities
            
        Returns:
            List of unified match states
        """
        matches = list(self.unified_matches.values())
        
        # Filter by status
        if status:
            if status == "live":
                matches = [m for m in matches if m.match.is_live()]
            elif status == "upcoming":
                matches = [m for m in matches if not m.match.is_live() and not m.match.is_finished()]
            elif status == "completed":
                matches = [m for m in matches if m.match.is_finished()]
        
        # Filter by arbitrage
        if with_arbitrage:
            matches = [m for m in matches if m.arbitrage_opportunities]
        
        return matches
    
    def get_arbitrage_opportunities(self, active_only: bool = True) -> List[ArbitrageOpportunity]:
        """
        Get arbitrage opportunities.
        
        Args:
            active_only: Only return currently active opportunities
            
        Returns:
            List of arbitrage opportunities
        """
        if active_only:
            return [opp for opp in self.active_arbitrage if opp.is_valid()]
        else:
            return self.arbitrage_history.copy()
    
    def get_provider_comparison(self, unified_id: str) -> Optional[Dict[str, Any]]:
        """
        Get detailed provider comparison for a match.
        
        Args:
            unified_id: Unified match ID
            
        Returns:
            Provider comparison data
        """
        if unified_id not in self.unified_matches:
            return None
        
        unified_match = self.unified_matches[unified_id]
        
        comparison = {
            "match_id": unified_id,
            "providers": {},
            "best_prices": {},
            "arbitrage": [],
            "data_quality": {}
        }
        
        # Add provider-specific data
        for provider, match_id in unified_match.provider_match_ids.items():
            comparison["providers"][provider] = {
                "match_id": match_id,
                "has_prices": provider in unified_match.price_comparison.provider_prices if unified_match.price_comparison else False,
                "has_score": unified_match.score is not None,
                "has_statistics": unified_match.statistics is not None
            }
        
        # Add best prices
        if unified_match.price_comparison:
            comparison["best_prices"] = {
                "player1_back": {
                    "price": unified_match.price_comparison.best_back_player1,
                    "provider": unified_match.price_comparison.best_back_player1_provider
                },
                "player1_lay": {
                    "price": unified_match.price_comparison.best_lay_player1,
                    "provider": unified_match.price_comparison.best_lay_player1_provider
                },
                "player2_back": {
                    "price": unified_match.price_comparison.best_back_player2,
                    "provider": unified_match.price_comparison.best_back_player2_provider
                },
                "player2_lay": {
                    "price": unified_match.price_comparison.best_lay_player2,
                    "provider": unified_match.price_comparison.best_lay_player2_provider
                }
            }
        
        # Add arbitrage opportunities
        for opp in unified_match.arbitrage_opportunities:
            comparison["arbitrage"].append({
                "type": opp.type,
                "profit_percentage": opp.profit_percentage,
                "risk_level": opp.risk_level
            })
        
        # Add data quality
        for provider, quality in unified_match.data_quality.items():
            comparison["data_quality"][provider] = {
                "status": quality.status.value,
                "latency_ms": quality.latency_ms,
                "quality_score": quality.calculate_quality_score()
            }
        
        return comparison