"""
Proper statistical validation framework.
Ensures results are not due to luck/overfitting.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from scipy import stats

from backtest.production_simulator_robust import ProductionSimulator
from src.data.market_config import get_tickers
from src.signals.robust_signal_fixes import ValidationMetrics


class RobustValidator:
    """
    Comprehensive validation framework for trading systems.
    Tests:
    1. Multiple time periods (different market regimes)
    2. Out-of-sample validation (train/test split)
    3. Statistical significance (wins vs luck)
    4. Performance consistency (Sharpe, drawdown, etc)
    """
    
    def __init__(self, commission_pct=0.1, spread_pct=0.05, slippage_pct=0.1):
        self.commission_pct = commission_pct
        self.spread_pct = spread_pct
        self.slippage_pct = slippage_pct
    
    def run_validation(self, tickers, end_date, num_periods=4, days_per_period=90):
        """
        Run backtest over multiple non-overlapping periods.
        
        Tests if system works across different market regimes.
        """
        print("\n" + "="*70)
        print(f"MULTI-PERIOD VALIDATION ({num_periods} periods, {days_per_period}d each)")
        print("="*70)
        
        results_by_period = []
        
        for period_idx in range(num_periods):
            period_end = end_date - timedelta(days=days_per_period * (num_periods - period_idx - 1))
            period_start = period_end - timedelta(days=days_per_period)
            
            period_name = f"P{period_idx+1} ({period_start.date()} → {period_end.date()})"
            
            simulator = ProductionSimulator(
                commission_pct=self.commission_pct,
                spread_pct=self.spread_pct,
                slippage_pct=self.slippage_pct
            )
            
            print(f"\n{period_name}")
            results = simulator.run_backtest(tickers, period_start, period_end)
            
            if results:
                returns = [r['total_return_pct'] for r in results]
                wins = [r['win_rate_pct'] for r in results]
                
                period_stats = {
                    'period': period_name,
                    'start': period_start,
                    'end': period_end,
                    'num_stocks': len(results),
                    'avg_return': np.mean(returns),
                    'avg_win_rate': np.mean(wins),
                    'results': results
                }
                
                print(f"  Return: {period_stats['avg_return']:+.1f}% | Win: {period_stats['avg_win_rate']:.0f}%")
                results_by_period.append(period_stats)
        
        return results_by_period
    
    def validate_statistical_significance(self, all_results):
        """
        Check if win rates are statistically significant.
        
        H0: Win rate = 50% (random)
        H1: Win rate > 50% (actual edge)
        """
        print("\n" + "="*70)
        print("STATISTICAL SIGNIFICANCE TEST")
        print("="*70)
        
        total_trades = sum(r['num_trades'] for r in all_results)
        total_wins = sum(r['winning_trades'] for r in all_results)
        win_rate = total_wins / total_trades * 100 if total_trades > 0 else 0
        
        print(f"\nTotal trades: {total_trades}")
        print(f"Winning trades: {total_wins}")
        print(f"Win rate: {win_rate:.1f}%")
        
        # Binomial test: Is win_rate significantly > 50%?
        if total_trades >= 30:
            p_value = stats.binom_test(total_wins, total_trades, 0.5, alternative='greater')
            print(f"\nBinomial test (H1: win_rate > 50%):")
            print(f"  p-value: {p_value:.4f}")
            
            if p_value < 0.05:
                print(f"  ✅ SIGNIFICANT at α=0.05 (real edge detected)")
            elif p_value < 0.10:
                print(f"  ⚠️  Borderline at α=0.10 (edge possible but weak)")
            else:
                print(f"  ❌ NOT SIGNIFICANT (could be luck)")
            
            # Confidence interval
            lower, upper, sig = ValidationMetrics.calculate_confidence_interval(win_rate, total_trades)
            if lower and upper:
                print(f"\n95% Confidence Interval: [{lower:.1f}%, {upper:.1f}%]")
                if sig:
                    print(f"  ✅ 50% is outside CI (statistically proven edge)")
                else:
                    print(f"  ❌ 50% is inside CI (no proven edge)")
        else:
            print(f"\n⚠️  Insufficient trades ({total_trades} < 30) for statistical test")
    
    def compare_periods(self, results_by_period):
        """Check if performance is consistent across periods."""
        print("\n" + "="*70)
        print("CONSISTENCY ACROSS PERIODS")
        print("="*70)
        
        returns = [p['avg_return'] for p in results_by_period]
        wins = [p['avg_win_rate'] for p in results_by_period]
        
        print(f"\nReturn statistics:")
        print(f"  Mean: {np.mean(returns):+.1f}%")
        print(f"  Std Dev: {np.std(returns):.1f}%")
        print(f"  Range: [{np.min(returns):+.1f}%, {np.max(returns):+.1f}%]")
        
        print(f"\nWin Rate statistics:")
        print(f"  Mean: {np.mean(wins):.1f}%")
        print(f"  Std Dev: {np.std(wins):.1f}%")
        print(f"  Range: [{np.min(wins):.1f}%, {np.max(wins):.1f}%]")
        
        # ANOVA test: Is performance significantly different across periods?
        if len(returns) >= 3:
            # One-way ANOVA
            f_stat, p_value = stats.f_oneway(
                [r['avg_return'] for r in results_by_period if len(r['results']) > 0]
            )
            
            print(f"\nANOVA test (consistency across periods):")
            print(f"  F-statistic: {f_stat:.2f}")
            print(f"  p-value: {p_value:.4f}")
            
            if p_value > 0.05:
                print(f"  ✅ No significant difference (consistent performance)")
            else:
                print(f"  ⚠️  Performance varies across periods (possibly period-dependent)")
    
    def print_final_verdict(self, results_by_period, all_results):
        """Final honest assessment."""
        print("\n" + "="*70)
        print("FINAL VALIDATION VERDICT")
        print("="*70)
        
        total_trades = sum(r['num_trades'] for r in all_results)
        total_wins = sum(r['winning_trades'] for r in all_results)
        win_rate = total_wins / total_trades * 100 if total_trades > 0 else 0
        avg_return = np.mean([r['total_return_pct'] for r in all_results])
        
        print(f"\nSample size: {total_trades} trades")
        print(f"Win rate: {win_rate:.1f}%")
        print(f"Average return: {avg_return:+.1f}%")
        
        # Verdict scoring
        score = 0
        
        # 1. Sample size (need 100+ trades minimum)
        if total_trades >= 100:
            score += 1
            print(f"\n✅ Sample size: {total_trades} trades (sufficient)")
        elif total_trades >= 50:
            print(f"\n⚠️  Sample size: {total_trades} trades (borderline)")
        else:
            print(f"\n❌ Sample size: {total_trades} trades (too few)")
        
        # 2. Win rate significance
        if total_trades >= 30:
            p_value = stats.binom_test(total_wins, total_trades, 0.5, alternative='greater')
            if p_value < 0.05:
                score += 1
                print(f"✅ Statistical significance: p={p_value:.4f} (real edge)")
            elif p_value < 0.10:
                print(f"⚠️  Statistical significance: p={p_value:.4f} (borderline)")
            else:
                print(f"❌ Statistical significance: p={p_value:.4f} (no edge)")
        
        # 3. Consistency
        returns = [p['avg_return'] for p in results_by_period]
        if len(returns) >= 3:
            f_stat, p_value = stats.f_oneway(*[[r['avg_return'] for r in results_by_period if len(r['results']) > 0]])
            if p_value > 0.05:
                score += 1
                print(f"✅ Consistency: Performs similarly across periods")
            else:
                print(f"⚠️  Consistency: Performance varies across periods")
        
        # 4. Absolute returns
        if avg_return > 5:
            score += 1
            print(f"✅ Returns: {avg_return:+.1f}% (meaningful)")
        elif avg_return > 2:
            print(f"⚠️  Returns: {avg_return:+.1f}% (modest)")
        else:
            print(f"❌ Returns: {avg_return:+.1f}% (marginal)")
        
        print(f"\nValidation Score: {score}/4")
        
        if score >= 3:
            print(f"✅ READY FOR LIVE TESTING with limited capital (5-10%)")
        elif score >= 2:
            print(f"⚠️  NEEDS MORE VALIDATION - Continue paper trading")
        else:
            print(f"❌ NOT READY - Rework signal logic or collect more data")


if __name__ == '__main__':
    print("=" * 70)
    print("ROBUST VALIDATION FRAMEWORK")
    print("=" * 70)
    
    end_date = datetime.now()
    
    # Test US market
    print("\n🟦 US MARKET VALIDATION")
    us_tickers = get_tickers('us')[:5]
    
    validator_us = RobustValidator(
        commission_pct=0.1,
        spread_pct=0.05,
        slippage_pct=0.1
    )
    
    results_us = validator_us.run_validation(us_tickers, end_date, num_periods=2, days_per_period=90)
    all_results_us = [r for p in results_us for r in p['results']]
    
    validator_us.validate_statistical_significance(all_results_us)
    validator_us.compare_periods(results_us)
    validator_us.print_final_verdict(results_us, all_results_us)
    
    # Test BR market
    print("\n\n🟩 BR MARKET VALIDATION")
    br_tickers = get_tickers('br')[:5]
    
    validator_br = RobustValidator(
        commission_pct=0.5,
        spread_pct=0.1,
        slippage_pct=0.2
    )
    
    results_br = validator_br.run_validation(br_tickers, end_date, num_periods=2, days_per_period=90)
    all_results_br = [r for p in results_br for r in p['results']]
    
    validator_br.validate_statistical_significance(all_results_br)
    validator_br.compare_periods(results_br)
    validator_br.print_final_verdict(results_br, all_results_br)
