"""
Robust trend detection using SOTA techniques.
Replaces simple linear regression with methods resistant to outliers and market shocks.
"""

import numpy as np
import pandas as pd
from scipy import stats, signal
from sklearn.linear_model import HuberRegressor, RANSACRegressor


class RobustTrendDetector:
    """Detect trends using multiple robust methods resistant to outliers."""
    
    def __init__(self, lookback_period=20):
        self.lookback_period = lookback_period
    
    def theil_sen_slope(self, prices):
        """
        Theil-Sen slope: Median-based robust regression.
        Resistant to outliers (gap moves don't distort the slope).
        
        Returns: slope, intercept
        """
        if len(prices) < 2:
            return 0, prices[0]
        
        x = np.arange(len(prices))
        result = stats.theilslopes(prices, x, alpha=0.95)
        slope, intercept, low, high = result
        
        return slope, intercept
    
    def lowess_trend(self, prices, frac=0.3):
        """
        LOWESS (Locally Weighted Scatterplot Smoothing) - simplified implementation.
        Non-parametric method that captures local trend changes.
        Better than linear regression for non-linear markets.
        
        Returns: smoothed trend line
        """
        if len(prices) < 3:
            return prices.copy()
        
        # Simple implementation: weighted average of nearby points
        x = np.arange(len(prices))
        smoothed = np.zeros_like(prices)
        window = max(3, int(len(prices) * frac))
        
        for i in range(len(prices)):
            # Find neighbors
            start = max(0, i - window)
            end = min(len(prices), i + window + 1)
            
            # Distance-based weights (closer points have higher weight)
            indices = np.arange(start, end)
            distances = np.abs(indices - i)
            weights = np.exp(-distances**2 / (2 * (window/2)**2))
            weights /= weights.sum()
            
            smoothed[i] = np.sum(prices[start:end] * weights)
        
        return smoothed
    
    def huber_regression(self, prices):
        """
        Huber Regression: Combines L2 loss (normal) + L1 loss (robust).
        Less sensitive to outliers than OLS, but doesn't ignore them completely.
        
        Returns: fitted trend line, robustness score
        """
        x = np.arange(len(prices)).reshape(-1, 1)
        
        huber = HuberRegressor(epsilon=1.35, max_iter=100)
        huber.fit(x, prices)
        
        trend = huber.predict(x)
        slope = huber.coef_[0]
        
        # Robustness: how many points were weighted down?
        residuals = prices - trend
        outlier_fraction = np.sum(np.abs(residuals) > 1.35 * np.std(residuals)) / len(prices)
        robustness = 1 - outlier_fraction
        
        return trend, slope, robustness
    
    def ransac_regression(self, prices):
        """
        RANSAC (Random Sample Consensus): Robust to large amount of outliers.
        Finds best-fit line by randomly sampling inliers.
        
        Returns: fitted trend line, inlier fraction
        """
        x = np.arange(len(prices)).reshape(-1, 1)
        
        ransac = RANSACRegressor(random_state=42, max_trials=100)
        ransac.fit(x, prices)
        
        trend = ransac.predict(x)
        slope = ransac.estimator_.coef_[0]
        inlier_fraction = ransac.inlier_mask_.sum() / len(prices)
        
        return trend, slope, inlier_fraction
    
    def kalman_filter_trend(self, prices, process_variance=1e-5, measurement_variance=0.1):
        """
        Kalman Filter: Optimal recursive algorithm for trend extraction.
        Adapts to trend changes in real-time.
        
        Returns: filtered trend, trend velocity (slope)
        """
        n = len(prices)
        
        # State: [position, velocity]
        # Measurement matrix: H = [1, 0] (we observe position)
        # State transition: F = [1, dt; 0, 1] (constant velocity model)
        
        dt = 1.0
        F = np.array([[1, dt], [0, 1]])  # State transition
        H = np.array([[1, 0]])            # Measurement matrix
        Q = np.array([[0, 0], [0, process_variance]])  # Process noise
        R = np.array([[measurement_variance]])          # Measurement noise
        
        # Initial state
        x = np.array([prices[0], 0])  # position, velocity
        P = np.eye(2)  # Covariance
        
        filtered_positions = []
        velocities = []
        
        for z in prices:
            # Predict
            x = F @ x
            P = F @ P @ F.T + Q
            
            # Update
            y = z - (H @ x)[0]  # Innovation
            S = (H @ P @ H.T + R)[0, 0]  # Innovation covariance
            K = (P @ H.T / S)[:, 0]  # Kalman gain
            
            x = x + K * y
            P = (np.eye(2) - K.reshape(2, 1) @ H) @ P
            
            filtered_positions.append(x[0])
            velocities.append(x[1])
        
        return np.array(filtered_positions), np.array(velocities)
    
    def hodrick_prescott_filter(self, prices, lambda_param=1600):
        """
        Hodrick-Prescott Filter: Separates trend from cyclical component.
        Standard in econometrics for trend extraction.
        
        Returns: trend component
        """
        prices_array = np.array(prices, dtype=float)
        T = len(prices_array)
        
        # HP filter is: minimize sum((y_t - t_t)^2) + lambda * sum((t_{t+1} - 2*t_t + t_{t-1})^2)
        # This is equivalent to solving a linear system
        
        I = np.eye(T)
        D = np.zeros((T - 2, T))
        for i in range(T - 2):
            D[i, i] = 1
            D[i, i + 1] = -2
            D[i, i + 2] = 1
        
        trend = np.linalg.solve(I + lambda_param * D.T @ D, prices_array)
        
        return trend
    
    def get_robust_trend(self, data):
        """
        Multi-method consensus approach using all robust techniques.
        
        Returns: dict with results from all methods + consensus
        """
        if len(data) < self.lookback_period:
            return {'consensus': 'unknown', 'confidence': 0}
        
        prices = data.iloc[-self.lookback_period:]['Close'].values
        x = np.arange(len(prices))
        
        # Method 1: Theil-Sen
        ts_slope, ts_intercept = self.theil_sen_slope(prices)
        ts_trend = ts_slope * x + ts_intercept
        ts_direction = 'uptrend' if ts_slope > 0 else ('downtrend' if ts_slope < 0 else 'consolidation')
        ts_strength = abs(ts_slope / np.std(prices)) if np.std(prices) > 0 else 0
        
        # Method 2: LOWESS
        lowess_trend = self.lowess_trend(prices)
        lowess_slope = (lowess_trend[-1] - lowess_trend[0]) / len(prices)
        lowess_direction = 'uptrend' if lowess_slope > 0 else ('downtrend' if lowess_slope < 0 else 'consolidation')
        
        # Method 3: Huber
        huber_trend, huber_slope, huber_robust = self.huber_regression(prices)
        huber_direction = 'uptrend' if huber_slope > 0 else ('downtrend' if huber_slope < 0 else 'consolidation')
        
        # Method 4: RANSAC
        ransac_trend, ransac_slope, ransac_inliers = self.ransac_regression(prices)
        ransac_direction = 'uptrend' if ransac_slope > 0 else ('downtrend' if ransac_slope < 0 else 'consolidation')
        
        # Method 5: Kalman
        kalman_positions, kalman_velocities = self.kalman_filter_trend(prices)
        kalman_slope = kalman_velocities[-1]
        kalman_direction = 'uptrend' if kalman_slope > 0 else ('downtrend' if kalman_slope < 0 else 'consolidation')
        
        # Method 6: HP Filter
        hp_trend = self.hodrick_prescott_filter(prices, lambda_param=1600)
        hp_slope = (hp_trend[-1] - hp_trend[0]) / len(prices)
        hp_direction = 'uptrend' if hp_slope > 0 else ('downtrend' if hp_slope < 0 else 'consolidation')
        
        # Consensus
        directions = [ts_direction, lowess_direction, huber_direction, ransac_direction, kalman_direction, hp_direction]
        downtrend_count = sum(1 for d in directions if 'down' in d)
        uptrend_count = sum(1 for d in directions if 'up' in d)
        
        if downtrend_count >= 3:
            consensus = 'downtrend'
            confidence = downtrend_count / 6
        elif uptrend_count >= 3:
            consensus = 'uptrend'
            confidence = uptrend_count / 6
        else:
            consensus = 'consolidation'
            confidence = 0.5
        
        return {
            'consensus': consensus,
            'confidence': confidence,
            'methods': {
                'theil_sen': {
                    'slope': ts_slope,
                    'direction': ts_direction,
                    'strength': ts_strength,
                    'trend': ts_trend
                },
                'lowess': {
                    'slope': lowess_slope,
                    'direction': lowess_direction,
                    'trend': lowess_trend
                },
                'huber': {
                    'slope': huber_slope,
                    'direction': huber_direction,
                    'robustness': huber_robust,
                    'trend': huber_trend
                },
                'ransac': {
                    'slope': ransac_slope,
                    'direction': ransac_direction,
                    'inlier_fraction': ransac_inliers,
                    'trend': ransac_trend
                },
                'kalman': {
                    'slope': kalman_slope,
                    'direction': kalman_direction,
                    'trend': kalman_positions,
                    'velocity': kalman_velocities
                },
                'hp_filter': {
                    'slope': hp_slope,
                    'direction': hp_direction,
                    'trend': hp_trend
                }
            }
        }
    
    def should_trust_mean_reversion_robust(self, data):
        """
        Decide if mean-reversion signal should be trusted using robust trend detection.
        
        Returns: (should_trade, multiplier, reason)
        """
        trend = self.get_robust_trend(data)
        consensus = trend['consensus']
        confidence = trend['confidence']
        
        if consensus == 'consolidation':
            return True, 1.0, "Consolidation (robust) - mean reversion likely"
        elif consensus == 'uptrend':
            return True, 0.7, "Uptrend (robust) - mean reversion possible"
        elif consensus == 'downtrend':
            if confidence >= 0.75:  # 5+ methods agree
                return False, 0.2, f"Strong downtrend ({confidence:.0%}) - avoid mean reversion"
            elif confidence >= 0.5:  # 3+ methods agree
                return True, 0.5, f"Moderate downtrend ({confidence:.0%}) - reduce confidence"
            else:
                return True, 0.8, f"Weak downtrend ({confidence:.0%}) - mean reversion possible"
        
        return True, 1.0, "Unknown trend"


if __name__ == '__main__':
    from src.data.fetch_data import fetch_ticker_data
    
    detector = RobustTrendDetector()
    
    print("=" * 100)
    print("TESTING ROBUST TREND DETECTION (SOTA Methods)")
    print("=" * 100)
    
    for ticker in ['NVDA', 'MSFT']:
        print(f"\n\n{'='*100}")
        print(f"TICKER: {ticker}")
        print(f"{'='*100}")
        
        if ticker == 'NVDA':
            data = fetch_ticker_data(ticker, start='2025-11-11', end='2025-12-01', progress=False)
        else:
            data = fetch_ticker_data(ticker, start='2025-10-17', end='2025-11-06', progress=False)
        
        if len(data) >= 20:
            result = detector.get_robust_trend(data)
            should_trade, mult, reason = detector.should_trust_mean_reversion_robust(data)
            
            print(f"\n🎯 CONSENSUS (from 6 methods):")
            print(f"  Direction: {result['consensus'].upper()}")
            print(f"  Confidence: {result['confidence']:.0%}")
            
            print(f"\n📊 INDIVIDUAL METHOD RESULTS:")
            for method_name, method_data in result['methods'].items():
                print(f"\n  {method_name.upper()}:")
                print(f"    Direction: {method_data['direction']}")
                print(f"    Slope: {method_data['slope']:.6f}")
                if 'robustness' in method_data:
                    print(f"    Robustness: {method_data['robustness']:.0%}")
                if 'inlier_fraction' in method_data:
                    print(f"    Inlier Fraction: {method_data['inlier_fraction']:.0%}")
            
            print(f"\n⚡ MEAN-REVERSION DECISION:")
            print(f"  Should trade: {'YES ✅' if should_trade else 'NO ❌'}")
            print(f"  Multiplier: {mult:.1f}x")
            print(f"  Reason: {reason}")
