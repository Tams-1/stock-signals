#!/usr/bin/env python3
"""
Debug: Log confidence values day-by-day to understand why threshold doesn't matter
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
from src.signals.trend_detector_v2 import TrendDetectorV2

# Config
START = "2025-08-01"
END = "2026-02-14"
TICKER = "VALE3.SA"  # Focus on VALE3 (only 1 trade, biggest gap)
LOOKBACK = 120

print("="*70)
print("🔍 CONFIDENCE DEBUG - VALE3")
print("="*70)
print(f"Period: {START} to {END}")
print(f"Expected: Many high-confidence days (VALE3 went +76%)")
print(f"Actual: Only 1 trade in 6 months\n")

# Download data
print("📥 Downloading VALE3 data...")
start_dl = pd.Timestamp(START) - timedelta(days=LOOKBACK + 30)
df = yf.download(TICKER, start=start_dl, end=END, progress=False)

if isinstance(df.columns, pd.MultiIndex):
    df.columns = df.columns.get_level_values(0)

print(f"✓ Got {len(df)} days of data\n")

# Get trading days
trading_days = df[df.index >= pd.Timestamp(START)].index

detector = TrendDetectorV2()

print("="*70)
print("DAY-BY-DAY CONFIDENCE")
print("="*70)
print(f"{'Date':<12} {'Price':<10} {'Trend':<12} {'Confidence':<12} {'Pass 0.25?':<12} {'Pass 0.15?':<12}")
print("-"*70)

high_conf_days = []
above_025 = 0
above_015 = 0

for day in trading_days:
    # Historical data up to (not including) this day
    historical = df[df.index < day].tail(LOOKBACK)
    
    if len(historical) < 50:
        continue
    
    # Detect trend
    result = detector.detect_trend(historical)
    consensus = result.get('consensus', 'unknown')
    confidence = result.get('confidence', 0.0)
    price = historical['Close'].iloc[-1]
    
    # Map consensus to simple trend
    if consensus in ['uptrend', 'bull_pullback']:
        trend = "uptrend"
    elif consensus in ['downtrend', 'bear_bounce']:
        trend = "downtrend"
    else:
        trend = "neutral"
    
    pass_025 = "✓" if confidence > 0.25 else "✗"
    pass_015 = "✓" if confidence > 0.15 else "✗"
    
    if confidence > 0.25:
        above_025 += 1
    if confidence > 0.15:
        above_015 += 1
    
    if confidence > 0.20:  # Show high confidence days
        high_conf_days.append({
            'date': day.strftime('%Y-%m-%d'),
            'price': price,
            'trend': trend,
            'confidence': confidence
        })
    
    # Print every 5th day to avoid spam
    if len(trading_days) > 50:
        if day == trading_days[0] or day == trading_days[-1] or day.day % 5 == 0:
            print(f"{day.strftime('%Y-%m-%d'):<12} R${price:>7.2f} {trend:<12} {confidence:>11.3f} {pass_025:<12} {pass_015:<12}")
    else:
        print(f"{day.strftime('%Y-%m-%d'):<12} R${price:>7.2f} {trend:<12} {confidence:>11.3f} {pass_025:<12} {pass_015:<12}")

print("\n" + "="*70)
print("📊 SUMMARY")
print("="*70)

total_days = len(trading_days)
print(f"\nTotal trading days: {total_days}")
print(f"Days with confidence > 0.25: {above_025} ({above_025/total_days*100:.1f}%)")
print(f"Days with confidence > 0.15: {above_015} ({above_015/total_days*100:.1f}%)")

print(f"\n🔥 HIGH CONFIDENCE DAYS (>0.20):")
if high_conf_days:
    for item in high_conf_days[:10]:  # Show first 10
        print(f"   {item['date']}: {item['trend']:<10} conf={item['confidence']:.3f} @ R${item['price']:.2f}")
    if len(high_conf_days) > 10:
        print(f"   ... and {len(high_conf_days) - 10} more")
else:
    print("   ❌ NONE! This is the problem!")

print(f"\n{'='*70}")
print("🎯 DIAGNOSIS")
print(f"{'='*70}\n")

if above_025 == 0:
    print("❌ PROBLEM FOUND: Confidence NEVER exceeds 0.25!")
    print("   → Threshold is irrelevant (always too high)")
    print("   → TrendDetectorV2 is too conservative")
    print("   → Need to fix confidence calculation\n")
elif above_025 < 10:
    print("⚠️  PROBLEM: Confidence rarely exceeds 0.25")
    print(f"   → Only {above_025} days out of {total_days}")
    print("   → Explains low trade count\n")
else:
    print("✓ Confidence exceeds 0.25 regularly")
    print("  → Problem must be elsewhere (position sizing? execution?)\n")

# Price context
print("📈 VALE3 Price Movement:")
print(f"   Start: R$ {df[df.index >= pd.Timestamp(START)]['Close'].iloc[0]:.2f}")
print(f"   End:   R$ {df['Close'].iloc[-1]:.2f}")
print(f"   Gain:  {((df['Close'].iloc[-1] / df[df.index >= pd.Timestamp(START)]['Close'].iloc[0]) - 1) * 100:+.1f}%")
print(f"\n   → Strong uptrend, confidence should be HIGH most days")
