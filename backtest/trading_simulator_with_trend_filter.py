"""
Enhanced trading simulator with trend filtering.
Incorporates trend detection to distinguish consolidation from downtrends.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np
import pandas as pd
from datetime import datetime, timedelta

from src.signals.information_flow import InformationFlowDetector
from src.signals.momentum_reversal import MomentumReversalDetector
from src.signals.trend_detection import TrendDetector
from src.data.fetch_data import fetch_ticker_data


class EnhancedTradingSimulator:
    """Trading simulator with trend-aware signal filtering."""
    
    def __init__(self, initial_capital=10000, position_size=0.5):
        self.initial_capital = initial_capital
        self.position_size = position_size
        self.info_detector = InformationFlowDetector()
        self.mom_detector = MomentumReversalDetector()
        self.trend_detector = TrendDetector()
    
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
    
    def calculate_signal_score(self, signals, data):
        """Calculate signal score with trend filtering."""
        if not signals:
            return 0, None, "No signals"
        
        # Base signal strength
        avg_strength = np.mean([s['strength'] for s in signals])
        directions = [s['direction'] for s in signals if s['direction']]
        
        if directions:
            bullish = sum(1 for d in directions if d == 'bullish')
            bearish = sum(1 for d in directions if d == 'bearish')
            direction = 'bullish' if bullish > bearish else ('bearish' if bearish > bullish else None)
        else:
            direction = None
        
        # TREND FILTERING
        trend_context = self.trend_detector.get_trend_context(data)
        should_trust_mr, multiplier, trend_reason = self.trend_detector.should_trust_mean_reversion(data)
        
        # Apply multiplier to signal strength
        adjusted_strength = avg_strength * multiplier
        
        return adjusted_strength, direction, f"Base: {avg_strength:.2f}, Trend filter: {multiplier:.1f}x → {adjusted_strength:.2f}"
    
    def simulate_ticker(self, ticker, start_date, end_date, threshold=0.5, use_trend_filter=True):
        """Simulate trading on a single ticker with optional trend filtering."""
        print(f"Simulating {ticker}...", end=" ", flush=True)
        
        try:
            data = fetch_ticker_data(ticker, start=start_date, end=end_date, progress=False)
        except:
            print("Failed to fetch data")
            return None
        
        if len(data) < 40:
            print("Insufficient data")
            return None
        
        # Convert to standard arrays
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
            
            if use_trend_filter:
                signal_score, signal_direction, signal_note = self.calculate_signal_score(signals, window)
            else:
                # Original logic without trend filtering
                if not signals:
                    signal_score = 0
                    signal_direction = None
                else:
                    avg_strength = np.mean([s['strength'] for s in signals])
                    directions = [s['direction'] for s in signals if s['direction']]
                    signal_score = avg_strength
                    signal_direction = 'bullish' if sum(1 for d in directions if d == 'bullish') > sum(1 for d in directions if d == 'bearish') else ('bearish' if any(d == 'bearish' for d in directions) else None)
            
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
            'equity_log': equity_log
        }
        
        print(f"Return: {total_return:+.1f}% | Trades: {len(trades)} | Win: {win_rate:.0f}%")
        
        return result
    
    def run_backtest(self, tickers, start_date, end_date, threshold=0.5, use_trend_filter=True):
        """Run backtest with or without trend filtering."""
        mode = "WITH TREND FILTER" if use_trend_filter else "WITHOUT TREND FILTER"
        
        print(f"\n{'='*70}")
        print(f"BACKTEST {mode}")
        print(f"{'='*70}")
        print(f"Period: {start_date.date()} to {end_date.date()}")
        print(f"Threshold: {threshold:.2f}")
        print(f"Stocks: {len(tickers)}\n")
        
        results = []
        
        for ticker in tickers:
            result = self.simulate_ticker(ticker, start_date, end_date, threshold=threshold, use_trend_filter=use_trend_filter)
            if result:
                results.append(result)
        
        return results


if __name__ == '__main__':
    print("\n\n" + "=" * 70)
    print("COMPARING: WITH vs WITHOUT TREND FILTER")
    print("=" * 70)
    
    end_date = datetime.now()
    start_date = end_date - timedelta(days=180)
    
    test_tickers = ['AAPL', 'MSFT', 'NVDA', 'GOOGL', 'TSLA']
    
    # Without trend filter (original)
    print("\n\n" + "🔴" * 35)
    simulator_no_filter = EnhancedTradingSimulator()
    results_no_filter = simulator_no_filter.run_backtest(
        test_tickers, start_date, end_date, threshold=0.5, use_trend_filter=False
    )
    
    # With trend filter (improved)
    print("\n\n" + "🟢" * 35)
    simulator_with_filter = EnhancedTradingSimulator()
    results_with_filter = simulator_with_filter.run_backtest(
        test_tickers, start_date, end_date, threshold=0.5, use_trend_filter=True
    )
    
    # Compare results
    print("\n\n" + "=" * 70)
    print("COMPARISON: IMPACT OF TREND FILTERING")
    print("=" * 70)
    
    print(f"\n{'Ticker':<10} {'Without Filter':<30} {'With Filter':<30}")
    print("-" * 70)
    
    for i, ticker in enumerate(test_tickers):
        if i < len(results_no_filter) and i < len(results_with_filter):
            r_no = results_no_filter[i]
            r_with = results_with_filter[i]
            
            print(f"{ticker:<10} Return: {r_no['total_return_pct']:+6.1f}%, Win: {r_no['win_rate_pct']:5.0f}%   |   Return: {r_with['total_return_pct']:+6.1f}%, Win: {r_with['win_rate_pct']:5.0f}%")
