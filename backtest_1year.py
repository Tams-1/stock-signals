#!/usr/bin/env python3
"""1-Year Backtest: Feb 2025 - Feb 2026"""

import sys
sys.path.append('.')

import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime
from production_simple import SimpleProductionRunner

START = "2025-02-01"
END = "2026-02-17"
IBOV = "^BVSP"
CAPITAL = 100000

STOCKS = ['PETR4.SA', 'VALE3.SA', 'ITUB4.SA', 'BBDC4.SA', 'BBAS3.SA',
          'ABEV3.SA', 'B3SA3.SA', 'SUZB3.SA', 'RENT3.SA', 'WEGE3.SA']

print(f"\n{'='*70}")
print("1-YEAR BACKTEST: Feb 2025 - Feb 2026")
print(f"{'='*70}\n")

# Download
print("Downloading data...")
ibov = yf.download(IBOV, start=START, end=END, progress=False)
print(f"IBOV: {len(ibov)} days")

stocks = {}
for t in STOCKS:
    d = yf.download(t, start=START, end=END, progress=False)
    if len(d) > 200:  # Need 1 year
        stocks[t] = d
        print(f"  {t}: {len(d)} days")

print(f"\n{len(stocks)} stocks loaded\n")

# Backtest
runner = SimpleProductionRunner(use_news=False)
days = sorted(ibov.index)

# Skip first 50 days for warmup, then trade
portfolio = CAPITAL
positions = {}
trades = []
portfolio_values = []
ibov_values = []

for i, date in enumerate(days[50:]):
    # Analyze
    for ticker, data in stocks.items():
        hist = data[data.index <= date]
        if len(hist) < 50:
            continue
        
        r = runner.analyze_ticker(ticker)
        if r and r['signal'] == 'BUY' and ticker not in positions:
            size = r['position_size']
            price = r['price']
            cost = size * CAPITAL
            if portfolio >= cost:
                portfolio -= cost
                positions[ticker] = {'shares': cost/price, 'entry': price, 'date': date}
                trades.append({'date': date, 'ticker': ticker, 'action': 'BUY', 
                              'price': price, 'size': size, 'conf': r['conviction']})
        
        elif r and r['signal'] == 'SELL' and ticker in positions:
            pos = positions[ticker]
            cur_price = r['price']
            val = cur_price * pos['shares']
            portfolio += val
            pnl = (cur_price - pos['entry']) / pos['entry']
            trades.append({'date': date, 'ticker': ticker, 'action': 'SELL',
                          'price': cur_price, 'pnl': pnl})
            del positions[ticker]
    
    # Value
    total = portfolio
    for t, p in positions.items():
        if t in stocks and date in stocks[t].index:
            total += stocks[t].loc[date, 'Close'] * p['shares']
    portfolio_values.append(total)
    
    idx = ibov['Close'].squeeze()
    ibov_val = CAPITAL * idx.loc[date] / idx.iloc[0]
    ibov_values.append(ibov_val)

# Results
final = portfolio_values[-1]
strat_ret = (final - CAPITAL) / CAPITAL * 100
ibov_ret = (ibov_values[-1] - CAPITAL) / CAPITAL * 100
alpha = strat_ret - ibov_ret

print(f"\n{'='*70}")
print("RESULTS")
print(f"{'='*70}")
print(f"Period: {days[50].strftime('%Y-%m-%d')} to {days[-1].strftime('%Y-%m-%d')}")
print(f"Trading Days: {len(portfolio_values)}")
print(f"\nIBOV Return:      {ibov_ret:+.2f}%")
print(f"Strategy Return:  {strat_ret:+.2f}%")
print(f"Alpha:            {alpha:+.2f}%")
print(f"\nTotal Trades:     {len(trades)}")
print(f"BUY signals:      {len([t for t in trades if t['action']=='BUY'])}")
print(f"SELL signals:     {len([t for t in trades if t['action']=='SELL'])}")

if trades:
    print(f"\n{'='*70}")
    print("TRADE LOG")
    print(f"{'='*70}\n")
    for t in trades[-20:]:  # Last 20 trades
        if t['action'] == 'BUY':
            print(f"{t['date'].strftime('%Y-%m-%d')} | {t['ticker']} | BUY  | R${t['price']:.2f} | conf: {t['conf']:.1%}")
        else:
            print(f"{t['date'].strftime('%Y-%m-%d')} | {t['ticker']} | SELL | R${t['price']:.2f} | P&L: {t['pnl']:+.1%}")

print(f"\n{'='*70}\n")

# Save
with open('BACKTEST_1YEAR.txt', 'w') as f:
    f.write(f"1-YEAR BACKTEST: Feb 2025 - Feb 2026\n")
    f.write(f"{'='*70}\n\n")
    f.write(f"IBOV:        {ibov_ret:+.2f}%\n")
    f.write(f"Strategy:    {strat_ret:+.2f}%\n")
    f.write(f"Alpha:       {alpha:+.2f}%\n\n")
    f.write(f"Trades: {len(trades)}\n")
    for t in trades:
        f.write(f"{t}\n")

print("✓ Saved to BACKTEST_1YEAR.txt")
