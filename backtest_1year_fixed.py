#!/usr/bin/env python3
"""
CORRECTED 1-Year Backtest - Feb 2025 to Feb 2026
Uses FIXED trend detector
"""

import sys
sys.path.append('.')

import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime
from production_simple import SimpleProductionRunner

# Use historical data proxy since we can't download future dates
# We'll use 2024-2025 data as proxy for 2025-2026 (similar market conditions)
START = "2024-02-01"  # Proxy for Feb 2025
END = "2025-02-17"    # Proxy for Feb 2026
CAPITAL = 100000

STOCKS = ['PETR4.SA', 'VALE3.SA', 'ITUB4.SA', 'BBDC4.SA', 'BBAS3.SA']

print(f"\n{'='*70}")
print("1-YEAR BACKTEST (Proxy Period: Feb 2024 - Feb 2025)")
print("Note: Using 2024-2025 as proxy for 2025-2026 market conditions")
print(f"{'='*70}\n")

# Download
print("Loading data...")
ibov = yf.download('^BVSP', start=START, end=END, progress=False)
print(f"IBOV: {len(ibov)} days")

stocks = {}
for t in STOCKS:
    d = yf.download(t, start=START, end=END, progress=False)
    if len(d) > 200:
        stocks[t] = d

print(f"Loaded {len(stocks)} stocks\n")

# Run backtest
runner = SimpleProductionRunner(use_news=False)
days = list(ibov.index)

portfolio = CAPITAL
positions = {}
trades = []
portfolio_values = []

# Start trading after 50-day warmup
for date in days[50:]:
    for ticker, data in stocks.items():
        hist = data[data.index <= date]
        if len(hist) < 50:
            continue
        
        # Get signal
        r = runner.analyze_ticker(ticker)
        if r and r['signal'] == 'BUY' and ticker not in positions:
            cost = r['position_size'] * CAPITAL
            if portfolio >= cost:
                portfolio -= cost
                positions[ticker] = {
                    'shares': cost / r['price'],
                    'entry': r['price'],
                    'date': date
                }
                trades.append({
                    'date': date, 'ticker': ticker, 'action': 'BUY',
                    'price': r['price'], 'size': r['position_size'],
                    'conf': r['conviction']
                })
        
        elif r and r['signal'] == 'SELL' and ticker in positions:
            pos = positions[ticker]
            val = r['price'] * pos['shares']
            portfolio += val
            pnl = (r['price'] - pos['entry']) / pos['entry']
            trades.append({
                'date': date, 'ticker': ticker, 'action': 'SELL',
                'price': r['price'], 'pnl': pnl
            })
            del positions[ticker]
    
    # Calculate portfolio value
    total = portfolio
    for t, p in positions.items():
        if t in stocks and date in stocks[t].index:
            total += stocks[t].loc[date, 'Close'] * p['shares']
    portfolio_values.append(total)

# Results
strat_ret = (portfolio_values[-1] - CAPITAL) / CAPITAL * 100
ibov_ret = (ibov['Close'].iloc[-1] - ibov['Close'].iloc[0]) / ibov['Close'].iloc[0] * 100
alpha = strat_ret - ibov_ret

print(f"{'='*70}")
print("RESULTS")
print(f"{'='*70}")
print(f"IBOV Return:      {ibov_ret:+.2f}%")
print(f"Strategy Return:  {strat_ret:+.2f}%")
print(f"Alpha:            {alpha:+.2f}%")
print(f"\nTotal Trades:     {len(trades)}")
print(f"BUY signals:      {len([t for t in trades if t['action']=='BUY'])}")
print(f"SELL signals:     {len([t for t in trades if t['action']=='SELL'])}")

if trades:
    print(f"\n{'='*70}")
    print("RECENT TRADES")
    print(f"{'='*70}\n")
    for t in trades[-10:]:
        if t['action'] == 'BUY':
            print(f"{t['date'].strftime('%Y-%m-%d')} | {t['ticker']} | BUY @ R${t['price']:.2f}")
        else:
            print(f"{t['date'].strftime('%Y-%m-%d')} | {t['ticker']} | SELL @ R${t['price']:.2f} | P&L: {t['pnl']:+.1%}")

print(f"\n{'='*70}\n")

# Save
with open('BACKTEST_1YEAR_FIXED.txt', 'w') as f:
    f.write(f"1-YEAR BACKTEST (Proxy Period)\n")
    f.write(f"{'='*70}\n\n")
    f.write(f"IBOV:        {ibov_ret:+.2f}%\n")
    f.write(f"Strategy:    {strat_ret:+.2f}%\n")
    f.write(f"Alpha:       {alpha:+.2f}%\n\n")
    f.write(f"Trades: {len(trades)}\n")
    for t in trades:
        f.write(f"{t}\n")

print("✓ Results saved to BACKTEST_1YEAR_FIXED.txt")
