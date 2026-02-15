"""
Information flow signals: volume anomalies, volatility regime shifts, order imbalance.
Based on market microstructure and information asymmetry theory.
"""

import numpy as np
import pandas as pd
from scipy import stats

class InformationFlowDetector:
    """Detect information-driven moves through volume and volatility analysis."""
    
    def __init__(self, lookback_period=20):
        self.lookback_period = lookback_period
    
    def detect_volume_anomaly(self, data):
        """
        Detect unusual volume at extreme price levels.
        High volume at new highs/lows suggests information discovery.
        
        Returns: (signal_strength, direction, explanation)
        """
        if len(data) < self.lookback_period:
            return 0, None, "Insufficient data"
        
        recent = data.iloc[-1]
        history = data.iloc[-self.lookback_period:]
        
        # Calculate z-score of current volume
        try:
            avg_volume = float(history['Volume'].mean())
            std_volume = float(history['Volume'].std())
        except (TypeError, ValueError):
            return 0, None, "Invalid volume data"
        
        if std_volume <= 1e-8:
            return 0, None, "No volume variation"
        
        volume_zscore = (float(recent['Volume']) - avg_volume) / std_volume
        
        # Check if at price extreme
        try:
            high_20 = float(history['High'].max())
            low_20 = float(history['Low'].min())
            current_price = float(recent['Close'])
        except (TypeError, ValueError):
            return 0, None, "Invalid price data"
        
        at_high = current_price >= high_20 * 0.99
        at_low = current_price <= low_20 * 1.01
        
        if (at_high or at_low) and volume_zscore > 2.0:
            price_direction = "above" if at_high else "below"
            signal_direction = 'bullish' if at_high else 'bearish'
            explanation = f"Extreme volume ({volume_zscore:.1f}σ) at price {price_direction} 20-day {('high' if at_high else 'low')}"
            return min(volume_zscore / 3.0, 1.0), signal_direction, explanation
        
        return 0, None, "Normal volume"
    
    def detect_volatility_regime_shift(self, data):
        """
        Detect shift in volatility regime (GARCH-style detection).
        Sudden increase in realized volatility suggests new information.
        
        Returns: (signal_strength, direction, explanation)
        """
        if len(data) < self.lookback_period + 5:
            return 0, None, "Insufficient data"
        
        try:
            history = data.iloc[-self.lookback_period:]
            prev_history = data.iloc[-(self.lookback_period + 5):-5]
            
            # Calculate returns volatility
            curr_returns = history['Close'].pct_change().std()
            prev_returns = prev_history['Close'].pct_change().std()
            
            if prev_returns == 0 or np.isnan(curr_returns) or np.isnan(prev_returns):
                return 0, None, "No volatility data"
            
            vol_ratio = curr_returns / prev_returns
            
            # F-test for variance change (2-tailed at 95%)
            f_stat = (curr_returns ** 2) / (prev_returns ** 2)
            p_value = 1 - stats.f.cdf(f_stat, len(history) - 1, len(prev_history) - 1)
            
            if p_value < 0.05 and vol_ratio > 1.3:
                explanation = f"Volatility regime shift: {vol_ratio:.2f}x increase (p={p_value:.3f})"
                return min((vol_ratio - 1.0), 1.0), None, explanation
            
            return 0, None, "Stable volatility"
        except (TypeError, ValueError, ZeroDivisionError):
            return 0, None, "Volatility calculation error"
    
    def detect_bid_ask_expansion(self, data):
        """
        Detect bid-ask spread expansion (proxy: high-low range vs typical).
        Expansion suggests uncertainty and information asymmetry.
        
        Returns: (signal_strength, direction, explanation)
        """
        if len(data) < self.lookback_period:
            return 0, None, "Insufficient data"
        
        try:
            history = data.iloc[-self.lookback_period:]
            recent = data.iloc[-1]
            
            # High-Low range as proxy for spread
            curr_range = recent['High'] - recent['Low']
            ranges = history['High'].sub(history['Low'])
            avg_range = ranges.mean()
            std_range = ranges.std()
            
            if avg_range == 0 or std_range == 0 or np.isnan(avg_range) or np.isnan(std_range):
                return 0, None, "No range data"
            
            range_zscore = (curr_range - avg_range) / std_range
            
            if np.isnan(range_zscore):
                return 0, None, "Range calculation error"
            
            if range_zscore > 2.0:
                explanation = f"Bid-ask spread expansion: {range_zscore:.1f}σ above normal"
                return min(range_zscore / 3.0, 1.0), None, explanation
            
            return 0, None, "Normal spread"
        except (TypeError, ValueError, ZeroDivisionError):
            return 0, None, "Spread calculation error"
    
    def run_all(self, data):
        """
        Run all information flow detectors.
        
        Returns: List[(signal_type: str, strength: float, direction: str|None, explanation: str)]
        Standardized to return 4-tuples for consistency with MomentumReversalDetector.
        """
        signals = []
        
        vol_strength, vol_dir, vol_exp = self.detect_volume_anomaly(data)
        if vol_strength > 0:
            signals.append(('volume_anomaly', vol_strength, vol_dir, vol_exp))
        
        regime_strength, regime_dir, regime_exp = self.detect_volatility_regime_shift(data)
        if regime_strength > 0:
            signals.append(('volatility_shift', regime_strength, regime_dir, regime_exp))
        
        spread_strength, spread_dir, spread_exp = self.detect_bid_ask_expansion(data)
        if spread_strength > 0:
            signals.append(('spread_expansion', spread_strength, spread_dir, spread_exp))
        
        return signals
