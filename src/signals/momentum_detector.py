"""
Phase 4: Momentum Detection Module

Detects bull market momentum using:
- Price momentum: 5-bar MA > 20-bar MA, slope > +0.05%/bar
- Volume momentum: Recent volume > 1.2x average
- Persistence check: Momentum sustained 3+ consecutive days?
- Output: momentum_strength (0-1.0)

This module feeds into the momentum strategy for bull market trading.
"""

import numpy as np
import pandas as pd
from typing import Dict, Tuple, Optional, List
import logging

logger = logging.getLogger(__name__)


class MomentumDetector:
    """Detect and measure price/volume momentum strength."""
    
    def __init__(self, short_ma_period: int = 5, long_ma_period: int = 20,
                 volume_multiplier: float = 1.2, persistence_days: int = 3,
                 slope_threshold: float = 0.0005):
        """
        Initialize momentum detector.
        
        Args:
            short_ma_period: Short MA window (fast trend)
            long_ma_period: Long MA window (slow trend)
            volume_multiplier: Volume threshold multiplier (1.2 = 20% above average)
            persistence_days: Minimum consecutive days for sustained momentum
            slope_threshold: Minimum slope (0.0005 = 0.05%/bar)
        """
        self.short_ma_period = short_ma_period
        self.long_ma_period = long_ma_period
        self.volume_multiplier = volume_multiplier
        self.persistence_days = persistence_days
        self.slope_threshold = slope_threshold
        
        # For determining the lookback window
        self.lookback_period = max(long_ma_period, persistence_days) + 10
    
    def detect_momentum(self, df: pd.DataFrame) -> Dict:
        """
        Detect momentum using integrated price and volume analysis.
        
        Args:
            df: DataFrame with OHLCV data
        
        Returns:
            {
                'momentum_strength': float 0-1.0,
                'momentum_type': 'bullish' or 'bearish' or 'none',
                'price_momentum': float,
                'volume_momentum': float,
                'persistence': int (consecutive days),
                'ma_cross': bool,
                'slope': float,
                'details': {...}
            }
        """
        if len(df) < self.long_ma_period + 2:
            return {
                'momentum_strength': 0.0,
                'momentum_type': 'none',
                'price_momentum': 0.0,
                'volume_momentum': 0.0,
                'persistence': 0,
                'ma_cross': False,
                'slope': 0.0,
                'details': {'error': 'Insufficient data'}
            }
        
        try:
            # Detect price momentum
            price_momentum, ma_cross, slope = self._detect_price_momentum(df)
            
            # Detect volume momentum
            volume_momentum = self._detect_volume_momentum(df)
            
            # Check persistence
            persistence_days = self._check_persistence(df, ma_cross)
            
            # Combine into strength score
            momentum_strength = self._calculate_momentum_strength(
                price_momentum, volume_momentum, persistence_days, ma_cross
            )
            
            # Determine momentum type
            if momentum_strength > 0.6:
                momentum_type = 'bullish' if ma_cross else 'bearish'
            else:
                momentum_type = 'none'
            
            return {
                'momentum_strength': momentum_strength,
                'momentum_type': momentum_type,
                'price_momentum': price_momentum,
                'volume_momentum': volume_momentum,
                'persistence': persistence_days,
                'ma_cross': ma_cross,
                'slope': slope,
                'details': {
                    'short_ma_period': self.short_ma_period,
                    'long_ma_period': self.long_ma_period,
                    'volume_multiplier': self.volume_multiplier
                }
            }
        
        except Exception as e:
            logger.error(f"Error detecting momentum: {e}")
            return {
                'momentum_strength': 0.0,
                'momentum_type': 'none',
                'price_momentum': 0.0,
                'volume_momentum': 0.0,
                'persistence': 0,
                'ma_cross': False,
                'slope': 0.0,
                'details': {'error': str(e)}
            }
    
    def _detect_price_momentum(self, df: pd.DataFrame) -> Tuple[float, bool, float]:
        """
        Detect price momentum using MA crossover and slope.
        
        Returns:
            (momentum: float 0-1.0, ma_cross: bool, slope: float)
        """
        prices = df['Close'].values
        
        # Calculate moving averages
        short_ma = pd.Series(prices).rolling(window=self.short_ma_period).mean().values
        long_ma = pd.Series(prices).rolling(window=self.long_ma_period).mean().values
        
        # Get current values (last bar)
        current_short_ma = short_ma[-1]
        current_long_ma = long_ma[-1]
        
        # Check if short MA > long MA (bullish)
        ma_cross = current_short_ma > current_long_ma
        
        # Calculate slope of short MA (rate of change)
        if len(short_ma) >= 5:
            recent_slope = (short_ma[-1] - short_ma[-5]) / (5 * current_short_ma) if current_short_ma > 0 else 0
        else:
            recent_slope = 0.0
        
        # Price momentum score
        # MA distance: How far is short MA above/below long MA?
        if current_long_ma > 0:
            ma_distance = abs(current_short_ma - current_long_ma) / current_long_ma
        else:
            ma_distance = 0.0
        
        # Slope strength: How steep is the momentum?
        slope_strength = max(0, min(1.0, abs(recent_slope) / self.slope_threshold))
        
        # Combine: MA distance (40%) + slope strength (60%)
        momentum = ma_distance * 0.4 + slope_strength * 0.6
        momentum = min(1.0, momentum)
        
        return momentum, ma_cross, recent_slope
    
    def _detect_volume_momentum(self, df: pd.DataFrame) -> float:
        """
        Detect volume momentum (elevated recent volume).
        
        Returns:
            momentum: float 0-1.0
        """
        volumes = df['Volume'].values
        
        if len(volumes) < 5:
            return 0.0
        
        # Average volume over past 20 days (excluding today)
        if len(volumes) > self.long_ma_period:
            avg_volume = np.mean(volumes[-self.long_ma_period:-1])
        else:
            avg_volume = np.mean(volumes[:-1])
        
        # Current volume
        current_volume = volumes[-1]
        
        if avg_volume == 0:
            return 0.0
        
        # Volume ratio
        volume_ratio = current_volume / avg_volume
        
        # Momentum: How much above the threshold?
        if volume_ratio >= self.volume_multiplier:
            momentum = min(1.0, (volume_ratio - 1.0) / 0.5)
        else:
            momentum = 0.0
        
        return momentum
    
    def _check_persistence(self, df: pd.DataFrame, current_ma_cross: bool) -> int:
        """
        Check if momentum has persisted for N consecutive days.
        
        Returns:
            Number of consecutive days with momentum
        """
        if len(df) < self.persistence_days:
            return 0
        
        prices = df['Close'].values
        short_ma = pd.Series(prices).rolling(window=self.short_ma_period).mean().values
        long_ma = pd.Series(prices).rolling(window=self.long_ma_period).mean().values
        
        # Check last N days for consistent MA cross
        consecutive_days = 0
        
        for i in range(len(df) - 1, max(len(df) - self.persistence_days - 1, 0), -1):
            if short_ma[i] > long_ma[i]:  # Bullish
                consecutive_days += 1
            else:
                break
        
        return consecutive_days
    
    def _calculate_momentum_strength(self, price_momentum: float, volume_momentum: float,
                                    persistence: int, ma_cross: bool) -> float:
        """
        Calculate combined momentum strength.
        
        Formula:
        - Base: Average of price + volume momentum
        - Boost: Persistence (3+ days = +0.2 boost)
        - Filter: MA cross must be in place
        """
        if not ma_cross:
            # No MA cross = weak momentum signal
            base = (price_momentum + volume_momentum) / 2
            return base * 0.5
        
        base = (price_momentum + volume_momentum) / 2
        
        # Persistence boost
        if persistence >= self.persistence_days:
            persistence_boost = min(0.2, persistence * 0.05)
        else:
            persistence_boost = -0.1 * (self.persistence_days - persistence)
        
        strength = base + persistence_boost
        strength = max(0.0, min(1.0, strength))
        
        return strength
    
    def get_momentum_signals(self, df: pd.DataFrame) -> List[Tuple[str, float, str, str]]:
        """
        Get momentum signals as formatted list (compatible with other detectors).
        
        Returns:
            List of (signal_type, strength, direction, explanation) tuples
        """
        result = self.detect_momentum(df)
        momentum = result['momentum_strength']
        momentum_type = result['momentum_type']
        persistence = result['persistence']
        volume_mom = result['volume_momentum']
        
        signals = []
        
        if momentum_type == 'bullish':
            explanation = f"Bullish momentum detected (strength={momentum:.2f}, persistence={persistence}d, volume_ratio={volume_mom:.2f})"
            signals.append(('momentum_bullish', momentum, 'bullish', explanation))
        elif momentum_type == 'bearish':
            explanation = f"Bearish momentum detected (strength={momentum:.2f}, persistence={persistence}d)"
            signals.append(('momentum_bearish', momentum, 'bearish', explanation))
        else:
            explanation = "No clear momentum detected"
            signals.append(('momentum_none', momentum, None, explanation))
        
        return signals
    
    def get_momentum_historical(self, df: pd.DataFrame, lookback: int = 20) -> pd.DataFrame:
        """
        Get momentum scores for each day in lookback window.
        
        Returns:
            DataFrame with momentum metrics over time
        """
        if len(df) < self.long_ma_period:
            return pd.DataFrame()
        
        lookback = min(lookback, len(df))
        data_subset = df.tail(lookback)
        
        momentum_scores = []
        dates = []
        
        for i in range(self.long_ma_period, len(df)):
            df_slice = df.iloc[i - self.long_ma_period:i + 1]
            result = self.detect_momentum(df_slice)
            
            momentum_scores.append(result['momentum_strength'])
            dates.append(df.index[i] if hasattr(df, 'index') else i)
        
        return pd.DataFrame({
            'date': dates[-lookback:],
            'momentum_strength': momentum_scores[-lookback:]
        })
