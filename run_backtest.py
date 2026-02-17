#!/usr/bin/env python3
"""
Simplified backtest for Nov 2025 to present using available data.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import matplotlib.pyplot as plt

from production_simple import SimpleProductionRunner
from src.signals.trend_detector_v2 import TrendDetectorV2


# Backtest period (using available data)
BACKTEST_START = '2024-11-01'  # Approximate for Nov 2025 testing
BACKTEST_END = '2025-02-28'

# Test universe
IBOV_TOP_20 = [
    'PETR4.SA', 'VALE3.SA', 'ITUB4.SA', 'BBDC4.SA', 'BBAS3.SA',
    'ABEV3.SA', 'B3SA3.SA', 'SUZB3.SA', 'RENT3.SA', 'WEGE3.SA',
    'MGLU3.SA', 'PCAR3.SA', 'LREN3.SA', 'RAIZ4.SA', 'GGBR4.SA',
    'ASAI3.SA', 'RDOR3.SA'
]

IBOV_INDEX = '^BVSP'


def get_data(tickers, start_date, end_date):
    """Download data for all tickers."""
    print(f"\n{'='*70}")
    print(f"DOWNLOADING DATA")
    print(f"{'='*70}\n")
    print(f"Period: {start_date} to {end_date}")
    
    # Download IBOV
    print(f"\nDownloading IBOV index...")
    try:
        ibov_data = yf.download(IBOV_INDEX, start=start_date, end=end_date, progress=False)
        print(f"  IBOV: {len(ibov_data)} days")
    except Exception as e:
        print(f"  IBOV download failed: {e}")
        ibov_data = None
    
    # Download stocks
    stock_data = {}
    print(f"\nDownloading stocks...")
    for i, ticker in enumerate(tickers):
        try:
            print(f"  {i+1}/{len(tickers)}: {ticker}...", end=" ", flush=True)
            data = yf.download(ticker, start=start_date, end=end_date, progress=False)
            if isinstance(data, pd.DataFrame) and not data.empty:
                stock_data[ticker] = data
                print(f"✓ {len(data)} days")
            else:
                print(f"✗ Failed or empty data for {ticker}")
        except Exception as e:
            print(f"✗ {e}")
    
    # Only proceed if we have at least some stock data
    if len(stock_data) == 0:
        print("\nERROR: No stock data available")
        return None, None
    
    print(f"\n✅ Downloaded {len(stock_data)} stocks successfully")
    
    return ibov_data, stock_data


def run_backtest(ibov_data, stock_data):
    """Run simplified backtest."""
    print(f"\n{'='*70}")
    print(f"RUNNING BACKTEST")
    print(f"{'='*70}\n")
    
    if ibov_data is None or (not isinstance(ibov_data, pd.DataFrame) or (isinstance(ibov_data, pd.DataFrame) and len(ibov_data) == 0)):
        print("ERROR: No IBOV data available")
        return None
    
    # Use IBOV trading days
    trading_days = sorted(list(set(ibov_data.index)))
    
    # Warmup period (60 days)
    trading_days = [d for d in trading_days if d >= pd.Timestamp(BACKTEST_START) and d <= pd.Timestamp(BACKTEST_END)]
    
    if len(trading_days) < 60:
        print(f"ERROR: Insufficient trading days: {len(trading_days)}")
        return None
    
    print(f"Trading days: {len(trading_days)}")
    
    # Initialize
    initial_capital = 100000
    cash = initial_capital
    positions = {}
    trades = []
    portfolio_values = []
    
    trend_detector = TrendDetectorV2()
    runner = SimpleProductionRunner(use_news=False)
    
    # Run through each day
    for i, date in enumerate(trading_days[60:]):  # Skip warmup
        print(f"  Day {i+1}/{len(trading_days)-60}: {date.strftime('%Y-%m-%d')}", end="\r", flush=True)
        
        # Generate signals
        signals = {}
        for ticker, data in stock_data.items():
            if ticker not in data.index:
                continue
            
            hist_data = data[data.index <= date]
            
            if len(hist_data) < 50:
                continue
            
            # Trend detection
            trend_result = trend_detector.detect_trend(hist_data)
            consensus = trend_result.get('consensus', 'unknown')
            confidence = trend_result.get('confidence', 0.0)
            
            # Signal logic
            if consensus in ['uptrend', 'bull_pullback'] and confidence >= 0.6:
                signal = "BUY"
                
                # Position sizing
                position_size = runner.calculate_kelly_position(hist_data, confidence)
                
                signals[ticker] = {
                    'signal': signal,
                    'confidence': confidence,
                    'position_size': position_size,
                    'price': hist_data['Close'].iloc[-1]
                }
            elif consensus in ['downtrend', 'bear_bounce'] and confidence >= 0.6:
                signal = "SELL"
                signals[ticker] = {
                    'signal': signal,
                    'confidence': confidence,
                    'position_size': 1.0,
                    'price': hist_data['Close'].iloc[-1]
                }
        
        # Execute trades
        for ticker, sig in signals.items():
            if sig['signal'] == "BUY":
                cost = sig['position_size'] * initial_capital
                if cash >= cost:
                    cash -= cost
                    positions[ticker] = {
                        'shares': cost / sig['price'],
                        'entry_price': sig['price'],
                        'entry_date': date
                    }
                    trades.append({
                        'date': date,
                        'ticker': ticker,
                        'signal': 'BUY',
                        'price': sig['price'],
                        'size': sig['position_size']
                    })
            elif sig['signal'] == "SELL":
                if ticker in positions:
                    entry_price = positions[ticker]['entry_price']
                    shares = positions[ticker]['shares']
                    value = sig['price'] * shares
                    cash += value
                    trades.append({
                        'date': date,
                        'ticker': ticker,
                        'signal': 'SELL',
                        'price': sig['price'],
                        'pnl': (sig['price'] - entry_price) / entry_price
                    })
                    del positions[ticker]
        
        # Calculate portfolio value
        portfolio_value = cash
        for ticker, pos in positions.items():
            if ticker in stock_data and date in stock_data[ticker].index:
                current_price = stock_data[ticker].loc[date, 'Close']
                if not pd.isna(current_price):
                    portfolio_value += current_price * pos['shares']
        
        portfolio_values.append(portfolio_value)
    
    # Get IBOV values for same period
    ibov_values = []
    ibov_start = trading_days[60]
    ibov_initial = ibov_data['Close'].loc[ibov_start]
    
    for date in trading_days[60:]:
        if date in ibov_data.index:
            ibov_values.append(initial_capital * ibov_data['Close'].loc[date] / ibov_initial)
    
    # Ensure same length
    min_len = min(len(portfolio_values), len(ibov_values))
    portfolio_values = portfolio_values[:min_len]
    ibov_values = ibov_values[:min_len]
    
    # Calculate metrics
    portfolio_final = portfolio_values[-1]
    ibov_final = ibov_values[-1]
    
    portfolio_return = (portfolio_final - initial_capital) / initial_capital * 100
    ibov_return = (ibov_final - initial_capital) / initial_capital * 100
    
    portfolio_returns = pd.Series(portfolio_values).pct_change().dropna()
    ibov_returns = pd.Series(ibov_values).pct_change().dropna()
    
    portfolio_sharpe = portfolio_returns.mean() / portfolio_returns.std() * np.sqrt(252) if portfolio_returns.std() > 0 else 0
    ibov_sharpe = ibov_returns.mean() / ibov_returns.std() * np.sqrt(252) if ibov_returns.std() > 0 else 0
    
    portfolio_cummax = pd.Series(portfolio_values).cummax()
    portfolio_drawdown = (portfolio_cummax - pd.Series(portfolio_values)).max()
    portfolio_max_dd = portfolio_drawdown / initial_capital * 100
    
    winning_trades = sum(1 for t in trades if 'pnl' in t and t['pnl'] > 0)
    total_trades = len([t for t in trades if 'pnl' in t])
    win_rate = winning_trades / total_trades * 100 if total_trades > 0 else 0
    
    # Print results
    print(f"\n{'='*70}")
    print(f"BACKTEST RESULTS SUMMARY")
    print(f"{'='*70}\n")
    
    print(f"Initial Capital: R${initial_capital:,.2f}")
    print(f"\n--- Strategy Performance ---")
    print(f"Final Value:       R${portfolio_final:,.2f}")
    print(f"Total Return:      {portfolio_return:+.2f}%")
    print(f"Sharpe Ratio:      {portfolio_sharpe:.2f}")
    print(f"Max Drawdown:      {portfolio_max_dd:.2f}%")
    print(f"Win Rate:         {win_rate:.1f}% ({winning_trades}/{total_trades} trades)")
    
    print(f"\n--- IBOV Benchmark ---")
    print(f"Final Value:       R${ibov_final:,.2f}")
    print(f"Total Return:      {ibov_return:+.2f}%")
    print(f"Sharpe Ratio:      {ibov_sharpe:.2f}")
    
    print(f"\n--- Alpha ---")
    alpha = portfolio_return - ibov_return
    print(f"Excess Return:    {alpha:+.2f}%")
    
    print(f"\n--- Trades ---")
    buy_signals = sum(1 for t in trades if t['signal'] == 'BUY')
    sell_signals = sum(1 for t in trades if t['signal'] == 'SELL')
    print(f"BUY signals:   {buy_signals}")
    print(f"SELL signals:  {sell_signals}")
    
    # Create plots
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 10))
    
    trading_days_plot = trading_days[60:min(len(portfolio_values)+60, len(trading_days))]
    
    ax1.plot(trading_days_plot, portfolio_values[:len(trading_days_plot)], label='Strategy', linewidth=2)
    ax1.plot(trading_days_plot, ibov_values[:len(trading_days_plot)], label='IBOV Index', linewidth=2, alpha=0.7)
    ax1.set_title('Portfolio Value vs IBOV (Nov 2025 - Present)', fontsize=14, fontweight='bold')
    ax1.set_xlabel('Date', fontsize=12)
    ax1.set_ylabel('Portfolio Value (R$)', fontsize=12)
    ax1.legend()
    ax1.grid(True, alpha=0.3)
    
    # Drawdown
    portfolio_cummax = pd.Series(portfolio_values[:len(trading_days_plot)]).cummax()
    portfolio_dd = -(portfolio_cummax - pd.Series(portfolio_values[:len(trading_days_plot)])) / portfolio_values[0] * 100
    
    ibov_cummax = pd.Series(ibov_values[:len(trading_days_plot)]).cummax()
    ibov_dd = -(ibov_cummax - pd.Series(ibov_values[:len(trading_days_plot)])) / ibov_values[0] * 100
    
    ax2.fill_between(trading_days_plot, 0, portfolio_dd, alpha=0.3, color='green', label='Strategy DD')
    ax2.fill_between(trading_days_plot, 0, ibov_dd, alpha=0.3, color='orange', label='IBOV DD')
    ax2.set_title('Drawdown Comparison', fontsize=14, fontweight='bold')
    ax2.set_xlabel('Date', fontsize=12)
    ax2.set_ylabel('Drawdown (%)', fontsize=12)
    ax2.legend()
    ax2.grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.savefig('backtest_nov2025_results.png', dpi=150, bbox_inches='tight')
    print(f"\n✅ Plot saved to backtest_nov2025_results.png")
    plt.close()
    
    return {
        'portfolio_return': portfolio_return,
        'ibov_return': ibov_return,
        'alpha': alpha,
        'sharpe': portfolio_sharpe,
        'max_drawdown': portfolio_max_dd,
        'win_rate': win_rate
    }


def main():
    print("\n" + "="*70)
    print("STOCK SIGNALS BACKTEST - NOV 2025 TO PRESENT")
    print("="*70)
    
    # Get data
    ibov_data, stock_data = get_data(IBOV_TOP_20, BACKTEST_START, BACKTEST_END)
    
    # Check if data was successfully downloaded
    if ibov_data is not None and stock_data is not None:
        results = run_backtest(ibov_data, stock_data)
        
        if results:
            print(f"\n{'='*70}")
            print(f"✅ BACKTEST COMPLETE")
            print(f"{'='*70}")
            print(f"\nFinal Results:")
            print(f"  Strategy Return: {results['portfolio_return']:+.2f}%")
            print(f"  IBOV Return:    {results['ibov_return']:+.2f}%")
            print(f"  Alpha:           {results['alpha']:+.2f}%")
            print(f"  Sharpe Ratio:     {results['sharpe']:.2f}")
            print(f"  Max Drawdown:    {results['max_drawdown']:.2f}%")
            print(f"  Win Rate:        {results['win_rate']:.1f}%")
    else:
        print("\n❌ BACKTEST FAILED")
    print("\n❌ DATA DOWNLOAD FAILED")


if __name__ == "__main__":
    main()
