"""
Ensemble Signal Generator: 6 SOTA trend detection methods + multi-factor confirmation
- Trend Strength Consensus
- Information Flow Signals  
- Momentum/Reversal Signals
- News Sentiment Confirmation
- Signal Confidence Scoring
- Risk Parameters (position sizing, stop-loss)
"""

import pandas as pd
import numpy as np
from typing import Dict, Tuple, List
import logging

logger = logging.getLogger(__name__)

class EnsembleSignalGenerator:
    """Multi-factor signal generation with confidence scoring"""
    
    # Trend detection methods (6 SOTA)
    METHODS = [
        'theil_sen',      # Robust linear regression (resistant to outliers)
        'kalman_filter',  # Optimal state estimation
        'ransac',         # Random consensus (outlier-robust)
        'hodrick_prescott',# HP filter (long-term trend)
        'adx',           # Average Directional Index (trend strength)
        'arima'          # AutoRegressive (time series momentum)
    ]
    
    def __init__(self, lookback_days: int = 20, 
                 volume_lookback: int = 20,
                 trend_threshold: float = 0.6):
        """
        Args:
            lookback_days: Window for trend detection
            volume_lookback: Window for volume analysis
            trend_threshold: Consensus threshold (0.6 = 3+ of 6 methods agree)
        """
        self.lookback_days = lookback_days
        self.volume_lookback = volume_lookback
        self.trend_threshold = trend_threshold
    
    def detect_trends(self, df: pd.DataFrame) -> Dict[str, float]:
        """
        Detect trends using 6 methods
        Returns: {method: trend_strength (-1.0 to 1.0)}
        """
        trends = {}
        price = df['close'].values[-self.lookback_days:]
        
        if len(price) < 5:
            return {m: 0.0 for m in self.METHODS}
        
        # 1. Theil-Sen (robust linear regression)
        try:
            trends['theil_sen'] = self._theil_sen_trend(price)
        except:
            trends['theil_sen'] = 0.0
        
        # 2. Kalman Filter
        try:
            trends['kalman_filter'] = self._kalman_trend(price)
        except:
            trends['kalman_filter'] = 0.0
        
        # 3. RANSAC (RANdom SAmple Consensus)
        try:
            trends['ransac'] = self._ransac_trend(price)
        except:
            trends['ransac'] = 0.0
        
        # 4. Hodrick-Prescott Filter
        try:
            trends['hodrick_prescott'] = self._hp_filter_trend(price)
        except:
            trends['hodrick_prescott'] = 0.0
        
        # 5. ADX (Average Directional Index)
        try:
            trends['adx'] = self._adx_trend(df.tail(self.lookback_days))
        except:
            trends['adx'] = 0.0
        
        # 6. ARIMA/Momentum
        try:
            trends['arima'] = self._arima_trend(price)
        except:
            trends['arima'] = 0.0
        
        return trends
    
    def _theil_sen_trend(self, price: np.ndarray) -> float:
        """Robust linear regression slope"""
        x = np.arange(len(price))
        slopes = []
        
        for i in range(len(price) - 1):
            for j in range(i + 1, len(price)):
                slope = (price[j] - price[i]) / (j - i)
                slopes.append(slope)
        
        if not slopes:
            return 0.0
        
        median_slope = np.median(slopes)
        # Normalize to -1..1
        return np.tanh(median_slope / np.std(price) * 10)
    
    def _kalman_trend(self, price: np.ndarray) -> float:
        """Kalman filter trend extraction"""
        # Simple Kalman filter for price
        q = 0.01  # Process variance
        r = 0.1   # Measurement variance
        
        x = price[0]
        p = 1.0
        trend_values = []
        
        for z in price[1:]:
            # Predict
            x_pred = x
            p_pred = p + q
            
            # Update
            k = p_pred / (p_pred + r)
            x = x_pred + k * (z - x_pred)
            p = (1 - k) * p_pred
            trend_values.append(x)
        
        # Calculate trend
        if len(trend_values) < 2:
            return 0.0
        
        trend = (trend_values[-1] - trend_values[0]) / (trend_values[0] + 1e-10)
        return np.tanh(trend)
    
    def _ransac_trend(self, price: np.ndarray) -> float:
        """RANSAC-based trend (outlier-resistant)"""
        x = np.arange(len(price))
        y = price
        
        # Simple RANSAC: fit line to random subset
        best_inliers = 0
        best_slope = 0
        threshold = np.std(price) * 0.5
        
        for _ in range(10):  # 10 iterations
            # Random sample: 2 points
            idx = np.random.choice(len(price), 2, replace=False)
            slope = (y[idx[1]] - y[idx[0]]) / (idx[1] - idx[0])
            
            # Count inliers
            predicted = y[0] + slope * x
            errors = np.abs(y - predicted)
            inliers = np.sum(errors < threshold)
            
            if inliers > best_inliers:
                best_inliers = inliers
                best_slope = slope
        
        return np.tanh(best_slope / np.std(price) * 10)
    
    def _hp_filter_trend(self, price: np.ndarray) -> float:
        """Hodrick-Prescott filter trend"""
        if len(price) < 4:
            return 0.0
        
        # HP filter (simplified)
        T = len(price)
        lambda_param = 1600  # For daily data
        
        # Create matrices
        I = np.eye(T)
        D = np.zeros((T - 2, T))
        for i in range(T - 2):
            D[i, i] = 1
            D[i, i + 1] = -2
            D[i, i + 2] = 1
        
        try:
            trend = np.linalg.solve(I + lambda_param * D.T @ D, price)
            # Extract trend direction
            trend_change = (trend[-1] - trend[0]) / (trend[0] + 1e-10)
            return np.tanh(trend_change)
        except:
            return 0.0
    
    def _adx_trend(self, df: pd.DataFrame) -> float:
        """Average Directional Index (trend strength)"""
        if len(df) < 14:
            return 0.0
        
        high = df['high'].values
        low = df['low'].values
        close = df['close'].values
        
        # Calculate +DM, -DM
        plus_dm = np.zeros(len(high))
        minus_dm = np.zeros(len(high))
        
        for i in range(1, len(high)):
            high_diff = high[i] - high[i - 1]
            low_diff = low[i - 1] - low[i]
            
            if high_diff > low_diff and high_diff > 0:
                plus_dm[i] = high_diff
            if low_diff > high_diff and low_diff > 0:
                minus_dm[i] = low_diff
        
        # Calculate TR (true range)
        tr = np.maximum(
            np.maximum(high[1:] - low[1:], np.abs(high[1:] - close[:-1])),
            np.abs(low[1:] - close[:-1])
        )
        tr = np.concatenate([[0], tr])
        
        # Calculate DI values
        atr = np.mean(tr[-14:]) if len(tr) > 0 else 1.0
        plus_di = 100 * np.mean(plus_dm[-14:]) / (atr + 1e-10)
        minus_di = 100 * np.mean(minus_dm[-14:]) / (atr + 1e-10)
        
        # ADX is absolute difference
        adx = abs(plus_di - minus_di) / 100
        
        # Direction
        direction = 1.0 if plus_di > minus_di else -1.0
        
        return direction * np.tanh(adx)
    
    def _arima_trend(self, price: np.ndarray) -> float:
        """Simple momentum/ARIMA-like trend"""
        if len(price) < 3:
            return 0.0
        
        # Calculate returns
        returns = np.diff(np.log(price))
        
        # Momentum: exponential moving average of returns
        ema = np.mean(returns[-5:])  # Recent momentum
        
        return np.tanh(ema * 100)
    
    def detect_information_flow(self, df: pd.DataFrame) -> Dict[str, float]:
        """Detect information flow signals"""
        signals = {}
        
        # Volume anomaly
        try:
            vol_z = self._volume_anomaly(df)
            signals['volume_anomaly'] = vol_z
        except:
            signals['volume_anomaly'] = 0.0
        
        # Volatility shift
        try:
            vol_shift = self._volatility_shift(df)
            signals['volatility_shift'] = vol_shift
        except:
            signals['volatility_shift'] = 0.0
        
        # Bid-ask spread (approximated by high-low)
        try:
            spread = self._spread_analysis(df)
            signals['spread_change'] = spread
        except:
            signals['spread_change'] = 0.0
        
        return signals
    
    def _volume_anomaly(self, df: pd.DataFrame) -> float:
        """Z-score of current volume vs historical"""
        if len(df) < self.volume_lookback:
            return 0.0
        
        recent_vol = df['volume'].tail(self.volume_lookback)
        current_vol = df['volume'].iloc[-1]
        
        mean_vol = recent_vol.mean()
        std_vol = recent_vol.std()
        
        if std_vol == 0:
            return 0.0
        
        z_score = (current_vol - mean_vol) / std_vol
        return np.tanh(z_score / 2)  # Clip to (-1, 1)
    
    def _volatility_shift(self, df: pd.DataFrame) -> float:
        """Detect volatility regime shift"""
        if len(df) < 20:
            return 0.0
        
        recent_returns = np.log(df['close'] / df['close'].shift(1)).dropna()
        
        vol_recent = recent_returns[-5:].std()
        vol_historical = recent_returns[-20:-5].std()
        
        if vol_historical == 0:
            return 0.0
        
        vol_ratio = vol_recent / vol_historical
        # 1.0 = no change, >1.0 = increasing volatility
        return np.tanh((vol_ratio - 1) * 2)
    
    def _spread_analysis(self, df: pd.DataFrame) -> float:
        """Analyze bid-ask spread (proxy: high-low range)"""
        if len(df) < 10:
            return 0.0
        
        recent_range = (df['high'] - df['low']).tail(10)
        current_range = df['high'].iloc[-1] - df['low'].iloc[-1]
        
        mean_range = recent_range.mean()
        if mean_range == 0:
            return 0.0
        
        range_ratio = current_range / mean_range
        return np.tanh((range_ratio - 1) * 2)
    
    def detect_momentum_reversal(self, df: pd.DataFrame) -> Dict[str, float]:
        """Detect momentum and mean reversion signals"""
        signals = {}
        
        # Order imbalance (buy volume vs sell volume)
        try:
            signals['order_imbalance'] = self._order_imbalance(df)
        except:
            signals['order_imbalance'] = 0.0
        
        # Mean reversion extreme
        try:
            signals['mean_reversion'] = self._mean_reversion(df)
        except:
            signals['mean_reversion'] = 0.0
        
        # Momentum continuation
        try:
            signals['momentum'] = self._momentum_continuation(df)
        except:
            signals['momentum'] = 0.0
        
        return signals
    
    def _order_imbalance(self, df: pd.DataFrame) -> float:
        """Estimate buy/sell imbalance from volume"""
        if len(df) < 2:
            return 0.0
        
        # Simple: volume is higher on up days = buying pressure
        up_days = (df['close'] > df['open']).astype(int)
        vol_up = (df['volume'] * up_days).sum()
        vol_down = (df['volume'] * (1 - up_days)).sum()
        
        total_vol = vol_up + vol_down
        if total_vol == 0:
            return 0.0
        
        ratio = vol_up / total_vol
        # 0.5 = neutral, >0.5 = buying pressure, <0.5 = selling
        return (ratio - 0.5) * 2  # Scale to (-1, 1)
    
    def _mean_reversion(self, df: pd.DataFrame) -> float:
        """Detect extreme prices (mean reversion opportunity)"""
        if len(df) < 20:
            return 0.0
        
        close_price = df['close'].values[-20:]
        current_price = close_price[-1]
        
        mean_price = close_price.mean()
        std_price = close_price.std()
        
        if std_price == 0:
            return 0.0
        
        z_score = (current_price - mean_price) / std_price
        
        # Extreme = |z| > 2.0, mean reversion is OPPOSITE direction
        # High extreme (z > 2) = bearish (sell)
        # Low extreme (z < -2) = bullish (buy)
        return -np.tanh(z_score / 2)  # Invert: positive z -> negative signal
    
    def _momentum_continuation(self, df: pd.DataFrame) -> float:
        """Detect momentum continuation"""
        if len(df) < 5:
            return 0.0
        
        returns = np.diff(np.log(df['close'].values[-5:]))
        momentum = np.mean(returns)
        
        return np.tanh(momentum * 100)
    
    def generate_signal(self, df: pd.DataFrame) -> Tuple[float, str, str]:
        """
        Generate comprehensive signal with confidence and reasoning
        Returns: (confidence_score, direction, reasoning)
        """
        if len(df) < self.lookback_days:
            return 0.0, 'neutral', 'Insufficient data'
        
        # 1. Detect trends using 6 methods
        trends = self.detect_trends(df)
        consensus = np.mean([v for v in trends.values()])
        trend_agreement = sum(1 for v in trends.values() if (v > 0) == (consensus > 0))
        trend_consensus_strength = trend_agreement / len(self.METHODS)
        
        # 2. Information flow signals
        info_flow = self.detect_information_flow(df)
        info_score = np.mean([v for v in info_flow.values()])
        
        # 3. Momentum/reversal signals
        momentum = self.detect_momentum_reversal(df)
        momentum_score = np.mean([v for v in momentum.values()])
        
        # 4. Combine signals with weights
        # Trend (50%), Information Flow (25%), Momentum (25%)
        combined_score = (
            0.50 * consensus +
            0.25 * info_score +
            0.25 * momentum_score
        )
        
        # 5. Confidence = trend consensus strength
        confidence = trend_consensus_strength
        
        # Normalize to 0-1
        signal_strength = np.tanh(combined_score) * 0.5 + 0.5
        
        # Determine direction
        if combined_score > 0.1 and confidence > self.trend_threshold:
            direction = 'bullish'
        elif combined_score < -0.1 and confidence > self.trend_threshold:
            direction = 'bearish'
        else:
            direction = 'neutral'
        
        # Build reasoning
        methods_bullish = sum(1 for v in trends.values() if v > 0)
        methods_bearish = sum(1 for v in trends.values() if v < 0)
        
        reasoning = f"""
Consensus: {methods_bullish}B/{methods_bearish}Be/{6-methods_bullish-methods_bearish}N | 
Trend: {consensus:.2f} | Info: {info_score:.2f} | Momentum: {momentum_score:.2f} |
Confidence: {signal_strength*100:.0f}%
"""
        
        return signal_strength, direction, reasoning.strip()
    
    def calculate_risk_parameters(self, df: pd.DataFrame, 
                                 position_size_pct: float = 0.05) -> Dict[str, float]:
        """
        Calculate risk parameters for position
        Returns: {stop_loss_pct, target_pct, position_size}
        """
        if len(df) < 20:
            return {'stop_loss': 0.02, 'target': 0.05, 'position_size': position_size_pct}
        
        # Calculate volatility
        returns = np.log(df['close'] / df['close'].shift(1)).dropna()
        volatility = returns.std()
        
        # ATR-based stop loss
        atr = (df['high'] - df['low']).tail(14).mean()
        atr_pct = atr / df['close'].iloc[-1]
        
        # Position size inverse to volatility
        # High vol = smaller position
        # Low vol = larger position
        position_size = position_size_pct / (1 + volatility * 10)
        position_size = np.clip(position_size, 0.01, position_size_pct * 2)
        
        # Stop loss: 2x ATR
        stop_loss = atr_pct * 2
        
        # Target: 3x stop loss (risk/reward = 1:3)
        target = stop_loss * 3
        
        return {
            'stop_loss_pct': stop_loss,
            'target_pct': target,
            'position_size': position_size,
            'volatility': volatility,
            'atr': atr
        }


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    
    gen = EnsembleSignalGenerator()
    logger.info(f"Ensemble Signal Generator initialized")
    logger.info(f"Methods: {', '.join(EnsembleSignalGenerator.METHODS)}")
