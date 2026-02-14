"""
Enhanced Trading Simulator with Realistic Trading Costs.

Improvements over base simulator:
1. 0.1% slippage on entry and exit prices
2. $5 commission per round-trip trade
3. Proper cost tracking and calculation
4. Detailed trade logging with costs
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

from src.signals.information_flow import InformationFlowDetector
from src.signals.momentum_reversal import MomentumReversalDetector
from src.data.fetch_data import fetch_ticker_data


class EnhancedCostSimulator:
    """Trading simulator with realistic costs."""
    
    def __init__(self, initial_capital=10000, position_size=0.5, 
                 slippage_pct=0.1, commission_per_trade=5.0):
        """
        Initialize simulator with realistic costs.
        
        Args:
            initial_capital: Starting capital in dollars
            position_size: Fraction of capital to use per position (0-1)
            slippage_pct: Slippage on entry and exit (default 0.1%)
            commission_per_trade: Fixed commission per round-trip trade in dollars (default $5)
        """
        self.initial_capital = initial_capital
        self.position_size = position_size
        self.slippage_pct = slippage_pct
        self.commission_per_trade = commission_per_trade
        
        self.info_detector = InformationFlowDetector()
        self.mom_detector = MomentumReversalDetector()
    
    def apply_slippage(self, price, direction='buy'):
        """Apply slippage to price based on direction."""
        if direction == 'buy':
            # Buying costs more due to slippage
            return price * (1 + self.slippage_pct / 100)
        else:
            # Selling gets less due to slippage
            return price * (1 - self.slippage_pct / 100)
    
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
        """Simulate trading on a single ticker with realistic costs."""
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
        entry_price_with_slippage = None
        max_drawdown = 0.0
        peak_equity = float(self.initial_capital)
        
        trades = []
        equity_log = []
        total_costs = 0.0
        
        # Slide window
        window_size = 20
        for i in range(window_size, len(data)):
            date = dates[i]
            current_price = float(closes[i])
            
            # Current equity (with unrealized costs if holding)
            current_equity = cash + (shares * current_price)
            equity_log.append({
                'date': date, 
                'equity': current_equity,
                'cash': cash,
                'shares': shares,
                'position_value': shares * current_price if shares > 0 else 0
            })
            
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
                    # BUY with slippage
                    filled_price = self.apply_slippage(current_price, direction='buy')
                    position_value = cash * self.position_size
                    shares = position_value / filled_price
                    cash -= position_value
                    entry_price = current_price
                    entry_price_with_slippage = filled_price
                    entry_date = date
                
                elif signal_direction == 'bearish' and shares > 0:
                    # SELL with slippage
                    filled_price = self.apply_slippage(current_price, direction='sell')
                    proceeds = shares * filled_price
                    
                    # Calculate costs
                    entry_cost = shares * entry_price_with_slippage
                    gross_pnl = proceeds - entry_cost
                    net_pnl = gross_pnl - self.commission_per_trade
                    
                    # Percentage calculations on original prices (no slippage)
                    pnl_pct_no_costs = ((current_price - entry_price) / entry_price) * 100
                    pnl_pct_with_costs = (net_pnl / (shares * entry_price)) * 100
                    
                    cash += proceeds
                    total_costs += self.commission_per_trade
                    
                    # Also add back slippage costs (difference between filled and market)
                    slippage_cost_entry = shares * entry_price * (self.slippage_pct / 100)
                    slippage_cost_exit = shares * current_price * (self.slippage_pct / 100)
                    total_costs += slippage_cost_entry + slippage_cost_exit
                    
                    trades.append({
                        'entry_date': entry_date,
                        'exit_date': date,
                        'entry_price': entry_price,
                        'entry_price_filled': entry_price_with_slippage,
                        'exit_price': current_price,
                        'exit_price_filled': filled_price,
                        'shares': shares,
                        'gross_pnl': gross_pnl,
                        'commission': self.commission_per_trade,
                        'slippage_cost': slippage_cost_entry + slippage_cost_exit,
                        'net_pnl': net_pnl,
                        'pnl_pct_no_costs': pnl_pct_no_costs,
                        'pnl_pct_with_costs': pnl_pct_with_costs,
                        'hold_days': (date - entry_date).days,
                        'cost_ratio': (self.commission_per_trade + slippage_cost_entry + slippage_cost_exit) / abs(gross_pnl) if gross_pnl != 0 else 0
                    })
                    
                    shares = 0.0
                    entry_price = None
                    entry_date = None
                    entry_price_with_slippage = None
        
        # Close open positions (forced liquidation at market with slippage)
        if shares > 0:
            final_price = float(closes[-1])
            filled_price = self.apply_slippage(final_price, direction='sell')
            proceeds = shares * filled_price
            
            entry_cost = shares * entry_price_with_slippage
            gross_pnl = proceeds - entry_cost
            net_pnl = gross_pnl - self.commission_per_trade
            
            pnl_pct_no_costs = ((final_price - entry_price) / entry_price) * 100
            pnl_pct_with_costs = (net_pnl / (shares * entry_price)) * 100
            
            total_costs += self.commission_per_trade
            slippage_cost_entry = shares * entry_price * (self.slippage_pct / 100)
            slippage_cost_exit = shares * final_price * (self.slippage_pct / 100)
            total_costs += slippage_cost_entry + slippage_cost_exit
            
            cash += proceeds
            
            trades.append({
                'entry_date': entry_date,
                'exit_date': dates[-1],
                'entry_price': entry_price,
                'entry_price_filled': entry_price_with_slippage,
                'exit_price': final_price,
                'exit_price_filled': filled_price,
                'shares': shares,
                'gross_pnl': gross_pnl,
                'commission': self.commission_per_trade,
                'slippage_cost': slippage_cost_entry + slippage_cost_exit,
                'net_pnl': net_pnl,
                'pnl_pct_no_costs': pnl_pct_no_costs,
                'pnl_pct_with_costs': pnl_pct_with_costs,
                'hold_days': (dates[-1] - entry_date).days,
                'cost_ratio': (self.commission_per_trade + slippage_cost_entry + slippage_cost_exit) / abs(gross_pnl) if gross_pnl != 0 else 0
            })
        
        # Final equity
        final_equity = cash + (shares * float(closes[-1]))
        total_return_no_costs = ((final_equity + total_costs) - self.initial_capital) / self.initial_capital * 100
        total_return_with_costs = (final_equity - self.initial_capital) / self.initial_capital * 100
        
        # Stats
        if trades:
            winning = sum(1 for t in trades if t['net_pnl'] > 0)
            losing = sum(1 for t in trades if t['net_pnl'] < 0)
            win_rate = winning / len(trades) * 100 if trades else 0
            
            # Use net P&L for calculations
            avg_win = np.mean([t['net_pnl'] for t in trades if t['net_pnl'] > 0]) if winning > 0 else 0
            avg_loss = np.mean([t['net_pnl'] for t in trades if t['net_pnl'] < 0]) if losing > 0 else 0
            
            # Gross stats (before costs)
            avg_win_gross = np.mean([t['gross_pnl'] for t in trades if t['gross_pnl'] > 0]) if winning > 0 else 0
            avg_loss_gross = np.mean([t['gross_pnl'] for t in trades if t['gross_pnl'] < 0]) if losing > 0 else 0
            
            total_cost_all_trades = sum(t['commission'] + t['slippage_cost'] for t in trades)
        else:
            win_rate = 0
            avg_win = 0
            avg_loss = 0
            avg_win_gross = 0
            avg_loss_gross = 0
            winning = 0
            losing = 0
            total_cost_all_trades = 0
        
        result = {
            'ticker': ticker,
            'initial_capital': self.initial_capital,
            'final_equity': final_equity,
            'total_return_pct_with_costs': total_return_with_costs,
            'total_return_pct_no_costs': total_return_no_costs,
            'costs_impact_pct': total_return_no_costs - total_return_with_costs,
            'max_drawdown_pct': max_drawdown * 100,
            'num_trades': len(trades),
            'win_rate_pct': win_rate,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'avg_win_gross': avg_win_gross,
            'avg_loss_gross': avg_loss_gross,
            'winning_trades': winning,
            'losing_trades': losing,
            'total_trading_costs': total_cost_all_trades,
            'total_slippage_costs': sum(t['slippage_cost'] for t in trades),
            'total_commissions': sum(t['commission'] for t in trades),
            'trades': trades,
            'equity_log': equity_log
        }
        
        print(f"Return (with costs): {total_return_with_costs:+.1f}% | "
              f"Return (no costs): {total_return_no_costs:+.1f}% | "
              f"Cost impact: {total_return_no_costs - total_return_with_costs:+.1f}% | "
              f"Trades: {len(trades)} | Win: {win_rate:.0f}%")
        
        return result
    
    def run_backtest(self, tickers, start_date, end_date, threshold=0.5):
        """Run backtest on multiple tickers."""
        print(f"\n{'='*90}")
        print(f"BACKTEST WITH REALISTIC COSTS: {start_date.date()} to {end_date.date()}")
        print(f"Initial capital: ${self.initial_capital:,.0f}")
        print(f"Position size: {self.position_size*100:.0f}% per trade")
        print(f"Signal threshold: {threshold:.2f}")
        print(f"Slippage: {self.slippage_pct:.2f}% on entry/exit")
        print(f"Commission: ${self.commission_per_trade:.0f} per round-trip trade")
        print(f"{'='*90}\n")
        
        results = []
        
        for i, ticker in enumerate(tickers):
            result = self.simulate_ticker(ticker, start_date, end_date, threshold=threshold)
            if result:
                results.append(result)
        
        return results
    
    def generate_report(self, results):
        """Generate backtest report with cost breakdown."""
        if not results:
            print("\nNo results to report")
            return
        
        print(f"\n{'='*90}")
        print("BACKTEST RESULTS WITH REALISTIC COSTS")
        print(f"{'='*90}\n")
        
        # Individual results
        print("INDIVIDUAL STOCKS (with costs):")
        print(f"{'Ticker':<10} {'Return(w/o)':<12} {'Return(w/)':<12} {'Cost Impact':<12} {'Trades':<8} {'Win %':<8}")
        print("-" * 70)
        
        all_returns_no_costs = []
        all_returns_with_costs = []
        all_cost_impacts = []
        all_trades = []
        
        for result in results:
            print(f"{result['ticker']:<10} {result['total_return_pct_no_costs']:>+10.1f}% "
                  f"{result['total_return_pct_with_costs']:>+10.1f}% "
                  f"{result['costs_impact_pct']:>+10.1f}% "
                  f"{result['num_trades']:>6} {result['win_rate_pct']:>6.0f}%")
            
            all_returns_no_costs.append(result['total_return_pct_no_costs'])
            all_returns_with_costs.append(result['total_return_pct_with_costs'])
            all_cost_impacts.append(result['costs_impact_pct'])
            all_trades.extend(result['trades'])
        
        # Portfolio statistics
        print(f"\n{'='*90}")
        print("PORTFOLIO STATISTICS (REALISTIC COSTS INCLUDED):")
        print(f"{'='*90}")
        
        avg_return_no_costs = np.mean(all_returns_no_costs)
        avg_return_with_costs = np.mean(all_returns_with_costs)
        avg_cost_impact = np.mean(all_cost_impacts)
        total_trades = len(all_trades)
        
        print(f"Average return (without costs): {avg_return_no_costs:+.2f}%")
        print(f"Average return (with costs):    {avg_return_with_costs:+.2f}%")
        print(f"Average cost impact:            {avg_cost_impact:+.2f}%")
        
        if all_trades:
            total_pnl = sum(t['net_pnl'] for t in all_trades)
            total_pnl_no_costs = sum(t['gross_pnl'] for t in all_trades)
            total_costs = sum(t['commission'] + t['slippage_cost'] for t in all_trades)
            
            win_count = sum(1 for t in all_trades if t['net_pnl'] > 0)
            loss_count = sum(1 for t in all_trades if t['net_pnl'] < 0)
            overall_win_rate = win_count / total_trades * 100
            
            print(f"\nTotal trades: {total_trades}")
            print(f"Winning trades: {win_count} ({overall_win_rate:.0f}%)")
            print(f"Losing trades: {loss_count}")
            
            print(f"\nP&L Summary:")
            print(f"  Total P&L (before costs): ${total_pnl_no_costs:+,.2f}")
            print(f"  Total costs (comm + slip): ${total_costs:+,.2f}")
            print(f"  Total P&L (after costs):  ${total_pnl:+,.2f}")
            print(f"  Avg P&L per trade (after costs): ${total_pnl/total_trades:+,.2f}")
            print(f"  Costs as % of gross P&L: {total_costs/abs(total_pnl_no_costs)*100:.1f}%" if total_pnl_no_costs != 0 else "  N/A")
            
            print(f"\nCost Breakdown:")
            total_commission = sum(t['commission'] for t in all_trades)
            total_slippage = sum(t['slippage_cost'] for t in all_trades)
            print(f"  Total commissions: ${total_commission:,.2f}")
            print(f"  Total slippage costs: ${total_slippage:,.2f}")
        
        return results
