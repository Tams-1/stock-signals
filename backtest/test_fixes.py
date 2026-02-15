#!/usr/bin/env python3
"""
Quick test of Fix #1 (regime detector) + Fix #2 (threshold 0.35) on Period 4.

Expected improvement:
- Baseline: +1.06%
- Fix #1: +0.52% (better regime classification)
- Fix #2: ~+1-2% (capture 397 missed moves)
- Target: +3-5% combined
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from backtest.production_simulator_robust import ProductionSimulator
import json


# Period 4: Feb 2025 - Feb 2026 (bull market test)
START_DATE = "2025-02-01"
END_DATE = "2026-02-28"

# Sample tickers for quick test
SAMPLE_TICKERS = [
    "PETR4.SA",
    "VALE3.SA",
    "ITUB4.SA",
    "BBDC4.SA",
    "BBAS3.SA",
]


def main():
    print("=" * 80)
    print("TESTING FIX #1 (REGIME) + FIX #2 (THRESHOLD)")
    print(f"Period 4: {START_DATE} to {END_DATE}")
    print("=" * 80)
    print()
    print("Changes:")
    print("  Fix #1: TrendDetectorV2 (50-day macro + 20-day micro)")
    print("  Fix #2: Threshold 0.50 → 0.35")
    print()
    print("Baseline (old): +1.06% return")
    print("Target (fixes): +3-5% return")
    print()
    print("=" * 80)
    print()
    
    # Run simulator with fixes
    sim = ProductionSimulator(
        initial_capital=10000,
        position_size=0.5,
        commission_pct=0.1,
        spread_pct=0.05,
        slippage_pct=0.1
    )
    
    results = sim.run_backtest(
        SAMPLE_TICKERS,
        START_DATE,
        END_DATE,
        base_threshold=0.35  # Explicitly set (already default now)
    )
    
    # Save results
    output_file = Path(__file__).parent / "test_fixes_results.json"
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2)
    
    print()
    print("=" * 80)
    print("RESULTS")
    print("=" * 80)
    
    if 'portfolio_return_pct' in results:
        new_return = results['portfolio_return_pct']
        print(f"Portfolio return: {new_return:+.2f}%")
        print(f"Baseline (old):   +1.06%")
        print(f"Improvement:      {new_return - 1.06:+.2f}%")
        print()
        
        if new_return > 3.0:
            print("✓ SUCCESS: Beats target (+3%)")
        elif new_return > 1.58:
            print("✓ PARTIAL: Better than Fix #1 alone (+1.58%), but below target")
        else:
            print("✗ ISSUE: Lower than expected, check integration")
        
        print()
        print(f"Win rate: {results.get('win_rate_pct', 0):.1f}%")
        print(f"Trades: {results.get('total_trades', 0)}")
        print(f"Sharpe: {results.get('sharpe_ratio', 0):.2f}")
    
    print()
    print(f"Detailed results: {output_file}")


if __name__ == "__main__":
    main()
