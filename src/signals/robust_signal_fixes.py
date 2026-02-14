"""
Bug fixes for signal detectors.
Fixes the issues found in code review:
1. Silent exception handling in order_imbalance
2. Proper z-score thresholds (2.0 → 2.5)
3. Better volatility regime detection
"""

import numpy as np
import pandas as pd
from scipy import stats


class FixedInformationFlowDetector:
    """Fixed version of InformationFlowDetector with proper error handling."""
    
    def __init__(self, lookback_period=20):
        self.lookback_period = lookback_period
    
    def detect_volume_anomaly(self, data):
        """
        Detect unusual volume at extreme price levels.
        FIX: Better error handling and edge case detection
        """
        if len(data) < self.lookback_period:
            return 0, "Insufficient data"
        
        try:
            recent = data.iloc[-1]
            history = data.iloc[-self.lookback_period:]
            
            # Safe conversion to float
            avg_volume = float(history['Volume'].mean())
            std_volume = float(history['Volume'].std())
            current_volume = float(recent['Volume'])
            
            if std_volume <= 1e-8 or avg_volume <= 0:
                return 0, "No volume variation"
            
            volume_zscore = (current_volume - avg_volume) / std_volume
            
            # Price extremes
            high_20 = float(history['High'].max())
            low_20 = float(history['Low'].min())
            current_price = float(recent['Close'])
            
            # At extreme with HIGH volume
            at_high = current_price >= high_20 * 0.99
            at_low = current_price <= low_20 * 1.01
            
            # FIX: Raised threshold from 2.0 to 2.5 (more extreme)
            if (at_high or at_low) and volume_zscore > 2.5:
                direction = "above" if at_high else "below"
                explanation = f"Extreme volume ({volume_zscore:.1f}σ) at price {direction} 20-day {('high' if at_high else 'low')}"
                return min(volume_zscore / 3.0, 1.0), explanation
            
            return 0, "Normal volume"
        
        except Exception as e:
            return 0, f"Error: {str(e)[:30]}"  # Specific error, not silent fail
    
    def detect_volatility_regime_shift(self, data):
        """
        FIX: Better handling of edge cases and zero volatility
        """
        if len(data) < self.lookback_period + 5:
            return 0, "Insufficient data"
        
        try:
            history = data.iloc[-self.lookback_period:]
            prev_history = data.iloc[-(self.lookback_period + 5):-5]
            
            curr_returns = history['Close'].pct_change().std()
            prev_returns = prev_history['Close'].pct_change().std()
            
            if prev_returns == 0 or curr_returns == 0:
                return 0, "No volatility data"
            
            vol_ratio = curr_returns / prev_returns
            
            # F-test
            f_stat = (curr_returns ** 2) / (prev_returns ** 2)
            try:
                p_value = 1 - stats.f.cdf(f_stat, len(history) - 1, len(prev_history) - 1)
            except:
                return 0, "F-test failed"
            
            # FIX: Raised vol_ratio threshold from 1.3 to 1.5 (more extreme)
            if p_value < 0.05 and vol_ratio > 1.5:
                explanation = f"Volatility regime shift: {vol_ratio:.2f}x increase (p={p_value:.3f})"
                return min((vol_ratio - 1.0), 1.0), explanation
            
            return 0, "Stable volatility"
        
        except Exception as e:
            return 0, f"Error: {str(e)[:30]}"


class FixedMomentumReversalDetector:
    """Fixed version of MomentumReversalDetector with proper thresholds."""
    
    def __init__(self, lookback_period=20):
        self.lookback_period = lookback_period
    
    def detect_order_imbalance(self, data):
        """
        FIX: Proper exception handling (was silently returning 1.0 p-value)
        Raised threshold: 2.5σ instead of 2.0σ
        """
        if len(data) < self.lookback_period:
            return 0, None, "Insufficient data"
        
        try:
            history = data.iloc[-self.lookback_period:]
            
            # Calculate up/down volume
            up_volume = 0
            down_volume = 0
            
            for i in range(1, len(history)):
                close_diff = history.iloc[i]['Close'] - history.iloc[i-1]['Close']
                vol = history.iloc[i]['Volume']
                
                if close_diff > 0:
                    up_volume += vol
                elif close_diff < 0:
                    down_volume += vol
            
            total_volume = up_volume + down_volume
            if total_volume == 0:
                return 0, None, "No volume"
            
            imbalance_ratio = (up_volume - down_volume) / total_volume
            
            # FIX: Proper exception handling
            try:
                p_value = stats.binom_test(
                    int(up_volume), 
                    int(total_volume), 
                    0.5, 
                    alternative='two-sided'
                )
            except ValueError as e:
                return 0, None, f"Binomial test failed: {str(e)[:20]}"
            
            # FIX: Raised threshold from 0.15 to 0.20 (more extreme)
            if abs(imbalance_ratio) > 0.20 and p_value < 0.05:
                direction = 'bullish' if imbalance_ratio > 0 else 'bearish'
                explanation = f"Order imbalance: {abs(imbalance_ratio)*100:.1f}% bias {direction} (p={p_value:.3f})"
                return min(abs(imbalance_ratio) * 2, 1.0), direction, explanation
            
            return 0, None, "Balanced order flow"
        
        except Exception as e:
            return 0, None, f"Error: {str(e)[:30]}"
    
    def detect_mean_reversion_extreme(self, data):
        """
        FIX: Stricter threshold (2.5σ instead of 2.0σ)
        Use proper volatility calculation
        """
        if len(data) < self.lookback_period:
            return 0, None, "Insufficient data"
        
        try:
            history = data.iloc[-self.lookback_period:]
            recent = data.iloc[-1]
            
            # Cumulative return
            cum_returns = (recent['Close'] / history.iloc[0]['Close']) - 1
            
            # Rolling volatility
            returns = history['Close'].pct_change().dropna()
            mean_return = returns.mean()
            std_return = returns.std()
            
            if std_return == 0 or len(returns) < 3:
                return 0, None, "No volatility"
            
            # Z-score
            zscore = cum_returns / std_return
            
            # FIX: Raised from 2.0σ to 2.5σ (more extreme)
            if abs(zscore) > 2.5:
                direction = 'bearish' if zscore > 0 else 'bullish'
                explanation = f"Mean reversion extreme: {zscore:.1f}σ {direction} signal"
                return min(abs(zscore) / 3.0, 1.0), direction, explanation
            
            return 0, None, "Normal range"
        
        except Exception as e:
            return 0, None, f"Error: {str(e)[:30]}"


class ValidationMetrics:
    """Calculate proper statistical validation metrics."""
    
    @staticmethod
    def calculate_confidence_interval(win_rate, num_trades, confidence=0.95):
        """
        Calculate 95% confidence interval for win rate.
        
        Returns: (lower_bound, upper_bound, is_significant)
        
        Significant: 50% is NOT in confidence interval
        """
        if num_trades < 30:
            return None, None, False  # Too few samples
        
        p = win_rate / 100.0
        se = np.sqrt(p * (1 - p) / num_trades)
        
        # 95% CI (1.96 standard errors)
        z = 1.96
        lower = max(0, p - z * se) * 100
        upper = min(1, p + z * se) * 100
        
        # Is 50% in confidence interval?
        is_significant = not (lower <= 50 <= upper)
        
        return lower, upper, is_significant
    
    @staticmethod
    def calculate_sharpe_ratio(returns_pct, risk_free_rate=2.0):
        """Calculate Sharpe ratio for returns."""
        returns = np.array(returns_pct) / 100.0
        excess_return = returns.mean() - (risk_free_rate / 100.0)
        if returns.std() == 0:
            return 0
        return excess_return / returns.std()
    
    @staticmethod
    def drawdown_analysis(equity_log):
        """Calculate maximum drawdown and drawdown duration."""
        if not equity_log:
            return 0, 0
        
        equities = np.array([e['equity'] for e in equity_log])
        running_max = np.maximum.accumulate(equities)
        drawdowns = (equities - running_max) / running_max
        
        max_dd = np.min(drawdowns)
        
        # Duration of max drawdown
        max_dd_idx = np.argmin(drawdowns)
        recovery_idx = np.where(running_max[max_dd_idx:] > running_max[max_dd_idx])[0]
        duration = recovery_idx[0] if len(recovery_idx) > 0 else len(drawdowns) - max_dd_idx
        
        return abs(max_dd) * 100, duration
    
    @staticmethod
    def print_statistical_summary(results):
        """Print statistically valid summary."""
        returns = [r['total_return_pct'] for r in results]
        win_rates = [r['win_rate_pct'] for r in results]
        trades = [r['num_trades'] for r in results]
        
        print("\n" + "="*70)
        print("STATISTICAL VALIDATION SUMMARY")
        print("="*70)
        
        print(f"\nSample Size: {len(results)} stocks")
        print(f"Total trades: {sum(trades)}")
        
        print(f"\nReturns:")
        print(f"  Mean: {np.mean(returns):+.2f}%")
        print(f"  Median: {np.median(returns):+.2f}%")
        print(f"  Std Dev: {np.std(returns):.2f}%")
        
        print(f"\nWin Rates:")
        print(f"  Mean: {np.mean(win_rates):.1f}%")
        print(f"  Median: {np.median(win_rates):.1f}%")
        
        # Confidence intervals on aggregate win rate
        total_wins = sum(1 for r in results if r['winning_trades'] > 0)
        agg_win_rate = total_wins / len(results) * 100 if results else 0
        lower, upper, sig = ValidationMetrics.calculate_confidence_interval(agg_win_rate, len(results))
        
        print(f"\nAggregate Win Rate: {agg_win_rate:.1f}%")
        if lower and upper:
            print(f"  95% CI: [{lower:.1f}%, {upper:.1f}%]")
            print(f"  Statistically significant: {'✅ YES' if sig else '❌ NO (could be luck)'}")
        else:
            print(f"  ⚠️  Too few trades ({len(results)}) for confidence interval")
        
        # Sharpe ratio
        sharpe = ValidationMetrics.calculate_sharpe_ratio(returns)
        print(f"\nSharpe Ratio: {sharpe:.2f}")
        if sharpe < 1.0:
            print(f"  ⚠️  Below 1.0 (not compelling)")
        elif sharpe < 1.5:
            print(f"  ⚠️  Adequate but risky")
        else:
            print(f"  ✅ Good risk-adjusted returns")
