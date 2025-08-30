"""Data aggregation service for multi-provider tennis data."""

from .models import (
    UnifiedMatchState,
    ProviderPrice,
    ArbitrageOpportunity,
    DataQuality,
    PriceComparison
)
from .match_matcher import MatchMatcher
from .aggregator_service import AggregatorService

__all__ = [
    "UnifiedMatchState",
    "ProviderPrice",
    "ArbitrageOpportunity",
    "DataQuality",
    "PriceComparison",
    "MatchMatcher",
    "AggregatorService"
]