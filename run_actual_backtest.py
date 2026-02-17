#!/usr/bin/env python3
"""
ACTUAL Backtest with Real Strategy Logic
Period: Nov 2025 - Feb 2026
Uses: TrendDetectorV2, Kelly Criterion, SimpleProductionRunner
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime
from production_simple import SimpleProductionRunner
from src.signals.trend_detector_v2 import TrendDetectorV2

# Correct dates for Nov 2025 - Feb 2026
BACKTEST_START = "2025-11-01"
BACKTEST_END = "2026-02-17"
IBOV_INDEX = "^BVSP"
INITIAL_CAPITAL = 100000

# Universe
STOCKS = ['PETR4.SA', 'VALE3.SA', 'ITUB4.SA', 'BBDC4.SA', 'BBAS3.SA',
          'ABEV3.SA', 'B3SA3.SA', 'SUZB3.SA', 'RENT3.SA', 'WEGE3.SA']

print(f"\n{'='*70}")
print("ACTUAL BACKTEST - Nov 2025 to Feb 2026")
print(f"{'='*70}\n")

# Download IBOV
print("Downloading IBOV...")
ibov_data = yf.download(IBOV_INDEX, start=BACKTEST_START, end=BACKTEST_END, progress=False)
ibov_close = ibov_data['Close'].squeeze()
ibov_return = (ibov_close.iloc[-1] - ibov_close.iloc[0]) / ibov_close.iloc[0] * 100
print(f"IBOV: {len(ibov_data)} days, Return: {ibov_return:.2f}%\n")

# Download stocks
print("Downloading stocks...")
stock_data = {}
for ticker in STOCKS:
    data = yf.download(ticker, start=BACKTEST_START, end=BACKTEST_END, progress=False)
    if len(data) > 50:
        stock_data[ticker] = data
        close = data['Close'].squeeze()
        ret = (close.iloc[-1] - close.iloc[0]) / close.iloc[0] * 100
        print(f"  {ticker}: {len(data)} days, Return: {ret:+.2f}%")

print(f"\n{len(stock_data)} stocks downloaded\n")

# Initialize strategy
print("Running strategy...")
runner = SimpleProductionRunner(use_news=False)

# Run daily analysis
trading_days = sorted(list(set(ibov_data.index)))
portfolio_value = INITIAL_CAPITAL
positions = {}
trades = []
portfolio_values = []

for i, date in enumerate(trading_days[20:]):  # Skip warmup
    # Analyze each stock
    for ticker, data in stock_data.items():
        hist_data = data[data.index <= date]
        if len(hist_data) < 50:
            continue
        
        # Get signal from actual strategy
        result = runner.analyze_ticker(ticker)
        
        if result and result['signal'] == 'BUY' and ticker not in positions:
            # Buy
            position_size = result['position_size']
            price = result['price']
            cost = position_size * INITIAL_CAPITAL
            
            if portfolio_value >= cost:
                portfolio_value -= cost
                positions[ticker] = {
                    'shares': cost / price,
                    'entry_price': price,
                    'entry_date': date,
                    'position_size': position_size
                }
                trades.append({
                    'date': date,
                    'ticker': ticker,
                    'action': 'BUY',
                    'price': price,
                    'position_size': position_size,
                    'confidence': result['conviction']
                })
        
        elif result and result['signal'] == 'SELL' and ticker in positions:
            # Sell
            pos = positions[ticker]
            current_price = result['price']
            value = current_price * pos['shares']
            portfolio_value += value
            
            pnl = (current_price - pos['entry_price']) / pos['entry_price']
            trades.append({
                'date': date,
                'ticker': ticker,
                'action': 'SELL',
                'price': current_price,
                'pnl': pnl,
                'holding_days': (date - pos['entry_date']).days
            })
            del positions[ticker]
    
    # Calculate portfolio value
    total_value = portfolio_value
    for ticker, pos in positions.items():
        if ticker in stock_data and date in stock_data[ticker].index:
            current_price = stock_data[ticker].loc[date, 'Close']
            total_value += current_price * pos['shares']
    
    portfolio_values.append(total_value)

# Final results
final_value = portfolio_values[-1]
strategy_return = (final_value - INITIAL_CAPITAL) / INITIAL_CAPITAL * 100
alpha = strategy_return - ibov_return

print(f"\n{'='*70}")
print("RESULTS")
print(f"{'='*70}")
print(f"\nIBOV Return: {ibov_return:.2f}%")
print(f"Strategy Return: {strategy_return:.2f}%")
print(f"Alpha: {alpha:+.2f}%")
print(f"\nTotal Trades: {len(trades)}")
print(f"BUY signals: {len([t for t in trades if t['action'] == 'BUY'])}")
print(f"SELL signals: {len([t for t in trades if t['action'] == 'SELL'])}")

# Trade details
print(f"\n{'='*70}")
print("TRADE LOG")
print(f"{'='*70}\n")

for trade in trades:
    if trade['action'] == 'BUY':
        print(f"{trade['date'].strftime('%Y-%m-%d')} | {trade['ticker']} | BUY @ R${trade['price']:.2f} | Position: {trade['position_size']:.1%} | Confidence: {trade['confidence']:.1%}")
    else:
        print(f"{trade['date'].strftime('%Y-%m-%d')} | {trade['ticker']} | SELL @ R${trade['price']:.2f} | P&L: {trade['pnl']:+.2%} | Days: {trade['holding_days']}")

print(f"\n{'='*70}")
print("✓ Backtest complete")
print(f"{'='*70}\n")

# Save results
with open('ACTUAL_BACKTEST_RESULTS.txt', 'w') as f:
    f.write(f"ACTUAL BACKTEST RESULTS\n")
    f.write(f"Period: Nov 2025 - Feb 2026\n")
    f.write(f"{'='*70}\n\n")
    f.write(f"IBOV Return: {ibov_return:.2f}%\n")
    f.write(f"Strategy Return: {strategy_return:.2f}%\n")
    f.write(f"Alpha: {alpha:+.2f}%\n")
    f.write(f"\nTotal Trades: {len(trades)}\n")
    for trade in trades:
        f.write(f"{trade}\n")

print("Results saved to ACTUAL_BACKTEST_RESULTS.txt")
