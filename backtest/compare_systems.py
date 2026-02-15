#!/usr/bin/env python3
"""
Compare OLD vs NEW system implementations to identify differences.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.data.fetch_data import fetch_ticker_data


def analyze_window_difference():
    """Analyze the key difference in data windowing."""
    print("="*80)
    print("CRITICAL DIFFERENCE FOUND: DATA WINDOWING")
    print("="*80)
    print()
    
    # Get sample data
    data = fetch_ticker_data("PETR4.SA", "2025-02-01", "2026-02-28")
    
    window_size = 50
    i = 100  # Sample index
    signal_date_idx = i - 1
    
    # OLD system (production_simulator_robust.py)
    old_window = data.iloc[max(0, i - window_size - 1):i].copy()
    
    # NEW system (production_simulator_full.py)
    new_window = data.iloc[:signal_date_idx + 1].copy()
    
    print(f"At index i={i} (signal_date_idx={signal_date_idx}):")
    print()
    print(f"OLD system window:")
    print(f"  - Start index: {max(0, i - window_size - 1)}")
    print(f"  - End index: {i}")
    print(f"  - Window size: {len(old_window)} days")
    print(f"  - Data range: Rolling 50-day window")
    print()
    print(f"NEW system window:")
    print(f"  - Start index: 0")
    print(f"  - End index: {signal_date_idx + 1}")
    print(f"  - Window size: {len(new_window)} days")
    print(f"  - Data range: ALL data from start to signal date")
    print()
    print("="*80)
    print("IMPACT ANALYSIS")
    print("="*80)
    print()
    print("The NEW system uses CUMULATIVE data (all history) while")
    print("OLD system uses ROLLING window (last 50 days only).")
    print()
    print("This is NOT look-ahead bias (both use data from BEFORE signal date).")
    print("But it gives NEW system more context for:")
    print("  - TrendDetectorV2 (50-day macro + 20-day micro needs history)")
    print("  - ConvictionScorer (better signal confidence with more data)")
    print()
    print("VERDICT: Different approach, not a bug, but explains performance gap.")
    print()
    print("RECOMMENDATION: Test both approaches for fair comparison:")
    print("  1. NEW with cumulative (current)")
    print("  2. NEW with rolling 50-day (apples-to-apples)")
    print()


if __name__ == "__main__":
    analyze_window_difference()
