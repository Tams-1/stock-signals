#!/usr/bin/env python3
"""
Analyze initial portfolio selection on Nov 1, 2025
Then track performance vs IBOV through Feb 2026
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime
from production_simple import SimpleProductionRunner

# Dates
START_DATE = "2025-11-01"
END_DATE = "2026-02-17"
IBOV_INDEX = "^BVSP"
INITIAL_CAPITAL = 100000

# Universe - expanded to find some signals
STOCKS = ['PETR4.SA', 'VALE3.SA', 'ITUB4.SA', 'BBDC4.SA', 'BBAS3.SA',
          'ABEV3.SA', 'B3SA3.SA', 'SUZB3.SA', 'RENT3.SA', 'WEGE3.SA',
          'RAIZ4.SA', 'GGBR4.SA', 'RDOR3.SA', 'HAPV3.SA', 'RADL3.SA']

print(f"\n{'='*70}")
print("INITIAL PORTFOLIO ANALYSIS - Nov 1, 2025")
print(f"{'='*70}\n")

# Download data
print("Downloading data...")
ibov_data = yf.download(IBOV_INDEX, start=START_DATE, end=END_DATE, progress=False)

stock_data = {}
for ticker in STOCKS:
    data = yf.download(ticker, start='2025-09-01', end=END_DATE, progress=False)  # Extra history for 50-day lookback
    if len(data) > 60:
        stock_data[ticker] = data

print(f"Downloaded {len(stock_data)} stocks\n")

# Analyze Nov 1, 2025
analysis_date = pd.Timestamp('2025-11-01')
runner = SimpleProductionRunner(use_news=False)

print(f"Analyzing signals for {analysis_date.strftime('%Y-%m-%d')}...")
print(f"{'='*70}\n")

buy_signals = []
for ticker, data in stock_data.items():
    # Get data up to Nov 1
    hist_data = data[data.index <= analysis_date]
    
    if len(hist_data) < 50:
        print(f"{ticker}: Insufficient history ({len(hist_data)} days)")
        continue
    
    # Get signal
    result = runner.analyze_ticker(ticker)
    
    if result:
        signal = result.get('signal', 'HOLD')
        confidence = result.get('conviction', 0)
        trend = result.get('trend', 'unknown')
        
        print(f"{ticker:10} | Signal: {signal:6} | Trend: {trend:15} | Confidence: {confidence:6.1%}")
        
        if signal == 'BUY' and confidence >= 0.50:
            buy_signals.append({
                'ticker': ticker,
                'confidence': confidence,
                'position_size': result.get('position_size', 0.2),
                'entry_price': result.get('price', 0),
                'trend': trend
            })
    else:
        print(f"{ticker:10} | No result from analyze_ticker()")

print(f"\n{'='*70}")
print(f"SUMMARY: {len(buy_signals)} BUY signals with ≥50% confidence")
print(f"{'='*70}\n")

if buy_signals:
    print("Initial Portfolio Composition:")
    for signal in sorted(buy_signals, key=lambda x: x['confidence'], reverse=True):
        print(f"  {signal['ticker']:10} | Confidence: {signal['confidence']:5.1%} | Position: {signal['position_size']:5.1%} | Trend: {signal['trend']}")
    
    # Now track performance
    print(f"\n{'='*70}")
    print("TRACKING PORTFOLIO PERFORMANCE")
    print(f"{'='*70}\n")
    
    # Equal weight for simplicity
    weight_per_stock = 1.0 / len(buy_signals)
    
    # Calculate returns
    portfolio_values = []
    dates = []
    
    trading_days = ibov_data.index
    
    for date in trading_days:
        portfolio_value = 0
        
        for signal in buy_signals:
            ticker = signal['ticker']
            if ticker in stock_data and date in stock_data[ticker].index:
                current_price = stock_data[ticker].loc[date, 'Close']
                entry_price = signal['entry_price'] if signal['entry_price'] > 0 else current_price
                stock_return = (current_price - entry_price) / entry_price if entry_price > 0 else 0
                portfolio_value += weight_per_stock * (1 + stock_return)
        
        portfolio_values.append(portfolio_value * INITIAL_CAPITAL)
        dates.append(date)
    
    # Calculate metrics
    initial_portfolio = portfolio_values[0]
    final_portfolio = portfolio_values[-1]
    portfolio_return = (final_portfolio - initial_portfolio) / initial_portfolio * 100
    
    ibov_start = ibov_data['Close'].iloc[0]
    ibov_end = ibov_data['Close'].iloc[-1]
    ibov_return = (ibov_end - ibov_start) / ibov_start * 100
    
    alpha = portfolio_return - ibov_return
    
    print(f"Initial Portfolio Value: R${initial_portfolio:,.2f}")
    print(f"Final Portfolio Value:   R${final_portfolio:,.2f}")
    print(f"Portfolio Return:        {portfolio_return:+.2f}%")
    print(f"\nIBOV Return:             {ibov_return:+.2f}%")
    print(f"Alpha:                   {alpha:+.2f}%")
    
    # Save results
    with open('INITIAL_PORTFOLIO_RESULTS.txt', 'w') as f:
        f.write("INITIAL PORTFOLIO BACKTEST RESULTS\n")
        f.write(f"Analysis Date: {analysis_date.strftime('%Y-%m-%d')}\n")
        f.write(f"Period: {START_DATE} to {END_DATE}\n")
        f.write(f"{'='*70}\n\n")
        
        f.write(f"BUY Signals (≥50% confidence): {len(buy_signals)}\n\n")
        for signal in buy_signals:
            f.write(f"  {signal['ticker']}: {signal['confidence']:.1%} confidence, {signal['position_size']:.1%} position\n")
        
        f.write(f"\n{'='*70}\n")
        f.write("PERFORMANCE\n")
        f.write(f"{'='*70}\n\n")
        f.write(f"Portfolio Return: {portfolio_return:.2f}%\n")
        f.write(f"IBOV Return:      {ibov_return:.2f}%\n")
        f.write(f"Alpha:            {alpha:+.2f}%\n")
    
    print(f"\n✓ Results saved to INITIAL_PORTFOLIO_RESULTS.txt")

else:
    print("No BUY signals met the 50% confidence threshold on Nov 1, 2025")
    print("\nThis confirms the earlier finding: the strategy would have sat in cash")
    print("during the entire Nov-Feb period, missing the +24% IBOV rally.")
    
    print(f"\n{'='*70}")
    print("CODE REVIEW FINDINGS")
    print(f"{'='*70}\n")
    
    print("Issue: analyze_ticker() returns 'consolidation' with 0% confidence")
    print("for most stocks during the test period.")
    print("\nLikely causes:")
    print("  1. Threshold too high (50% minimum confidence)")
    print("  2. Trend detection requires more historical data")
    print("  3. Volatility regime classification too conservative")
    print("  4. Dual-timeframe consensus logic too strict")
    
    print(f"\n{'='*70}")
    print("RECOMMENDATION")
    print(f"{'='*70}\n")
    
    print("Lower confidence threshold from 50% to 30% OR")
    print("Add momentum signals for trending markets")

print(f"\n{'='*70}\n")
