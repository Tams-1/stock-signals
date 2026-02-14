"""
Multi-market backtest: Run trading simulation on any market (US, BR, etc).
Supports flag-based market selection and generates reports + plots.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from src.data.market_config import get_tickers, get_market_name, get_market_config
from src.signals.information_flow import InformationFlowDetector
from src.signals.momentum_reversal import MomentumReversalDetector
from src.data.fetch_data import fetch_ticker_data


class MultiMarketBacktester:
    """Backtest on any market."""
    
    def __init__(self, market='us', initial_capital=10000, position_size=0.5):
        self.market = market
        self.initial_capital = initial_capital
        self.position_size = position_size
        self.market_name = get_market_name(market)
        self.market_config = get_market_config(market)
        self.info_detector = InformationFlowDetector()
        self.mom_detector = MomentumReversalDetector()
    
    def detect_signals(self, data):
        """Detect all signals in the data."""
        signals = []
        
        try:
            info_sigs = self.info_detector.run_all(data)
            for sig_type, strength, explanation in info_sigs:
                signals.append({'type': sig_type, 'strength': strength, 'direction': None})
        except:
            pass
        
        try:
            mom_sigs = self.mom_detector.run_all(data)
            for sig_type, strength, direction, explanation in mom_sigs:
                signals.append({'type': sig_type, 'strength': strength, 'direction': direction})
        except:
            pass
        
        return signals
    
    def calculate_signal_score(self, signals):
        """Calculate overall signal score."""
        if not signals:
            return 0, None
        
        avg_strength = np.mean([s['strength'] for s in signals])
        directions = [s['direction'] for s in signals if s['direction']]
        
        if directions:
            bullish = sum(1 for d in directions if d == 'bullish')
            bearish = sum(1 for d in directions if d == 'bearish')
            direction = 'bullish' if bullish > bearish else ('bearish' if bearish > bullish else None)
        else:
            direction = None
        
        return avg_strength, direction
    
    def simulate_ticker(self, ticker, start_date, end_date, threshold=0.5):
        """Simulate trading on a single ticker."""
        print(f"Simulating {ticker}...", end=" ", flush=True)
        
        try:
            data = fetch_ticker_data(ticker, start=start_date, end=end_date, progress=False)
        except:
            print("Failed to fetch data")
            return None
        
        if len(data) < 40:
            print("Insufficient data")
            return None
        
        # Convert to standard arrays for easier access
        closes = np.array(data['Close'].values).flatten().astype(float)
        dates = data.index.tolist()
        
        # Trading variables
        cash = float(self.initial_capital)
        shares = 0.0
        entry_price = None
        entry_date = None
        max_drawdown = 0.0
        peak_equity = float(self.initial_capital)
        
        trades = []
        equity_log = []
        
        # Slide window
        window_size = 20
        for i in range(window_size, len(data)):
            date = dates[i]
            current_price = float(closes[i])
            
            # Current equity
            current_equity = cash + (shares * current_price)
            equity_log.append({'date': date, 'equity': current_equity})
            
            # Track drawdown
            if current_equity > peak_equity:
                peak_equity = current_equity
            if peak_equity > 0:
                drawdown = (peak_equity - current_equity) / peak_equity
                max_drawdown = max(max_drawdown, drawdown)
            
            # Get window
            window = data.iloc[max(0, i-window_size):i].copy()
            if len(window) < window_size:
                continue
            
            # Detect signals
            signals = self.detect_signals(window)
            signal_score, signal_direction = self.calculate_signal_score(signals)
            
            # Trading logic
            if signal_score > threshold:
                if signal_direction == 'bullish' and shares == 0:
                    # Buy
                    position_value = cash * self.position_size
                    shares = position_value / current_price
                    cash -= position_value
                    entry_price = current_price
                    entry_date = date
                
                elif signal_direction == 'bearish' and shares > 0:
                    # Sell
                    proceeds = shares * current_price
                    cash += proceeds
                    
                    pnl = proceeds - (shares * entry_price)
                    pnl_pct = (pnl / (shares * entry_price) * 100) if entry_price else 0
                    
                    trades.append({
                        'entry_date': entry_date,
                        'exit_date': date,
                        'entry_price': entry_price,
                        'exit_price': current_price,
                        'shares': shares,
                        'pnl': pnl,
                        'pnl_pct': pnl_pct,
                        'hold_days': (date - entry_date).days
                    })
                    
                    shares = 0.0
                    entry_price = None
                    entry_date = None
        
        # Close open positions
        if shares > 0:
            final_price = float(closes[-1])
            proceeds = shares * final_price
            cash += proceeds
            
            pnl = proceeds - (shares * entry_price)
            pnl_pct = (pnl / (shares * entry_price) * 100) if entry_price else 0
            
            trades.append({
                'entry_date': entry_date,
                'exit_date': dates[-1],
                'entry_price': entry_price,
                'exit_price': final_price,
                'shares': shares,
                'pnl': pnl,
                'pnl_pct': pnl_pct,
                'hold_days': (dates[-1] - entry_date).days
            })
        
        # Final equity
        final_equity = cash + (shares * float(closes[-1]))
        total_return = (final_equity - self.initial_capital) / self.initial_capital * 100
        
        # Stats
        if trades:
            winning = sum(1 for t in trades if t['pnl'] > 0)
            losing = sum(1 for t in trades if t['pnl'] < 0)
            win_rate = winning / len(trades) * 100 if trades else 0
            avg_win = np.mean([t['pnl'] for t in trades if t['pnl'] > 0]) if winning > 0 else 0
            avg_loss = np.mean([t['pnl'] for t in trades if t['pnl'] < 0]) if losing > 0 else 0
        else:
            win_rate = 0
            avg_win = 0
            avg_loss = 0
            winning = 0
            losing = 0
        
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
            'winning_trades': winning,
            'losing_trades': losing,
            'trades': trades,
            'equity_log': equity_log
        }
        
        print(f"Return: {total_return:+.1f}% | Trades: {len(trades)} | Win: {win_rate:.0f}%")
        
        return result
    
    def run_backtest(self, tickers=None, start_date=None, end_date=None, threshold=0.5):
        """Run backtest on multiple tickers."""
        if tickers is None:
            tickers = get_tickers(self.market)
        
        if start_date is None:
            end_date = datetime.now()
            start_date = end_date - timedelta(days=180)
        elif end_date is None:
            end_date = datetime.now()
        
        print(f"\n{'='*70}")
        print(f"BACKTEST: {self.market_name} ({self.market.upper()})")
        print(f"{'='*70}")
        print(f"Period: {start_date.date()} to {end_date.date()}")
        print(f"Initial capital: ${self.initial_capital:,.0f}")
        print(f"Position size: {self.position_size*100:.0f}% per trade")
        print(f"Signal threshold: {threshold:.2f}")
        print(f"Stocks: {len(tickers)}")
        print(f"{'='*70}\n")
        
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
        print(f"BACKTEST RESULTS - {self.market_name.upper()}")
        print(f"{'='*70}\n")
        
        # Individual results
        print("INDIVIDUAL STOCKS:")
        print(f"{'Ticker':<15} {'Return':<12} {'Trades':<10} {'Win Rate':<12} {'Max DD':<10}")
        print("-" * 59)
        
        all_returns = []
        all_trades = []
        
        for result in results:
            print(f"{result['ticker']:<15} {result['total_return_pct']:>+10.1f}% {result['num_trades']:>8} "
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
            
            print(f"Market: {self.market_name}")
            print(f"Average return (stocks): {avg_return:+.1f}%")
            print(f"Median return (stocks): {median_return:+.1f}%")
            print(f"Total trades: {total_trades}")
            print(f"Winning trades: {win_count} ({overall_win_rate:.0f}%)")
            print(f"Losing trades: {loss_count}")
            print(f"Total P&L: ${total_pnl:+,.0f}")
            print(f"Avg P&L per trade: ${total_pnl/total_trades:+,.0f}")
        
        return results


if __name__ == '__main__':
    # Test both markets
    for market in ['us', 'br']:
        print(f"\n\n{'#'*70}")
        print(f"# TESTING {market.upper()} MARKET")
        print(f"{'#'*70}")
        
        backtest = MultiMarketBacktester(market=market, initial_capital=10000, position_size=0.5)
        
        # Get a few tickers for quick test
        tickers = get_tickers(market)[:5]
        
        end_date = datetime.now()
        start_date = end_date - timedelta(days=180)
        
        results = backtest.run_backtest(tickers=tickers, start_date=start_date, end_date=end_date, threshold=0.5)
        backtest.generate_report(results)
