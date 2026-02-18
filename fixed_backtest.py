#!/usr/bin/env python3
"""
FIXED Backtest - Nov 2025 to Feb 2026
Resolves look-ahead bias and confidence threshold issues
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

from production_simple import SimpleProductionRunner
from src.signals.trend_detector_v2 import TrendDetectorV2

# Download period needs 50 days warmup before Nov 1, 2025
DOWNLOAD_START = "2025-09-01"  # Get data from Sep to have 50+ days before Nov 1
BACKTEST_START = "2025-11-01"  # Actual backtest start
BACKTEST_END = "2026-02-17"
IBOV_INDEX = "^BVSP"
INITIAL_CAPITAL = 100000

# Universe
STOCKS = ['PETR4.SA', 'VALE3.SA', 'ITUB4.SA', 'BBDC4.SA', 'BBAS3.SA',
          'ABEV3.SA', 'B3SA3.SA', 'SUZB3.SA', 'RENT3.SA', 'WEGE3.SA']

print(f"\n{'='*70}")
print("FIXED BACKTEST - Nov 2025 to Feb 2026")
print(f"{'='*70}\n")

# Download extended data for warmup
print(f"Downloading data from {DOWNLOAD_START} to {BACKTEST_END}...")

# Download IBOV
print("  Downloading IBOV...")
ibov_data = yf.download(IBOV_INDEX, start=DOWNLOAD_START, end=BACKTEST_END, progress=False)
ibov_close = ibov_data['Close'].squeeze()

# Calculate IBOV return for backtest period only
backtest_ibov = ibov_close[ibov_close.index >= BACKTEST_START]
if len(backtest_ibov) > 0:
    ibov_return = (backtest_ibov.iloc[-1] - backtest_ibov.iloc[0]) / backtest_ibov.iloc[0] * 100
else:
    ibov_return = 0

print(f"  IBOV: {len(ibov_data)} total days, {len(backtest_ibov)} backtest days")
print(f"  IBOV Return (Nov-Feb): {ibov_return:.2f}%\n")

# Download stocks
print("Downloading stocks...")
stock_data = {}
for ticker in STOCKS:
    data = yf.download(ticker, start=DOWNLOAD_START, end=BACKTEST_END, progress=False)
    if len(data) >= 50:  # Need at least 50 days for trend detection
        stock_data[ticker] = data
        # Calculate return for backtest period only
        backtest_close = data['Close'].squeeze()
        backtest_close = backtest_close[backtest_close.index >= BACKTEST_START]
        if len(backtest_close) > 0:
            ret = (backtest_close.iloc[-1] - backtest_close.iloc[0]) / backtest_close.iloc[0] * 100
            print(f"  {ticker}: {len(data)} total days, Return: {ret:+.2f}%")
        else:
            print(f"  {ticker}: {len(data)} total days (no backtest data)")
    else:
        print(f"  {ticker}: SKIPPED (only {len(data)} days)")

print(f"\n{len(stock_data)} stocks with sufficient data\n")

# Get trading days from IBOV data, starting from BACKTEST_START
trading_days = sorted([d for d in ibov_data.index if d >= pd.Timestamp(BACKTEST_START)])
print(f"Backtest trading days: {len(trading_days)} days\n")

# Initialize strategy (no news for backtest)
runner = SimpleProductionRunner(use_news=False)

# Run backtest
portfolio_value = INITIAL_CAPITAL
positions = {}
trades = []
portfolio_values = []

# Warmup: skip first 20 days to allow trend detection to stabilize
warmup_days = 20
actual_trading_days = trading_days[warmup_days:]

print(f"Running strategy on {len(actual_trading_days)} days (after {warmup_days}-day warmup)...\n")

for i, date in enumerate(actual_trading_days):
    # Progress every 20 days
    if i % 20 == 0:
        print(f"  Processing {date.strftime('%Y-%m-%d')}... ({i}/{len(actual_trading_days)})")
    
    # Analyze each stock with HISTORICAL data (no look-ahead bias)
    for ticker, full_data in stock_data.items():
        # Get data up to current date ONLY
        hist_data = full_data[full_data.index <= date]
        
        if len(hist_data) < 50:
            continue
        
        # FIX: Pass historical data to analyze_ticker
        result = runner.analyze_ticker(ticker, data=hist_data)
        
        if result is None:
            continue
        
        # Process BUY signal
        if result['signal'] == 'BUY' and ticker not in positions:
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
        
        # Process SELL signal
        elif result['signal'] == 'SELL' and ticker in positions:
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
        if ticker in stock_data:
            hist_data = stock_data[ticker][stock_data[ticker].index <= date]
            if len(hist_data) > 0:
                price_val = hist_data['Close'].iloc[-1]
                # Handle both scalar and Series
                if hasattr(price_val, 'item'):
                    current_price = float(price_val.item())
                elif hasattr(price_val, 'iloc'):
                    current_price = float(price_val.iloc[0])
                else:
                    current_price = float(price_val)
                total_value += current_price * pos['shares']
    
    portfolio_values.append({'date': date, 'value': total_value})

# Close all positions at end of backtest
print("\nClosing remaining positions...")
for ticker, pos in list(positions.items()):
    final_data = stock_data[ticker]
    final_data = final_data[final_data.index <= actual_trading_days[-1]]
    if len(final_data) > 0:
        price_val = final_data['Close'].iloc[-1]
        # Handle both scalar and Series
        if hasattr(price_val, 'item'):
            current_price = float(price_val.item())
        elif hasattr(price_val, 'iloc'):
            current_price = float(price_val.iloc[0])
        else:
            current_price = float(price_val)
        
        value = current_price * pos['shares']
        portfolio_value += value
        
        pnl = (current_price - pos['entry_price']) / pos['entry_price']
        trades.append({
            'date': actual_trading_days[-1],
            'ticker': ticker,
            'action': 'SELL (FINAL)',
            'price': current_price,
            'pnl': pnl,
            'holding_days': (actual_trading_days[-1] - pos['entry_date']).days
        })
        del positions[ticker]

# Final results
final_value = portfolio_values[-1]['value'] if portfolio_values else INITIAL_CAPITAL
strategy_return = (final_value - INITIAL_CAPITAL) / INITIAL_CAPITAL * 100
alpha = strategy_return - ibov_return

buy_trades = [t for t in trades if 'BUY' in t['action']]
sell_trades = [t for t in trades if 'SELL' in t['action']]

print(f"\n{'='*70}")
print("RESULTS")
print(f"{'='*70}")
print(f"\nIBOV Return:        {ibov_return:+.2f}%")
print(f"Strategy Return:    {strategy_return:+.2f}%")
print(f"Alpha:              {alpha:+.2f}%")
print(f"\nTotal Trades:       {len(trades)}")
print(f"BUY signals:        {len(buy_trades)}")
print(f"SELL signals:       {len(sell_trades)}")
print(f"Positions held:     {len(positions)} (still open)")

if buy_trades:
    avg_confidence = np.mean([t['confidence'] for t in buy_trades])
    print(f"\nAverage confidence: {avg_confidence:.1%}")

# Trade details
if buy_trades:
    print(f"\n{'='*70}")
    print("TRADE LOG - BUY SIGNALS")
    print(f"{'='*70}\n")
    
    for trade in buy_trades:
        print(f"{trade['date'].strftime('%Y-%m-%d')} | {trade['ticker']} | BUY @ R${trade['price']:.2f} | Pos: {trade['position_size']:.1%} | Conf: {trade['confidence']:.1%}")

if sell_trades:
    print(f"\n{'='*70}")
    print("TRADE LOG - SELL SIGNALS")
    print(f"{'='*70}\n")
    
    winning_sells = [t for t in sell_trades if t.get('pnl', 0) > 0]
    total_pnl = sum([t.get('pnl', 0) for t in sell_trades])
    
    for trade in sell_trades:
        emoji = "🟢" if trade.get('pnl', 0) > 0 else "🔴"
        print(f"{trade['date'].strftime('%Y-%m-%d')} | {trade['ticker']} | {emoji} SELL @ R${trade['price']:.2f} | P&L: {trade.get('pnl', 0):+.2%} | Days: {trade.get('holding_days', 0)}")
    
    print(f"\nWin rate: {len(winning_sells)}/{len(sell_trades)} ({len(winning_sells)/len(sell_trades)*100:.0f}%)")
    print(f"Average P&L: {total_pnl/len(sell_trades):+.2%}")

# Portfolio value chart
print(f"\n{'='*70}")
print("PORTFOLIO VALUE OVER TIME")
print(f"{'='*70}\n")
print(f"{'Date':<12} {'Portfolio':>15} {'Return':>10}")
print("-" * 40)
for pv in portfolio_values[::max(1, len(portfolio_values)//10)]:  # Sample ~10 points
    ret = (pv['value'] - INITIAL_CAPITAL) / INITIAL_CAPITAL * 100
    print(f"{pv['date'].strftime('%Y-%m-%d'):<12} R${pv['value']:>13,.0f} {ret:>9.1f}%")

print(f"\n{'='*70}")
print("✓ Backtest complete")
print(f"{'='*70}\n")

# Save results
with open('FIXED_BACKTEST_RESULTS.txt', 'w') as f:
    f.write(f"FIXED BACKTEST RESULTS\n")
    f.write(f"Period: Nov 2025 - Feb 2026\n")
    f.write(f"Fixes applied:\n")
    f.write(f"  1. Modified analyze_ticker() to accept pre-loaded data\n")
    f.write(f"  2. Fixed look-ahead bias - now uses historical data only\n")
    f.write(f"  3. Relaxed confidence calculation in TrendDetectorV2\n")
    f.write(f"  4. Changed confidence formula: 0.5 base + scale instead of strict threshold\n")
    f.write(f"{'='*70}\n\n")
    f.write(f"IBOV Return: {ibov_return:.2f}%\n")
    f.write(f"Strategy Return: {strategy_return:.2f}%\n")
    f.write(f"Alpha: {alpha:+.2f}%\n")
    f.write(f"\nTotal Trades: {len(trades)}\n")
    f.write(f"BUY signals: {len(buy_trades)}\n")
    f.write(f"SELL signals: {len(sell_trades)}\n")
    
    if buy_trades:
        f.write(f"\n--- BUY TRADES ---\n")
        for trade in buy_trades:
            f.write(f"{trade['date'].strftime('%Y-%m-%d')} | {trade['ticker']} | BUY @ R${trade['price']:.2f} | Conf: {trade['confidence']:.1%}\n")

print("Results saved to FIXED_BACKTEST_RESULTS.txt")
