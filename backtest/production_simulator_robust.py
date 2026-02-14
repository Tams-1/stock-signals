"""
Production-grade trading simulator with robust validation.
Fixes:
1. Look-ahead bias (use only prior day's close for signal)
2. Realistic costs (commissions, spread, slippage)
3. Next-day execution (realistic fill prices)
4. Proper statistics (hold-out validation ready)
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np
import pandas as pd
from datetime import datetime, timedelta

from src.signals.information_flow import InformationFlowDetector
from src.signals.momentum_reversal import MomentumReversalDetector
from src.signals.robust_trend_detection import RobustTrendDetector
from src.data.fetch_data import fetch_ticker_data


class ProductionSimulator:
    """
    Production-grade simulator with NO look-ahead bias.
    
    Key differences from backtest version:
    1. Uses ONLY prior day's close to generate signals
    2. Trades execute at next day's open (realistic gap risk)
    3. Includes realistic costs: commission, spread, slippage
    4. Proper position tracking and risk management
    """
    
    def __init__(self, initial_capital=10000, position_size=0.5, 
                 commission_pct=0.1, spread_pct=0.05, slippage_pct=0.1):
        """
        Initialize simulator with realistic costs.
        
        Args:
            commission_pct: Broker commission (0.1% = typical retail)
            spread_pct: Bid-ask spread (0.05% = tight, 0.1% = realistic)
            slippage_pct: Market impact slippage (0.1% = realistic for retail)
        """
        self.initial_capital = initial_capital
        self.position_size = position_size
        self.commission_pct = commission_pct
        self.spread_pct = spread_pct
        self.slippage_pct = slippage_pct
        
        self.info_detector = InformationFlowDetector()
        self.mom_detector = MomentumReversalDetector()
        self.trend_detector = RobustTrendDetector()
    
    def detect_signals(self, data):
        """Detect all signals in the data."""
        signals = []
        
        try:
            info_sigs = self.info_detector.run_all(data)
            for sig_type, strength, explanation in info_sigs:
                signals.append({'type': sig_type, 'strength': strength, 'direction': None})
        except Exception as e:
            pass
        
        try:
            mom_sigs = self.mom_detector.run_all(data)
            for sig_type, strength, direction, explanation in mom_sigs:
                signals.append({'type': sig_type, 'strength': strength, 'direction': direction})
        except Exception as e:
            pass
        
        return signals
    
    def calculate_signal_score(self, signals, data, base_threshold=0.5):
        """Calculate signal score with robust trend filtering."""
        if not signals:
            return 0, None, base_threshold
        
        avg_strength = np.mean([s['strength'] for s in signals])
        directions = [s['direction'] for s in signals if s['direction']]
        
        if directions:
            bullish = sum(1 for d in directions if d == 'bullish')
            bearish = sum(1 for d in directions if d == 'bearish')
            direction = 'bullish' if bullish > bearish else ('bearish' if bearish > bullish else None)
        else:
            direction = None
        
        # Robust trend filtering
        try:
            trend_context = self.trend_detector.get_robust_trend(data)
            consensus = trend_context['consensus']
            confidence = trend_context['confidence']
        except:
            consensus = 'unknown'
            confidence = 0.5
        
        # Moderate strategy: adjust threshold based on trend
        if consensus == 'consolidation':
            adjusted_threshold = base_threshold
        elif consensus == 'downtrend':
            if confidence >= 0.8:
                adjusted_threshold = base_threshold + 0.15
            elif confidence >= 0.5:
                adjusted_threshold = base_threshold + 0.05
            else:
                adjusted_threshold = base_threshold - 0.05
        elif consensus == 'uptrend':
            if confidence >= 0.8:
                adjusted_threshold = base_threshold - 0.1
            else:
                adjusted_threshold = base_threshold
        else:
            adjusted_threshold = base_threshold
        
        return avg_strength, direction, adjusted_threshold
    
    def apply_costs(self, price, is_entry=True):
        """
        Apply realistic trading costs to price.
        
        Entry: Price + spread/2 + slippage + commission
        Exit: Price - spread/2 - slippage - commission
        """
        if is_entry:
            # Buying: pay more
            cost_pct = (self.spread_pct / 2 + self.slippage_pct + self.commission_pct) / 100
            return price * (1 + cost_pct)
        else:
            # Selling: receive less
            cost_pct = (self.spread_pct / 2 + self.slippage_pct + self.commission_pct) / 100
            return price * (1 - cost_pct)
    
    def simulate_ticker(self, ticker, start_date, end_date, base_threshold=0.5):
        """
        Simulate trading with NO look-ahead bias.
        
        Key: Signal generated on day N using data through day N-1
             Trade executes on day N+1 at open price
        """
        print(f"Simulating {ticker}...", end=" ", flush=True)
        
        try:
            data = fetch_ticker_data(ticker, start=start_date, end=end_date, progress=False)
        except:
            print("Failed to fetch data")
            return None
        
        if len(data) < 40:
            print("Insufficient data")
            return None
        
        closes = np.array(data['Close'].values).flatten().astype(float)
        opens = np.array(data['Open'].values).flatten().astype(float)
        dates = data.index.tolist()
        
        # Trading state
        cash = float(self.initial_capital)
        shares = 0.0
        entry_price = None
        entry_date = None
        max_drawdown = 0.0
        peak_equity = float(self.initial_capital)
        
        trades = []
        equity_log = []
        signal_log = []
        
        window_size = 20
        
        # === KEY FIX: Two-day offset for look-ahead bias ===
        # Day i: Generate signal using data[0:i] (all data BEFORE day i)
        # Day i+1: Execute trade using opens[i+1] (next day's open)
        
        for i in range(window_size + 1, len(data) - 1):  # -1 to have next day for execution
            signal_date = dates[i - 1]  # Signal generated today
            execution_date = dates[i]   # Trade executes tomorrow
            execution_price = opens[i]  # Use next day's open (realistic)
            
            # Current equity (using prior close)
            current_price = closes[i - 1]  # Prior close for equity calc
            current_equity = cash + (shares * current_price)
            equity_log.append({'date': signal_date, 'equity': current_equity})
            
            # Track drawdown
            if current_equity > peak_equity:
                peak_equity = current_equity
            if peak_equity > 0:
                drawdown = (peak_equity - current_equity) / peak_equity
                max_drawdown = max(max_drawdown, drawdown)
            
            # Get signal window: data BEFORE today (no look-ahead)
            window = data.iloc[max(0, i - window_size - 1):i].copy()
            if len(window) < window_size:
                continue
            
            # Detect signals (using only prior data)
            signals = self.detect_signals(window)
            signal_score, signal_direction, threshold = self.calculate_signal_score(
                signals, window, base_threshold
            )
            
            signal_log.append({
                'date': signal_date,
                'signal_score': signal_score,
                'direction': signal_direction,
                'threshold': threshold,
                'execution_date': execution_date,
                'execution_price': execution_price
            })
            
            # Trading logic: Execute tomorrow at open
            if signal_score > threshold and signal_direction:
                if signal_direction == 'bullish' and shares == 0:
                    # BUY at next day's open with costs
                    fill_price = self.apply_costs(execution_price, is_entry=True)
                    position_value = cash * self.position_size
                    shares = position_value / fill_price
                    cash -= position_value
                    entry_price = fill_price
                    entry_date = execution_date
                
                elif signal_direction == 'bearish' and shares > 0:
                    # SELL at next day's open with costs
                    fill_price = self.apply_costs(execution_price, is_entry=False)
                    proceeds = shares * fill_price
                    cash += proceeds
                    
                    pnl = proceeds - (shares * entry_price)
                    pnl_pct = (pnl / (shares * entry_price) * 100) if entry_price else 0
                    
                    trades.append({
                        'entry_date': entry_date,
                        'exit_date': execution_date,
                        'entry_price': entry_price,
                        'exit_price': fill_price,
                        'shares': shares,
                        'pnl': pnl,
                        'pnl_pct': pnl_pct,
                        'hold_days': (execution_date - entry_date).days
                    })
                    
                    shares = 0.0
                    entry_price = None
                    entry_date = None
        
        # Close open positions at last available price
        if shares > 0:
            final_price = self.apply_costs(closes[-1], is_entry=False)
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
        final_equity = cash + (shares * closes[-1])
        total_return = (final_equity - self.initial_capital) / self.initial_capital * 100
        
        # Statistics
        if trades:
            winning = sum(1 for t in trades if t['pnl'] > 0)
            losing = sum(1 for t in trades if t['pnl'] < 0)
            win_rate = winning / len(trades) * 100 if trades else 0
        else:
            win_rate = 0
            winning = 0
            losing = 0
        
        result = {
            'ticker': ticker,
            'total_return_pct': total_return,
            'num_trades': len(trades),
            'win_rate_pct': win_rate,
            'winning_trades': winning,
            'losing_trades': losing,
            'trades': trades,
            'equity_log': equity_log,
            'signal_log': signal_log,
            'total_costs': self.initial_capital * (
                self.commission_pct + self.spread_pct + self.slippage_pct
            ) / 100 * (len(trades) * 2)  # Rough estimate
        }
        
        print(f"Return: {total_return:+.1f}% | Trades: {len(trades)} | Win: {win_rate:.0f}%")
        
        return result
    
    def run_backtest(self, tickers, start_date, end_date, base_threshold=0.5):
        """Run production-grade backtest with NO look-ahead bias."""
        
        print(f"\n{'='*70}")
        print(f"PRODUCTION BACKTEST (NO Look-Ahead Bias)")
        print(f"{'='*70}")
        print(f"Period: {start_date.date()} to {end_date.date()}")
        print(f"Costs: {self.commission_pct:.2f}% commission + {self.spread_pct:.2f}% spread + {self.slippage_pct:.2f}% slippage")
        print(f"Threshold: {base_threshold:.2f}")
        print(f"Stocks: {len(tickers)}\n")
        
        results = []
        
        for ticker in tickers:
            result = self.simulate_ticker(ticker, start_date, end_date, base_threshold)
            if result:
                results.append(result)
        
        return results


if __name__ == '__main__':
    from src.data.market_config import get_tickers
    
    print("=" * 70)
    print("PRODUCTION SIMULATION: No Look-Ahead, Realistic Costs")
    print("=" * 70)
    
    end_date = datetime.now()
    start_date = end_date - timedelta(days=180)
    
    # Test on subset
    us_tickers = get_tickers('us')[:5]
    br_tickers = get_tickers('br')[:5]
    
    print("\n🟦 US MARKET (Production)")
    simulator_us = ProductionSimulator(
        initial_capital=10000,
        commission_pct=0.1,  # 0.1% typical retail
        spread_pct=0.05,      # 0.05% on large-caps
        slippage_pct=0.1      # 0.1% market impact
    )
    results_us = simulator_us.run_backtest(us_tickers, start_date, end_date)
    
    print("\n🟩 BR MARKET (Production)")
    simulator_br = ProductionSimulator(
        initial_capital=10000,
        commission_pct=0.5,   # 0.5% typical BR brokers
        spread_pct=0.1,       # 0.1% on emerging market
        slippage_pct=0.2      # 0.2% higher impact
    )
    results_br = simulator_br.run_backtest(br_tickers, start_date, end_date)
    
    # Summary
    print("\n" + "=" * 70)
    print("RESULTS WITH REALISTIC COSTS")
    print("=" * 70)
    
    if results_us:
        us_returns = [r['total_return_pct'] for r in results_us]
        print(f"\nUS Market:")
        print(f"  Average return: {np.mean(us_returns):+.1f}%")
        print(f"  Median return: {np.median(us_returns):+.1f}%")
        print(f"  Win rate: {np.mean([r['win_rate_pct'] for r in results_us]):.0f}%")
    
    if results_br:
        br_returns = [r['total_return_pct'] for r in results_br]
        print(f"\nBR Market:")
        print(f"  Average return: {np.mean(br_returns):+.1f}%")
        print(f"  Median return: {np.median(br_returns):+.1f}%")
        print(f"  Win rate: {np.mean([r['win_rate_pct'] for r in results_br]):.0f}%")
