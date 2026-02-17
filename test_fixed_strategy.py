#!/usr/bin/env python3
"""
FIXED Production Simple - Lower thresholds for better signal generation
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List
from src.signals.trend_detector_v2 import TrendDetectorV2

class FixedProductionRunner:
    """Fixed version with lower thresholds"""
    
    def __init__(self, use_news: bool = True, n_workers: int = None):
        self.trend_detector = TrendDetectorV2()
        self.use_news = use_news
        self.n_workers = n_workers or 8
        print(f"✅ Fixed system initialized (workers={self.n_workers})")
    
    def get_data(self, ticker: str, lookback: int = 60) -> pd.DataFrame:
        """Download data with retry logic"""
        for attempt in range(3):
            try:
                end = datetime.now()
                start = end - timedelta(days=lookback + 10)
                data = yf.download(ticker, start=start.strftime('%Y-%m-%d'), 
                                  end=end.strftime('%Y-%m-%d'), progress=False)
                if isinstance(data.columns, pd.MultiIndex):
                    data.columns = data.columns.get_level_values(0)
                if len(data) >= lookback:
                    return data
            except Exception as e:
                if attempt < 2:
                    import time
                    time.sleep(2 ** attempt)
        return None
    
    def analyze_ticker(self, ticker: str) -> Dict:
        """Analyze with LOWER thresholds"""
        try:
            data = self.get_data(ticker)
            if data is None or len(data) < 50:
                return None
            
            current_price = float(data['Close'].iloc[-1])
            
            # Trend detection
            trend_result = self.trend_detector.detect_trend(data)
            consensus = trend_result.get('consensus', 'unknown')
            confidence = trend_result.get('confidence', 0.0)
            
            # FIX #1: Lower threshold from 50% to 30%
            # FIX #2: Include 'consolidation' as potential buy in bull markets
            MIN_CONFIDENCE = 0.30  # Was 0.50
            
            # Map consensus - BE MORE PERMISSIVE
            if consensus in ['uptrend', 'bull_pullback']:
                trend = "uptrend"
                signal_confidence = confidence
            elif consensus == 'consolidation' and confidence >= 0.25:
                # NEW: Allow consolidation with decent confidence
                trend = "uptrend"  # Treat as potential breakout
                signal_confidence = confidence * 0.8  # Slightly discounted
            elif consensus in ['downtrend', 'bear_bounce']:
                trend = "downtrend"
                signal_confidence = confidence
            else:
                trend = "neutral"
                signal_confidence = 0
            
            signal = "HOLD"
            position_size = 0.0
            conviction = 0.0
            
            if trend == "uptrend" and signal_confidence >= MIN_CONFIDENCE:
                signal = "BUY"
                conviction = signal_confidence
                
                # Kelly Criterion - simplified
                returns = data['Close'].pct_change().dropna()
                volatility = returns.std() * np.sqrt(252)
                
                if volatility > 0:
                    kelly = conviction / volatility * 0.5  # Half Kelly for safety
                    position_size = max(0.10, min(0.80, kelly))
                else:
                    position_size = 0.20
            
            return {
                "ticker": ticker,
                "price": current_price,
                "trend": trend,
                "signal": signal,
                "conviction": conviction,
                "position_size": position_size,
                "raw_consensus": consensus,
                "raw_confidence": confidence
            }
            
        except Exception as e:
            print(f"  ❌ Error: {e}")
            return None


if __name__ == "__main__":
    # Test on a few stocks
    print("\n" + "="*70)
    print("TESTING FIXED STRATEGY")
    print("="*70 + "\n")
    
    runner = FixedProductionRunner(use_news=False)
    test_stocks = ['PETR4.SA', 'VALE3.SA', 'ITUB4.SA', 'BBDC4.SA', 'BBAS3.SA']
    
    buy_signals = []
    for ticker in test_stocks:
        result = runner.analyze_ticker(ticker)
        if result:
            print(f"{ticker:10} | {result['raw_consensus']:15} | raw_conf: {result['raw_confidence']:.1%} | "
                  f"signal: {result['signal']:4} | conv: {result['conviction']:.1%} | size: {result['position_size']:.1%}")
            if result['signal'] == 'BUY':
                buy_signals.append(ticker)
    
    print(f"\n{'='*70}")
    print(f"BUY SIGNALS: {len(buy_signals)} / {len(test_stocks)}")
    if buy_signals:
        print(f"Stocks: {', '.join(buy_signals)}")
    print(f"{'='*70}\n")
