#!/usr/bin/env python3
"""
Backtest with intelligent exit management
Tests the new ExitManager against the baseline system
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import json

from src.signals.trend_detector_v2 import TrendDetectorV2
from src.risk.exit_manager import ExitManager, Position


class BacktestWithExits:
    """
    Backtest with intelligent exit management
    Compares performance with stop loss, take profit, and trailing stops
    """
    
    def __init__(
        self,
        initial_capital: float = 100000.0,
        confidence_threshold: float = 0.25,
    ):
        self.initial_capital = initial_capital
        self.capital = initial_capital
        self.confidence_threshold = confidence_threshold
        
        self.trend_detector = TrendDetectorV2()
        self.exit_manager = ExitManager()
        
        # Track active positions
        self.positions: Dict[str, Position] = {}
        
        # Track history
        self.trades = []
        self.equity_curve = []
        self.previous_trends = {}
        
    def get_historical_data(
        self,
        ticker: str,
        start_date: str,
        end_date: str,
    ) -> pd.DataFrame:
        """Download historical data"""
        data = yf.download(
            ticker,
            start=start_date,
            end=end_date,
            progress=False
        )
        
        # Flatten MultiIndex if needed
        if isinstance(data.columns, pd.MultiIndex):
            data.columns = ['_'.join(col).strip('_') if col[1] else col[0] 
                          for col in data.columns.values]
            data = data.rename(columns={
                f'Open_{ticker}': 'Open',
                f'High_{ticker}': 'High',
                f'Low_{ticker}': 'Low',
                f'Close_{ticker}': 'Close',
                f'Volume_{ticker}': 'Volume',
            })
        
        return data
    
    def simulate_trade(
        self,
        ticker: str,
        date: str,
        price: float,
        action: str,
        size: float,
        reason: str,
    ):
        """Record a trade"""
        trade = {
            'date': date,
            'ticker': ticker,
            'action': action,
            'price': price,
            'size': size,
            'reason': reason,
            'capital': self.capital,
        }
        
        self.trades.append(trade)
        
        # Calculate position value if entry
        if action == "BUY":
            position_value = self.capital * size
            trade['position_value'] = position_value
            trade['shares'] = position_value / price
    
    def check_entry_signal(
        self,
        ticker: str,
        data: pd.DataFrame,
        current_date: pd.Timestamp,
    ) -> Optional[Dict]:
        """Check for entry signal"""
        # Get data up to current date
        historical = data.loc[:current_date]
        
        if len(historical) < 50:
            return None
        
        # Detect trend
        trend_result = self.trend_detector.detect_trend(historical)
        consensus = trend_result.get('consensus', 'unknown')
        confidence = trend_result.get('confidence', 0.0)
        
        # Map consensus to trend
        if consensus in ['uptrend', 'bull_pullback']:
            trend = "bullish"
        elif consensus in ['downtrend', 'bear_bounce']:
            trend = "bearish"
        else:
            trend = "neutral"
        
        # Store trend for next iteration
        self.previous_trends[ticker] = trend
        
        # Entry condition: bullish with confidence > threshold
        if trend == "bullish" and confidence > self.confidence_threshold:
            # Calculate position size based on confidence
            position_size = self.exit_manager.calculate_position_size(confidence)
            
            if position_size > 0:
                return {
                    'action': 'BUY',
                    'confidence': confidence,
                    'position_size': position_size,
                    'trend': trend,
                }
        
        return None
    
    def check_exit_signal(
        self,
        ticker: str,
        data: pd.DataFrame,
        current_date: pd.Timestamp,
    ) -> Optional[Dict]:
        """Check for exit signal on active position"""
        if ticker not in self.positions:
            return None
        
        position = self.positions[ticker]
        
        # Get data up to current date
        historical = data.loc[:current_date]
        current_price = historical['Close'].iloc[-1]
        
        # Update position with current price
        position = self.exit_manager.update_position(position, current_price, historical)
        self.positions[ticker] = position
        
        # Detect current trend
        trend_result = self.trend_detector.detect_trend(historical)
        consensus = trend_result.get('consensus', 'unknown')
        
        if consensus in ['uptrend', 'bull_pullback']:
            trend = "bullish"
        elif consensus in ['downtrend', 'bear_bounce']:
            trend = "bearish"
        else:
            trend = "neutral"
        
        # Get previous trend
        prev_trend = self.previous_trends.get(ticker, "bullish")
        
        # Check exit conditions
        exit_signal = self.exit_manager.check_exit(
            position=position,
            current_trend=trend,
            previous_trend=prev_trend,
            news_sentiment=None,  # No news for now
        )
        
        # Store trend for next iteration
        self.previous_trends[ticker] = trend
        
        if exit_signal.should_exit:
            return {
                'action': 'SELL',
                'exit_percentage': exit_signal.exit_percentage,
                'reason': exit_signal.reason.value,
                'price': current_price,
                'gain': (current_price - position.entry_price) / position.entry_price,
            }
        
        return None
    
    def run_backtest(
        self,
        tickers: List[str],
        start_date: str,
        end_date: str,
    ) -> Dict:
        """
        Run backtest with exit management
        
        Returns:
            Dict with performance metrics
        """
        print(f"\n🔄 Backtesting with Exit Manager...")
        print(f"Period: {start_date} → {end_date}")
        print(f"Tickers: {len(tickers)}")
        print(f"Initial Capital: R$ {self.initial_capital:,.2f}\n")
        
        # Download all data
        all_data = {}
        for ticker in tickers:
            print(f"📥 Downloading {ticker}...", end=" ")
            data = self.get_historical_data(ticker, start_date, end_date)
            if len(data) > 0:
                all_data[ticker] = data
                print(f"✓ {len(data)} days")
            else:
                print("✗ No data")
        
        if not all_data:
            print("❌ No data downloaded")
            return {}
        
        # Get common date range
        common_dates = None
        for data in all_data.values():
            if common_dates is None:
                common_dates = set(data.index)
            else:
                common_dates &= set(data.index)
        
        common_dates = sorted(list(common_dates))
        print(f"\n📊 {len(common_dates)} trading days in common\n")
        
        # Simulate trading day by day
        for i, date in enumerate(common_dates):
            if i < 50:  # Need 50 days of history
                continue
            
            # Check all tickers
            for ticker in all_data.keys():
                data = all_data[ticker]
                
                # Check if we have a position
                if ticker in self.positions:
                    # Check for exit signal
                    exit_signal = self.check_exit_signal(ticker, data, date)
                    
                    if exit_signal:
                        position = self.positions[ticker]
                        exit_pct = exit_signal['exit_percentage']
                        exit_price = exit_signal['price']
                        reason = exit_signal['reason']
                        gain = exit_signal['gain']
                        
                        # Calculate profit
                        position_value = self.capital * position.size
                        exit_value = position_value * (1 + gain)
                        profit = exit_value - position_value
                        
                        # Partial or full exit
                        if exit_pct >= 1.0:
                            # Full exit
                            self.capital += profit
                            self.simulate_trade(
                                ticker=ticker,
                                date=date.strftime("%Y-%m-%d"),
                                price=exit_price,
                                action="SELL",
                                size=position.size,
                                reason=reason,
                            )
                            del self.positions[ticker]
                        else:
                            # Partial exit
                            partial_profit = profit * exit_pct
                            self.capital += partial_profit
                            position.size *= (1.0 - exit_pct)
                            self.positions[ticker] = position
                            
                            self.simulate_trade(
                                ticker=ticker,
                                date=date.strftime("%Y-%m-%d"),
                                price=exit_price,
                                action="SELL_PARTIAL",
                                size=position.size * exit_pct,
                                reason=reason,
                            )
                
                else:
                    # Check for entry signal
                    entry_signal = self.check_entry_signal(ticker, data, date)
                    
                    if entry_signal:
                        position_size = entry_signal['position_size']
                        confidence = entry_signal['confidence']
                        entry_price = data.loc[date, 'Close']
                        
                        # Create new position
                        position = self.exit_manager.initialize_position(
                            ticker=ticker,
                            entry_price=entry_price,
                            entry_date=date.strftime("%Y-%m-%d"),
                            size=position_size,
                            df=data.loc[:date],
                        )
                        
                        self.positions[ticker] = position
                        
                        self.simulate_trade(
                            ticker=ticker,
                            date=date.strftime("%Y-%m-%d"),
                            price=entry_price,
                            action="BUY",
                            size=position_size,
                            reason=f"bullish_conf_{confidence:.2f}",
                        )
            
            # Record equity curve
            total_equity = self.capital
            for ticker, position in self.positions.items():
                data = all_data[ticker]
                current_price = data.loc[date, 'Close']
                position_value = self.capital * position.size
                gain = (current_price - position.entry_price) / position.entry_price
                total_equity += position_value * gain
            
            self.equity_curve.append({
                'date': date,
                'equity': total_equity,
                'cash': self.capital,
                'positions': len(self.positions),
            })
        
        # Close remaining positions at end
        final_date = common_dates[-1]
        for ticker in list(self.positions.keys()):
            position = self.positions[ticker]
            data = all_data[ticker]
            final_price = data.loc[final_date, 'Close']
            gain = (final_price - position.entry_price) / position.entry_price
            
            position_value = self.capital * position.size
            exit_value = position_value * (1 + gain)
            profit = exit_value - position_value
            self.capital += profit
            
            self.simulate_trade(
                ticker=ticker,
                date=final_date.strftime("%Y-%m-%d"),
                price=final_price,
                action="SELL",
                size=position.size,
                reason="backtest_end",
            )
            
            del self.positions[ticker]
        
        # Calculate metrics
        final_equity = self.capital
        total_return = (final_equity - self.initial_capital) / self.initial_capital
        
        buy_trades = [t for t in self.trades if t['action'] == "BUY"]
        sell_trades = [t for t in self.trades if t['action'] in ["SELL", "SELL_PARTIAL"]]
        
        # Calculate win rate
        winning_trades = 0
        losing_trades = 0
        
        for sell in sell_trades:
            ticker = sell['ticker']
            sell_date = sell['date']
            
            # Find corresponding buy
            buy = None
            for b in reversed(buy_trades):
                if b['ticker'] == ticker and b['date'] < sell_date:
                    buy = b
                    break
            
            if buy:
                gain = (sell['price'] - buy['price']) / buy['price']
                if gain > 0:
                    winning_trades += 1
                else:
                    losing_trades += 1
        
        win_rate = winning_trades / len(sell_trades) if sell_trades else 0
        
        results = {
            'initial_capital': self.initial_capital,
            'final_equity': final_equity,
            'total_return_pct': total_return * 100,
            'total_trades': len(buy_trades),
            'winning_trades': winning_trades,
            'losing_trades': losing_trades,
            'win_rate': win_rate,
            'trades': self.trades,
            'equity_curve': self.equity_curve,
        }
        
        return results


def main():
    """Run backtest comparison"""
    
    # Test parameters (same as previous backtest)
    tickers = ["VALE3.SA", "ITUB3.SA", "KLBN11.SA", "MTRE3.SA", "ITSA4.SA"]
    start_date = "2025-08-01"
    end_date = "2026-02-14"
    
    # Run backtest with exits
    bt = BacktestWithExits(
        initial_capital=100000.0,
        confidence_threshold=0.25,
    )
    
    results = bt.run_backtest(tickers, start_date, end_date)
    
    # Print results
    print(f"\n{'='*70}")
    print(f"📊 BACKTEST RESULTS - Exit Manager")
    print(f"{'='*70}\n")
    
    print(f"Initial Capital:  R$ {results['initial_capital']:>12,.2f}")
    print(f"Final Equity:     R$ {results['final_equity']:>12,.2f}")
    print(f"Total Return:     {results['total_return_pct']:>12.2f}%")
    print(f"\nTrades:           {results['total_trades']:>12}")
    print(f"Winning:          {results['winning_trades']:>12} ({results['win_rate']*100:.1f}%)")
    print(f"Losing:           {results['losing_trades']:>12}")
    
    # Save results
    output_file = "backtest/backtest_with_exits_results.json"
    with open(output_file, 'w') as f:
        # Convert timestamps to strings for JSON
        json_results = results.copy()
        json_results['equity_curve'] = [
            {
                'date': e['date'].strftime("%Y-%m-%d"),
                'equity': e['equity'],
                'cash': e['cash'],
                'positions': e['positions'],
            }
            for e in results['equity_curve']
        ]
        
        json.dump(json_results, f, indent=2)
    
    print(f"\n✅ Results saved to {output_file}")
    print(f"{'='*70}\n")


if __name__ == "__main__":
    main()
