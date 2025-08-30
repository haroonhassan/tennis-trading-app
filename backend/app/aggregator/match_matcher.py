"""Match matching service for identifying same matches across providers."""

import re
import logging
from typing import Dict, List, Optional, Tuple, Set
from datetime import datetime, timedelta
from difflib import SequenceMatcher

from ..providers.tennis_models import TennisMatch


class MatchMatcher:
    """Identifies same matches across different providers using fuzzy matching."""
    
    def __init__(self, logger: Optional[logging.Logger] = None):
        """
        Initialize match matcher.
        
        Args:
            logger: Optional logger
        """
        self.logger = logger or logging.getLogger(__name__)
        
        # Common name variations and abbreviations
        self.name_variations = {
            # Common abbreviations
            "alexander": ["alex", "a"],
            "nicholas": ["nick", "n"],
            "christopher": ["chris", "c"],
            "rafael": ["rafa", "r"],
            "novak": ["n"],
            "roger": ["r"],
            "stefanos": ["s"],
            "daniil": ["d"],
            "andrey": ["a"],
            
            # Last name variations
            "djokovic": ["djoko"],
            "federer": ["fed"],
            "nadal": ["rafa"],
            "tsitsipas": ["tsitsi"],
            "medvedev": ["med"],
            "zverev": ["z"],
            "alcaraz": ["alca"],
            
            # Common misspellings and variations
            "monfils": ["monfis"],
            "tsonga": ["jo-wilfried tsonga", "jo wilfried tsonga"],
        }
        
        # Tournament name variations
        self.tournament_variations = {
            "us open": ["us open", "u.s. open", "united states open", "flushing meadows"],
            "french open": ["french open", "roland garros", "roland-garros", "rg"],
            "wimbledon": ["wimbledon", "the championships", "all england club"],
            "australian open": ["australian open", "aus open", "ao", "melbourne"],
            "atp finals": ["atp finals", "tour finals", "masters cup", "year-end championships"],
            "indian wells": ["indian wells", "bnp paribas open", "iw"],
            "miami": ["miami open", "miami masters", "key biscayne"],
            "monte carlo": ["monte carlo", "monte-carlo", "rolex masters"],
            "rome": ["rome", "italian open", "internazionali d'italia"],
            "madrid": ["madrid", "madrid open", "mutua madrid"],
        }
        
        # Cache for matched pairs
        self._match_cache: Dict[str, str] = {}  # provider_match_key -> unified_id
        self._unified_matches: Dict[str, Set[str]] = {}  # unified_id -> set of provider_match_keys
    
    def match_players(self, player1_name: str, player2_name: str) -> Tuple[float, bool]:
        """
        Match player names using fuzzy matching.
        
        Args:
            player1_name: First player name
            player2_name: Second player name
            
        Returns:
            Tuple of (similarity score, is_match)
        """
        # Normalize names
        name1 = self._normalize_name(player1_name)
        name2 = self._normalize_name(player2_name)
        
        # Direct match
        if name1 == name2:
            return 1.0, True
        
        # Check variations
        if self._check_name_variations(name1, name2):
            return 0.95, True
        
        # Fuzzy matching
        similarity = SequenceMatcher(None, name1, name2).ratio()
        
        # Check if last names match (more important)
        parts1 = name1.split()
        parts2 = name2.split()
        
        if len(parts1) > 0 and len(parts2) > 0:
            last_name_similarity = SequenceMatcher(None, parts1[-1], parts2[-1]).ratio()
            
            # Weight last name more heavily
            weighted_similarity = (similarity * 0.4) + (last_name_similarity * 0.6)
            
            # Match if weighted similarity is high enough
            is_match = weighted_similarity > 0.85
            
            return weighted_similarity, is_match
        
        # Default fuzzy match threshold
        is_match = similarity > 0.9
        return similarity, is_match
    
    def match_tournaments(self, tournament1: str, tournament2: str) -> Tuple[float, bool]:
        """
        Match tournament names using fuzzy matching.
        
        Args:
            tournament1: First tournament name
            tournament2: Second tournament name
            
        Returns:
            Tuple of (similarity score, is_match)
        """
        # Normalize names
        name1 = self._normalize_tournament(tournament1)
        name2 = self._normalize_tournament(tournament2)
        
        # Direct match
        if name1 == name2:
            return 1.0, True
        
        # Check variations
        for canonical, variations in self.tournament_variations.items():
            norm_variations = [self._normalize_tournament(v) for v in variations]
            if name1 in norm_variations and name2 in norm_variations:
                return 0.95, True
        
        # Fuzzy matching
        similarity = SequenceMatcher(None, name1, name2).ratio()
        
        # Check if key words match (e.g., both contain "open" or "masters")
        keywords1 = set(name1.split())
        keywords2 = set(name2.split())
        common_keywords = keywords1.intersection(keywords2)
        
        if len(common_keywords) > 0:
            keyword_bonus = len(common_keywords) * 0.1
            similarity = min(1.0, similarity + keyword_bonus)
        
        is_match = similarity > 0.8
        return similarity, is_match
    
    def find_match(
        self,
        match: TennisMatch,
        provider: str,
        candidates: List[Tuple[str, TennisMatch]]
    ) -> Optional[str]:
        """
        Find matching match from other providers.
        
        Args:
            match: Match to find
            provider: Provider of the match
            candidates: List of (provider, match) tuples to search
            
        Returns:
            Unified match ID if found, None otherwise
        """
        # Create match key
        match_key = self._create_match_key(match, provider)
        
        # Check cache
        if match_key in self._match_cache:
            return self._match_cache[match_key]
        
        best_match_score = 0
        best_match_id = None
        
        for other_provider, candidate in candidates:
            if other_provider == provider:
                continue
            
            # Calculate match score
            score = self._calculate_match_score(match, candidate)
            
            if score > best_match_score:
                best_match_score = score
                # Get or create unified ID
                candidate_key = self._create_match_key(candidate, other_provider)
                if candidate_key in self._match_cache:
                    best_match_id = self._match_cache[candidate_key]
                else:
                    best_match_id = self._generate_unified_id(match, candidate)
        
        # If we found a good match
        if best_match_score > 0.85:
            # Update cache
            self._match_cache[match_key] = best_match_id
            
            # Track unified matches
            if best_match_id not in self._unified_matches:
                self._unified_matches[best_match_id] = set()
            self._unified_matches[best_match_id].add(match_key)
            
            self.logger.info(
                f"Matched {provider} match ({match.player1.name} vs {match.player2.name}) "
                f"with unified ID {best_match_id} (score: {best_match_score:.2f})"
            )
            
            return best_match_id
        
        # No match found, create new unified ID
        unified_id = self._generate_unified_id(match)
        self._match_cache[match_key] = unified_id
        self._unified_matches[unified_id] = {match_key}
        
        return unified_id
    
    def _calculate_match_score(self, match1: TennisMatch, match2: TennisMatch) -> float:
        """
        Calculate similarity score between two matches.
        
        Args:
            match1: First match
            match2: Second match
            
        Returns:
            Similarity score (0-1)
        """
        score = 0.0
        weights = {
            "players": 0.5,
            "tournament": 0.2,
            "time": 0.2,
            "surface": 0.1
        }
        
        # Match players (order doesn't matter)
        players1 = {match1.player1.name.lower(), match1.player2.name.lower()}
        players2 = {match2.player1.name.lower(), match2.player2.name.lower()}
        
        player_scores = []
        for p1 in players1:
            best_score = 0
            for p2 in players2:
                sim, _ = self.match_players(p1, p2)
                best_score = max(best_score, sim)
            player_scores.append(best_score)
        
        player_match_score = sum(player_scores) / len(player_scores) if player_scores else 0
        score += player_match_score * weights["players"]
        
        # Match tournament
        tournament_sim, _ = self.match_tournaments(
            match1.tournament_name,
            match2.tournament_name
        )
        score += tournament_sim * weights["tournament"]
        
        # Match time (if scheduled)
        if match1.scheduled_start and match2.scheduled_start:
            time_diff = abs((match1.scheduled_start - match2.scheduled_start).total_seconds())
            # Within 1 hour is considered same match
            if time_diff < 3600:
                time_score = 1.0 - (time_diff / 3600)
            else:
                time_score = 0
            score += time_score * weights["time"]
        else:
            # If no scheduled time, give partial credit
            score += 0.5 * weights["time"]
        
        # Match surface
        if match1.surface == match2.surface:
            score += weights["surface"]
        
        return score
    
    def _normalize_name(self, name: str) -> str:
        """
        Normalize player name for matching.
        
        Args:
            name: Player name
            
        Returns:
            Normalized name
        """
        # Convert to lowercase
        name = name.lower().strip()
        
        # Remove common titles and suffixes
        name = re.sub(r'\b(jr|sr|iii|ii|iv)\b', '', name)
        
        # Remove special characters
        name = re.sub(r'[^\w\s-]', '', name)
        
        # Normalize whitespace
        name = ' '.join(name.split())
        
        return name
    
    def _normalize_tournament(self, name: str) -> str:
        """
        Normalize tournament name for matching.
        
        Args:
            name: Tournament name
            
        Returns:
            Normalized name
        """
        # Convert to lowercase
        name = name.lower().strip()
        
        # Remove year references
        name = re.sub(r'\b\d{4}\b', '', name)
        
        # Remove common words
        stop_words = ['the', 'presented', 'by', 'sponsored']
        for word in stop_words:
            name = re.sub(r'\b' + word + r'\b', '', name)
        
        # Remove special characters
        name = re.sub(r'[^\w\s-]', '', name)
        
        # Normalize whitespace
        name = ' '.join(name.split())
        
        return name
    
    def _check_name_variations(self, name1: str, name2: str) -> bool:
        """
        Check if names are known variations of each other.
        
        Args:
            name1: First name
            name2: Second name
            
        Returns:
            True if names are variations
        """
        for canonical, variations in self.name_variations.items():
            if canonical in name1 or canonical in name2:
                for variation in variations:
                    if variation in name1 or variation in name2:
                        return True
        
        return False
    
    def _create_match_key(self, match: TennisMatch, provider: str) -> str:
        """
        Create a unique key for a match.
        
        Args:
            match: Match object
            provider: Provider name
            
        Returns:
            Match key
        """
        players = sorted([match.player1.name.lower(), match.player2.name.lower()])
        return f"{provider}:{players[0]}:{players[1]}:{match.tournament_name.lower()}"
    
    def _generate_unified_id(self, *matches: TennisMatch) -> str:
        """
        Generate a unified match ID.
        
        Args:
            matches: One or more matches
            
        Returns:
            Unified ID
        """
        # Use first match for generating ID
        match = matches[0]
        
        # Create ID from players and tournament
        players = sorted([match.player1.name.lower(), match.player2.name.lower()])
        tournament = self._normalize_tournament(match.tournament_name)
        
        # Add timestamp if available
        if match.scheduled_start:
            date_str = match.scheduled_start.strftime("%Y%m%d")
        else:
            date_str = datetime.now().strftime("%Y%m%d")
        
        # Create hash for uniqueness
        import hashlib
        content = f"{players[0]}:{players[1]}:{tournament}:{date_str}"
        hash_suffix = hashlib.md5(content.encode()).hexdigest()[:8]
        
        return f"unified_{hash_suffix}"
    
    def get_unified_matches(self) -> Dict[str, Set[str]]:
        """
        Get all unified match mappings.
        
        Returns:
            Dictionary of unified_id -> set of provider match keys
        """
        return self._unified_matches.copy()
    
    def clear_cache(self):
        """Clear the match cache."""
        self._match_cache.clear()
        self._unified_matches.clear()
        self.logger.info("Match cache cleared")