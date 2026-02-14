"""
Trend detection filters to distinguish oversold consolidation from downtrends.
Helps distinguish between mean-reversion (consolidation) and trend-continuation opportunities.
"""

import numpy as np
import pandas as pd
from scipy import stats


class TrendDetector:
    """Detect market trend and distinguish consolidation from trending moves."""
    
    def __init__(self, lookback_period=20):
        self.lookback_period = lookback_period
    
    def detect_trend_via_slope(self, data):
        """
        Detect trend using linear regression slope.
        
        Returns: 
            trend_direction: 'uptrend', 'downtrend', 'consolidation'
            trend_strength: 0-1.0 (how strong the trend is)
            slope: Linear regression slope
        """
        if len(data) < self.lookback_period:
            return 'unknown', 0, 0
        
        history = data.iloc[-self.lookback_period:]
        closes = history['Close'].values
        
        # Linear regression
        x = np.arange(len(closes))
        slope, intercept, r_value, p_value, std_err = stats.linregress(x, closes)
        
        # Slope interpretation
        price_range = closes.max() - closes.min()
        if price_range == 0:
            return 'consolidation', 0, 0
        
        slope_pct = (slope / closes[0]) * 100  # Slope as % of starting price
        
        # Trend strength via R-squared (how well does line fit?)
        trend_strength = abs(r_value)
        
        # Direction
        if slope > 0:
            direction = 'uptrend'
        elif slope < 0:
            direction = 'downtrend'
        else:
            direction = 'consolidation'
        
        return direction, trend_strength, slope_pct
    
    def detect_trend_via_moving_averages(self, data):
        """
        Detect trend using moving average crosses.
        
        Returns:
            trend_direction: 'uptrend', 'downtrend', 'consolidation'
            ma_ratio: ratio of short MA to long MA
        """
        if len(data) < self.lookback_period:
            return 'unknown', 0
        
        history = data.iloc[-self.lookback_period:]
        
        # Moving averages
        ma_short = history['Close'].iloc[-5:].mean()  # 5-day avg
        ma_long = history['Close'].mean()  # 20-day avg
        
        ma_ratio = ma_short / ma_long
        
        if ma_ratio > 1.01:  # Short MA above long MA by >1%
            direction = 'uptrend'
        elif ma_ratio < 0.99:  # Short MA below long MA by >1%
            direction = 'downtrend'
        else:
            direction = 'consolidation'
        
        return direction, ma_ratio
    
    def detect_trend_via_adx(self, data):
        """
        ADX (Average Directional Index) - measures trend strength, 0-100.
        
        Returns:
            trend_direction: 'strong_up', 'strong_down', 'weak'
            adx_value: 0-100 (higher = stronger trend)
        """
        if len(data) < 30:
            return 'weak', 0
        
        high = data['High'].values
        low = data['Low'].values
        close = data['Close'].values
        
        # Calculate True Range
        tr = np.maximum(
            high[1:] - low[1:],
            np.maximum(
                np.abs(high[1:] - close[:-1]),
                np.abs(low[1:] - close[:-1])
            )
        )
        
        # Plus and Minus DM
        plus_dm = np.where(high[1:] - high[:-1] > low[:-1] - low[1:], 
                          np.maximum(high[1:] - high[:-1], 0), 0)
        minus_dm = np.where(low[:-1] - low[1:] > high[1:] - high[:-1],
                           np.maximum(low[:-1] - low[1:], 0), 0)
        
        # Average TR, Plus DI, Minus DI (using 14-period)
        atr = np.mean(tr[-14:]) if len(tr) >= 14 else np.mean(tr)
        plus_di = 100 * np.mean(plus_dm[-14:]) / atr if atr > 0 else 0
        minus_di = 100 * np.mean(minus_dm[-14:]) / atr if atr > 0 else 0
        
        # ADX (simplified)
        di_diff = abs(plus_di - minus_di)
        adx = di_diff / (plus_di + minus_di + 0.001) * 100
        
        # Direction
        if adx > 25:  # Strong trend threshold
            direction = 'strong_up' if plus_di > minus_di else 'strong_down'
        else:
            direction = 'weak'  # Weak or range-bound
        
        return direction, adx
    
    def detect_trend_via_price_structure(self, data):
        """
        Detect trend by looking at higher lows (uptrend) or lower highs (downtrend).
        
        Returns:
            trend_direction: 'uptrend', 'downtrend', 'consolidation'
            structure_strength: 0-1.0 (how consistent is the pattern?)
        """
        if len(data) < self.lookback_period:
            return 'unknown', 0
        
        history = data.iloc[-self.lookback_period:]
        
        # Split into two halves
        mid = len(history) // 2
        first_half = history.iloc[:mid]
        second_half = history.iloc[mid:]
        
        first_low = first_half['Low'].min()
        first_high = first_half['High'].max()
        second_low = second_half['Low'].min()
        second_high = second_half['High'].max()
        
        # Trend logic
        higher_lows = second_low > first_low
        lower_highs = second_high < first_high
        
        if higher_lows and second_high > first_high:
            direction = 'uptrend'
            strength = min((second_low - first_low) / first_low, 1.0)
        elif lower_highs and second_low < first_low:
            direction = 'downtrend'
            strength = min((first_high - second_high) / first_high, 1.0)
        else:
            direction = 'consolidation'
            strength = 0.5
        
        return direction, strength
    
    def get_trend_context(self, data):
        """
        Composite trend detection using all 4 methods.
        
        Returns: dict with trend info from all methods + consensus
        """
        slope_dir, slope_strength, slope_pct = self.detect_trend_via_slope(data)
        ma_dir, ma_ratio = self.detect_trend_via_moving_averages(data)
        adx_dir, adx_value = self.detect_trend_via_adx(data)
        price_dir, price_strength = self.detect_trend_via_price_structure(data)
        
        # Consensus: which direction appears in most methods?
        directions = [slope_dir, ma_dir, adx_dir, price_dir]
        downtrend_count = sum(1 for d in directions if 'down' in d.lower())
        uptrend_count = sum(1 for d in directions if 'up' in d.lower())
        
        if downtrend_count >= 2:
            consensus = 'downtrend'
            confidence = downtrend_count / 4
        elif uptrend_count >= 2:
            consensus = 'uptrend'
            confidence = uptrend_count / 4
        else:
            consensus = 'consolidation'
            confidence = 0.5
        
        return {
            'consensus': consensus,
            'confidence': confidence,
            'slope': {
                'direction': slope_dir,
                'strength': slope_strength,
                'slope_pct': slope_pct
            },
            'moving_avg': {
                'direction': ma_dir,
                'ratio': ma_ratio
            },
            'adx': {
                'direction': adx_dir,
                'adx_value': adx_value
            },
            'price_structure': {
                'direction': price_dir,
                'strength': price_strength
            }
        }
    
    def should_trust_mean_reversion(self, data):
        """
        Decide if mean-reversion signal should be trusted.
        
        Returns: 
            should_trade: bool (True if consolidation/weak trend, False if strong downtrend)
            signal_multiplier: 0-1.0 (multiply mean-reversion signal strength by this)
            reason: explanation
        """
        trend = self.get_trend_context(data)
        
        if trend['consensus'] == 'consolidation':
            return True, 1.0, "Consolidation - mean reversion likely to work"
        
        elif trend['consensus'] == 'uptrend':
            return True, 0.7, "Uptrend - mean reversion possible but reduce confidence"
        
        elif trend['consensus'] == 'downtrend':
            confidence = trend['confidence']
            
            if confidence >= 0.75:
                # Very strong downtrend
                return False, 0.3, f"Strong downtrend ({confidence:.0%}) - avoid mean reversion"
            elif confidence >= 0.5:
                # Moderate downtrend
                return True, 0.4, f"Moderate downtrend ({confidence:.0%}) - reduce mean reversion signal"
            else:
                # Weak downtrend
                return True, 0.7, f"Weak downtrend ({confidence:.0%}) - mean reversion still possible"


if __name__ == '__main__':
    from src.data.fetch_data import fetch_ticker_data
    
    # Test on NVDA (winner) and MSFT (loser)
    detector = TrendDetector()
    
    print("=" * 80)
    print("TESTING TREND DETECTION")
    print("=" * 80)
    
    for ticker in ['NVDA', 'MSFT']:
        print(f"\n{'='*80}")
        print(f"TICKER: {ticker}")
        print(f"{'='*80}")
        
        data = fetch_ticker_data(ticker, start='2025-10-15', end='2025-11-10', progress=False)
        
        if len(data) >= 20:
            trend = detector.get_trend_context(data)
            should_trade, multiplier, reason = detector.should_trust_mean_reversion(data)
            
            print(f"\nConsensus: {trend['consensus'].upper()}")
            print(f"Confidence: {trend['confidence']:.0%}")
            
            print(f"\n  Slope: {trend['slope']['direction']} (strength={trend['slope']['strength']:.2f})")
            print(f"  MA Cross: {trend['moving_avg']['direction']}")
            print(f"  ADX: {trend['adx']['direction']} (value={trend['adx']['adx_value']:.0f})")
            print(f"  Price Structure: {trend['price_structure']['direction']} (strength={trend['price_structure']['strength']:.2f})")
            
            print(f"\nMean Reversion Trustworthiness:")
            print(f"  Should trade: {should_trade}")
            print(f"  Signal multiplier: {multiplier:.1f}x")
            print(f"  Reason: {reason}")
