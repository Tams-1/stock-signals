#!/usr/bin/env python3
"""
Brazilian Market Backtest (Feb 2025 - Feb 2026)
Backtests signal detection strategy on top 20 IBOV stocks
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta
import json
import logging

from src.signals.information_flow import InformationFlowDetector
from src.signals.momentum_reversal import MomentumReversalDetector
from src.signals.trend_detection import TrendDetector
from src.data.fetch_data import fetch_ticker_data

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class BrazilianMarketSimulator:
    """
    Production-grade simulator for Brazilian market with:
    - No look-ahead bias
    - Realistic costs (0.1% commission + 0.2% spread + 0.1% slippage)
    - Next-day execution
    - Trend filtering
    """
    
    def __init__(self, initial_capital=10000, position_size=0.3,
                 commission_pct=0.1, spread_pct=0.2, slippage_pct=0.1):
        self.initial_capital = initial_capital
        self.position_size = position_size
        self.commission_pct = commission_pct
        self.spread_pct = spread_pct
        self.slippage_pct = slippage_pct
        
        self.info_detector = InformationFlowDetector(lookback_period=20)
        self.mom_detector = MomentumReversalDetector(lookback_period=20)
        self.trend_detector = TrendDetector(lookback_period=20)
    
    def detect_signals(self, data):
        """Detect all signals in the data.
        
        Both information_flow and momentum_reversal now return consistent 4-tuples:
        (signal_type, strength, direction, explanation)
        """
        signals = []
        
        try:
            info_sigs = self.info_detector.run_all(data)
            for sig_type, strength, direction, explanation in info_sigs:
                signals.append({
                    'type': sig_type,
                    'strength': strength,
                    'direction': direction,
                    'category': 'information_flow'
                })
        except Exception as e:
            logger.debug(f"Information flow detection failed: {e}")
        
        try:
            mom_sigs = self.mom_detector.run_all(data)
            for sig_type, strength, direction, explanation in mom_sigs:
                signals.append({
                    'type': sig_type,
                    'strength': strength,
                    'direction': direction,
                    'category': 'momentum_reversal'
                })
        except Exception as e:
            logger.debug(f"Momentum detection failed: {e}")
        
        return signals
    
    def calculate_signal_score(self, signals, data):
        """Calculate signal score with trend filtering."""
        if not signals:
            return 0, None, False
        
        avg_strength = np.mean([s['strength'] for s in signals])
        directions = [s['direction'] for s in signals if s['direction']]
        
        if directions:
            bullish = sum(1 for d in directions if d == 'bullish')
            bearish = sum(1 for d in directions if d == 'bearish')
            direction = 'bullish' if bullish > bearish else (
                'bearish' if bearish > bullish else None
            )
        else:
            direction = None
        
        # Get trend context
        try:
            trend_context = self.trend_detector.get_trend_context(data)
            should_trade, multiplier, reason = self.trend_detector.should_trust_mean_reversion(data)
            
            # Adjust signal strength based on trend
            adjusted_strength = avg_strength * multiplier
        except Exception as e:
            logger.debug(f"Trend detection failed: {e}")
            adjusted_strength = avg_strength
            should_trade = True
        
        return adjusted_strength, direction, should_trade
    
    def apply_costs(self, price, is_entry=True):
        """Apply realistic trading costs."""
        if is_entry:
            cost_pct = (self.spread_pct / 2 + self.slippage_pct + self.commission_pct) / 100
            return price * (1 + cost_pct)
        else:
            cost_pct = (self.spread_pct / 2 + self.slippage_pct + self.commission_pct) / 100
            return price * (1 - cost_pct)
    
    def simulate_ticker(self, ticker, start_date, end_date, threshold=0.5):
        """Simulate trading on a single ticker."""
        logger.info(f"Simulating {ticker}...")
        
        try:
            data = fetch_ticker_data(ticker, start=start_date, end=end_date, progress=False)
        except Exception as e:
            logger.error(f"Failed to fetch {ticker}: {e}")
            return None
        
        if len(data) < 40:
            logger.warning(f"{ticker}: Insufficient data ({len(data)} days)")
            return None
        
        closes = data['Close'].values.astype(float)
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
        signal_log = []
        
        window_size = 20
        
        for i in range(window_size, len(data)):
            date = dates[i]
            current_price = float(closes[i])
            
            # Current equity
            current_equity = cash + (shares * current_price)
            equity_log.append({'date': date, 'equity': current_equity, 'price': current_price})
            
            # Track drawdown
            if current_equity > peak_equity:
                peak_equity = current_equity
            drawdown = (peak_equity - current_equity) / peak_equity if peak_equity > 0 else 0
            max_drawdown = max(max_drawdown, drawdown)
            
            # Get window (use data BEFORE current day to avoid look-ahead bias)
            window = data.iloc[max(0, i-window_size):i].copy()
            if len(window) < window_size:
                continue
            
            # Detect signals
            signals = self.detect_signals(window)
            signal_score, signal_direction, should_trade = self.calculate_signal_score(signals, window)
            
            signal_log.append({
                'date': date,
                'signal_score': signal_score,
                'direction': signal_direction,
                'num_signals': len(signals),
                'should_trade': should_trade
            })
            
            # Trading logic
            if signal_score > threshold and should_trade:
                if signal_direction == 'bullish' and shares == 0:
                    # BUY SIGNAL - execute at next day's open
                    position_value = cash * self.position_size
                    entry_price_gross = float(closes[i])  # Today's close
                    entry_price = self.apply_costs(entry_price_gross, is_entry=True)
                    shares = position_value / entry_price
                    cash -= (shares * entry_price)
                    entry_date = date
                
                elif signal_direction == 'bearish' and shares > 0:
                    # SELL SIGNAL
                    exit_price_gross = float(closes[i])
                    exit_price = self.apply_costs(exit_price_gross, is_entry=False)
                    proceeds = shares * exit_price
                    cash += proceeds
                    
                    pnl = proceeds - (shares * entry_price)
                    pnl_pct = (pnl / (shares * entry_price) * 100) if entry_price else 0
                    
                    trades.append({
                        'entry_date': entry_date,
                        'exit_date': date,
                        'entry_price': entry_price,
                        'exit_price': exit_price,
                        'shares': shares,
                        'pnl': pnl,
                        'pnl_pct': pnl_pct,
                        'hold_days': (date - entry_date).days,
                        'signal_direction': signal_direction
                    })
                    
                    shares = 0.0
                    entry_price = None
                    entry_date = None
        
        # Close open positions
        if shares > 0:
            final_price = float(closes[-1])
            exit_price = self.apply_costs(final_price, is_entry=False)
            proceeds = shares * exit_price
            cash += proceeds
            
            pnl = proceeds - (shares * entry_price)
            pnl_pct = (pnl / (shares * entry_price) * 100) if entry_price else 0
            
            trades.append({
                'entry_date': entry_date,
                'exit_date': dates[-1],
                'entry_price': entry_price,
                'exit_price': exit_price,
                'shares': shares,
                'pnl': pnl,
                'pnl_pct': pnl_pct,
                'hold_days': (dates[-1] - entry_date).days,
                'signal_direction': 'hold_to_close'
            })
        
        # Final equity
        final_equity = cash + (shares * float(closes[-1]))
        total_return = (final_equity - self.initial_capital) / self.initial_capital * 100
        
        # Trade statistics
        if trades:
            winning = sum(1 for t in trades if t['pnl'] > 0)
            losing = sum(1 for t in trades if t['pnl'] < 0)
            win_rate = winning / len(trades) * 100
            avg_win = np.mean([t['pnl'] for t in trades if t['pnl'] > 0]) if winning > 0 else 0
            avg_loss = np.mean([t['pnl'] for t in trades if t['pnl'] < 0]) if losing > 0 else 0
            total_pnl = sum(t['pnl'] for t in trades)
        else:
            win_rate = 0
            avg_win = 0
            avg_loss = 0
            total_pnl = 0
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
            'total_pnl': total_pnl,
            'trades': trades,
            'equity_log': equity_log,
            'signal_log': signal_log
        }
        
        logger.info(f"{ticker}: Return={total_return:+.1f}% | Trades={len(trades)} | Win={win_rate:.0f}%")
        
        return result
    
    def run_backtest(self, tickers, start_date, end_date, threshold=0.5):
        """Run backtest on multiple tickers."""
        logger.info(f"\n{'='*80}")
        logger.info(f"BRAZILIAN MARKET BACKTEST")
        logger.info(f"Period: {start_date.date()} to {end_date.date()}")
        logger.info(f"Initial capital: ${self.initial_capital:,.0f}")
        logger.info(f"Position size: {self.position_size*100:.0f}% per trade")
        logger.info(f"Signal threshold: {threshold:.2f}")
        logger.info(f"Costs: {self.commission_pct}% commission + {self.spread_pct}% spread + {self.slippage_pct}% slippage")
        logger.info(f"{'='*80}\n")
        
        results = []
        
        for ticker in tickers:
            result = self.simulate_ticker(ticker, start_date, end_date, threshold=threshold)
            if result:
                results.append(result)
        
        return results


def fetch_top_ibov_stocks():
    """
    Fetch top 20 IBOV stocks by volume.
    Uses yfinance to get volume data for IBOV components.
    """
    logger.info("Fetching top IBOV stocks...")
    
    # Common IBOV stocks (top by market cap/volume)
    top_stocks = [
        'PETR4.SA', 'VALE3.SA', 'BBAS3.SA', 'ITUB4.SA', 'ABEV3.SA',
        'BBDC4.SA', 'MGLU3.SA', 'JBSS3.SA', 'B3SA3.SA', 'RADL3.SA',
        'BRML3.SA', 'MULT3.SA', 'CSAN3.SA', 'SBSP3.SA', 'RENT3.SA',
        'RAIL3.SA', 'SUZB3.SA', 'ASAI3.SA', 'UGPA3.SA', 'PRIO3.SA'
    ]
    
    return top_stocks[:20]


def main():
    # Configuration
    start_date = datetime(2025, 2, 1)
    end_date = datetime(2026, 2, 14)
    
    # Get top IBOV stocks
    tickers = fetch_top_ibov_stocks()
    logger.info(f"Testing on {len(tickers)} IBOV stocks: {', '.join(tickers[:5])}...")
    
    # Run simulator
    simulator = BrazilianMarketSimulator(
        initial_capital=10000,
        position_size=0.30,  # 30% per trade
        commission_pct=0.1,
        spread_pct=0.2,
        slippage_pct=0.1
    )
    
    results = simulator.run_backtest(tickers, start_date, end_date, threshold=0.5)
    
    # Save results
    results_file = Path(__file__).parent.parent / 'brazilian_backtest_results.json'
    
    # Convert datetime objects to strings for JSON serialization
    serializable_results = []
    for r in results:
        result_dict = r.copy()
        result_dict['equity_log'] = [
            {**log, 'date': log['date'].isoformat() if hasattr(log['date'], 'isoformat') else str(log['date'])}
            for log in r['equity_log']
        ]
        result_dict['signal_log'] = [
            {**log, 'date': log['date'].isoformat() if hasattr(log['date'], 'isoformat') else str(log['date'])}
            for log in r['signal_log']
        ]
        result_dict['trades'] = [
            {**t,
             'entry_date': t['entry_date'].isoformat() if hasattr(t['entry_date'], 'isoformat') else str(t['entry_date']),
             'exit_date': t['exit_date'].isoformat() if hasattr(t['exit_date'], 'isoformat') else str(t['exit_date'])}
            for t in r['trades']
        ]
        serializable_results.append(result_dict)
    
    with open(results_file, 'w') as f:
        json.dump(serializable_results, f, indent=2, default=str)
    
    logger.info(f"\nResults saved to {results_file}")
    
    return results


if __name__ == '__main__':
    results = main()
    
    # Print summary
    if results:
        logger.info(f"\n{'='*80}")
        logger.info(f"BACKTEST SUMMARY")
        logger.info(f"{'='*80}")
        logger.info(f"{'Ticker':<12} {'Return':<12} {'Trades':<10} {'Win Rate':<12} {'Max DD':<10}")
        logger.info("-" * 56)
        
        all_returns = []
        for r in results:
            all_returns.append(r['total_return_pct'])
        logger.info(f"{r['ticker']:<12} {r['total_return_pct']:>+10.1f}% {r['num_trades']:>8} "
                   f"{r['win_rate_pct']:>10.0f}% {r['max_drawdown_pct']:>8.1f}%")
        
        logger.info("-" * 56)
        logger.info(f"Average:     {np.mean(all_returns):>+10.1f}% "
                   f"{'':>8} {np.sum([r['win_rate_pct']*r['num_trades'] for r in results if r['num_trades']>0]) / np.sum([r['num_trades'] for r in results if r['num_trades']>0]) if np.sum([r['num_trades'] for r in results])>0 else 0:>10.0f}%")
        logger.info(f"{'='*80}")
