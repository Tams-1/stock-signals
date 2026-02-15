#!/usr/bin/env python3
"""
Debug signal generation to understand why directions are neutral.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from production_simulator_full import ProductionSimulatorFull
from src.data.fetch_data import fetch_ticker_data


def debug_signals(ticker: str, date_str: str):
    """Debug signal generation for a specific date."""
    print(f"\nDebugging {ticker} on {date_str}")
    print("=" * 70)
    
    sim = ProductionSimulatorFull(initial_capital=10000, use_news_sentiment=False)
    
    # Get data up to that date
    data = fetch_ticker_data(ticker, "2025-02-01", "2026-02-28")
    
    # Find the date
    date_idx = None
    for i, d in enumerate(data.index):
        if str(d.date()) == date_str:
            date_idx = i
            break
    
    if date_idx is None:
        print(f"Date {date_str} not found")
        return
    
    # Get window and signal date
    window = data.iloc[:date_idx + 1]
    signal_date = data.index[date_idx]
    
    # Detect signals
    signals = sim.detect_signals(window, signal_date, ticker)
    
    print(f"\nSignals detected:")
    for category, sigs in signals.items():
        print(f"\n{category.upper()}:")
        for sig in sigs:
            print(f"  - {sig}")
    
    # Calculate conviction
    conviction, direction = sim.calculate_conviction(signals)
    
    print(f"\nConviction calculation:")
    print(f"  Conviction: {conviction:.3f}")
    print(f"  Direction: {direction}")
    
    # Get position size
    if conviction >= 0.40:
        position_size = sim.get_position_size(conviction)
        print(f"  Position size: {position_size:.2f}")


if __name__ == "__main__":
    # Debug a specific high-conviction neutral day
    debug_signals("PETR4.SA", "2025-04-17")
    debug_signals("ITUB4.SA", "2025-04-23")
