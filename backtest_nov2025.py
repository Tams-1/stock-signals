#!/usr/bin/env python3
"""
Backtest script for Nov 2025 to present.

Compares strategy performance vs IBOV benchmark.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
from pathlib import Path

from production_simple import SimpleProductionRunner
from src.signals.trend_detector_v2 import TrendDetectorV2


# Test universe - subset of IBOV stocks for speed
IBOV_TOP_20 = [
    'PETR4.SA', 'VALE3.SA', 'ITUB4.SA', 'BBDC4.SA', 'BBAS3.SA',
    'ABEV3.SA', 'B3SA3.SA', 'SUZB3.SA', 'RENT3.SA', 'WEGE3.SA',
    'MGLU3.SA', 'PCAR3.SA', 'LREN3.SA', 'RAIZ4.SA', 'GGBR4.SA',
    'ASAI3.SA', 'RDOR3.SA', 'PETR3.SA', 'ITSA4.SA'
]

# IBOV Index ticker
IBOV_INDEX = '^BVSP'

# Backtest period
BACKTEST_START = '2024-11-01'  # Using 2024 for now, since 2025 data won't exist
BACKTEST_END = datetime.now().strftime('%Y-%m-%d')


class BacktestEngine:
    """Backtest engine for stock signals strategy."""
    
    def __init__(self, initial_capital=100000):
        self.initial_capital = initial_capital
        self.cash = initial_capital
        self.positions = {}
        self.trades = []
        self.trend_detector = TrendDetectorV2()
        self.news_client = None
        
    def get_market_data(self, start_date, end_date):
        """Download historical data for all stocks."""
        print(f"\nDownloading data from {start_date} to {end_date}...")
        
        # Download IBOV index
        print(f"  Downloading {IBOV_INDEX}...")
        ibov_data = yf.download(IBOV_INDEX, start=start_date, end=end_date, progress=False)
        
        # Download stock data
        stock_data = {}
        for i, ticker in enumerate(IBOV_TOP_20):
            print(f"  Downloading {ticker} ({i+1}/{len(IBOV_TOP_20)})...")
            data = yf.download(ticker, start=start_date, end=end_date, progress=False)
            if not data.empty:
                stock_data[ticker] = data
        
        print(f"  Downloaded {len(stock_data)} stocks")
        
        return ibov_data, stock_data
    
    def generate_signals(self, stock_data, ibov_data, date):
        """Generate signals for all stocks on a given date."""
        signals = {}
        
        for ticker, data in stock_data.items():
            # Get data up to this date
            hist_data = data[data.index <= date]
            
            if len(hist_data) < 50:
                continue
            
            # Trend detection
            trend_result = self.trend_detector.detect_trend(hist_data)
            consensus = trend_result.get('consensus', 'unknown')
            confidence = trend_result.get('confidence', 0.0)
            
            # Simple signal logic (no news for backtest speed)
            signal = "HOLD"
            if consensus in ['uptrend', 'bull_pullback'] and confidence >= 0.6:
                signal = "BUY"
            elif consensus in ['downtrend', 'bear_bounce'] and confidence >= 0.6:
                signal = "SELL"
            
            if signal != "HOLD":
                # Kelly position sizing
                runner = SimpleProductionRunner(use_news=False)
                position_size = runner.calculate_kelly_position(hist_data, confidence)
                
                signals[ticker] = {
                    'signal': signal,
                    'confidence': confidence,
                    'position_size': position_size,
                    'price': hist_data['Close'].iloc[-1]
                }
        
        return signals
    
    def run_backtest(self, start_date, end_date):
        """Run full backtest."""
        print(f"\n{'='*70}")
        print(f"BACKTEST: {start_date} to {end_date}")
        print(f"{'='*70}\n")
        
        # Get data
        ibov_data, stock_data = self.get_market_data(start_date, end_date)
        
        if ibov_data.empty:
            print("ERROR: No IBOV data available")
            return None
        
        # Find common trading days
        trading_days = sorted(list(set(
            [d for data in stock_data.values() for d in data.index] +
            [d for d in ibov_data.index]
        )))[60:-1]  # Skip first 60 days for warmup
        
        print(f"Found {len(trading_days)} trading days for backtest\n")
        
        # Track portfolio value
        portfolio_values = [self.initial_capital]
        ibov_values = [self.initial_capital]
        signals_count = {'BUY': 0, 'SELL': 0, 'HOLD': 0}
        
        for i, date in enumerate(trading_days):
            # Generate signals
            signals = self.generate_signals(stock_data, ibov_data, date)
            
            # Execute trades
            for ticker, sig in signals.items():
                if sig['signal'] == "BUY":
                    # Buy
                    cost = sig['price'] * sig['position_size'] * self.initial_capital
                    if self.cash >= cost:
                        self.cash -= cost
                        self.positions[ticker] = {
                            'shares': sig['position_size'] * self.initial_capital / sig['price'],
                            'entry_price': sig['price'],
                            'entry_date': date
                        }
                        self.trades.append({
                            'date': date,
                            'ticker': ticker,
                            'signal': 'BUY',
                            'price': sig['price'],
                            'size': sig['position_size']
                        })
                elif sig['signal'] == "SELL":
                    # Sell
                    if ticker in self.positions:
                        entry_price = self.positions[ticker]['entry_price']
                        value = sig['price'] * self.positions[ticker]['shares']
                        self.cash += value
                        del self.positions[ticker]
                        self.trades.append({
                            'date': date,
                            'ticker': ticker,
                            'signal': 'SELL',
                            'price': sig['price'],
                            'pnl': (sig['price'] - entry_price) / entry_price
                        })
                
                signals_count[sig['signal']] += 1
            
            # Calculate portfolio value
            portfolio_value = self.cash
            for ticker, pos in self.positions.items():
                # Get latest price
                if ticker in stock_data:
                    price_data = stock_data[ticker][stock_data[ticker].index <= date]
                    if not price_data.empty:
                        current_price = price_data['Close'].iloc[-1]
                        portfolio_value += current_price * pos['shares']
            
            portfolio_values.append(portfolio_value)
            
            # Calculate IBOV value
            if date in ibov_data.index:
                ibov_return = ibov_data['Close'].loc[date] / ibov_data['Close'].iloc[0]
                ibov_values.append(self.initial_capital * ibov_return)
        
        # Print summary
        self.print_summary(portfolio_values, ibov_values, signals_count)
        
        # Plot results
        self.plot_results(portfolio_values, ibov_values, trading_days)
        
        return {
            'portfolio_values': portfolio_values,
            'ibov_values': ibov_values,
            'trades': self.trades,
            'signals_count': signals_count
        }
    
    def print_summary(self, portfolio_values, ibov_values, signals_count):
        """Print backtest summary."""
        portfolio_final = portfolio_values[-1]
        ibov_final = ibov_values[-1]
        
        portfolio_return = (portfolio_final - self.initial_capital) / self.initial_capital * 100
        ibov_return = (ibov_final - self.initial_capital) / self.initial_capital * 100
        
        # Calculate Sharpe ratio (simplified)
        portfolio_returns = pd.Series(portfolio_values).pct_change().dropna()
        ibov_returns = pd.Series(ibov_values).pct_change().dropna()
        
        portfolio_sharpe = portfolio_returns.mean() / portfolio_returns.std() * np.sqrt(252) if portfolio_returns.std() > 0 else 0
        ibov_sharpe = ibov_returns.mean() / ibov_returns.std() * np.sqrt(252) if ibov_returns.std() > 0 else 0
        
        # Max drawdown
        portfolio_cummax = pd.Series(portfolio_values).cummax()
        portfolio_drawdown = (portfolio_cummax - pd.Series(portfolio_values)).max()
        portfolio_max_dd = portfolio_drawdown / self.initial_capital * 100
        
        ibov_cummax = pd.Series(ibov_values).cummax()
        ibov_drawdown = (ibov_cummax - pd.Series(ibov_values)).max()
        ibov_max_dd = ibov_drawdown / self.initial_capital * 100
        
        # Win rate (count winning trades)
        winning_trades = sum(1 for t in self.trades if t.get('pnl', 0) > 0)
        total_trades = len([t for t in self.trades if 'pnl' in t])
        win_rate = winning_trades / total_trades * 100 if total_trades > 0 else 0
        
        print(f"\n{'='*70}")
        print(f"BACKTEST RESULTS")
        print(f"{'='*70}\n")
        
        print(f"Initial Capital: R${self.initial_capital:,.2f}")
        print(f"\n--- Portfolio Performance ---")
        print(f"Final Value:       R${portfolio_final:,.2f}")
        print(f"Total Return:      {portfolio_return:+.2f}%")
        print(f"Sharpe Ratio:      {portfolio_sharpe:.2f}")
        print(f"Max Drawdown:      {portfolio_max_dd:.2f}%")
        print(f"Win Rate:         {win_rate:.1f}% ({winning_trades}/{total_trades} trades)")
        
        print(f"\n--- IBOV Benchmark ---")
        print(f"Final Value:       R${ibov_final:,.2f}")
        print(f"Total Return:      {ibov_return:+.2f}%")
        print(f"Sharpe Ratio:      {ibov_sharpe:.2f}")
        print(f"Max Drawdown:      {ibov_max_dd:.2f}%")
        
        print(f"\n--- Alpha ---")
        alpha = portfolio_return - ibov_return
        print(f"Excess Return:    {alpha:+.2f}%")
        print(f"Alpha:            {alpha / 100:.3f}")
        
        print(f"\n--- Signals ---")
        for signal, count in signals_count.items():
            print(f"{signal:8s}: {count}")
        print(f"Total:          {sum(signals_count.values())}")
        print(f"{'='*70}\n")
    
    def plot_results(self, portfolio_values, ibov_values, trading_days):
        """Plot backtest results."""
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 10))
        
        # Plot 1: Portfolio value
        ax1.plot(trading_days, portfolio_values, label='Strategy', linewidth=2)
        ax1.plot(trading_days, ibov_values, label='IBOV Index', linewidth=2, alpha=0.7)
        ax1.set_title('Portfolio Value vs IBOV', fontsize=14, fontweight='bold')
        ax1.set_xlabel('Date', fontsize=12)
        ax1.set_ylabel('Portfolio Value (R$)', fontsize=12)
        ax1.legend()
        ax1.grid(True, alpha=0.3)
        
        # Plot 2: Drawdown
        portfolio_cummax = pd.Series(portfolio_values).cummax()
        portfolio_drawdown = -(portfolio_cummax - pd.Series(portfolio_values)) / pd.Series(portfolio_values)[0] * 100
        
        ibov_cummax = pd.Series(ibov_values).cummax()
        ibov_drawdown = -(ibov_cummax - pd.Series(ibov_values)) / pd.Series(ibov_values)[0] * 100
        
        ax2.fill_between(trading_days, 0, portfolio_drawdown, alpha=0.3, color='green', label='Strategy DD')
        ax2.fill_between(trading_days, 0, ibov_drawdown, alpha=0.3, color='orange', label='IBOV DD')
        ax2.set_title('Drawdown Comparison', fontsize=14, fontweight='bold')
        ax2.set_xlabel('Date', fontsize=12)
        ax2.set_ylabel('Drawdown (%)', fontsize=12)
        ax2.legend()
        ax2.grid(True, alpha=0.3)
        
        plt.tight_layout()
        
        # Save plot
        output_file = "backtest_results_nov2025.png"
        plt.savefig(output_file, dpi=150)
        print(f"Plot saved to {output_file}")
        
        plt.close()


def main():
    """Run backtest."""
    print("\n" + "="*70)
    print("STOCK SIGNALS BACKTEST ENGINE")
    print("="*70)
    
    engine = BacktestEngine(initial_capital=100000)
    
    # Run backtest
    results = engine.run_backtest(BACKTEST_START, BACKTEST_END)
    
    if results:
        print("\n✅ Backtest complete!")
        print(f"📊 Plots saved to backtest_results_nov2025.png")
    else:
        print("\n❌ Backtest failed")


if __name__ == "__main__":
    main()
