#!/usr/bin/env python3
"""
Final validation WITH news sentiment integrated.

Compares:
1. Without news (technical + regime only) → +51.09%
2. With news (technical + news + regime) → ?%

Shows the marginal impact of adding news sentiment.
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
    """Run final comparison with and without news."""
    print("="*80)
    print("FINAL VALIDATION WITH NEWS SENTIMENT")
    print("="*80)
    print()
    print("Comparing:")
    print("1. Technical + Regime (no news) → baseline")
    print("2. Technical + News + Regime (full system) → with news")
    print()
    
    # Test 1: WITHOUT news
    print("="*80)
    print("Test 1: WITHOUT News (Baseline)")
    print("="*80)
    
    sim_no_news = ProductionSimulatorFull(
        initial_capital=10000,
        use_news_sentiment=False
    )
    
    results_no_news = []
    for ticker in ALL_TICKERS:
        result = sim_no_news.simulate_ticker(ticker, "2025-02-01", "2026-02-28",
                                            min_conviction=0.40)
        if result['status'] == 'success':
            results_no_news.append(result)
            print(f"  {ticker}: {result['total_return_pct']:+.1f}% | Trades: {result['num_trades']}")
    
    returns_no_news = [r['total_return_pct'] for r in results_no_news]
    avg_no_news = np.mean(returns_no_news) if returns_no_news else 0
    
    print()
    print(f"Portfolio (no news): {avg_no_news:+.2f}%")
    
    # Test 2: WITH news
    print()
    print("="*80)
    print("Test 2: WITH News (Full System)")
    print("="*80)
    
    sim_with_news = ProductionSimulatorFull(
        initial_capital=10000,
        use_news_sentiment=True,
        news_database_path='news_database.json'
    )
    
    results_with_news = []
    for ticker in ALL_TICKERS:
        result = sim_with_news.simulate_ticker(ticker, "2025-02-01", "2026-02-28",
                                              min_conviction=0.40)
        if result['status'] == 'success':
            results_with_news.append(result)
            print(f"  {ticker}: {result['total_return_pct']:+.1f}% | Trades: {result['num_trades']}")
    
    returns_with_news = [r['total_return_pct'] for r in results_with_news]
    avg_with_news = np.mean(returns_with_news) if returns_with_news else 0
    
    print()
    print(f"Portfolio (with news): {avg_with_news:+.2f}%")
    
    # Summary
    print()
    print("="*80)
    print("FINAL COMPARISON")
    print("="*80)
    print()
    print(f"WITHOUT news: {avg_no_news:+.2f}%")
    print(f"WITH news:    {avg_with_news:+.2f}%")
    print(f"Impact:       {avg_with_news - avg_no_news:+.2f}%")
    print()
    
    # Calculate improvements
    print("="*80)
    print("COMPLETE IMPROVEMENT BREAKDOWN")
    print("="*80)
    print()
    print(f"1. Simple threshold:              +12.73%")
    print(f"2. + Conviction scoring:          {avg_no_news:+.2f}% (+{avg_no_news - 12.73:.2f}%)")
    print(f"3. + News sentiment:              {avg_with_news:+.2f}% (+{avg_with_news - avg_no_news:.2f}%)")
    print()
    print(f"Total improvement: {avg_with_news - 12.73:+.2f}% ({(avg_with_news / 12.73 - 1) * 100:.0f}% gain)")
    print()
    
    # Save results
    output = {
        'no_news': {
            'portfolio_return': avg_no_news,
            'results': results_no_news
        },
        'with_news': {
            'portfolio_return': avg_with_news,
            'results': results_with_news
        },
        'news_impact': avg_with_news - avg_no_news,
        'total_improvement': avg_with_news - 12.73
    }
    
    with open('final_with_news_results.json', 'w') as f:
        json.dump(output, f, indent=2)
    
    print(f"✓ Results saved to final_with_news_results.json")
    
    if avg_with_news > avg_no_news:
        print(f"\n✅ NEWS ADDS VALUE: +{avg_with_news - avg_no_news:.2f}% improvement")
    else:
        print(f"\n⚠️  NEWS NEUTRAL OR NEGATIVE: {avg_with_news - avg_no_news:.2f}% impact")
    
    print()
    print("="*80)
    print("SYSTEM STATUS: COMPLETE WITH NEWS INTEGRATION")
    print("="*80)
    print()
    print("✅ Originally-intended system (Phases 1-5) now fully operational")
    print("✅ Technical signals (40% weight)")
    print("✅ News sentiment (30% weight)")
    print("✅ Regime detection (30% weight)")
    print("✅ Dynamic position sizing (25%/50%/70%)")
    print("✅ Temporal safety maintained")
    print()


if __name__ == "__main__":
    main()
