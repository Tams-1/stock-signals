"""
Centralized configuration for the stock signals system.

This module contains all strategy parameters, thresholds, and settings
that should be consistent across the codebase.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class StrategyConfig:
    """Centralized strategy configuration."""
    
    # Confidence thresholds
    MIN_CONFIDENCE: float = 0.50  # Minimum confidence for trade signals
    
    # Position sizing
    MAX_POSITION_SIZE: float = 0.60  # Maximum position size (60%)
    MIN_POSITION_SIZE: float = 0.10  # Minimum position size (10%)
    DEFAULT_POSITION_SIZE: float = 0.20  # Default when calculation fails
    KELLY_FRACTION: float = 0.5  # Half-Kelly for safety
    
    # Trend detection periods
    MACRO_PERIOD: int = 50
    MICRO_PERIOD: int = 20
    
    # News settings
    NEWS_CACHE_TTL_HOURS: int = 6
    MIN_NEWS_SENTIMENT: float = 0.1  # Minimum sentiment to affect position sizing
    
    # Risk management
    MAX_PORTFOLIO_EXPOSURE: float = 0.80  # Maximum total portfolio exposure
    
    # Kelly Criterion specific
    KELLY_MIN_DATA_POINTS: int = 30  # Minimum data points for Kelly calculation


# Global config instance
CONFIG = StrategyConfig()


def get_config() -> StrategyConfig:
    """Get the global configuration instance."""
    return CONFIG
