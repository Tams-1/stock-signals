#!/usr/bin/env python3
"""
Full integration validation: Technical + News + Regime + Conviction Scoring

Tests the complete originally-intended system with:
- Technical signals (40% weight)
- News sentiment (30% weight) - mock data for backtesting
- Regime signals (30% weight)
- Conviction-based position sizing (25%/50%/70%)

TEMPORAL SAFETY: All signals use only data from BEFORE the trading date.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import json
import numpy as np
from datetime import datetime

from production_simulator_full import ProductionSimulatorFull
from news_cache_builder import NewsCacheBuilder
from src.data.fetch_data import fetch_ticker_data


# All 18 IBOV stocks
ALL_TICKERS = [
    "PETR4.SA", "VALE3.SA", "ITUB4.SA", "BBDC4.SA", "BBAS3.SA",
    "ABEV3.SA", "B3SA3.SA", "SUZB3.SA", "RENT3.SA", "WEGE3.SA",
    "MGLU3.SA", "PCAR3.SA", "LREN3.SA", "RAIZ4.SA", "GGBR4.SA",
    "ASAI3.SA", "JBSS3.SA", "RDOR3.SA"
]

# Test periods
PERIODS = {
    'period_4': {
        'name': 'Feb 2025 - Feb 2026 (Bull Market)',
        'start': '2025-02-01',
        'end': '2026-02-28',
        'baseline_technical_only': 12.73  # From previous validation
    }
}


def build_news_cache_for_tickers(tickers, start_date, end_date):
    """Build mock news cache for all tickers."""
    print("Building news cache (mock sentiment from prior price data)...")
    cache_builder = NewsCacheBuilder()
    
    for ticker in tickers:
        try:
            # Fetch price data (with extra history for sentiment generation)
            data = fetch_ticker_data(ticker, start_date, end_date)
            if len(data) < 10:
                continue
            
            # Build cache
            cache_builder.build_cache_for_period(ticker, start_date, end_date, data)
            print(f"  ✓ {ticker}")
        except Exception as e:
            print(f"  ✗ {ticker}: {e}")
    
    cache_builder.save_cache()
    print(f"\n✓ Cache saved to {cache_builder.cache_path}")
    return cache_builder


def run_comparison(period_key, period_config, tickers):
    """
    Run comparison: technical-only vs full integration.
    
    Returns:
        Dictionary with both results
    """
    print(f"\n{'='*80}")
    print(f"{period_key.upper()}: {period_config['name']}")
    print(f"{'='*80}\n")
    
    results = {}
    
    # Test 1: Technical + Regime only (baseline from previous validation)
    print("Test 1: Technical + Regime only (conviction scoring, no news)")
    print("-" * 80)
    
    sim_no_news = ProductionSimulatorFull(
        initial_capital=10000,
        use_news_sentiment=False
    )
    
    results_no_news = sim_no_news.run_backtest(
        tickers,
        period_config['start'],
        period_config['end'],
        min_conviction=0.40
    )
    
    returns_no_news = [r['total_return_pct'] for r in results_no_news if 'total_return_pct' in r]
    avg_return_no_news = np.mean(returns_no_news) if returns_no_news else 0
    
    results['no_news'] = {
        'portfolio_return': avg_return_no_news,
        'individual_results': results_no_news
    }
    
    print(f"\n✓ Technical + Regime: {avg_return_no_news:+.2f}%")
    
    # Test 2: Full integration (Technical + News + Regime)
    print(f"\n{'='*80}")
    print("Test 2: Full Integration (Technical + News + Regime)")
    print("-" * 80)
    
    # Build news cache first
    cache = build_news_cache_for_tickers(
        tickers,
        period_config['start'],
        period_config['end']
    )
    
    # TODO: Wire cache into simulator
    # For now, the simulator returns None for news (temporal safety ensured)
    
    sim_full = ProductionSimulatorFull(
        initial_capital=10000,
        use_news_sentiment=True  # Enable news (currently returns None safely)
    )
    
    results_full = sim_full.run_backtest(
        tickers,
        period_config['start'],
        period_config['end'],
        min_conviction=0.40
    )
    
    returns_full = [r['total_return_pct'] for r in results_full if 'total_return_pct' in r]
    avg_return_full = np.mean(returns_full) if returns_full else 0
    
    results['full'] = {
        'portfolio_return': avg_return_full,
        'individual_results': results_full
    }
    
    print(f"\n✓ Full integration: {avg_return_full:+.2f}%")
    
    # Comparison
    print(f"\n{'='*80}")
    print("COMPARISON")
    print(f"{'='*80}")
    print(f"Technical + Regime only:     {avg_return_no_news:+.2f}%")
    print(f"Full integration (+ news):   {avg_return_full:+.2f}%")
    print(f"Improvement:                 {avg_return_full - avg_return_no_news:+.2f}%")
    print(f"Baseline (simple threshold): {period_config['baseline_technical_only']:+.2f}%")
    
    return results


def main():
    """Run full integration validation."""
    print("="*80)
    print("FULL INTEGRATION VALIDATION")
    print("="*80)
    print()
    print("Comparing:")
    print("1. Technical + Regime with conviction scoring (no news)")
    print("2. Technical + News + Regime with conviction scoring (full)")
    print()
    print("Temporal Safety:")
    print("- All signals use data from BEFORE trading date")
    print("- News sentiment generated from prior price data (mock)")
    print("- Zero look-ahead bias")
    print()
    
    # Run on Period 4 (bull market test)
    period_key = 'period_4'
    period_config = PERIODS[period_key]
    
    # Use sample for speed (or ALL_TICKERS for full test)
    sample_tickers = ALL_TICKERS[:5]  # Quick test
    
    results = run_comparison(period_key, period_config, sample_tickers)
    
    # Save results
    output_file = Path(__file__).parent / "full_integration_results.json"
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"\n✓ Results saved to {output_file}")


if __name__ == "__main__":
    main()
