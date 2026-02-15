"""
Quick Phase 6 Test - Validates backtest code on small dataset

Runs 1 period with top 5 IBOV stocks for quick validation.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from datetime import datetime, timedelta
from multi_period_backtest import MultiPeriodBacktest
from phase_6_reporter import Phase6Reporter


def main():
    """Run quick validation test."""
    
    print("=" * 80)
    print("PHASE 6: QUICK VALIDATION TEST")
    print("=" * 80)
    print("\nRunning backtest on 1 period with 5 stocks (quick test)...\n")
    
    # Create backtest with limited tickers
    backtest = MultiPeriodBacktest(
        initial_capital=50000,
        position_size=0.05
    )
    
    # Override tickers for quick test
    backtest.tickers = backtest.tickers[:5]
    
    # Override periods for quick test - just test Period 4
    backtest.periods = {
        'period_4': {
            'name': 'Feb 2025 - Feb 2026 (Bull Market - Critical Test)',
            'start': datetime(2025, 2, 1),
            'end': datetime(2025, 12, 31),  # 10 months instead of 12
            'regime': 'uptrend'
        }
    }
    
    # Run backtest
    try:
        results = backtest.run_all_periods()
        print("\n" + "=" * 80)
        print("RESULTS")
        print("=" * 80)
        print(backtest.get_comparison_table().to_string(index=False))
        
        # Save results
        backtest.save_results('backtest_results_quick.json')
        
        # Generate report
        reporter = Phase6Reporter(backtest_results=results)
        reporter.generate_final_report('PHASE_6_QUICK_TEST_RESULTS.md')
        reporter.plot_performance_comparison('phase6_quick_perf.png')
        
        print("\n✓ Quick test complete!")
        
    except Exception as e:
        print(f"\n✗ Error during backtest: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    main()
