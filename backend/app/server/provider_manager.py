"""Provider manager for handling multiple data sources."""

import asyncio
import logging
from typing import Dict, List, Optional, Set, Any
from datetime import datetime, timedelta
from enum import Enum
from collections import defaultdict

from ..providers.base import BaseDataProvider
from ..providers.factory import DataProviderFactory
from ..providers.tennis_models import TennisMatch, TennisScore, MatchStatistics
from ..services.tennis_scores_service import TennisScoresService


class ProviderStatus(Enum):
    """Provider connection status."""
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    ERROR = "error"
    UNAUTHORIZED = "unauthorized"


class ProviderInfo:
    """Provider connection information."""
    
    def __init__(self, name: str, provider: BaseDataProvider):
        self.name = name
        self.provider = provider
        self.status = ProviderStatus.DISCONNECTED
        self.is_primary = False
        self.connected_at: Optional[datetime] = None
        self.last_update: Optional[datetime] = None
        self.error_count = 0
        self.last_error: Optional[str] = None
        self.service: Optional[TennisScoresService] = None
        
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "status": self.status.value,
            "is_primary": self.is_primary,
            "connected_at": self.connected_at.isoformat() if self.connected_at else None,
            "last_update": self.last_update.isoformat() if self.last_update else None,
            "error_count": self.error_count,
            "last_error": self.last_error
        }


class ProviderManager:
    """Manages multiple data providers with failover support."""
    
    def __init__(self, logger: Optional[logging.Logger] = None):
        """
        Initialize provider manager.
        
        Args:
            logger: Optional logger
        """
        self.logger = logger or logging.getLogger(__name__)
        self.providers: Dict[str, ProviderInfo] = {}
        self.primary_provider: Optional[str] = None
        self._match_cache: Dict[str, TennisMatch] = {}
        self._score_cache: Dict[str, TennisScore] = {}
        self._stats_cache: Dict[str, MatchStatistics] = {}
        self._update_callbacks: List[Any] = []
        self._lock = asyncio.Lock()
        self._running = False
        self._monitor_task: Optional[asyncio.Task] = None
        
    async def initialize(self, enabled_providers: List[str], primary_provider: str):
        """
        Initialize providers from configuration.
        
        Args:
            enabled_providers: List of provider names to enable
            primary_provider: Name of primary provider
        """
        async with self._lock:
            for provider_name in enabled_providers:
                try:
                    # Create provider instance
                    provider = DataProviderFactory.create_provider(provider_name, self.logger)
                    provider_info = ProviderInfo(provider_name, provider)
                    
                    # Create tennis service for this provider
                    provider_info.service = TennisScoresService(
                        provider=provider,
                        cache_ttl=30,
                        update_interval=20,
                        logger=self.logger
                    )
                    
                    # Set primary flag
                    if provider_name == primary_provider:
                        provider_info.is_primary = True
                        self.primary_provider = provider_name
                    
                    self.providers[provider_name] = provider_info
                    self.logger.info(f"Initialized provider: {provider_name}")
                    
                except Exception as e:
                    self.logger.error(f"Failed to initialize provider {provider_name}: {e}")
    
    async def connect_provider(self, provider_name: str) -> bool:
        """
        Connect to a specific provider.
        
        Args:
            provider_name: Provider to connect
            
        Returns:
            True if connected successfully
        """
        if provider_name not in self.providers:
            return False
        
        provider_info = self.providers[provider_name]
        provider_info.status = ProviderStatus.CONNECTING
        
        try:
            # Authenticate provider
            if provider_info.provider.authenticate():
                provider_info.status = ProviderStatus.CONNECTED
                provider_info.connected_at = datetime.now()
                provider_info.error_count = 0
                
                # Start monitoring service
                if provider_info.service:
                    provider_info.service.start_monitoring()
                
                self.logger.info(f"Connected to provider: {provider_name}")
                return True
            else:
                provider_info.status = ProviderStatus.UNAUTHORIZED
                provider_info.last_error = "Authentication failed"
                return False
                
        except Exception as e:
            provider_info.status = ProviderStatus.ERROR
            provider_info.error_count += 1
            provider_info.last_error = str(e)
            self.logger.error(f"Failed to connect to {provider_name}: {e}")
            return False
    
    async def connect_all(self):
        """Connect to all configured providers."""
        tasks = []
        for provider_name in self.providers:
            tasks.append(self.connect_provider(provider_name))
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        connected = sum(1 for r in results if r is True)
        self.logger.info(f"Connected to {connected}/{len(self.providers)} providers")
    
    async def disconnect_provider(self, provider_name: str):
        """
        Disconnect from a specific provider.
        
        Args:
            provider_name: Provider to disconnect
        """
        if provider_name not in self.providers:
            return
        
        provider_info = self.providers[provider_name]
        
        try:
            # Stop monitoring service
            if provider_info.service:
                provider_info.service.stop_monitoring()
            
            # Disconnect provider
            provider_info.provider.disconnect()
            provider_info.status = ProviderStatus.DISCONNECTED
            provider_info.connected_at = None
            
            self.logger.info(f"Disconnected from provider: {provider_name}")
            
        except Exception as e:
            self.logger.error(f"Error disconnecting from {provider_name}: {e}")
    
    async def disconnect_all(self):
        """Disconnect from all providers."""
        tasks = []
        for provider_name in self.providers:
            tasks.append(self.disconnect_provider(provider_name))
        
        await asyncio.gather(*tasks, return_exceptions=True)
    
    def get_provider_status(self) -> List[Dict[str, Any]]:
        """
        Get status of all providers.
        
        Returns:
            List of provider status dictionaries
        """
        return [info.to_dict() for info in self.providers.values()]
    
    async def get_all_matches(self, status: Optional[str] = None) -> List[TennisMatch]:
        """
        Get matches from all connected providers.
        
        Args:
            status: Optional status filter
            
        Returns:
            Merged and deduplicated match list
        """
        all_matches = []
        match_map = {}  # Use to deduplicate by match key
        
        # Collect matches from all connected providers
        for provider_info in self.providers.values():
            if provider_info.status != ProviderStatus.CONNECTED:
                continue
            
            try:
                if provider_info.service:
                    matches = provider_info.service.get_matches(status)
                    
                    for match in matches:
                        # Create a key for deduplication (based on player names and tournament)
                        key = self._get_match_key(match)
                        
                        # Prefer primary provider's data
                        if key not in match_map or provider_info.is_primary:
                            match_map[key] = match
                            # Add provider info to metadata
                            match.metadata["providers"] = match.metadata.get("providers", [])
                            if provider_info.name not in match.metadata["providers"]:
                                match.metadata["providers"].append(provider_info.name)
                        else:
                            # Add this provider to the existing match's provider list
                            if provider_info.name not in match_map[key].metadata.get("providers", []):
                                match_map[key].metadata.setdefault("providers", []).append(provider_info.name)
                    
                    provider_info.last_update = datetime.now()
                    
            except Exception as e:
                self.logger.error(f"Error getting matches from {provider_info.name}: {e}")
                provider_info.error_count += 1
                provider_info.last_error = str(e)
        
        # Convert to list and sort by scheduled start time
        all_matches = list(match_map.values())
        all_matches.sort(key=lambda m: m.scheduled_start or datetime.max)
        
        return all_matches
    
    async def get_match_details(self, match_id: str) -> Optional[Dict[str, Any]]:
        """
        Get detailed match information from available providers.
        
        Args:
            match_id: Match ID
            
        Returns:
            Match details with score and statistics
        """
        # Try primary provider first
        if self.primary_provider and self.primary_provider in self.providers:
            provider_info = self.providers[self.primary_provider]
            if provider_info.status == ProviderStatus.CONNECTED and provider_info.service:
                result = provider_info.service.get_match_summary(match_id)
                if result.get("match"):
                    result["providers"] = [self.primary_provider]
                    return result
        
        # Fall back to other providers
        for provider_info in self.providers.values():
            if provider_info.status != ProviderStatus.CONNECTED or provider_info.is_primary:
                continue
            
            try:
                if provider_info.service:
                    result = provider_info.service.get_match_summary(match_id)
                    if result.get("match"):
                        result["providers"] = [provider_info.name]
                        return result
            except Exception as e:
                self.logger.error(f"Error getting match details from {provider_info.name}: {e}")
        
        return None
    
    def _get_match_key(self, match: TennisMatch) -> str:
        """
        Generate a unique key for match deduplication.
        
        Args:
            match: Tennis match
            
        Returns:
            Match key string
        """
        # Use player names and tournament for deduplication
        players = sorted([match.player1.name.lower(), match.player2.name.lower()])
        tournament = match.tournament_name.lower().replace(" ", "")
        return f"{players[0]}_{players[1]}_{tournament}"
    
    def add_update_callback(self, callback):
        """
        Add callback for match updates.
        
        Args:
            callback: Async callback function
        """
        self._update_callbacks.append(callback)
    
    async def start_monitoring(self):
        """Start monitoring all providers."""
        if self._running:
            return
        
        self._running = True
        self._monitor_task = asyncio.create_task(self._monitor_loop())
        self.logger.info("Started provider monitoring")
    
    async def stop_monitoring(self):
        """Stop monitoring all providers."""
        self._running = False
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
        
        self.logger.info("Stopped provider monitoring")
    
    async def _monitor_loop(self):
        """Main monitoring loop."""
        while self._running:
            try:
                # Check provider health
                for provider_info in self.providers.values():
                    if provider_info.status == ProviderStatus.CONNECTED:
                        # Check if provider is still responsive
                        if provider_info.last_update:
                            time_since_update = (datetime.now() - provider_info.last_update).total_seconds()
                            if time_since_update > 120:  # 2 minutes without update
                                self.logger.warning(f"Provider {provider_info.name} seems unresponsive")
                                # Try to reconnect
                                await self.connect_provider(provider_info.name)
                
                # Get updated matches
                matches = await self.get_all_matches()
                
                # Notify callbacks
                for callback in self._update_callbacks:
                    try:
                        await callback({"type": "matches_update", "matches": matches})
                    except Exception as e:
                        self.logger.error(f"Error in update callback: {e}")
                
                # Wait before next iteration
                await asyncio.sleep(10)
                
            except Exception as e:
                self.logger.error(f"Error in monitor loop: {e}")
                await asyncio.sleep(5)
    
    async def handle_failover(self, failed_provider: str):
        """
        Handle provider failover.
        
        Args:
            failed_provider: Name of failed provider
        """
        if failed_provider != self.primary_provider:
            return
        
        # Find next available provider
        for provider_info in self.providers.values():
            if provider_info.name == failed_provider:
                continue
            
            if provider_info.status == ProviderStatus.CONNECTED:
                self.primary_provider = provider_info.name
                provider_info.is_primary = True
                self.logger.info(f"Failed over to provider: {provider_info.name}")
                
                # Notify about failover
                for callback in self._update_callbacks:
                    try:
                        await callback({
                            "type": "provider_failover",
                            "old_primary": failed_provider,
                            "new_primary": provider_info.name
                        })
                    except Exception as e:
                        self.logger.error(f"Error in failover callback: {e}")
                
                break