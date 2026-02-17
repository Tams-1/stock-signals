#!/usr/bin/env python3
"""
Comprehensive Backtest: Nov 2025 to Present
Stock-Signals Production-Hardening Branch
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import yfinance as yf
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
from src.signals.trend_detector_v2 import TrendDetectorV2
from production_simple import SimpleProductionRunner

# Configuration
BACKTEST_START = "2024-11-01"
BACKTEST_END = "2025-02-17"
IBOV_INDEX = "^BVSP"
INITIAL_CAPITAL = 100000

IBOV_TOP_20 = [
    "PETR4.SA", "VALE3.SA", "ITUB4.SA", "BBDC4.SA", "BBAS3.SA",
    "ABEV3.SA", "B3SA3.SA", "SUZB3.SA", "RENT3.SA", "WEGE3.SA",
    "MGLU3.SA", "PCAR3.SA", "LREN3.SA", "RAIZ4.SA", "GGBR4.SA",
    "ASAI3.SA", "RDOR3.SA", "ELET3.SA", "RADL3.SA", "EQTL3.SA"
]

def calculate_sharpe(returns):
    returns_clean = returns.dropna()
    if len(returns_clean) == 0 or returns_clean.std() == 0:
        return 0.0
    return returns_clean.mean() / returns_clean.std() * np.sqrt(252)

def calculate_sortino(returns):
    returns_clean = returns.dropna()
    downside_returns = returns_clean[returns_clean < 0]
    if len(downside_returns) == 0 or downside_returns.std() == 0:
        return 0.0
    return returns_clean.mean() / downside_returns.std() * np.sqrt(252)

def calculate_max_drawdown(values):
    cummax = pd.Series(values).cummax()
    drawdown = (cummax - pd.Series(values)).max()
    return drawdown / pd.Series(values)[0] * 100

def run_backtest():
    print("\n" + "="*70)
    print("STOCK SIGNALS BACKTEST - NOV 2024 TO FEB 2025")
    print("="*70)
    
    # Download IBOV
    print("\nDownloading IBOV index...")
    ibov_data = yf.download(IBOV_INDEX, start=BACKTEST_START, end=BACKTEST_END, progress=False)
    print(f"  IBOV: {len(ibov_data)} days")
    
    # Download stocks
    print("\nDownloading stocks...")
    stock_data = {}
    for ticker in IBOV_TOP_20:
        try:
            data = yf.download(ticker, start=BACKTEST_START, end=BACKTEST_END, progress=False)
            if not data.empty:
                stock_data[ticker] = data
        except:
            pass
    print(f"  Downloaded {len(stock_data)} stocks")
    
    # Run backtest
    print("\nRunning backtest...")
    trading_days = sorted(list(set(ibov_data.index)))
    trading_days = [d for d in trading_days if d >= pd.Timestamp(BACKTEST_START)]
    
    initial_capital = INITIAL_CAPITAL
    cash = initial_capital
    positions = {}
    trades = []
    portfolio_values = []
    ibov_values = []
    
    runner = SimpleProductionRunner(use_news=False)
    trend_detector = TrendDetectorV2()
    
    ibov_initial = ibov_data['Close'].iloc[0]
    
    for i, date in enumerate(trading_days[60:]):
        # Generate signals
        signals = {}
        for ticker, data in stock_data.items():
            hist_data = data[data.index <= date]
            if len(hist_data) < 50:
                continue
            
            result = runner.analyze_ticker(ticker)
            if result and result['signal'] != 'HOLD':
                signals[ticker] = result
        
        # Execute trades
        for ticker, sig in signals.items():
            if sig['signal'] == 'BUY':
                cost = sig['position_size'] * initial_capital
                if cash >= cost and ticker not in positions:
                    cash -= cost
                    positions[ticker] = {
                        'shares': cost / sig['price'],
                        'entry_price': sig['price']
                    }
                    trades.append({'date': date, 'ticker': ticker, 'signal': 'BUY', 'price': sig['price']})
            elif sig['signal'] == 'SELL' and ticker in positions:
                shares = positions[ticker]['shares']
                entry_price = positions[ticker]['entry_price']
                current_price = sig['price']
                value = current_price * shares
                cash += value
                trades.append({
                    'date': date,
                    'ticker': ticker,
                    'signal': 'SELL',
                    'price': current_price,
                    'pnl': (current_price - entry_price) / entry_price
                })
                del positions[ticker]
        
        # Calculate portfolio value
        portfolio_value = cash
        for ticker, pos in positions.items():
            if ticker in stock_data and date in stock_data[ticker].index:
                current_price = stock_data[ticker].loc[date, 'Close']
                portfolio_value += current_price * pos['shares']
        
        portfolio_values.append(portfolio_value)
        
        # IBOV value
        if date in ibov_data.index:
            ibov_values.append(initial_capital * ibov_data.loc[date, 'Close'] / ibov_initial)
    
    # Calculate metrics
    portfolio_final = portfolio_values[-1]
    ibov_final = ibov_values[-1]
    portfolio_return = (portfolio_final - initial_capital) / initial_capital * 100
    ibov_return = (ibov_final - initial_capital) / initial_capital * 100
    
    portfolio_returns = pd.Series(portfolio_values).pct_change().dropna()
    ibov_returns = pd.Series(ibov_values).pct_change().dropna()
    
    portfolio_sharpe = calculate_sharpe(portfolio_returns)
    ibov_sharpe = calculate_sharpe(ibov_returns)
    
    portfolio_sortino = calculate_sortino(portfolio_returns)
    ibov_sortino = calculate_sortino(ibov_returns)
    
    portfolio_max_dd = calculate_max_drawdown(portfolio_values)
    ibov_max_dd = calculate_max_drawdown(ibov_values)
    
    portfolio_vol = portfolio_returns.std() * np.sqrt(252) * 100
    ibov_vol = ibov_returns.std() * np.sqrt(252) * 100
    
    winning_trades = sum(1 for t in trades if 'pnl' in t and t['pnl'] > 0)
    total_trades = len([t for t in trades if 'pnl' in t])
    win_rate = winning_trades / total_trades * 100 if total_trades > 0 else 0
    
    # Print results
    print("\n" + "="*70)
    print("BACKTEST RESULTS")
    print("="*70)
    
    print(f"\nStrategy Performance:")
    print(f"  Final Value:       R${portfolio_final:,.2f}")
    print(f"  Total Return:      {portfolio_return:+.2f}%")
    print(f"  Sharpe Ratio:      {portfolio_sharpe:.2f}")
    print(f"  Sortino Ratio:     {portfolio_sortino:.2f}")
    print(f"  Max Drawdown:      {portfolio_max_dd:.2f}%")
    print(f"  Volatility:        {portfolio_vol:.2f}%")
    print(f"  Win Rate:          {win_rate:.1f}%")
    
    print(f"\nIBOV Benchmark:")
    print(f"  Final Value:       R${ibov_final:,.2f}")
    print(f"  Total Return:      {ibov_return:+.2f}%")
    print(f"  Sharpe Ratio:      {ibov_sharpe:.2f}")
    print(f"  Sortino Ratio:     {ibov_sortino:.2f}")
    print(f"  Max Drawdown:      {ibov_max_dd:.2f}%")
    print(f"  Volatility:        {ibov_vol:.2f}%")
    
    alpha = portfolio_return - ibov_return
    print(f"\nAlpha (Excess Return): {alpha:+.2f}%")
    print(f"Total Trades: {total_trades}")
    
    # Create plot
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 10))
    
    ax1.plot(portfolio_values, label='Strategy', linewidth=2, color='green')
    ax1.plot(ibov_values, label='IBOV', linewidth=2, alpha=0.7, color='orange')
    ax1.axhline(y=initial_capital, color='red', linestyle='--', alpha=0.5)
    ax1.set_title('Portfolio Value vs IBOV (Nov 2024 - Feb 2025)', fontsize=14, fontweight='bold')
    ax1.set_ylabel('Value (R$)')
    ax1.legend()
    ax1.grid(True, alpha=0.3)
    
    portfolio_dd = -(pd.Series(portfolio_values).cummax() - pd.Series(portfolio_values)) / portfolio_values[0] * 100
    ibov_dd = -(pd.Series(ibov_values).cummax() - pd.Series(ibov_values)) / ibov_values[0] * 100
    
    ax2.fill_between(range(len(portfolio_dd)), 0, portfolio_dd, alpha=0.3, color='green', label='Strategy DD')
    ax2.fill_between(range(len(ibov_dd)), 0, ibov_dd, alpha=0.3, color='orange', label='IBOV DD')
    ax2.set_title('Drawdown Comparison', fontsize=14, fontweight='bold')
    ax2.set_xlabel('Trading Days')
    ax2.set_ylabel('Drawdown (%)')
    ax2.legend()
    ax2.grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.savefig('backtest_results.png', dpi=150)
    print("\n✅ Plot saved to backtest_results.png")
    
    return {
        'portfolio_return': portfolio_return,
        'ibov_return': ibov_return,
        'alpha': alpha,
        'sharpe': portfolio_sharpe,
        'sortino': portfolio_sortino,
        'max_drawdown': portfolio_max_dd,
        'volatility': portfolio_vol,
        'win_rate': win_rate,
        'total_trades': total_trades
    }

if __name__ == "__main__":
    results = run_backtest()
    print("\n✅ BACKTEST COMPLETE")
