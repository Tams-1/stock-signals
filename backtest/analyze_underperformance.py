#!/usr/bin/env python3
"""
Deep dive: Why are we underperforming IBOV by 26%?

System: +14.50% (17 trades)
IBOV: +40.79%
Gap: -26.30%

Hypotheses to test:
1. Late entries (threshold 0.25 too high)
2. Early exits (confidence drops too fast)
3. Missing entire trends (threshold never crossed)
4. Position sizing too conservative
5. Not capturing the strongest moves
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json

# Period
START = "2025-08-01"
END = "2026-02-14"
TICKERS = ["VALE3.SA", "ITUB3.SA", "KLBN11.SA", "MTRE3.SA", "ITSA4.SA"]

print("="*70)
print("🔍 UNDERPERFORMANCE DEEP DIVE")
print("="*70)
print(f"\nPeriod: {START} to {END}")
print(f"System: +14.50% (17 trades)")
print(f"IBOV: +40.79%")
print(f"Gap: -26.30%\n")

# Load backtest results
with open('realtime_backtest_results.json', 'r') as f:
    results = json.load(f)

# Download all data
print("📥 Downloading market data...\n")
data = {}
for ticker in TICKERS:
    df = yf.download(ticker, start=START, end=END, progress=False)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    data[ticker] = df

ibov = yf.download("^BVSP", start=START, end=END, progress=False)
if isinstance(ibov.columns, pd.MultiIndex):
    ibov.columns = ibov.columns.get_level_values(0)

print("="*70)
print("📊 TICKER-BY-TICKER ANALYSIS")
print("="*70)

for ticker in TICKERS:
    df = data[ticker]
    if len(df) == 0:
        continue
    
    ticker_clean = ticker.replace('.SA', '')
    
    # Calculate buy & hold return
    buy_hold_return = ((df['Close'].iloc[-1] - df['Close'].iloc[0]) / df['Close'].iloc[0]) * 100
    
    # Get system performance
    ticker_result = results['ticker_results'].get(ticker, {})
    system_return = ticker_result.get('return_pct', 0.0)
    trades = ticker_result.get('trades', 0)
    
    # Calculate gap
    gap = system_return - buy_hold_return
    
    print(f"\n{ticker_clean}:")
    print(f"  Buy & Hold:  {buy_hold_return:+7.2f}%")
    print(f"  System:      {system_return:+7.2f}%")
    print(f"  Gap:         {gap:+7.2f}%")
    print(f"  Trades:      {trades}")
    
    if trades > 0:
        # Analyze entry/exit timing
        print(f"\n  📈 Price movement:")
        print(f"     Start: R$ {df['Close'].iloc[0]:.2f}")
        print(f"     End:   R$ {df['Close'].iloc[-1]:.2f}")
        print(f"     Peak:  R$ {df['Close'].max():.2f} ({((df['Close'].max() - df['Close'].iloc[0]) / df['Close'].iloc[0] * 100):+.1f}%)")
        print(f"     Low:   R$ {df['Close'].min():.2f} ({((df['Close'].min() - df['Close'].iloc[0]) / df['Close'].iloc[0] * 100):+.1f}%)")

print("\n" + "="*70)
print("🎯 KEY FINDINGS")
print("="*70)

# Overall comparison
total_buy_hold = 0
for ticker in TICKERS:
    df = data[ticker]
    if len(df) > 0:
        ticker_bh = ((df['Close'].iloc[-1] - df['Close'].iloc[0]) / df['Close'].iloc[0]) * 100
        total_buy_hold += ticker_bh

avg_buy_hold = total_buy_hold / len(TICKERS)

print(f"\n1. Average Buy & Hold: {avg_buy_hold:+.2f}%")
print(f"   System (equal weight): {results['total_return_pct']:+.2f}%")
print(f"   Difference: {results['total_return_pct'] - avg_buy_hold:+.2f}%")

print(f"\n2. Trade frequency:")
print(f"   Total trades: {results['total_trades']}")
print(f"   Trading days: 136")
print(f"   Trades per day: {results['total_trades'] / 136:.3f}")
print(f"   Trades per ticker: {results['total_trades'] / len(TICKERS):.1f}")

print(f"\n3. IBOV comparison:")
ibov_return = ((ibov['Close'].iloc[-1] - ibov['Close'].iloc[0]) / ibov['Close'].iloc[0]) * 100
print(f"   IBOV actual: {ibov_return:+.2f}%")
print(f"   System: {results['total_return_pct']:+.2f}%")
print(f"   Gap: {results['total_return_pct'] - ibov_return:+.2f}%")

print("\n" + "="*70)
print("🔎 HYPOTHESIS TESTING")
print("="*70)

# Hypothesis 1: Late entries
print("\nH1: Are we entering too late?")
print("    → Analysis: Check if first BUY is after significant run-up")
print("    → Example: VALE3 only 1 trade in 6 months")
print("    → If VALE3 went from R$50 → R$87 (+74%), we only captured 21.26%")

# Hypothesis 2: Early exits
print("\nH2: Are we exiting too early?")
print("    → Analysis: Check if SELL happened before peak")
print("    → Count trades: 17 total means 8-9 round trips")
print("    → In strong bull market, should be mostly HOLD")

# Hypothesis 3: Threshold too high
print("\nH3: Is confidence threshold 0.25 too conservative?")
print("    → Evidence: Only 17 trades in 136 days")
print("    → That's 1 trade per 8 days (very low for 5 tickers)")
print("    → VALE3: 1 trade only (buy & hold from Aug 11)")

# Hypothesis 4: Missing trends
print("\nH4: Are we missing entire trends?")
print("    → Check: How many days with confidence > 0.25?")
print("    → If detector shows uptrend but we don't trade → sizing issue")
print("    → If detector shows neutral → detection issue")

print("\n" + "="*70)
print("💡 RECOMMENDATIONS")
print("="*70)

print("\n1. Lower threshold to 0.20 or even 0.15")
print("   → More trades, catch trends earlier")
print("   → Test: Re-run backtest with threshold=0.20")

print("\n2. Implement Kelly Criterion for position sizing")
print("   → Currently: Fixed 25%/50%/70%")
print("   → Better: Scale with confidence (0.25→25%, 1.0→100%)")

print("\n3. Add trend-following exit rule")
print("   → Current: Exit when confidence drops")
print("   → Better: Trailing stop or only exit on reversal signal")

print("\n4. Analyze confidence distribution")
print("   → How many days confidence was >0.15 but <0.25?")
print("   → Those are missed opportunities")

print("\n" + "="*70)
print("🚀 NEXT STEPS")
print("="*70)

print("\n1. Create confidence heatmap (ticker × date)")
print("2. Overlay actual trades on price charts")
print("3. Backtest with threshold=0.20")
print("4. Implement adaptive threshold (lower in trends, higher in consolidation)")
print("5. Compare with simple HODL strategy")

print("\n" + "="*70)
