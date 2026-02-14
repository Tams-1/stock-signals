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
        
        Returns: (signal_strength, explanation)
        """
        if len(data) < self.lookback_period:
            return 0, "Insufficient data"
        
        recent = data.iloc[-1]
        history = data.iloc[-self.lookback_period:]
        
        # Calculate z-score of current volume
        avg_volume = history['Volume'].mean()
        std_volume = history['Volume'].std()
        
        if std_volume <= 0:
            return 0, "No volume variation"
        
        volume_zscore = (recent['Volume'] - avg_volume) / std_volume
        
        # Check if at price extreme
        high_20 = history['High'].max()
        low_20 = history['Low'].min()
        current_price = recent['Close']
        
        at_high = current_price >= high_20 * 0.99
        at_low = current_price <= low_20 * 1.01
        
        if (at_high or at_low) and volume_zscore > 2.0:
            direction = "above" if at_high else "below"
            explanation = f"Extreme volume ({volume_zscore:.1f}σ) at price {direction} 20-day {('high' if at_high else 'low')}"
            return min(volume_zscore / 3.0, 1.0), explanation
        
        return 0, "Normal volume"
    
    def detect_volatility_regime_shift(self, data):
        """
        Detect shift in volatility regime (GARCH-style detection).
        Sudden increase in realized volatility suggests new information.
        
        Returns: (signal_strength, explanation)
        """
        if len(data) < self.lookback_period + 5:
            return 0, "Insufficient data"
        
        history = data.iloc[-self.lookback_period:]
        prev_history = data.iloc[-(self.lookback_period + 5):-5]
        
        # Calculate returns volatility
        curr_returns = history['Close'].pct_change().std()
        prev_returns = prev_history['Close'].pct_change().std()
        
        if prev_returns == 0:
            return 0, "No previous volatility"
        
        vol_ratio = curr_returns / prev_returns
        
        # F-test for variance change (2-tailed at 95%)
        f_stat = (curr_returns ** 2) / (prev_returns ** 2)
        p_value = 1 - stats.f.cdf(f_stat, len(history) - 1, len(prev_history) - 1)
        
        if p_value < 0.05 and vol_ratio > 1.3:
            explanation = f"Volatility regime shift: {vol_ratio:.2f}x increase (p={p_value:.3f})"
            return min((vol_ratio - 1.0), 1.0), explanation
        
        return 0, "Stable volatility"
    
    def detect_bid_ask_expansion(self, data):
        """
        Detect bid-ask spread expansion (proxy: high-low range vs typical).
        Expansion suggests uncertainty and information asymmetry.
        
        Returns: (signal_strength, explanation)
        """
        if len(data) < self.lookback_period:
            return 0, "Insufficient data"
        
        history = data.iloc[-self.lookback_period:]
        recent = data.iloc[-1]
        
        # High-Low range as proxy for spread
        curr_range = recent['High'] - recent['Low']
        avg_range = history['High'].sub(history['Low']).mean()
        
        if avg_range == 0:
            return 0, "No range"
        
        range_zscore = (curr_range - avg_range) / history['High'].sub(history['Low']).std()
        
        if range_zscore > 2.0:
            explanation = f"Bid-ask spread expansion: {range_zscore:.1f}σ above normal"
            return min(range_zscore / 3.0, 1.0), explanation
        
        return 0, "Normal spread"
    
    def run_all(self, data):
        """Run all information flow detectors."""
        signals = []
        
        vol_strength, vol_exp = self.detect_volume_anomaly(data)
        if vol_strength > 0:
            signals.append(('volume_anomaly', vol_strength, vol_exp))
        
        regime_strength, regime_exp = self.detect_volatility_regime_shift(data)
        if regime_strength > 0:
            signals.append(('volatility_shift', regime_strength, regime_exp))
        
        spread_strength, spread_exp = self.detect_bid_ask_expansion(data)
        if spread_strength > 0:
            signals.append(('spread_expansion', spread_strength, spread_exp))
        
        return signals
