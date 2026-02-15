"""
Improved trend detection with dual-timeframe analysis.

FIX #1: Add macro regime (50-day) to prevent misclassifying bull market pullbacks as downtrends.

Key change:
- OLD: Single 20-day lookback → calls local dips "downtrend"
- NEW: 50-day macro + 20-day micro → recognizes bull market context
"""

import numpy as np
import pandas as pd
from scipy import stats


class TrendDetectorV2:
    """
    Dual-timeframe trend detection.
    
    Macro (50-day): Identifies the broader market regime (bull/bear/neutral)
    Micro (20-day): Identifies current state within that regime (uptrend/downtrend/consolidation)
    
    This prevents misclassifying bull market pullbacks as downtrends.
    """
    
    def __init__(self, macro_period=50, micro_period=20):
        self.macro_period = macro_period
        self.micro_period = micro_period
    
    def _calculate_slope_strength(self, prices):
        """
        Calculate normalized slope using Theil-Sen robust regression.
        
        Returns:
            slope: Daily price change (normalized)
            strength: Slope magnitude relative to volatility (0-1+)
        """
        if len(prices) < 2:
            return 0, 0
        
        x = np.arange(len(prices))
        result = stats.theilslopes(prices, x, alpha=0.95)
        slope = result[0]
        
        # Normalize by ATR-like measure (better than std for trends)
        daily_changes = np.diff(prices)
        atr = np.mean(np.abs(daily_changes))
        
        if atr > 0:
            strength = abs(slope) / atr
        else:
            strength = 0
        
        return slope, strength
    
    def _classify_trend(self, slope, strength, threshold=0.15):
        """
        Classify trend based on slope and strength.
        
        Args:
            slope: Daily price change
            strength: Normalized slope magnitude
            threshold: Minimum strength to call it a trend (default: 0.15)
        
        Returns:
            direction: 'uptrend', 'downtrend', or 'consolidation'
            confidence: 0-1 based on strength
        """
        if strength < threshold:
            return 'consolidation', strength / threshold
        
        if slope > 0:
            direction = 'uptrend'
        else:
            direction = 'downtrend'
        
        # Confidence scales with strength above threshold
        confidence = min(1.0, strength / (2 * threshold))
        
        return direction, confidence
    
    def detect_trend(self, data):
        """
        Detect trend using dual-timeframe analysis.
        
        Returns dict with:
            macro_regime: Bull/bear/neutral market context (50-day)
            micro_state: Current state within regime (20-day)
            consensus: Combined view (e.g., "bull_pullback", "bear_bounce", "uptrend")
            confidence: 0-1 overall confidence
        """
        if len(data) < self.micro_period:
            return {
                'macro_regime': 'unknown',
                'micro_state': 'unknown',
                'consensus': 'unknown',
                'confidence': 0
            }
        
        prices = data['Close'].values
        
        # Micro state (20-day): Current momentum
        micro_prices = prices[-self.micro_period:]
        micro_slope, micro_strength = self._calculate_slope_strength(micro_prices)
        micro_state, micro_conf = self._classify_trend(micro_slope, micro_strength, threshold=0.15)
        
        # Macro regime (50-day): Broader context
        if len(data) >= self.macro_period:
            macro_prices = prices[-self.macro_period:]
            macro_slope, macro_strength = self._calculate_slope_strength(macro_prices)
            macro_regime, macro_conf = self._classify_trend(macro_slope, macro_strength, threshold=0.10)
        else:
            # Not enough data for macro - use micro as proxy
            macro_regime = micro_state
            macro_conf = micro_conf
        
        # Consensus: Combine macro + micro
        consensus, confidence = self._get_consensus(
            macro_regime, macro_conf, micro_state, micro_conf
        )
        
        return {
            'macro_regime': macro_regime,
            'macro_confidence': macro_conf,
            'micro_state': micro_state,
            'micro_confidence': micro_conf,
            'consensus': consensus,
            'confidence': confidence,
            'slopes': {
                'macro': macro_slope if len(data) >= self.macro_period else micro_slope,
                'micro': micro_slope
            }
        }
    
    def _get_consensus(self, macro, macro_conf, micro, micro_conf):
        """
        Combine macro regime and micro state into a consensus view.
        
        Key logic:
        - In a bull market (macro uptrend), don't call it "downtrend" unless severe
        - In a bear market (macro downtrend), be skeptical of "uptrends"
        - Use consolidation as the default when uncertain
        """
        # Weight macro more heavily (2x) since it's more stable
        macro_weight = 2.0
        micro_weight = 1.0
        
        # Both agree → strong signal
        if macro == micro:
            consensus = macro
            confidence = (macro_conf * macro_weight + micro_conf * micro_weight) / (macro_weight + micro_weight)
        
        # Macro uptrend + micro downtrend → bull market pullback (still bullish context)
        elif macro == 'uptrend' and micro == 'downtrend':
            if micro_conf > 0.7:
                consensus = 'downtrend'  # Strong micro signal overrides
                confidence = micro_conf * 0.8  # Slightly discounted
            else:
                consensus = 'consolidation'  # Treat as pause in bull market
                confidence = 0.6
        
        # Macro downtrend + micro uptrend → bear market bounce (skeptical)
        elif macro == 'downtrend' and micro == 'uptrend':
            if micro_conf > 0.7:
                consensus = 'uptrend'  # Strong micro signal
                confidence = micro_conf * 0.8
            else:
                consensus = 'consolidation'  # Likely dead cat bounce
                confidence = 0.5
        
        # Macro trend + micro consolidation → trust macro
        elif micro == 'consolidation':
            consensus = macro
            confidence = macro_conf * 0.7  # Discounted since micro is unclear
        
        # Macro consolidation + micro trend → trust micro but cautiously
        elif macro == 'consolidation':
            consensus = micro
            confidence = micro_conf * 0.6
        
        # Shouldn't reach here, but default to consolidation
        else:
            consensus = 'consolidation'
            confidence = 0.5
        
        return consensus, confidence
    
    def get_regime_for_strategy(self, data):
        """
        Simplified output for strategy use.
        
        Returns:
            regime: 'uptrend', 'downtrend', or 'consolidation'
            confidence: 0-1
        """
        result = self.detect_trend(data)
        return result['consensus'], result['confidence']


# Backward compatibility wrapper
class RobustTrendDetector:
    """
    Drop-in replacement for old RobustTrendDetector.
    Uses new V2 logic but returns old format.
    """
    
    def __init__(self, lookback_period=20):
        self.lookback_period = lookback_period
        self.detector_v2 = TrendDetectorV2(macro_period=50, micro_period=lookback_period)
    
    def get_robust_trend(self, data):
        """
        Returns dict matching old interface:
            consensus: 'uptrend', 'downtrend', 'consolidation'
            confidence: 0-1
        """
        result = self.detector_v2.detect_trend(data)
        
        return {
            'consensus': result['consensus'],
            'confidence': result['confidence']
        }
