"""Provider-agnostic tennis data models."""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from datetime import datetime
from enum import Enum


class MatchStatus(Enum):
    """Match status."""
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    SUSPENDED = "suspended"
    RETIRED = "retired"
    WALKOVER = "walkover"
    CANCELLED = "cancelled"


class Surface(Enum):
    """Tennis court surface."""
    HARD = "hard"
    CLAY = "clay"
    GRASS = "grass"
    CARPET = "carpet"
    UNKNOWN = "unknown"


class TournamentLevel(Enum):
    """Tournament level/category."""
    GRAND_SLAM = "grand_slam"
    ATP_1000 = "atp_1000"
    ATP_500 = "atp_500"
    ATP_250 = "atp_250"
    WTA_1000 = "wta_1000"
    WTA_500 = "wta_500"
    WTA_250 = "wta_250"
    CHALLENGER = "challenger"
    ITF = "itf"
    EXHIBITION = "exhibition"
    OTHER = "other"


@dataclass
class Player:
    """Tennis player information."""
    id: str
    name: str
    country: Optional[str] = None
    ranking: Optional[int] = None
    seed: Optional[int] = None
    is_serving: bool = False
    
    def __hash__(self):
        return hash(self.id)


@dataclass
class GameScore:
    """Current game score (points)."""
    server_points: str  # "0", "15", "30", "40", "AD"
    receiver_points: str
    is_deuce: bool = False
    is_breakpoint: bool = False
    is_tiebreak: bool = False
    tiebreak_points: Optional[Dict[str, int]] = None  # {"player1": 5, "player2": 3}


@dataclass
class SetScore:
    """Score for a single set."""
    player1_games: int
    player2_games: int
    is_tiebreak: bool = False
    tiebreak_score: Optional[Dict[str, int]] = None
    is_completed: bool = False
    winner: Optional[str] = None  # Player ID


@dataclass
class TennisScore:
    """Complete tennis match score."""
    match_id: str
    player1: Player
    player2: Player
    sets: List[SetScore] = field(default_factory=list)
    current_set: int = 1
    current_game: Optional[GameScore] = None
    total_sets: int = 3  # Best of 3 or 5
    server: Optional[Player] = None
    match_status: MatchStatus = MatchStatus.NOT_STARTED
    winner: Optional[Player] = None
    timestamp: datetime = field(default_factory=datetime.now)
    
    @property
    def player1_sets_won(self) -> int:
        """Count sets won by player 1."""
        return sum(1 for s in self.sets if s.winner == self.player1.id and s.is_completed)
    
    @property
    def player2_sets_won(self) -> int:
        """Count sets won by player 2."""
        return sum(1 for s in self.sets if s.winner == self.player2.id and s.is_completed)
    
    @property
    def current_set_score(self) -> Optional[SetScore]:
        """Get current set score."""
        if self.current_set <= len(self.sets):
            return self.sets[self.current_set - 1]
        return None
    
    def get_score_string(self) -> str:
        """Get score as formatted string."""
        if not self.sets:
            return "0-0"
        
        score_parts = []
        for set_score in self.sets:
            score_parts.append(f"{set_score.player1_games}-{set_score.player2_games}")
            if set_score.is_tiebreak and set_score.tiebreak_score:
                tb = set_score.tiebreak_score
                score_parts[-1] += f"({tb.get(self.player1.id, 0)}-{tb.get(self.player2.id, 0)})"
        
        return " ".join(score_parts)


@dataclass
class ServeStatistics:
    """Serving statistics."""
    first_serve_in: int = 0
    first_serve_total: int = 0
    first_serve_points_won: int = 0
    second_serve_points_won: int = 0
    second_serve_total: int = 0
    aces: int = 0
    double_faults: int = 0
    service_games_played: int = 0
    service_games_won: int = 0
    break_points_saved: int = 0
    break_points_faced: int = 0
    
    @property
    def first_serve_percentage(self) -> float:
        """Calculate first serve percentage."""
        if self.first_serve_total == 0:
            return 0.0
        return (self.first_serve_in / self.first_serve_total) * 100
    
    @property
    def first_serve_win_percentage(self) -> float:
        """Calculate first serve win percentage."""
        if self.first_serve_in == 0:
            return 0.0
        return (self.first_serve_points_won / self.first_serve_in) * 100
    
    @property
    def second_serve_win_percentage(self) -> float:
        """Calculate second serve win percentage."""
        if self.second_serve_total == 0:
            return 0.0
        return (self.second_serve_points_won / self.second_serve_total) * 100
    
    @property
    def break_points_saved_percentage(self) -> float:
        """Calculate break points saved percentage."""
        if self.break_points_faced == 0:
            return 100.0
        return (self.break_points_saved / self.break_points_faced) * 100


@dataclass
class ReturnStatistics:
    """Return statistics."""
    return_points_played: int = 0
    return_points_won: int = 0
    break_points_won: int = 0
    break_points_opportunities: int = 0
    return_games_played: int = 0
    return_games_won: int = 0
    
    @property
    def return_points_win_percentage(self) -> float:
        """Calculate return points win percentage."""
        if self.return_points_played == 0:
            return 0.0
        return (self.return_points_won / self.return_points_played) * 100
    
    @property
    def break_points_conversion_rate(self) -> float:
        """Calculate break points conversion rate."""
        if self.break_points_opportunities == 0:
            return 0.0
        return (self.break_points_won / self.break_points_opportunities) * 100


@dataclass
class MatchStatistics:
    """Complete match statistics."""
    match_id: str
    player1: Player
    player2: Player
    player1_serve_stats: ServeStatistics = field(default_factory=ServeStatistics)
    player2_serve_stats: ServeStatistics = field(default_factory=ServeStatistics)
    player1_return_stats: ReturnStatistics = field(default_factory=ReturnStatistics)
    player2_return_stats: ReturnStatistics = field(default_factory=ReturnStatistics)
    
    # General stats
    player1_total_points_won: int = 0
    player2_total_points_won: int = 0
    player1_winners: int = 0
    player2_winners: int = 0
    player1_unforced_errors: int = 0
    player2_unforced_errors: int = 0
    player1_net_points_won: int = 0
    player1_net_points_total: int = 0
    player2_net_points_won: int = 0
    player2_net_points_total: int = 0
    
    match_duration_minutes: Optional[int] = None
    timestamp: datetime = field(default_factory=datetime.now)
    
    @property
    def player1_net_success_rate(self) -> float:
        """Calculate player 1 net success rate."""
        if self.player1_net_points_total == 0:
            return 0.0
        return (self.player1_net_points_won / self.player1_net_points_total) * 100
    
    @property
    def player2_net_success_rate(self) -> float:
        """Calculate player 2 net success rate."""
        if self.player2_net_points_total == 0:
            return 0.0
        return (self.player2_net_points_won / self.player2_net_points_total) * 100


@dataclass
class TennisMatch:
    """Complete tennis match information."""
    id: str
    provider_id: str  # Provider-specific ID
    provider: str  # Provider name (betfair, pinnacle, etc.)
    
    # Match details
    tournament_name: str
    
    # Players
    player1: Player
    player2: Player
    
    # Optional fields
    tournament_level: TournamentLevel = TournamentLevel.OTHER
    surface: Surface = Surface.UNKNOWN
    round: Optional[str] = None  # "Final", "Semi-Final", "Quarter-Final", etc.
    
    # Timing
    scheduled_start: Optional[datetime] = None
    actual_start: Optional[datetime] = None
    last_update: datetime = field(default_factory=datetime.now)
    
    # Status and scores
    status: MatchStatus = MatchStatus.NOT_STARTED
    score: Optional[TennisScore] = None
    statistics: Optional[MatchStatistics] = None
    
    # Betting data (optional)
    market_id: Optional[str] = None
    odds: Optional[Dict[str, float]] = None
    
    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def is_live(self) -> bool:
        """Check if match is currently live."""
        return self.status == MatchStatus.IN_PROGRESS
    
    def is_finished(self) -> bool:
        """Check if match is finished."""
        return self.status in [MatchStatus.COMPLETED, MatchStatus.RETIRED, MatchStatus.WALKOVER]
    
    def get_current_server(self) -> Optional[Player]:
        """Get current server from score."""
        if self.score and self.score.server:
            return self.score.server
        return None