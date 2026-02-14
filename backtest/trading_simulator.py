"""
Trading simulator: test signal profitability on historical data.
Simulates buy/sell actions based on detected signals and tracks P&L.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json

from src.signals.information_flow import InformationFlowDetector
from src.signals.momentum_reversal import MomentumReversalDetector


class TradingSimulator:
    """Simulate trades based on signals and track P&L."""
    
    def __init__(self, initial_capital=10000, position_size=0.5):
        """
        Initialize simulator.
        
        Args:
            initial_capital: Starting cash
            position_size: Fraction of capital to use per trade (0.0-1.0)
        """
        self.initial_capital = initial_capital
        self.position_size = position_size
        self.info_detector = InformationFlowDetector()
        self.mom_detector = MomentumReversalDetector()
        
        # Tracking
        self.trades = []
        self.equity_curve = []
        self.signals_log = []
    
    def detect_signals(self, data):
        """Detect all signals in the data."""
        signals = []
        
        # Information flow
        info_sigs = self.info_detector.run_all(data)
        for sig_type, strength, explanation in info_sigs:
            signals.append({
                'type': sig_type,
                'strength': strength,
                'direction': None,
                'source': 'technical'
            })
        
        # Momentum/reversal
        mom_sigs = self.mom_detector.run_all(data)
        for sig_type, strength, direction, explanation in mom_sigs:
            signals.append({
                'type': sig_type,
                'strength': strength,
                'direction': direction,
                'source': 'technical'
            })
        
        return signals
    
    def calculate_signal_score(self, signals):
        """
        Calculate overall signal score (0-1.0).
        Higher = stronger signal, more confident direction.
        """
        if not signals:
            return 0, None
        
        # Average strength
        avg_strength = np.mean([s['strength'] for s in signals])
        
        # Check directional consensus
        directions = [s['direction'] for s in signals if s['direction']]
        if directions:
            bullish_count = sum(1 for d in directions if d == 'bullish')
            bearish_count = sum(1 for d in directions if d == 'bearish')
            
            if bullish_count > bearish_count:
                direction = 'bullish'
            elif bearish_count > bullish_count:
                direction = 'bearish'
            else:
                direction = None
        else:
            direction = None
        
        return avg_strength, direction
    
    def simulate_ticker(self, ticker, start_date, end_date, threshold=0.5):
        """
        Simulate trading on a single ticker.
        
        Returns: dict with performance metrics
        """
        print(f"\nSimulating {ticker}...")
        
        try:
            data = yf.download(ticker, start=start_date, end=end_date, progress=False)
        except:
            print(f"  Failed to fetch {ticker}")
            return None
        
        if len(data) < 40:
            print(f"  Insufficient data")
            return None
        
        # Trading variables
        cash = self.initial_capital
        shares = 0
        entry_price = None
        entry_date = None
        max_drawdown = 0
        peak_equity = self.initial_capital
        
        trades = []
        equity_log = []
        
        # Slide window through data
        window_size = 20
        close_prices = data['Close'].values
        for i in range(window_size, len(data)):
            date = data.index[i]
            current_price = float(np.asarray(close_prices[i]).item())
            
            # Calculate current equity
            current_equity = float(cash) + float(shares * current_price)
            equity_log.append({'date': date, 'equity': current_equity})
            
            # Track peak and drawdown
            if float(current_equity) > float(peak_equity):
                peak_equity = float(current_equity)
            drawdown = (peak_equity - current_equity) / peak_equity
            max_drawdown = max(max_drawdown, drawdown)
            
            # Get window for signal detection
            window = data.iloc[i-window_size:i].copy()
            
            # Detect signals
            signals = self.detect_signals(window)
            signal_score, signal_direction = self.calculate_signal_score(signals)
            
            if signals:
                self.signals_log.append({
                    'ticker': ticker,
                    'date': date,
                    'score': signal_score,
                    'direction': signal_direction,
                    'signals': len(signals)
                })
            
            # Trading logic
            if signal_score > threshold:
                if signal_direction == 'bullish' and shares == 0:
                    # Buy signal
                    position_value = cash * self.position_size
                    shares = position_value / current_price
                    cash -= position_value
                    entry_price = current_price
                    entry_date = date
                
                elif signal_direction == 'bearish' and shares > 0:
                    # Sell signal
                    proceeds = shares * current_price
                    cash += proceeds
                    
                    pnl = proceeds - (shares * entry_price)
                    pnl_pct = pnl / (shares * entry_price) * 100
                    
                    trades.append({
                        'ticker': ticker,
                        'entry_date': entry_date,
                        'exit_date': date,
                        'entry_price': entry_price,
                        'exit_price': current_price,
                        'shares': shares,
                        'pnl': pnl,
                        'pnl_pct': pnl_pct,
                        'hold_days': (date - entry_date).days
                    })
                    
                    shares = 0
                    entry_price = None
                    entry_date = None
        
        # Close any open positions at end
        if shares > 0:
            final_price = float(np.asarray(close_prices[-1]).item())
            proceeds = shares * final_price
            cash += proceeds
            
            pnl = proceeds - (shares * entry_price)
            pnl_pct = pnl / (shares * entry_price) * 100
            
            trades.append({
                'ticker': ticker,
                'entry_date': entry_date,
                'exit_date': data.index[-1],
                'entry_price': entry_price,
                'exit_price': final_price,
                'shares': shares,
                'pnl': pnl,
                'pnl_pct': pnl_pct,
                'hold_days': (data.index[-1] - entry_date).days
            })
        
        # Calculate metrics
        final_equity = float(cash) + float(shares * float(np.asarray(close_prices[-1]).item()))
        total_return = (final_equity - self.initial_capital) / self.initial_capital * 100
        
        if trades:
            winning_trades = sum(1 for t in trades if t['pnl'] > 0)
            losing_trades = sum(1 for t in trades if t['pnl'] < 0)
            win_rate = winning_trades / len(trades) * 100 if trades else 0
            avg_win = np.mean([t['pnl'] for t in trades if t['pnl'] > 0]) if winning_trades > 0 else 0
            avg_loss = np.mean([t['pnl'] for t in trades if t['pnl'] < 0]) if losing_trades > 0 else 0
        else:
            win_rate = 0
            avg_win = 0
            avg_loss = 0
            winning_trades = 0
            losing_trades = 0
        
        result = {
            'ticker': ticker,
            'initial_capital': self.initial_capital,
            'final_equity': final_equity,
            'total_return_pct': total_return,
            'max_drawdown_pct': max_drawdown * 100,
            'num_trades': len(trades),
            'win_rate_pct': win_rate,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'winning_trades': winning_trades,
            'losing_trades': losing_trades,
            'trades': trades,
            'equity_log': equity_log
        }
        
        print(f"  Return: {total_return:+.1f}% | Trades: {len(trades)} | Win rate: {win_rate:.0f}%")
        
        return result
    
    def run_backtest(self, tickers, start_date, end_date, threshold=0.5):
        """Run backtest on multiple tickers."""
        print(f"\n{'='*70}")
        print(f"BACKTEST: {start_date.date()} to {end_date.date()}")
        print(f"Initial capital: ${self.initial_capital:,.0f}")
        print(f"Position size: {self.position_size*100:.0f}% per trade")
        print(f"Signal threshold: {threshold:.2f}")
        print(f"{'='*70}")
        
        results = []
        
        for i, ticker in enumerate(tickers):
            result = self.simulate_ticker(ticker, start_date, end_date, threshold=threshold)
            if result:
                results.append(result)
        
        return results
    
    def generate_report(self, results):
        """Generate backtest report."""
        if not results:
            print("\nNo results to report")
            return
        
        print(f"\n{'='*70}")
        print("BACKTEST RESULTS SUMMARY")
        print(f"{'='*70}\n")
        
        # Individual results
        print("INDIVIDUAL STOCKS:")
        print(f"{'Ticker':<10} {'Return':<12} {'Trades':<10} {'Win Rate':<12} {'Max DD':<10}")
        print("-" * 54)
        
        all_returns = []
        all_trades = []
        
        for result in results:
            print(f"{result['ticker']:<10} {result['total_return_pct']:>+10.1f}% {result['num_trades']:>8} "
                  f"{result['win_rate_pct']:>10.0f}% {result['max_drawdown_pct']:>8.1f}%")
            
            all_returns.append(result['total_return_pct'])
            all_trades.extend(result['trades'])
        
        # Portfolio statistics
        print(f"\n{'='*70}")
        print("PORTFOLIO STATISTICS:")
        print(f"{'='*70}")
        
        avg_return = np.mean(all_returns)
        median_return = np.median(all_returns)
        total_trades = len(all_trades)
        
        if all_trades:
            total_pnl = sum(t['pnl'] for t in all_trades)
            win_count = sum(1 for t in all_trades if t['pnl'] > 0)
            loss_count = sum(1 for t in all_trades if t['pnl'] < 0)
            overall_win_rate = win_count / total_trades * 100
            
            print(f"Average return (stocks): {avg_return:+.1f}%")
            print(f"Median return (stocks): {median_return:+.1f}%")
            print(f"Total trades: {total_trades}")
            print(f"Winning trades: {win_count} ({overall_win_rate:.0f}%)")
            print(f"Losing trades: {loss_count}")
            print(f"Total P&L: ${total_pnl:+,.0f}")
            print(f"Avg P&L per trade: ${total_pnl/total_trades:+,.0f}")
        
        return results


if __name__ == '__main__':
    # Test on a few tickers
    tickers = ['AAPL', 'MSFT', 'NVDA']
    
    end_date = datetime.now()
    start_date = end_date - timedelta(days=180)  # 6 months
    
    simulator = TradingSimulator(initial_capital=10000, position_size=0.5)
    results = simulator.run_backtest(tickers, start_date, end_date, threshold=0.5)
    simulator.generate_report(results)
