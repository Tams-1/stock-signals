"""
Momentum and reversal signals: cumulative volume profile, order imbalance, mean reversion.
Based on behavioral finance and market microstructure.
"""

import numpy as np
import pandas as pd
from scipy import stats

class MomentumReversalDetector:
    """Detect momentum persistence and mean reversion extremes."""
    
    def __init__(self, lookback_period=20):
        self.lookback_period = lookback_period
    
    def detect_order_imbalance(self, data):
        """
        Detect persistent buy/sell pressure (order imbalance).
        Measured as cumulative volume directional bias.
        
        Returns: (signal_strength, direction, explanation)
        """
        if len(data) < self.lookback_period:
            return 0, None, "Insufficient data"
        
        history = data.iloc[-self.lookback_period:]
        
        # Calculate up/down volume
        up_volume = 0
        down_volume = 0
        
        for i in range(1, len(history)):
            close_diff = history.iloc[i]['Close'] - history.iloc[i-1]['Close']
            if close_diff > 0:
                up_volume += history.iloc[i]['Volume']
            else:
                down_volume += history.iloc[i]['Volume']
        
        total_volume = up_volume + down_volume
        if total_volume == 0:
            return 0, None, "No volume"
        
        # Calculate imbalance ratio
        imbalance_ratio = (up_volume - down_volume) / total_volume
        
        # Binomial test for significance (are buy and sell volumes equal?)
        # Expected: 50/50 split
        p_value = stats.binom_test(int(up_volume), int(total_volume), 0.5, alternative='two-sided')
        
        if abs(imbalance_ratio) > 0.15 and p_value < 0.05:
            direction = 'bullish' if imbalance_ratio > 0 else 'bearish'
            explanation = f"Order imbalance: {abs(imbalance_ratio)*100:.1f}% bias {direction} (p={p_value:.3f})"
            return min(abs(imbalance_ratio) * 2, 1.0), direction, explanation
        
        return 0, None, "Balanced order flow"
    
    def detect_mean_reversion_extreme(self, data):
        """
        Detect statistical extremes suggesting mean reversion.
        Using z-score of returns over lookback period.
        
        Returns: (signal_strength, direction, explanation)
        """
        if len(data) < self.lookback_period:
            return 0, None, "Insufficient data"
        
        history = data.iloc[-self.lookback_period:]
        recent = data.iloc[-1]
        
        # Calculate cumulative returns
        cum_returns = (recent['Close'] / history.iloc[0]['Close']) - 1
        
        # Rolling returns distribution
        returns = history['Close'].pct_change().dropna()
        mean_return = returns.mean()
        std_return = returns.std()
        
        if std_return == 0:
            return 0, None, "No volatility"
        
        # Z-score of current position
        zscore = cum_returns / std_return if std_return > 0 else 0
        
        # Mean reversion signal if extreme (>2σ)
        if abs(zscore) > 2.0:
            direction = 'bearish' if zscore > 0 else 'bullish'  # Extreme up = sell pressure
            explanation = f"Mean reversion extreme: {zscore:.1f}σ {direction} signal"
            return min(abs(zscore) / 3.0, 1.0), direction, explanation
        
        return 0, None, "Normal range"
    
    def detect_momentum_continuation(self, data):
        """
        Detect continuation of strong momentum (price + volume).
        When both price and volume are trending, momentum is likely to persist.
        
        Returns: (signal_strength, direction, explanation)
        """
        if len(data) < self.lookback_period:
            return 0, None, "Insufficient data"
        
        history = data.iloc[-self.lookback_period:]
        
        # Price momentum: compare last 5 bars to previous 10
        recent_prices = history.iloc[-5:]['Close'].mean()
        older_prices = history.iloc[-15:-5]['Close'].mean()
        price_momentum = (recent_prices - older_prices) / older_prices
        
        # Volume momentum: recent volume vs older volume
        recent_vol = history.iloc[-5:]['Volume'].mean()
        older_vol = history.iloc[-15:-5]['Volume'].mean()
        vol_momentum = (recent_vol - older_vol) / older_vol if older_vol > 0 else 0
        
        # Both price and volume trending = strong momentum
        if (abs(price_momentum) > 0.02 and vol_momentum > 0.2):
            direction = 'bullish' if price_momentum > 0 else 'bearish'
            explanation = f"Momentum continuation: {price_momentum*100:.1f}% price move with {vol_momentum*100:.0f}% volume increase"
            return min(abs(price_momentum) * 2, 1.0), direction, explanation
        
        return 0, None, "Weak momentum"
    
    def run_all(self, data):
        """Run all momentum/reversal detectors."""
        signals = []
        
        imb_strength, imb_dir, imb_exp = self.detect_order_imbalance(data)
        if imb_strength > 0:
            signals.append(('order_imbalance', imb_strength, imb_dir, imb_exp))
        
        rev_strength, rev_dir, rev_exp = self.detect_mean_reversion_extreme(data)
        if rev_strength > 0:
            signals.append(('mean_reversion', rev_strength, rev_dir, rev_exp))
        
        mom_strength, mom_dir, mom_exp = self.detect_momentum_continuation(data)
        if mom_strength > 0:
            signals.append(('momentum_continuation', mom_strength, mom_dir, mom_exp))
        
        return signals
