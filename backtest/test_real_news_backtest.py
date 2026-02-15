#!/usr/bin/env python3
"""
Backtest with REAL news (Google News + FinBERT).

Compares:
1. WITHOUT news (technical + regime only)
2. WITH REAL news (technical + real news + regime)
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np
from production_simulator_real_news_v2 import ProductionSimulatorFull


ALL_TICKERS = [
    "PETR4.SA", "VALE3.SA", "ITUB4.SA", "BBDC4.SA", "BBAS3.SA",
    "ABEV3.SA", "B3SA3.SA", "SUZB3.SA", "RENT3.SA", "WEGE3.SA",
    "MGLU3.SA", "PCAR3.SA", "LREN3.SA", "RAIZ4.SA", "GGBR4.SA",
    "ASAI3.SA", "JBSS3.SA", "RDOR3.SA"
]


def main():
    print("="*80)
    print("BACKTEST WITH REAL NEWS (Google News + FinBERT)")
    print("="*80)
    print()
    
    # Test 1: WITHOUT news (baseline)
    print("="*80)
    print("Test 1: WITHOUT News (Baseline)")
    print("="*80)
    print()
    
    sim_no_news = ProductionSimulatorFull(
        initial_capital=10000,
        use_news_sentiment=False
    )
    
    results_no_news = []
    for ticker in ALL_TICKERS:
        try:
            result = sim_no_news.simulate_ticker(ticker, "2025-02-01", "2026-02-28", min_conviction=0.40)
            if result['status'] == 'success':
                results_no_news.append(result)
                print(f"  {ticker}: {result['total_return_pct']:+.1f}% | Trades: {result['num_trades']}")
        except Exception as e:
            print(f"  {ticker}: ERROR - {e}")
    
    returns_no_news = [r['total_return_pct'] for r in results_no_news]
    avg_no_news = np.mean(returns_no_news) if returns_no_news else 0
    
    print()
    print(f"Portfolio (no news): {avg_no_news:+.2f}%")
    print()
    
    # Test 2: WITH REAL news
    print("="*80)
    print("Test 2: WITH REAL News (Google News + FinBERT)")
    print("="*80)
    print()
    
    sim_with_news = ProductionSimulatorFull(
        initial_capital=10000,
        use_news_sentiment=True
    )
    
    results_with_news = []
    for ticker in ALL_TICKERS:
        try:
            result = sim_with_news.simulate_ticker(ticker, "2025-02-01", "2026-02-28", min_conviction=0.40)
            if result['status'] == 'success':
                results_with_news.append(result)
                print(f"  {ticker}: {result['total_return_pct']:+.1f}% | Trades: {result['num_trades']}")
        except Exception as e:
            print(f"  {ticker}: ERROR - {e}")
    
    returns_with_news = [r['total_return_pct'] for r in results_with_news]
    avg_with_news = np.mean(returns_with_news) if returns_with_news else 0
    
    print()
    print(f"Portfolio (with REAL news): {avg_with_news:+.2f}%")
    print()
    
    # Summary
    print("="*80)
    print("FINAL COMPARISON")
    print("="*80)
    print()
    print(f"WITHOUT news: {avg_no_news:+.2f}%")
    print(f"WITH REAL news: {avg_with_news:+.2f}%")
    print(f"News impact: {avg_with_news - avg_no_news:+.2f}%")
    print()
    print(f"Total improvement over baseline (+12.73%): {avg_with_news - 12.73:+.2f}%")
    print()
    print("="*80)
    print("BACKTEST COMPLETE")
    print("="*80)


if __name__ == "__main__":
    main()
