"""Match data normalizer for converting provider-specific formats to common models."""

import re
import logging
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime

from .tennis_models import (
    TennisMatch,
    TennisScore,
    MatchStatistics,
    Player,
    SetScore,
    GameScore,
    MatchStatus,
    Surface,
    TournamentLevel,
    ServeStatistics,
    ReturnStatistics
)


class MatchNormalizer:
    """Normalizes match data from different providers to common format."""
    
    def __init__(self, logger: Optional[logging.Logger] = None):
        """Initialize normalizer."""
        self.logger = logger or logging.getLogger(__name__)
        
        # Patterns for parsing scores
        self.score_pattern = re.compile(r'(\d+)-(\d+)')
        self.tiebreak_pattern = re.compile(r'\((\d+)-(\d+)\)')
        
    def normalize_match(self, provider: str, raw_data: Dict[str, Any]) -> Optional[TennisMatch]:
        """
        Normalize match data from any provider.
        
        Args:
            provider: Provider name (betfair, pinnacle, etc.)
            raw_data: Raw match data from provider
            
        Returns:
            Normalized TennisMatch or None
        """
        try:
            if provider.lower() == "betfair":
                return self._normalize_betfair_match(raw_data)
            elif provider.lower() == "pinnacle":
                return self._normalize_pinnacle_match(raw_data)
            elif provider.lower() == "smarkets":
                return self._normalize_smarkets_match(raw_data)
            else:
                self.logger.warning(f"Unknown provider: {provider}")
                return None
                
        except Exception as e:
            self.logger.error(f"Error normalizing match from {provider}: {e}")
            return None
    
    def _normalize_betfair_match(self, data: Dict[str, Any]) -> TennisMatch:
        """Normalize Betfair match data."""
        # Extract basic info
        market_id = data.get("marketId", "")
        event = data.get("event", {})
        
        # Parse event name for players
        event_name = event.get("name", "")
        player1_name, player2_name = self._parse_player_names(event_name)
        
        # Create players
        runners = data.get("runners", [])
        player1 = Player(
            id=str(runners[0].get("selectionId")) if runners else "1",
            name=player1_name
        )
        player2 = Player(
            id=str(runners[1].get("selectionId")) if runners else "2",
            name=player2_name
        )
        
        # Determine status
        in_play = data.get("inPlay", False)
        status = MatchStatus.IN_PROGRESS if in_play else MatchStatus.NOT_STARTED
        
        # Get competition info
        competition = data.get("competition", {})
        tournament_name = competition.get("name", "Unknown Tournament")
        
        # Create match
        match = TennisMatch(
            id=f"betfair_{market_id}",
            provider_id=market_id,
            provider="betfair",
            tournament_name=tournament_name,
            tournament_level=self._determine_tournament_level(tournament_name),
            player1=player1,
            player2=player2,
            status=status,
            market_id=market_id,
            scheduled_start=data.get("marketStartTime"),
            metadata={"raw_data": data}
        )
        
        # Try to extract score if available
        score_data = data.get("score")
        if score_data:
            match.score = self._parse_betfair_score(score_data, player1, player2)
        
        # Extract price data if available
        price_data = data.get("priceData")
        if price_data and price_data.get("runners"):
            odds = {}
            for runner in price_data.get("runners", []):
                runner_name = runner.get("selectionId")
                # Map selection IDs to player positions
                # In Betfair, runners[0] is typically player1, runners[1] is player2
                runner_idx = price_data.get("runners", []).index(runner)
                player_key = f"player{runner_idx + 1}"
                
                # Get best back and lay prices
                ex = runner.get("ex", {})
                available_to_back = ex.get("availableToBack", [])
                available_to_lay = ex.get("availableToLay", [])
                
                if available_to_back:
                    odds[f"{player_key}_back"] = available_to_back[0].get("price")
                    odds[f"{player_key}_back_size"] = available_to_back[0].get("size")
                
                if available_to_lay:
                    odds[f"{player_key}_lay"] = available_to_lay[0].get("price")
                    odds[f"{player_key}_lay_size"] = available_to_lay[0].get("size")
            
            # Store odds in match object
            match.odds = odds
            match.metadata["prices"] = odds  # Also store in metadata for backward compatibility
        
        return match
    
    def _normalize_pinnacle_match(self, data: Dict[str, Any]) -> TennisMatch:
        """Normalize Pinnacle match data (placeholder for future implementation)."""
        # This would be implemented when Pinnacle provider is added
        pass
    
    def _normalize_smarkets_match(self, data: Dict[str, Any]) -> TennisMatch:
        """Normalize Smarkets match data (placeholder for future implementation)."""
        # This would be implemented when Smarkets provider is added
        pass
    
    def normalize_score(self, provider: str, raw_score: Any) -> Optional[TennisScore]:
        """
        Normalize score data from any provider.
        
        Args:
            provider: Provider name
            raw_score: Raw score data
            
        Returns:
            Normalized TennisScore or None
        """
        try:
            if provider.lower() == "betfair":
                return self._parse_betfair_score(raw_score, None, None)
            # Add other providers as needed
            else:
                return None
                
        except Exception as e:
            self.logger.error(f"Error normalizing score from {provider}: {e}")
            return None
    
    def normalize_statistics(self, provider: str, raw_stats: Any) -> Optional[MatchStatistics]:
        """
        Normalize statistics data from any provider.
        
        Args:
            provider: Provider name
            raw_stats: Raw statistics data
            
        Returns:
            Normalized MatchStatistics or None
        """
        try:
            if provider.lower() == "betfair":
                return self._parse_betfair_statistics(raw_stats)
            # Add other providers as needed
            else:
                return None
                
        except Exception as e:
            self.logger.error(f"Error normalizing statistics from {provider}: {e}")
            return None
    
    def _parse_player_names(self, event_name: str) -> Tuple[str, str]:
        """Parse player names from event name."""
        # Common patterns: "Player1 v Player2", "Player1 vs Player2"
        if " v " in event_name:
            parts = event_name.split(" v ")
        elif " vs " in event_name:
            parts = event_name.split(" vs ")
        elif " - " in event_name:
            parts = event_name.split(" - ")
        else:
            parts = [event_name, "Unknown"]
        
        player1 = parts[0].strip() if parts else "Player 1"
        player2 = parts[1].strip() if len(parts) > 1 else "Player 2"
        
        return player1, player2
    
    def _parse_betfair_score(self, score_data: Any, player1: Optional[Player], player2: Optional[Player]) -> TennisScore:
        """Parse Betfair score format."""
        if isinstance(score_data, str):
            # Parse string score like "6-4 3-6 2-1"
            return self._parse_score_string(score_data, player1, player2)
        elif isinstance(score_data, dict):
            # Parse structured score data
            return self._parse_structured_score(score_data, player1, player2)
        else:
            return None
    
    def _parse_score_string(self, score_str: str, player1: Optional[Player], player2: Optional[Player]) -> TennisScore:
        """Parse score from string format."""
        # Default players if not provided
        if not player1:
            player1 = Player(id="1", name="Player 1")
        if not player2:
            player2 = Player(id="2", name="Player 2")
        
        score = TennisScore(
            match_id="",
            player1=player1,
            player2=player2
        )
        
        # Split into sets
        set_scores = score_str.strip().split()
        
        for set_str in set_scores:
            # Parse basic score
            match = self.score_pattern.search(set_str)
            if match:
                p1_games = int(match.group(1))
                p2_games = int(match.group(2))
                
                set_score = SetScore(
                    player1_games=p1_games,
                    player2_games=p2_games
                )
                
                # Check for tiebreak
                tb_match = self.tiebreak_pattern.search(set_str)
                if tb_match:
                    set_score.is_tiebreak = True
                    set_score.tiebreak_score = {
                        player1.id: int(tb_match.group(1)),
                        player2.id: int(tb_match.group(2))
                    }
                
                # Determine if set is complete
                if (p1_games >= 6 or p2_games >= 6) and abs(p1_games - p2_games) >= 1:
                    set_score.is_completed = True
                    set_score.winner = player1.id if p1_games > p2_games else player2.id
                
                score.sets.append(set_score)
        
        # Update current set
        score.current_set = len(score.sets)
        
        # Determine match status
        if score.player1_sets_won > score.total_sets // 2:
            score.match_status = MatchStatus.COMPLETED
            score.winner = player1
        elif score.player2_sets_won > score.total_sets // 2:
            score.match_status = MatchStatus.COMPLETED
            score.winner = player2
        elif score.sets:
            score.match_status = MatchStatus.IN_PROGRESS
        
        return score
    
    def _parse_structured_score(self, score_data: Dict, player1: Optional[Player], player2: Optional[Player]) -> TennisScore:
        """Parse structured score data."""
        # This would handle more complex score formats from APIs
        # Implementation depends on actual API response format
        pass
    
    def _parse_betfair_statistics(self, stats_data: Dict) -> MatchStatistics:
        """Parse Betfair statistics format."""
        # This would parse actual statistics from Betfair
        # Note: Betfair typically doesn't provide detailed tennis statistics
        # This is a placeholder for when statistics become available
        pass
    
    def _determine_tournament_level(self, tournament_name: str) -> TournamentLevel:
        """Determine tournament level from name."""
        name_lower = tournament_name.lower()
        
        if any(gs in name_lower for gs in ["australian open", "french open", "wimbledon", "us open"]):
            return TournamentLevel.GRAND_SLAM
        elif "atp 1000" in name_lower or "masters" in name_lower:
            return TournamentLevel.ATP_1000
        elif "atp 500" in name_lower:
            return TournamentLevel.ATP_500
        elif "atp 250" in name_lower:
            return TournamentLevel.ATP_250
        elif "wta 1000" in name_lower:
            return TournamentLevel.WTA_1000
        elif "wta 500" in name_lower:
            return TournamentLevel.WTA_500
        elif "wta 250" in name_lower:
            return TournamentLevel.WTA_250
        elif "challenger" in name_lower:
            return TournamentLevel.CHALLENGER
        elif "itf" in name_lower:
            return TournamentLevel.ITF
        else:
            return TournamentLevel.OTHER
    
    def _determine_surface(self, surface_str: str) -> Surface:
        """Determine surface type from string."""
        surface_lower = surface_str.lower()
        
        if "hard" in surface_lower:
            return Surface.HARD
        elif "clay" in surface_lower:
            return Surface.CLAY
        elif "grass" in surface_lower:
            return Surface.GRASS
        elif "carpet" in surface_lower:
            return Surface.CARPET
        else:
            return Surface.UNKNOWN