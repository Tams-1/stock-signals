#!/usr/bin/env python3
"""
Diagnose TrendDetectorV2 - Why is it generating 0 trades?
Test on specific dates/tickers to see confidence levels
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta

from src.signals.trend_detector_v2 import TrendDetectorV2

def diagnose_ticker(ticker: str, dates: list):
    """Test trend detector on specific dates"""
    print(f"\n{'='*70}")
    print(f"🔍 Diagnosing {ticker}")
    print(f"{'='*70}\n")
    
    # Download extended data (need lookback)
    start = pd.Timestamp(dates[0]) - timedelta(days=200)
    end = pd.Timestamp(dates[-1]) + timedelta(days=1)
    
    print(f"📥 Downloading data ({start.date()} to {end.date()})...")
    df = yf.download(ticker, start=start, end=end, progress=False)
    
    if df.empty:
        print(f"❌ No data for {ticker}")
        return
    
    # Flatten MultiIndex columns if present
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    
    print(f"✓ Got {len(df)} days of data\n")
    
    detector = TrendDetectorV2()
    
    for test_date in dates:
        test_ts = pd.Timestamp(test_date)
        
        # Get data up to (but not including) test date
        historical = df[df.index < test_ts].copy()
        
        if len(historical) < 100:
            print(f"⚠️  {test_date}: Insufficient data ({len(historical)} days)")
            continue
        
        # Debug: Check data format
        print(f"   DEBUG: Historical shape: {historical.shape}")
        print(f"   DEBUG: Historical columns: {historical.columns.tolist()}")
        print(f"   DEBUG: Last close: {historical['Close'].iloc[-1] if 'Close' in historical.columns else 'NO CLOSE COLUMN'}")
        
        result = detector.detect_trend(historical)
        
        print(f"   DEBUG: Result keys: {result.keys()}")
        
        consensus = result.get('consensus', 'unknown')
        confidence = result.get('confidence', 0.0)
        macro = result.get('macro_regime', 'unknown')
        micro = result.get('micro_state', 'unknown')
        price = historical['Close'].iloc[-1] if 'Close' in historical.columns and len(historical) > 0 else 0.0
        ma50 = historical['Close'].rolling(50).mean().iloc[-1] if len(historical) >= 50 else 0.0
        ma20 = historical['Close'].rolling(20).mean().iloc[-1] if len(historical) >= 20 else 0.0
        
        emoji = "🟢" if consensus == "uptrend" else "🔴" if consensus == "downtrend" else "⚪"
        threshold_check = "✓" if confidence > 0.25 else "✗"
        
        print(f"{emoji} {test_date}:")
        print(f"   Consensus: {consensus} (confidence: {confidence:.3f}) {threshold_check}")
        print(f"   Macro: {macro} | Micro: {micro}")
        print(f"   Price: R$ {price:.2f} | MA50: R$ {ma50:.2f} | MA20: R$ {ma20:.2f}")
        print(f"   Historical days: {len(historical)}")
        print()

if __name__ == "__main__":
    # Test VALE3 on strategic dates during Aug 2025 - Feb 2026
    test_dates = [
        "2025-08-15",  # Early in period
        "2025-09-15",  # 1 month in
        "2025-10-15",  # 2 months
        "2025-11-15",  # 3 months
        "2025-12-15",  # 4 months
        "2026-01-15",  # 5 months
        "2026-02-10",  # Near end
    ]
    
    print("\n" + "="*70)
    print("🔬 TREND DETECTOR V2 DIAGNOSTIC")
    print("="*70)
    print(f"Period: Aug 2025 - Feb 2026")
    print(f"Threshold: 0.25")
    print(f"Testing: {len(test_dates)} dates")
    
    diagnose_ticker("VALE3.SA", test_dates)
    
    print("\n" + "="*70)
    print("📊 SUMMARY")
    print("="*70)
    print("If ALL confidence values are < 0.25, the problem is:")
    print("  1. Confidence calculation is too conservative")
    print("  2. Thresholds in detector logic are wrong")
    print("  3. Data quality issues")
    print("\nIf SOME confidence > 0.25 but still 0 trades in backtest:")
    print("  Problem is in the backtest execution logic")
    print("="*70)
