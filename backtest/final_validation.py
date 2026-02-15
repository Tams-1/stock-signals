#!/usr/bin/env python3
"""
Final validation: Full integration with regime tie-breaker logic.

Compares:
1. Technical + Regime (simple threshold 0.35) → +12.73% baseline
2. Technical + Regime (conviction + tie-breaker) → ?% new

All with strict temporal safety - no look-ahead bias.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import json
import numpy as np

from production_simulator_full import ProductionSimulatorFull


ALL_TICKERS = [
    "PETR4.SA", "VALE3.SA", "ITUB4.SA", "BBDC4.SA", "BBAS3.SA",
    "ABEV3.SA", "B3SA3.SA", "SUZB3.SA", "RENT3.SA", "WEGE3.SA",
    "MGLU3.SA", "PCAR3.SA", "LREN3.SA", "RAIZ4.SA", "GGBR4.SA",
    "ASAI3.SA", "JBSS3.SA", "RDOR3.SA"
]


def main():
    """Run final validation."""
    print("="*80)
    print("FINAL VALIDATION - Full Integration with Regime Tie-Breaker")
    print("="*80)
    print()
    print("Testing: Technical + Regime + Conviction + Dynamic Position Sizing")
    print("Logic: Use regime as tie-breaker when signals conflict")
    print()
    print("Period 4 (Feb 2025 - Feb 2026)")
    print("Baseline (simple threshold 0.35): +12.73%")
    print()
    
    sim = ProductionSimulatorFull(
        initial_capital=10000,
        use_news_sentiment=False  # Start without news
    )
    
    results = sim.run_backtest(
        ALL_TICKERS,
        "2025-02-01",
        "2026-02-28",
        min_conviction=0.40
    )
    
    # Calculate portfolio metrics
    returns = [r['total_return_pct'] for r in results if 'total_return_pct' in r]
    trades = [r['num_trades'] for r in results if 'num_trades' in r]
    win_rates = [r['win_rate_pct'] for r in results if 'win_rate_pct' in r]
    
    portfolio_return = np.mean(returns) if returns else 0
    total_trades = sum(trades) if trades else 0
    avg_win_rate = np.mean(win_rates) if win_rates else 0
    
    print(f"\n{'='*80}")
    print("RESULTS")
    print(f"{'='*80}")
    print(f"Portfolio return: {portfolio_return:+.2f}%")
    print(f"Baseline (simple): +12.73%")
    print(f"Improvement: {portfolio_return - 12.73:+.2f}%")
    print(f"Total trades: {total_trades}")
    print(f"Avg win rate: {avg_win_rate:.1f}%")
    print(f"Stocks tested: {len(results)}/{len(ALL_TICKERS)}")
    
    # Save results
    output_file = Path(__file__).parent / "final_validation_results.json"
    with open(output_file, 'w') as f:
        json.dump({
            'portfolio_return': portfolio_return,
            'baseline': 12.73,
            'improvement': portfolio_return - 12.73,
            'total_trades': total_trades,
            'avg_win_rate': avg_win_rate,
            'individual_results': results
        }, f, indent=2)
    
    print(f"\n✓ Results saved to {output_file}")
    
    if portfolio_return > 12.73:
        print(f"\n✅ SUCCESS: Full integration beats baseline by {portfolio_return - 12.73:+.2f}%")
    elif portfolio_return > 10:
        print(f"\n⚠️  PARTIAL: Close to baseline, within acceptable range")
    else:
        print(f"\n❌ ISSUE: Underperforming baseline, needs investigation")


if __name__ == "__main__":
    main()
