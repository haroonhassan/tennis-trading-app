"""Tennis scores and statistics service with caching and scheduling."""

import asyncio
import threading
import time
import logging
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime, timedelta
from collections import defaultdict
from dataclasses import asdict

from ..providers.base import BaseDataProvider
from ..providers.factory import DataProviderFactory
from ..providers.tennis_models import (
    TennisMatch,
    TennisScore,
    MatchStatistics,
    Player,
    MatchStatus
)
from ..providers.normalizer import MatchNormalizer


class CacheEntry:
    """Cache entry with expiration."""
    
    def __init__(self, data: Any, ttl_seconds: int = 60):
        """
        Initialize cache entry.
        
        Args:
            data: Data to cache
            ttl_seconds: Time to live in seconds
        """
        self.data = data
        self.created_at = datetime.now()
        self.ttl = ttl_seconds
    
    def is_expired(self) -> bool:
        """Check if cache entry is expired."""
        age = (datetime.now() - self.created_at).total_seconds()
        return age > self.ttl
    
    def get(self) -> Optional[Any]:
        """Get data if not expired."""
        if not self.is_expired():
            return self.data
        return None


class MatchCache:
    """Provider-agnostic caching layer for match data."""
    
    def __init__(self, default_ttl: int = 60):
        """
        Initialize cache.
        
        Args:
            default_ttl: Default TTL in seconds
        """
        self.default_ttl = default_ttl
        self._matches: Dict[str, CacheEntry] = {}
        self._scores: Dict[str, CacheEntry] = {}
        self._stats: Dict[str, CacheEntry] = {}
        self._lock = threading.RLock()
    
    def get_match(self, match_id: str) -> Optional[TennisMatch]:
        """Get cached match."""
        with self._lock:
            entry = self._matches.get(match_id)
            if entry:
                return entry.get()
        return None
    
    def set_match(self, match: TennisMatch, ttl: Optional[int] = None):
        """Cache a match."""
        with self._lock:
            ttl = ttl or self.default_ttl
            self._matches[match.id] = CacheEntry(match, ttl)
    
    def get_score(self, match_id: str) -> Optional[TennisScore]:
        """Get cached score."""
        with self._lock:
            entry = self._scores.get(match_id)
            if entry:
                return entry.get()
        return None
    
    def set_score(self, match_id: str, score: TennisScore, ttl: Optional[int] = None):
        """Cache a score."""
        with self._lock:
            ttl = ttl or self.default_ttl
            self._scores[match_id] = CacheEntry(score, ttl)
    
    def get_stats(self, match_id: str) -> Optional[MatchStatistics]:
        """Get cached statistics."""
        with self._lock:
            entry = self._stats.get(match_id)
            if entry:
                return entry.get()
        return None
    
    def set_stats(self, match_id: str, stats: MatchStatistics, ttl: Optional[int] = None):
        """Cache statistics."""
        with self._lock:
            ttl = ttl or self.default_ttl
            self._stats[match_id] = CacheEntry(stats, ttl)
    
    def clear_expired(self):
        """Remove expired entries."""
        with self._lock:
            # Clear expired matches
            expired = [k for k, v in self._matches.items() if v.is_expired()]
            for key in expired:
                del self._matches[key]
            
            # Clear expired scores
            expired = [k for k, v in self._scores.items() if v.is_expired()]
            for key in expired:
                del self._scores[key]
            
            # Clear expired stats
            expired = [k for k, v in self._stats.items() if v.is_expired()]
            for key in expired:
                del self._stats[key]
    
    def clear_all(self):
        """Clear all cache."""
        with self._lock:
            self._matches.clear()
            self._scores.clear()
            self._stats.clear()


class UpdateScheduler:
    """Scheduler for polling match updates."""
    
    def __init__(self, interval_seconds: int = 30):
        """
        Initialize scheduler.
        
        Args:
            interval_seconds: Update interval in seconds
        """
        self.interval = interval_seconds
        self.running = False
        self._thread = None
        self._callbacks: List[Callable] = []
        self._stop_event = threading.Event()
    
    def add_callback(self, callback: Callable):
        """Add update callback."""
        self._callbacks.append(callback)
    
    def start(self):
        """Start scheduler."""
        if self.running:
            return
        
        self.running = True
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run)
        self._thread.daemon = True
        self._thread.start()
    
    def stop(self):
        """Stop scheduler."""
        self.running = False
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=5)
    
    def _run(self):
        """Main scheduler loop."""
        while self.running:
            # Execute callbacks
            for callback in self._callbacks:
                try:
                    callback()
                except Exception as e:
                    logging.error(f"Scheduler callback error: {e}")
            
            # Wait for next interval or stop
            if self._stop_event.wait(self.interval):
                break


class TennisScoresService:
    """Service for managing tennis scores and statistics."""
    
    def __init__(
        self,
        provider: Optional[BaseDataProvider] = None,
        cache_ttl: int = 60,
        update_interval: int = 30,
        logger: Optional[logging.Logger] = None
    ):
        """
        Initialize service.
        
        Args:
            provider: Data provider (or create default)
            cache_ttl: Cache TTL in seconds
            update_interval: Update interval in seconds
            logger: Optional logger
        """
        self.logger = logger or logging.getLogger(__name__)
        self.provider = provider
        self.normalizer = MatchNormalizer(self.logger)
        
        # Caching
        self.cache = MatchCache(default_ttl=cache_ttl)
        
        # Scheduling
        self.scheduler = UpdateScheduler(interval_seconds=update_interval)
        self.scheduler.add_callback(self._update_live_matches)
        
        # Track monitored matches
        self._monitored_matches: set = set()
        
    def set_provider(self, provider: BaseDataProvider):
        """Set data provider."""
        self.provider = provider
    
    def start_monitoring(self):
        """Start monitoring for updates."""
        if not self.provider:
            self.logger.error("No provider set")
            return
        
        self.scheduler.start()
        self.logger.info("Started monitoring tennis matches")
    
    def stop_monitoring(self):
        """Stop monitoring."""
        self.scheduler.stop()
        self.logger.info("Stopped monitoring tennis matches")
    
    def add_monitored_match(self, match_id: str):
        """Add match to monitor list."""
        self._monitored_matches.add(match_id)
    
    def remove_monitored_match(self, match_id: str):
        """Remove match from monitor list."""
        self._monitored_matches.discard(match_id)
    
    def get_matches(self, status: Optional[str] = None, use_cache: bool = True) -> List[TennisMatch]:
        """
        Get tennis matches.
        
        Args:
            status: Filter by status (live, upcoming, completed)
            use_cache: Whether to use cache
            
        Returns:
            List of tennis matches
        """
        if not self.provider:
            return []
        
        # Try cache first for all matches
        if use_cache and not status:
            cached_matches = []
            for match_id in list(self.cache._matches.keys()):
                match = self.cache.get_match(match_id)
                if match:
                    cached_matches.append(match)
            
            if cached_matches:
                return cached_matches
        
        # Fetch from provider
        try:
            matches = self.provider.get_tennis_matches(status)
            
            # Cache results
            for match in matches:
                # Live matches have shorter TTL
                ttl = 30 if match.is_live() else 120
                self.cache.set_match(match, ttl)
                
                # Auto-monitor live matches
                if match.is_live():
                    self._monitored_matches.add(match.id)
            
            return matches
            
        except Exception as e:
            self.logger.error(f"Error getting matches: {e}")
            return []
    
    def get_match_score(self, match_id: str, use_cache: bool = True) -> Optional[TennisScore]:
        """
        Get match score.
        
        Args:
            match_id: Match ID
            use_cache: Whether to use cache
            
        Returns:
            Tennis score or None
        """
        if not self.provider:
            return None
        
        # Try cache first
        if use_cache:
            score = self.cache.get_score(match_id)
            if score:
                return score
        
        # Fetch from provider
        try:
            score = self.provider.get_match_score(match_id)
            
            if score:
                # Cache with short TTL for live scores
                ttl = 15 if score.match_status == MatchStatus.IN_PROGRESS else 60
                self.cache.set_score(match_id, score, ttl)
            
            return score
            
        except Exception as e:
            self.logger.error(f"Error getting score for {match_id}: {e}")
            return None
    
    def get_match_statistics(self, match_id: str, use_cache: bool = True) -> Optional[MatchStatistics]:
        """
        Get match statistics.
        
        Args:
            match_id: Match ID
            use_cache: Whether to use cache
            
        Returns:
            Match statistics or None
        """
        if not self.provider:
            return None
        
        # Try cache first
        if use_cache:
            stats = self.cache.get_stats(match_id)
            if stats:
                return stats
        
        # Fetch from provider
        try:
            stats = self.provider.get_match_statistics(match_id)
            
            if stats:
                self.cache.set_stats(match_id, stats, 60)
            
            return stats
            
        except Exception as e:
            self.logger.error(f"Error getting stats for {match_id}: {e}")
            return None
    
    def get_serving_player(self, match_id: str) -> Optional[Player]:
        """
        Get current serving player.
        
        Args:
            match_id: Match ID
            
        Returns:
            Serving player or None
        """
        if not self.provider:
            return None
        
        try:
            # First try to get from score
            score = self.get_match_score(match_id)
            if score and score.server:
                return score.server
            
            # Fall back to provider method
            return self.provider.get_serving_player(match_id)
            
        except Exception as e:
            self.logger.error(f"Error getting server for {match_id}: {e}")
            return None
    
    def _update_live_matches(self):
        """Update monitored live matches."""
        if not self.provider or not self._monitored_matches:
            return
        
        for match_id in list(self._monitored_matches):
            try:
                # Update score
                score = self.provider.get_match_score(match_id)
                if score:
                    self.cache.set_score(match_id, score, 15)
                    
                    # Stop monitoring if match finished
                    if score.match_status in [MatchStatus.COMPLETED, MatchStatus.RETIRED]:
                        self._monitored_matches.discard(match_id)
                
                # Update stats if available
                stats = self.provider.get_match_statistics(match_id)
                if stats:
                    self.cache.set_stats(match_id, stats, 30)
                    
            except Exception as e:
                self.logger.error(f"Error updating match {match_id}: {e}")
        
        # Clean expired cache entries
        self.cache.clear_expired()
    
    def get_match_summary(self, match_id: str) -> Dict[str, Any]:
        """
        Get complete match summary.
        
        Args:
            match_id: Match ID
            
        Returns:
            Dictionary with match, score, and stats
        """
        result = {
            "match": None,
            "score": None,
            "statistics": None,
            "server": None
        }
        
        # Get match info
        matches = self.get_matches()
        for match in matches:
            if match.id == match_id:
                result["match"] = asdict(match)
                break
        
        # Get score
        score = self.get_match_score(match_id)
        if score:
            result["score"] = {
                "score_string": score.get_score_string(),
                "player1_sets": score.player1_sets_won,
                "player2_sets": score.player2_sets_won,
                "current_set": score.current_set,
                "status": score.match_status.value
            }
        
        # Get stats
        stats = self.get_match_statistics(match_id)
        if stats:
            result["statistics"] = asdict(stats)
        
        # Get server
        server = self.get_serving_player(match_id)
        if server:
            result["server"] = asdict(server)
        
        return result