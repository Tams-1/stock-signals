#!/usr/bin/env python3
"""Debug window sizes to verify rolling vs cumulative."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from fair_comparison import FairComparisonSimulator
from src.data.fetch_data import fetch_ticker_data


class DebugSimulator(FairComparisonSimulator):
    """Simulator with debug output."""
    
    def detect_signals(self, data, signal_date, ticker):
        """Override to log window size."""
        print(f"  Signal date: {signal_date.date()}, Window size: {len(data)} days")
        return super().detect_signals(data, signal_date, ticker)


def main():
    print("="*80)
    print("DEBUGGING WINDOW SIZES")
    print("="*80)
    print()
    
    sim = DebugSimulator(initial_capital=10000, use_news_sentiment=False)
    ticker = "PETR4.SA"
    
    print("TEST 1: Rolling Window")
    print("-"*80)
    result = sim.simulate_ticker(ticker, "2025-02-01", "2025-03-31",
                                use_rolling_window=True)
    print(f"Result: {result['total_return_pct']:+.2f}%")
    print()
    
    print("TEST 2: Cumulative Window")
    print("-"*80)
    result = sim.simulate_ticker(ticker, "2025-02-01", "2025-03-31",
                                use_rolling_window=False)
    print(f"Result: {result['total_return_pct']:+.2f}%")


if __name__ == "__main__":
    main()
