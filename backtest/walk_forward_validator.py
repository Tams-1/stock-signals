"""
Walk-Forward Validation Framework.

Implements proper out-of-sample validation:
1. Splits 6-month historical data into overlapping windows
2. Tunes signal parameters on first window (1 month in-sample)
3. Tests on next window (1 month out-of-sample) without retuning
4. Rolls forward month by month
5. Computes out-of-sample returns for each window
6. Reports average out-of-sample return vs. in-sample
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from copy import deepcopy

from backtest.enhanced_cost_simulator import EnhancedCostSimulator
from src.data.fetch_data import fetch_ticker_data


class WalkForwardValidator:
    """Implement walk-forward analysis for proper out-of-sample validation."""
    
    def __init__(self, 
                 initial_capital=10000, 
                 position_size=0.5,
                 in_sample_days=30,
                 out_sample_days=30,
                 step_days=30):
        """
        Initialize walk-forward validator.
        
        Args:
            in_sample_days: Days to use for optimization
            out_sample_days: Days to test on (without retuning)
            step_days: How many days to roll forward (typically = out_sample_days)
        """
        self.initial_capital = initial_capital
        self.position_size = position_size
        self.in_sample_days = in_sample_days
        self.out_sample_days = out_sample_days
        self.step_days = step_days
    
    def optimize_threshold(self, ticker, train_start, train_end):
        """
        Optimize signal threshold on in-sample data.
        
        Returns best threshold that maximizes in-sample returns.
        """
        print(f"    Optimizing threshold for {ticker} ({train_start.date()} to {train_end.date()})...", end=" ", flush=True)
        
        thresholds = [0.3, 0.4, 0.5, 0.6, 0.7]
        best_threshold = 0.5
        best_return = -100
        
        try:
            for threshold in thresholds:
                simulator = EnhancedCostSimulator(
                    initial_capital=self.initial_capital,
                    position_size=self.position_size
                )
                
                result = simulator.simulate_ticker(ticker, train_start, train_end, threshold=threshold)
                
                if result and result['total_return_pct_with_costs'] > best_return:
                    best_return = result['total_return_pct_with_costs']
                    best_threshold = threshold
        except:
            pass
        
        print(f"Best threshold: {best_threshold:.1f} (in-sample return: {best_return:+.1f}%)")
        return best_threshold
    
    def test_on_out_sample(self, ticker, test_start, test_end, threshold):
        """Test on out-of-sample data using optimized threshold."""
        try:
            simulator = EnhancedCostSimulator(
                initial_capital=self.initial_capital,
                position_size=self.position_size
            )
            
            result = simulator.simulate_ticker(ticker, test_start, test_end, threshold=threshold)
            return result
        except:
            return None
    
    def run_walk_forward(self, ticker, start_date, end_date):
        """
        Run walk-forward analysis on a single ticker.
        
        Returns list of windows with in-sample and out-of-sample results.
        """
        print(f"\n🔄 Walk-Forward Analysis: {ticker}")
        print(f"   Period: {start_date.date()} to {end_date.date()}")
        print(f"   In-sample: {self.in_sample_days}d | Out-of-sample: {self.out_sample_days}d")
        
        windows = []
        current_date = start_date
        window_idx = 1
        
        while current_date + timedelta(days=self.in_sample_days + self.out_sample_days) <= end_date:
            
            train_start = current_date
            train_end = current_date + timedelta(days=self.in_sample_days)
            
            test_start = train_end
            test_end = test_start + timedelta(days=self.out_sample_days)
            
            print(f"\n  Window {window_idx} ({train_start.date()} → {test_end.date()})")
            
            # 1. Optimize on in-sample data
            best_threshold = self.optimize_threshold(ticker, train_start, train_end)
            
            # 2. Get in-sample results with optimized threshold
            print(f"    In-sample backtest...", end=" ", flush=True)
            simulator = EnhancedCostSimulator(
                initial_capital=self.initial_capital,
                position_size=self.position_size
            )
            in_sample_result = simulator.simulate_ticker(
                ticker, train_start, train_end, threshold=best_threshold
            )
            
            if not in_sample_result:
                print("Failed to get in-sample results")
                current_date += timedelta(days=self.step_days)
                window_idx += 1
                continue
            
            print(f"Return: {in_sample_result['total_return_pct_with_costs']:+.1f}%")
            
            # 3. Test on out-of-sample data (NO retuning)
            print(f"    Out-of-sample test...", end=" ", flush=True)
            out_sample_result = self.test_on_out_sample(
                ticker, test_start, test_end, best_threshold
            )
            
            if not out_sample_result:
                print("Failed to get out-of-sample results")
                current_date += timedelta(days=self.step_days)
                window_idx += 1
                continue
            
            print(f"Return: {out_sample_result['total_return_pct_with_costs']:+.1f}%")
            
            # 4. Store window results
            window_data = {
                'window': window_idx,
                'in_sample_start': train_start,
                'in_sample_end': train_end,
                'out_sample_start': test_start,
                'out_sample_end': test_end,
                'optimized_threshold': best_threshold,
                'in_sample_return': in_sample_result['total_return_pct_with_costs'],
                'in_sample_trades': in_sample_result['num_trades'],
                'in_sample_win_rate': in_sample_result['win_rate_pct'],
                'out_sample_return': out_sample_result['total_return_pct_with_costs'],
                'out_sample_trades': out_sample_result['num_trades'],
                'out_sample_win_rate': out_sample_result['win_rate_pct'],
                'overfit_gap': in_sample_result['total_return_pct_with_costs'] - out_sample_result['total_return_pct_with_costs'],
                'in_sample_detail': in_sample_result,
                'out_sample_detail': out_sample_result
            }
            
            windows.append(window_data)
            
            # Roll forward
            current_date += timedelta(days=self.step_days)
            window_idx += 1
        
        return windows
    
    def run_walk_forward_multiple(self, tickers, start_date, end_date):
        """Run walk-forward analysis on multiple tickers."""
        print(f"\n{'='*80}")
        print(f"WALK-FORWARD VALIDATION")
        print(f"Period: {start_date.date()} to {end_date.date()}")
        print(f"{'='*80}")
        
        all_results = {}
        
        for ticker in tickers:
            try:
                windows = self.run_walk_forward(ticker, start_date, end_date)
                all_results[ticker] = windows
            except Exception as e:
                print(f"Error processing {ticker}: {e}")
                continue
        
        return all_results
    
    def generate_summary(self, all_results):
        """Generate summary statistics for walk-forward analysis."""
        print(f"\n{'='*80}")
        print("WALK-FORWARD VALIDATION SUMMARY")
        print(f"{'='*80}\n")
        
        # Aggregate statistics
        all_in_sample = []
        all_out_sample = []
        all_overfit_gaps = []
        
        print("By Ticker:")
        print(f"{'Ticker':<10} {'Avg In-Sample':<15} {'Avg Out-Sample':<15} {'Overfit Gap':<15} {'Windows':<8}")
        print("-" * 65)
        
        for ticker, windows in all_results.items():
            if not windows:
                continue
            
            in_sample_returns = [w['in_sample_return'] for w in windows]
            out_sample_returns = [w['out_sample_return'] for w in windows]
            overfit_gaps = [w['overfit_gap'] for w in windows]
            
            avg_in = np.mean(in_sample_returns)
            avg_out = np.mean(out_sample_returns)
            avg_gap = np.mean(overfit_gaps)
            
            print(f"{ticker:<10} {avg_in:>+13.2f}% {avg_out:>+13.2f}% {avg_gap:>+13.2f}% {len(windows):>6}")
            
            all_in_sample.extend(in_sample_returns)
            all_out_sample.extend(out_sample_returns)
            all_overfit_gaps.extend(overfit_gaps)
        
        # Portfolio-level statistics
        print(f"\n{'='*80}")
        print("AGGREGATE STATISTICS (All Tickers & Windows)")
        print(f"{'='*80}")
        
        if all_in_sample:
            avg_in_sample = np.mean(all_in_sample)
            std_in_sample = np.std(all_in_sample)
            min_in_sample = np.min(all_in_sample)
            max_in_sample = np.max(all_in_sample)
            
            avg_out_sample = np.mean(all_out_sample)
            std_out_sample = np.std(all_out_sample)
            min_out_sample = np.min(all_out_sample)
            max_out_sample = np.max(all_out_sample)
            
            avg_gap = np.mean(all_overfit_gaps)
            
            print(f"\nIn-Sample Performance:")
            print(f"  Average return: {avg_in_sample:+.2f}%")
            print(f"  Std Dev: {std_in_sample:.2f}%")
            print(f"  Range: [{min_in_sample:+.2f}%, {max_in_sample:+.2f}%]")
            
            print(f"\nOut-of-Sample Performance (TRUE EDGE):")
            print(f"  Average return: {avg_out_sample:+.2f}%")
            print(f"  Std Dev: {std_out_sample:.2f}%")
            print(f"  Range: [{min_out_sample:+.2f}%, {max_out_sample:+.2f}%]")
            
            print(f"\nOverfitting Analysis:")
            print(f"  Average overfit gap: {avg_gap:+.2f}%")
            print(f"  (In-Sample Performance - Out-of-Sample Performance)")
            
            # Determine if there's a real edge
            print(f"\n{'='*80}")
            print("VERDICT:")
            print(f"{'='*80}")
            
            if avg_out_sample > 0.5:
                print(f"✅ POSITIVE OUT-OF-SAMPLE EDGE DETECTED")
                print(f"   Average out-of-sample return: {avg_out_sample:+.2f}%")
                print(f"   This suggests a real, testable edge (not just overfitting)")
            elif avg_out_sample > 0 and avg_gap > 5:
                print(f"⚠️  WEAK OUT-OF-SAMPLE EDGE WITH SIGNIFICANT OVERFITTING")
                print(f"   Average out-of-sample return: {avg_out_sample:+.2f}%")
                print(f"   Average overfitting gap: {avg_gap:+.2f}% (suggests parameter tuning was too aggressive)")
            elif avg_out_sample > 0:
                print(f"⚠️  MARGINAL OUT-OF-SAMPLE EDGE")
                print(f"   Average out-of-sample return: {avg_out_sample:+.2f}%")
                print(f"   Need more data/windows to confirm")
            else:
                print(f"❌ NO REAL EDGE DETECTED")
                print(f"   Average out-of-sample return: {avg_out_sample:+.2f}%")
                print(f"   System appears to be overfitted - in-sample tuning not predictive")
            
            print(f"\nNote: Out-of-sample returns include {self.initial_capital} capital base")
            print(f"      with realistic trading costs (0.1% slippage + $5 commission/round-trip)")
        
        return {
            'avg_in_sample': np.mean(all_in_sample) if all_in_sample else 0,
            'avg_out_sample': np.mean(all_out_sample) if all_out_sample else 0,
            'avg_overfit_gap': np.mean(all_overfit_gaps) if all_overfit_gaps else 0,
            'num_windows': len(all_in_sample),
            'std_out_sample': np.std(all_out_sample) if all_out_sample else 0
        }


if __name__ == '__main__':
    from src.data.market_config import get_tickers
    
    end_date = datetime.now()
    start_date = end_date - timedelta(days=180)  # 6 months
    
    # Test on a few tickers
    test_tickers = ['AAPL', 'MSFT', 'NVDA']
    
    validator = WalkForwardValidator(
        initial_capital=10000,
        position_size=0.5,
        in_sample_days=30,
        out_sample_days=30,
        step_days=30
    )
    
    results = validator.run_walk_forward_multiple(test_tickers, start_date, end_date)
    summary = validator.generate_summary(results)
