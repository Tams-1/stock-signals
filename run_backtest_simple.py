#!/usr/bin/env python3
"""
Simplified robust backtest for production-hardening validation.

Tests the production system with real data.
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


# Test universe
TEST_TICKERS = ['VALE3.SA', 'PETR4.SA', 'ITUB4.SA', 'BBDC4.SA']
IBOV_INDEX = '^BVSP'

# Period (using available historical data)
START_DATE = '2024-11-01'
END_DATE = '2025-02-28'


def download_data():
    """Download data for backtest."""
    print(f"\n{'='*70}")
    print(f"DOWNLOADING DATA")
    print(f"{'='*70}\n")
    
    # Download IBOV
    print("Downloading IBOV index...")
    try:
        ibov_data = yf.download(IBOV_INDEX, start=START_DATE, end=END_DATE, progress=False)
        if ibov_data.empty:
            print("ERROR: IBOV data is empty")
            return None, None
        print(f"  IBOV: {len(ibov_data)} days")
    except Exception as e:
        print(f"  IBOV download failed: {e}")
        return None, None
    
    # Download stocks
    stock_data = {}
    print(f"\nDownloading stocks...")
    for ticker in TEST_TICKERS:
        try:
            print(f"  {ticker}...", end=" ")
            data = yf.download(ticker, start=START_DATE, end=END_DATE, progress=False)
            if isinstance(data, pd.DataFrame) and not data.empty and len(data) >= 50:
                stock_data[ticker] = data
                print(f"✓ {len(data)} days")
            else:
                print(f"✗ (insufficient)")
        except Exception as e:
            print(f"✗ {e}")
    
    print(f"\nDownloaded {len(stock_data)} stocks successfully")
    return ibov_data, stock_data


def run_simple_backtest(ibov_data, stock_data):
    """Run simplified backtest."""
    print(f"\n{'='*70}")
    print(f"RUNNING BACKTEST")
    print(f"{'='*70}\n")
    
    if ibov_data is None or ibov_data.empty:
        print("ERROR: No IBOV data")
        return None
    
    if not stock_data:
        print("ERROR: No stock data")
        return None
    
    # Get common trading days
    trading_days = sorted(list(set(ibov_data.index)))
    trading_days = [d for d in trading_days if d >= pd.Timestamp(START_DATE)]
    
    if len(trading_days) < 60:
        print(f"ERROR: Only {len(trading_days)} trading days available")
        return None
    
    # Warmup period: skip first 60 days
    warmup_days = 60
    trading_days = trading_days[warmup_days:]
    
    print(f"Trading days: {len(trading_days)}")
    print(f"Warmup period: {warmup_days} days")
    print(f"Backtest period: {len(trading_days) - warmup_days} days")
    
    # Initialize
    initial_capital = 100000
    cash = initial_capital
    positions = {}
    trades = []
    
    portfolio_values = []
    ibov_values = []
    
    trend_detector = TrendDetectorV2()
    runner = SimpleProductionRunner(use_news=False)
    
    # Track signals
    buy_signals = 0
    sell_signals = 0
    hold_signals = 0
    
    for i, date in enumerate(trading_days):
        if (i + 1) % 10 == 0:
            print(f"  Processing {date.strftime('%Y-%m-%d')} ({i+1}/{len(trading_days) days)...", end=" \r", flush=True)
        
        # Generate signals
        for ticker, data in stock_data.items():
            if date not in data.index:
                continue
            
            # Get history up to this date
            hist_data = data[data.index <= date]
            
            if len(hist_data) < 50:
                continue
            
            # Trend detection
            trend_result = trend_detector.detect_trend(hist_data)
            consensus = trend_result.get('consensus', 'unknown')
            confidence = trend_result.get('confidence', 0.0)
            
            # Signal logic
            if consensus in ['uptrend', 'bull_pullback'] and confidence >= 0.7:
                signal = "BUY"
                buy_signals += 1
                # Position sizing
                position_size = runner.calculate_kelly_position(hist_data, confidence)
                
                # Execute BUY
                cost = position_size * initial_capital
                if cash >= cost:
                    cash -= cost
                    positions[ticker] = {
                        'shares': cost / hist_data['Close'].iloc[-1],
                        'entry_price': hist_data['Close'].iloc[-1],
                        'entry_date': date
                    }
                    trades.append({
                        'date': date,
                        'ticker': ticker,
                        'signal': 'BUY',
                        'price': hist_data['close'].iloc[-1],
                        'position_size': position_size
                    })
            
            elif consensus in ['downtrend', 'bear_bounce'] and confidence >= 0.7:
                signal = "SELL"
                sell_signals += 1
                
                # Execute SELL
                if ticker in positions:
                    entry_price = positions[ticker]['entry_price']
                    shares = positions[ticker]['shares']
                    current_price = hist_data['Close'].iloc[-1]
                    
                    value = current_price * shares
                    cash += value
                    
                    trades.append({
                        'date': date,
                        'ticker': ticker,
                        'signal': 'SELL',
                        'price': current_price,
                        'entry_price': entry_price,
                        'pnl': (current_price - entry_price) / entry_price
                    })
                    del positions[ticker]
            else:
                hold_signals += 1
        
        # Calculate portfolio value
        portfolio_value = cash
        for ticker, pos in positions.items():
            if ticker in stock_data and date in stock_data[ticker].index:
                current_price = stock_data[ticker].at[date, 'Close']
                if not pd.isna(current_price):
                    portfolio_value += current_price * pos['shares']
        
        portfolio_values.append(portfolio_value)
        
        # Calculate IBOV value
        if date in ibov_data.index:
            ibov_initial = ibov_data['Close'].iloc[warmup_days]
            ibov_current = ibov_data['Close'].at[date]
            ibov_values.append(initial_capital * ibov_current / ibov_initial)
    
    # Final value
    portfolio_final = portfolio_values[-1]
    ibov_final = ibov_values[-1]
    
    # Calculate metrics
    portfolio_return = (portfolio_final - initial_capital) / initial_capital * 100
    ibov_return = (ibov_final - initial_capital) / initial_capital * 100
    alpha = portfolio_return - ibov_return
    
    # Calculate Sharpe
    portfolio_returns = pd.Series(portfolio_values).pct_change().dropna()
    if len(portfolio_returns) > 1 and portfolio_returns.std() > 0:
        portfolio_sharpe = portfolio_returns.mean() / portfolio_returns.std() * np.sqrt(252)
    else:
        portfolio_sharpe = 0
    
    # Drawdown
    portfolio_cummax = pd.Series(portfolio_values).cummax()
    portfolio_drawdown = (portfolio_cummax - pd.Series(portfolio_values)).max()
    max_dd_pct = portfolio_drawdown / portfolio_values[0] * 100
    
    # Win rate
    winning_trades = sum(1 for t in trades if t.get('pnl', 0) > 0)
    total_trades = len([t for t in trades if 'pnl' in t])
    win_rate = winning_trades / total_trades * 100 if total_trades > 0 else 0
    
    # Print results
    print(f"\n{'='*70}")
    print(f"BACKTEST RESULTS SUMMARY")
    print(f"{'='*70}\n")
    
    print(f"Initial Capital:  R${initial_capital:,.2f}")
    
    print(f"\n--- Strategy Performance ---")
    print(f"Final Value:       R${portfolio_final:,.2f}")
    print(f"Total Return:      {portfolio_return:+.2f}%")
    print(f"Sharpe Ratio:      {portfolio_sharpe:.2f}")
    print(f"Max Drawdown:      {max_dd_pct:.2f}%")
    print(f"Win Rate:         {win_rate:.1f}% ({winning_trades}/{total_trades})")
    print(f"Total Trades:      {total_trades}")
    
    print(f"\n--- IBOV Benchmark ---")
    print(f"Final Value:       R${ibov_final:,.2f}")
    print(f"Total Return:      {ibov_return:+.2f}%")
    
    print(f"\n--- Signals ---")
    print(f"BUY:   {buy_signals}")
    print(f"SELL:  {sell_signals}")
    print(f"HOLD:  {hold_signals}")
    
    print(f"\n--- Alpha ---")
    print(f"Excess Return:    {alpha:+.2f}%")
    print(f"Alpha:           {alpha/100:.3f}")
    
    # Plot results
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 10))
    
    # Portfolio value chart
    dates_range = trading_days[warmup_days:]
    portfolio_plot_values = portfolio_values[:len(dates_range)]
    ibov_plot_values = ibov_values[:len(dates_range)]
    
    ax1.plot(dates_range, portfolio_plot_values, label='Strategy', linewidth=2)
    ax1.plot(dates_range, ibov_plot_values, label='IBOV Index', linewidth=2, alpha=0.7)
    ax1.set_title('Portfolio Value vs IBOV (Production-Hardening Validation)', fontsize=14, font_weight='bold')
    ax1.set_xlabel('Date', fontsize=12)
    ax1.set_ylabel('Portfolio Value (R$)', fontsize=12)
    ax1.legend()
    ax1.grid(True, alpha=0.3)
    
    # Drawdown chart
    portfolio_cummax = pd.Series(portfolio_plot_values).cummax()
    portfolio_dd = -(portfolio_cummax - pd.Series(portfolio_plot_values)) / portfolio_plot_values[0] * 100
    
    ibov_cummax = pd.Series(ibov_plot_values). cummax()
    ibov_dd = -(ibov_cummax - pd.Series(ibov_plot_values)) / ibov_plot_values[0] * 100
    
    ax2.fill_between(dates_range, 0, portfolio_dd, alpha=0.3, color='green', label='Strategy DD')
    ax2.fill_between(dates_range, 0, ibov_dd, alpha=0.3, color='orange', label='IBOV DD')
    ax2.set_title('Drawdown Comparison', fontsize=14, fontweight='bold')
    ax2.set_xlabel('Date', fontsize=12)
    ax2.set_ylabel('Drawdown (%)', fontsize=12)
    ax2.legend()
    ax2.grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.savefig('backtest_production_hardening_results.png', dpi=150, bbox_inches='tight')
    print(f"\n✅ Plot saved to backtest_production_hardening_results.png")
    plt.close()
    
    return {
        'portfolio_return': portfolio_return,
        'ibov_return': ibov_return,
        'alpha': alpha,
        'sharpe': portfolio_sharpe,
        'max_drawdown': max_dd_pct,
        'win_rate': win_rate,
        'total_trades': total_trades,
        'buy_signals': buy_signals,
        'sell_signals': sell_signals,
        'hold_signals': hold_signals
    }


def main():
    print("="*70)
    print("STOCK SIGNALS PRODUCTION HARDENING BACKTEST")
    print("="*70)
    
    # Download data
    ibov_data, stock_data = download_data()
    
    if ibov_data is not None and stock_data is not None:
        results = run_simple_backtest(ibov_data, stock_data)
        
        if results:
            print(f"\n{'='*70}")
            print("✅ BACKTEST COMPLETE")
            print(f"{'='*70}")
    else:
        print("\n❌ BACKTEST FAILED")


if __name__ == "__main__":
    main()
