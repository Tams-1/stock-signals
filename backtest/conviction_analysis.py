#!/usr/bin/env python3
"""
Analyze conviction scoring behavior to understand why it underperforms simple threshold.

Compares:
- Simple threshold (0.35) → +12.73% Period 4
- Conviction-based (min 0.40) → +4.78% Period 4

Need to understand:
1. What conviction scores are being generated?
2. How many trades are filtered out?
3. What's the position sizing distribution?
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from production_simulator_full import ProductionSimulatorFull
from src.data.fetch_data import fetch_ticker_data


def analyze_conviction_behavior(ticker: str, start_date: str, end_date: str):
    """
    Analyze conviction scoring for a single ticker.
    """
    print(f"\nAnalyzing {ticker}")
    print("=" * 70)
    
    # Create simulator
    sim = ProductionSimulatorFull(initial_capital=10000, use_news_sentiment=False)
    
    # Get data
    data = fetch_ticker_data(ticker, start_date, end_date)
    
    if len(data) < 60:
        print("  Insufficient data")
        return
    
    # Sample conviction scores throughout the period
    window_size = 50
    dates = data.index
    
    conviction_log = []
    
    for i in range(window_size + 1, min(len(data) - 1, window_size + 50)):  # Sample 50 days
        signal_date_idx = i - 1
        signal_date = dates[signal_date_idx]
        
        # Get window
        window = data.iloc[:signal_date_idx + 1].copy()
        
        # Get signals
        signals = sim.detect_signals(window, signal_date, ticker)
        
        # Calculate conviction
        conviction, direction = sim.calculate_conviction(signals)
        
        # Get position size
        position_size = sim.get_position_size(conviction) if conviction >= 0.40 else 0.0
        
        conviction_log.append({
            'date': str(signal_date.date()),
            'conviction': conviction,
            'direction': direction,
            'position_size': position_size,
            'technical_count': len(signals.get('technical', [])),
            'regime_count': len(signals.get('regime', []))
        })
    
    # Analyze
    convictions = [c['conviction'] for c in conviction_log]
    sizes = [c['position_size'] for c in conviction_log if c['position_size'] > 0]
    
    print(f"\nConviction Statistics:")
    print(f"  Mean: {sum(convictions)/len(convictions):.3f}")
    print(f"  Min:  {min(convictions):.3f}")
    print(f"  Max:  {max(convictions):.3f}")
    print(f"  % above 0.40: {100 * sum(1 for c in convictions if c >= 0.40) / len(convictions):.1f}%")
    print(f"  % above 0.60: {100 * sum(1 for c in convictions if c >= 0.60) / len(convictions):.1f}%")
    print(f"  % above 0.80: {100 * sum(1 for c in convictions if c >= 0.80) / len(convictions):.1f}%")
    
    if sizes:
        print(f"\nPosition Sizing (when trading):")
        print(f"  Avg size: {sum(sizes)/len(sizes):.2f}")
        print(f"  25% positions: {sum(1 for s in sizes if 0.2 < s < 0.3)}")
        print(f"  50% positions: {sum(1 for s in sizes if 0.4 < s < 0.6)}")
        print(f"  70% positions: {sum(1 for s in sizes if s > 0.6)}")
    
    # Compare to simple threshold
    print(f"\nComparison:")
    print(f"  Days with conviction >= 0.40: {sum(1 for c in convictions if c >= 0.40)}/{len(convictions)}")
    print(f"  Days with conviction >= 0.60: {sum(1 for c in convictions if c >= 0.60)}/{len(convictions)}")
    print(f"  Days with conviction >= 0.80: {sum(1 for c in convictions if c >= 0.80)}/{len(convictions)}")
    
    # Sample some low/high conviction days
    print(f"\nSample Low Conviction Days (< 0.40):")
    low_conv = [c for c in conviction_log if c['conviction'] < 0.40][:3]
    for c in low_conv:
        print(f"  {c['date']}: conviction={c['conviction']:.3f}, tech={c['technical_count']}, regime={c['regime_count']}")
    
    print(f"\nSample High Conviction Days (>= 0.60):")
    high_conv = [c for c in conviction_log if c['conviction'] >= 0.60][:3]
    for c in high_conv:
        print(f"  {c['date']}: conviction={c['conviction']:.3f}, direction={c['direction']}, size={c['position_size']:.2f}")


def main():
    """Run conviction analysis."""
    print("=" * 70)
    print("CONVICTION SCORING ANALYSIS")
    print("=" * 70)
    print()
    print("Question: Why does conviction-based system (+4.78%) underperform")
    print("simple threshold system (+12.73%)?")
    print()
    
    # Analyze sample tickers
    tickers = ["PETR4.SA", "ITUB4.SA", "BBDC4.SA"]
    
    for ticker in tickers:
        analyze_conviction_behavior(
            ticker,
            "2025-02-01",
            "2026-02-28"
        )


if __name__ == "__main__":
    main()
