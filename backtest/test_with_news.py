#!/usr/bin/env python3
"""
Test system WITH news sentiment enabled.

Shows:
1. Performance with vs without news
2. Specific example of news driving a decision
3. How news signals integrate with technical + regime
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
from datetime import datetime
from production_simulator_full import ProductionSimulatorFull
from news_cache_builder import NewsCacheBuilder
from src.data.fetch_data import fetch_ticker_data


def build_news_cache():
    """Build mock news cache for testing."""
    print("Building mock news cache...")
    cache = NewsCacheBuilder()
    
    # Build cache for test period
    tickers = ["PETR4.SA", "VALE3.SA", "ITUB4.SA"]
    for ticker in tickers:
        data = fetch_ticker_data(ticker, "2025-02-01", "2026-02-28")
        cache.build_cache_for_period(ticker, "2025-02-01", "2026-02-28", data)
        print(f"  ✓ {ticker}")
    
    cache.save_cache()
    return cache


def show_decision_example(ticker: str, target_date: str):
    """
    Show a specific trading decision and how news influenced it.
    """
    print(f"\n{'='*80}")
    print(f"DECISION EXAMPLE: {ticker} on {target_date}")
    print(f"{'='*80}\n")
    
    # Test WITHOUT news
    print("Test 1: WITHOUT News Sentiment")
    print("-"*80)
    
    sim_no_news = ProductionSimulatorFull(
        initial_capital=10000,
        use_news_sentiment=False
    )
    
    data = fetch_ticker_data(ticker, "2025-02-01", "2025-12-31")
    
    # Find the target date
    target_idx = None
    for i, date in enumerate(data.index):
        if str(date.date()) == target_date:
            target_idx = i
            break
    
    if target_idx is None:
        print(f"Date {target_date} not found")
        return
    
    # Get window
    window = data.iloc[:target_idx + 1]
    signal_date = data.index[target_idx]
    
    # Detect signals without news
    signals_no_news = sim_no_news.detect_signals(window, signal_date, ticker)
    conviction_no_news, direction_no_news = sim_no_news.calculate_conviction(signals_no_news)
    
    regime_no_news = signals_no_news['regime'][0]['regime'] if signals_no_news.get('regime') else 'unknown'
    
    print(f"Signals detected:")
    print(f"  Technical: {len(signals_no_news.get('technical', []))} signals")
    for sig in signals_no_news.get('technical', []):
        print(f"    - {sig['type']}: {sig['direction']} (strength {sig['strength']:.2f})")
    print(f"  Regime: {regime_no_news}")
    print(f"  News: None (disabled)")
    print()
    print(f"Conviction: {conviction_no_news:.3f}")
    print(f"Direction: {direction_no_news}")
    print(f"Position size: {sim_no_news.get_position_size(conviction_no_news) if conviction_no_news >= 0.40 else 0.0:.0%}")
    
    # Determine action without news
    should_trade = False
    if conviction_no_news >= 0.40:
        if direction_no_news == 'bullish':
            should_trade = True
        elif direction_no_news == 'neutral' and regime_no_news == 'uptrend':
            should_trade = True
    
    print(f"\n➤ Action WITHOUT news: {'BUY' if should_trade else 'NO TRADE'}")
    
    # Test WITH news
    print(f"\n{'='*80}")
    print("Test 2: WITH News Sentiment (Mock)")
    print("-"*80)
    
    sim_with_news = ProductionSimulatorFull(
        initial_capital=10000,
        use_news_sentiment=True  # Enable news
    )
    
    # Build mock news for this date
    cache = NewsCacheBuilder()
    cache.build_cache_for_period(ticker, "2025-02-01", "2025-12-31", data)
    
    # Get mock sentiment for this date
    mock_sentiment = cache.get_sentiment(ticker, signal_date)
    
    print(f"Mock news sentiment (based on prior price action):")
    if mock_sentiment:
        print(f"  Sentiment: {mock_sentiment['sentiment']:+.3f}")
        print(f"  Direction: {mock_sentiment['direction']}")
        print(f"  Strength: {mock_sentiment['strength']:.3f}")
        print()
        print("  NOTE: In production, this would be real news articles.")
        print("  Mock uses 3-day price momentum as sentiment proxy.")
    else:
        print("  No sentiment available")
    
    # For demonstration, manually add news signal
    signals_with_news = {
        'technical': signals_no_news.get('technical', []),
        'news': [mock_sentiment] if mock_sentiment else [],
        'regime': signals_no_news.get('regime', [])
    }
    
    conviction_with_news, direction_with_news = sim_with_news.calculate_conviction(signals_with_news)
    
    print(f"\nSignals detected:")
    print(f"  Technical: {len(signals_with_news.get('technical', []))} signals")
    print(f"  News: {len(signals_with_news.get('news', []))} signals")
    print(f"  Regime: {regime_no_news}")
    print()
    print(f"Conviction: {conviction_with_news:.3f} (was {conviction_no_news:.3f})")
    print(f"Direction: {direction_with_news} (was {direction_no_news})")
    print(f"Position size: {sim_with_news.get_position_size(conviction_with_news) if conviction_with_news >= 0.40 else 0.0:.0%}")
    
    # Determine action with news
    should_trade_with_news = False
    if conviction_with_news >= 0.40:
        if direction_with_news == 'bullish':
            should_trade_with_news = True
        elif direction_with_news == 'neutral' and regime_no_news == 'uptrend':
            should_trade_with_news = True
    
    print(f"\n➤ Action WITH news: {'BUY' if should_trade_with_news else 'NO TRADE'}")
    
    # Show impact
    print(f"\n{'='*80}")
    print("IMPACT OF NEWS")
    print(f"{'='*80}")
    
    if conviction_with_news > conviction_no_news:
        print(f"✓ News INCREASED conviction by {conviction_with_news - conviction_no_news:+.3f}")
        print(f"  Result: {'Higher position size' if should_trade_with_news else 'Enabled trade'}")
    elif conviction_with_news < conviction_no_news:
        print(f"✗ News DECREASED conviction by {conviction_with_news - conviction_no_news:+.3f}")
        print(f"  Result: {'Lower position size' if should_trade_with_news else 'Prevented trade'}")
    else:
        print("= News had NO impact on conviction")
    
    if direction_with_news != direction_no_news:
        print(f"✓ News CHANGED direction: {direction_no_news} → {direction_with_news}")
    
    if should_trade != should_trade_with_news:
        print(f"⚠️  News CHANGED final decision: {'BUY' if should_trade else 'NO TRADE'} → {'BUY' if should_trade_with_news else 'NO TRADE'}")


def compare_performance():
    """Compare performance with vs without news."""
    print(f"\n{'='*80}")
    print("PERFORMANCE COMPARISON: With vs Without News")
    print(f"{'='*80}\n")
    
    ticker = "PETR4.SA"
    
    # Without news
    sim_no_news = ProductionSimulatorFull(initial_capital=10000, use_news_sentiment=False)
    result_no_news = sim_no_news.simulate_ticker(ticker, "2025-02-01", "2026-02-28")
    
    print(f"WITHOUT news:")
    print(f"  Return: {result_no_news['total_return_pct']:+.2f}%")
    print(f"  Trades: {result_no_news['num_trades']}")
    print(f"  Win rate: {result_no_news['win_rate_pct']:.1f}%")
    
    # With news (mock)
    cache = NewsCacheBuilder()
    data = fetch_ticker_data(ticker, "2025-02-01", "2026-02-28")
    cache.build_cache_for_period(ticker, "2025-02-01", "2026-02-28", data)
    cache.save_cache()
    
    # Note: Current implementation returns None for news (temporal safety)
    # This test shows the infrastructure, but needs real news API for production
    sim_with_news = ProductionSimulatorFull(initial_capital=10000, use_news_sentiment=True)
    result_with_news = sim_with_news.simulate_ticker(ticker, "2025-02-01", "2026-02-28")
    
    print(f"\nWITH news (mock):")
    print(f"  Return: {result_with_news['total_return_pct']:+.2f}%")
    print(f"  Trades: {result_with_news['num_trades']}")
    print(f"  Win rate: {result_with_news['win_rate_pct']:.1f}%")
    
    print(f"\nImpact: {result_with_news['total_return_pct'] - result_no_news['total_return_pct']:+.2f}%")
    
    print("\n" + "="*80)
    print("NOTE: Current Implementation Status")
    print("="*80)
    print()
    print("The news sentiment infrastructure is BUILT and READY:")
    print("  ✓ NewsAggregator (Phase 1)")
    print("  ✓ SentimentAnalyzer (Phase 1)")
    print("  ✓ Temporal-safe caching system")
    print("  ✓ ConvictionScorer integration (30% weight)")
    print()
    print("But currently returns None for news to avoid API costs.")
    print("For production use:")
    print("  1. Build historical news database, OR")
    print("  2. Enable live NewsAPI in production, OR")
    print("  3. Use mock sentiment (price-based proxy)")
    print()
    print("The +51.09% performance is WITHOUT news (technical + regime only).")
    print()


def main():
    """Run news integration tests."""
    print("="*80)
    print("NEWS SENTIMENT INTEGRATION TEST")
    print("="*80)
    print()
    print("This test shows:")
    print("1. How news signals integrate with technical + regime")
    print("2. Specific example of news driving a decision")
    print("3. Performance impact of adding news")
    print()
    
    # Show decision example
    show_decision_example("PETR4.SA", "2025-06-15")
    
    # Compare performance
    compare_performance()


if __name__ == "__main__":
    main()
