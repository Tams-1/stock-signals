#!/usr/bin/env python3
"""
Full validation of Fix #1 (regime detector) + Fix #2 (threshold).

Tests:
1. All 18 IBOV stocks on Period 4 (Feb 2025 - Feb 2026)
2. All 4 periods with new fixes
3. Comparison vs baseline results

Expected results:
- Period 4: +6-12% average (vs +1.06% baseline)
- Multi-period: Beat baseline in 3+/4 periods
- Win rates: 50-70% (realistic)
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from backtest.production_simulator_robust import ProductionSimulator
import json
import numpy as np


# All 18 IBOV top-volume stocks
ALL_TICKERS = [
    "PETR4.SA", "VALE3.SA", "ITUB4.SA", "BBDC4.SA", "BBAS3.SA",
    "ABEV3.SA", "B3SA3.SA", "SUZB3.SA", "RENT3.SA", "WEGE3.SA",
    "MGLU3.SA", "PCAR3.SA", "LREN3.SA", "RAIZ4.SA", "GGBR4.SA",
    "ASAI3.SA", "JBSS3.SA", "RDOR3.SA"
]

# Multi-period definitions
PERIODS = {
    'period_1': {
        'name': 'Jan-Jun 2024 (Choppy + Bull Mix)',
        'start': '2024-01-01',
        'end': '2024-06-30',
        'baseline_return': 4.28
    },
    'period_2': {
        'name': 'Jul-Dec 2024 (Continuation)',
        'start': '2024-07-01',
        'end': '2024-12-31',
        'baseline_return': 2.47
    },
    'period_3': {
        'name': 'Jan-Feb 2025 (Trending)',
        'start': '2025-01-01',
        'end': '2025-02-28',
        'baseline_return': 2.60
    },
    'period_4': {
        'name': 'Feb 2025 - Feb 2026 (Bull Market)',
        'start': '2025-02-01',
        'end': '2026-02-28',
        'baseline_return': 1.06
    }
}


def run_period_test(period_key, period_config, tickers):
    """Run backtest on a single period."""
    print(f"\n{'='*80}")
    print(f"{period_key.upper()}: {period_config['name']}")
    print(f"{'='*80}")
    
    sim = ProductionSimulator(
        initial_capital=10000,
        position_size=0.5,
        commission_pct=0.1,
        spread_pct=0.05,
        slippage_pct=0.1
    )
    
    results = sim.run_backtest(
        tickers,
        period_config['start'],
        period_config['end'],
        base_threshold=0.35
    )
    
    # Calculate portfolio metrics
    returns = [r['total_return_pct'] for r in results if 'total_return_pct' in r]
    trades = [r['num_trades'] for r in results if 'num_trades' in r]
    win_rates = [r['win_rate_pct'] for r in results if 'win_rate_pct' in r]
    
    portfolio_return = np.mean(returns) if returns else 0
    total_trades = sum(trades) if trades else 0
    avg_win_rate = np.mean(win_rates) if win_rates else 0
    
    print(f"\n{'='*80}")
    print(f"PERIOD SUMMARY")
    print(f"{'='*80}")
    print(f"Portfolio return: {portfolio_return:+.2f}%")
    print(f"Baseline: {period_config['baseline_return']:+.2f}%")
    print(f"Improvement: {portfolio_return - period_config['baseline_return']:+.2f}%")
    print(f"Total trades: {total_trades}")
    print(f"Avg win rate: {avg_win_rate:.1f}%")
    print(f"Stocks tested: {len(results)}/{len(tickers)}")
    
    return {
        'period': period_key,
        'name': period_config['name'],
        'portfolio_return': portfolio_return,
        'baseline_return': period_config['baseline_return'],
        'improvement': portfolio_return - period_config['baseline_return'],
        'total_trades': total_trades,
        'avg_win_rate': avg_win_rate,
        'stocks_tested': len(results),
        'individual_results': results
    }


def main():
    """Run full validation."""
    print("="*80)
    print("FULL VALIDATION - FIX #1 (REGIME) + FIX #2 (THRESHOLD)")
    print("="*80)
    print()
    print("Changes:")
    print("  Fix #1: TrendDetectorV2 (50-day macro + 20-day micro)")
    print("  Fix #2: Threshold 0.50 → 0.35")
    print()
    print(f"Testing: {len(ALL_TICKERS)} IBOV stocks across 4 periods")
    print()
    
    all_results = {}
    
    # Test each period
    for period_key, period_config in PERIODS.items():
        try:
            result = run_period_test(period_key, period_config, ALL_TICKERS)
            all_results[period_key] = result
        except Exception as e:
            print(f"\n✗ Error in {period_key}: {str(e)}")
            all_results[period_key] = {'error': str(e)}
    
    # Save results
    output_file = Path(__file__).parent / "full_validation_results.json"
    with open(output_file, 'w') as f:
        json.dump(all_results, f, indent=2)
    
    print(f"\n{'='*80}")
    print("MULTI-PERIOD SUMMARY")
    print(f"{'='*80}")
    
    periods_beat_baseline = 0
    total_improvement = 0
    
    for period_key in ['period_1', 'period_2', 'period_3', 'period_4']:
        if period_key in all_results and 'error' not in all_results[period_key]:
            result = all_results[period_key]
            improvement = result['improvement']
            
            status = "✓" if improvement > 0 else "✗"
            print(f"{period_key}: {result['portfolio_return']:+.2f}% (baseline: {result['baseline_return']:+.2f}%) {status}")
            
            if improvement > 0:
                periods_beat_baseline += 1
            total_improvement += improvement
    
    print()
    print(f"Periods beating baseline: {periods_beat_baseline}/4")
    print(f"Average improvement: {total_improvement / 4:+.2f}%")
    print()
    
    # Success criteria
    if periods_beat_baseline >= 3:
        print("✓ SUCCESS: Beat baseline in 3+ periods")
    else:
        print("⚠ PARTIAL: Need improvement in more periods")
    
    if all_results.get('period_4', {}).get('portfolio_return', 0) > 5:
        print("✓ SUCCESS: Period 4 >+5% (bull market capture)")
    else:
        print("⚠ PARTIAL: Period 4 needs stronger returns")
    
    print()
    print(f"Detailed results: {output_file}")


if __name__ == "__main__":
    main()
