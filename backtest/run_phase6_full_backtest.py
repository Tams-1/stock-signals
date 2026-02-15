"""
Phase 6: Full Multi-Period Backtesting

Runs comprehensive backtests across 4 periods with 18 IBOV stocks.
Includes walk-forward validation and full reporting.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import json
from datetime import datetime
from multi_period_backtest import MultiPeriodBacktest
from walk_forward_validator import WalkForwardValidator
from phase_6_reporter import Phase6Reporter


def run_full_backtest():
    """Run full Phase 6 backtesting suite."""
    
    print("\n" + "=" * 100)
    print(" " * 30 + "PHASE 6: FULL BACKTESTING SUITE")
    print("=" * 100)
    
    print("\n📊 STEP 1: Multi-Period Backtest (4 periods x 18 IBOV stocks)")
    print("-" * 100)
    
    backtest = MultiPeriodBacktest(
        initial_capital=50000,
        position_size=0.05
    )
    
    print(f"Running backtest on {len(backtest.tickers)} stocks across 4 periods...")
    print(f"Stocks: {', '.join(backtest.tickers[:9])}... (+{len(backtest.tickers)-9} more)")
    print(f"Periods: Jan 2024 - Feb 2026 (14 months)\n")
    
    backtest_results = backtest.run_all_periods()
    
    # Print summary table
    print("\n" + "=" * 100)
    print("MULTI-PERIOD SUMMARY")
    print("=" * 100)
    print(backtest.get_comparison_table().to_string(index=False))
    
    # Save backtest results
    backtest.save_results('backtest_results_full.json')
    
    print("\n📊 STEP 2: Walk-Forward Out-of-Sample Validation")
    print("-" * 100)
    
    # Run walk-forward validation on top 3 IBOV stocks
    validator = WalkForwardValidator(
        initial_capital=50000,
        position_size=0.05,
        in_sample_days=90,    # 3 months
        out_sample_days=30,   # 1 month
        step_days=30          # Roll monthly
    )
    
    print(f"Running walk-forward validation on Period 4 (most important)...")
    wf_results = validator.run_walk_forward_multiple(
        backtest.tickers[:5],
        backtest.periods['period_4']['start'],
        backtest.periods['period_4']['end']
    )
    
    # Generate walk-forward summary
    print("\n" + "=" * 100)
    wf_summary = validator.generate_summary(wf_results)
    
    # Save walk-forward results
    wf_json = {
        'validators': wf_results,
        'summary': wf_summary
    }
    
    with open(Path(__file__).parent / 'wf_results_full.json', 'w') as f:
        json.dump(wf_json, f, indent=2, default=str)
    
    print("\n📊 STEP 3: Generate Comprehensive Reports & Visualizations")
    print("-" * 100)
    
    reporter = Phase6Reporter(
        backtest_results=backtest_results,
        wf_results=wf_results
    )
    
    # Generate all reports
    reporter.export_all()
    
    print("\n" + "=" * 100)
    print("PHASE 6: FULL BACKTESTING COMPLETE ✓")
    print("=" * 100)
    
    # Print final verdict
    print("\n📋 FINAL VERDICT:\n")
    
    p4 = backtest_results.get('period_4', {})
    s4 = p4.get('summary', {})
    
    v1_baseline = 3.68
    metric1 = s4.get('avg_return_pct', 0) > v1_baseline
    
    beats_ibov = sum(1 for r in backtest_results.values() 
                    if r.get('summary', {}).get('beats_ibov', False))
    metric2 = beats_ibov >= 2
    
    beats_cdi = sum(1 for r in backtest_results.values() 
                   if r.get('summary', {}).get('beats_cdi', False))
    metric3 = beats_cdi >= 2
    
    all_pass = metric1 and metric2 and metric3
    
    print(f"✓ v2 beats v1 (>3.68%): {'PASS ✓' if metric1 else 'FAIL ✗'} - v2: {s4.get('avg_return_pct', 0):+.2f}%")
    print(f"✓ v2 beats IBOV (≥2 periods): {'PASS ✓' if metric2 else 'FAIL ✗'} - {beats_ibov}/4 periods")
    print(f"✓ v2 beats CDI (≥2 periods): {'PASS ✓' if metric3 else 'FAIL ✗'} - {beats_cdi}/4 periods")
    
    print(f"\n{'🎉 READY FOR PHASE 7 ✓✓✓' if all_pass else '⚠️  NEEDS REFINEMENT'}")
    
    print("\n📁 Generated Files:")
    print("   - backtest_results_full.json (detailed results)")
    print("   - wf_results_full.json (walk-forward validation)")
    print("   - PHASE_6_BACKTEST_RESULTS.md (comprehensive report)")
    print("   - phase6_performance.png (performance charts)")
    print("   - phase6_wf_results.png (walk-forward charts)")
    
    return backtest_results, wf_results


if __name__ == '__main__':
    try:
        backtest_results, wf_results = run_full_backtest()
        print("\n✓ Phase 6 full backtesting complete!")
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
