#!/usr/bin/env python3
"""
Day-by-day realistic backtest simulating real-time trading
Period: 2026-01-01 to 2026-02-14
Tickers: VALE3, INTB3, KLBN11, MTRE3, ITSA4
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Tuple
import json

from src.signals.trend_detector_v2 import TrendDetectorV2
from src.news.free_news_client import FreeNewsClient

# Test configuration
START_DATE = "2025-08-01"
END_DATE = "2026-02-14"
INITIAL_CAPITAL_PER_TICKER = 10000.0
TICKERS = ["VALE3.SA", "ITUB3.SA", "KLBN11.SA", "MTRE3.SA", "ITSA4.SA"]
LOOKBACK_DAYS = 120  # For trend detection

class RealtimeBacktester:
    """Realistic day-by-day backtester"""
    
    def __init__(self, tickers: List[str], start_date: str, end_date: str, 
                 initial_capital: float, use_news: bool = True):
        self.tickers = tickers
        self.start_date = pd.Timestamp(start_date)
        self.end_date = pd.Timestamp(end_date)
        self.initial_capital_per_ticker = initial_capital
        self.total_capital = initial_capital * len(tickers)
        self.use_news = use_news
        
        # Components
        self.trend_detector = TrendDetectorV2()
        if use_news:
            self.news_client = FreeNewsClient()
        
        # Portfolio tracking
        self.positions = {ticker: 0.0 for ticker in tickers}  # Shares held
        self.cash = {ticker: initial_capital for ticker in tickers}  # Cash per ticker
        self.portfolio_history = []
        
        # Performance tracking
        self.trades = []
        self.daily_returns = []
        
        print(f"✅ Backtester initialized")
        print(f"   Period: {start_date} to {end_date}")
        print(f"   Tickers: {len(tickers)}")
        print(f"   Capital: R$ {self.total_capital:,.2f}")
        print(f"   News: {'ON' if use_news else 'OFF'}")
    
    def download_data(self) -> Dict[str, pd.DataFrame]:
        """Download all data once"""
        print(f"\n📥 Downloading data...")
        
        data = {}
        download_start = self.start_date - timedelta(days=LOOKBACK_DAYS + 30)
        
        for ticker in self.tickers:
            print(f"   {ticker}...", end=" ")
            try:
                df = yf.download(
                    ticker,
                    start=download_start.strftime("%Y-%m-%d"),
                    end=(self.end_date + timedelta(days=1)).strftime("%Y-%m-%d"),
                    progress=False
                )
                
                # Flatten MultiIndex columns if present
                if isinstance(df.columns, pd.MultiIndex):
                    df.columns = df.columns.get_level_values(0)
                
                if len(df) > 0:
                    data[ticker] = df
                    print(f"✓ ({len(df)} days)")
                else:
                    print("✗ No data")
            except Exception as e:
                print(f"✗ Error: {e}")
        
        return data
    
    def get_signal(self, ticker: str, current_date: pd.Timestamp, 
                   data: pd.DataFrame) -> Tuple[str, float, Dict]:
        """
        Get trading signal for ticker on current_date.
        Uses data UP TO (but not including) current_date.
        """
        # Get historical data up to yesterday
        historical = data[data.index < current_date].tail(LOOKBACK_DAYS)
        
        if len(historical) < 50:
            return "HOLD", 0.0, {"reason": "insufficient_data"}
        
        # Trend detection
        trend_result = self.trend_detector.detect_trend(historical)
        consensus = trend_result.get('consensus', 'unknown')
        confidence = trend_result.get('confidence', 0.0)
        
        # Map consensus to simple trend
        if consensus in ['uptrend', 'bull_pullback']:
            trend = "uptrend"
        elif consensus in ['downtrend', 'bear_bounce']:
            trend = "downtrend"
        else:
            trend = "neutral"
        
        # Get news from yesterday (simulating real-time)
        news_sentiment = 0.0
        if self.use_news:
            try:
                yesterday = (current_date - timedelta(days=1)).strftime("%Y-%m-%d")
                news_sentiment = self.news_client.get_sentiment(ticker, yesterday)
            except Exception as e:
                pass  # Silently fail on news errors
        
        # SOTA: Pure confidence-based approach
        # Ignore trend classification - use raw confidence as signal
        # This captures early movements regardless of trend label
        
        # Use confidence directly as score
        # Positive confidence = bullish, negative would be bearish
        base_score = confidence
        
        # Incorporate news sentiment (optional boost)
        if self.use_news and abs(news_sentiment) > 0.1:
            base_score += news_sentiment * 0.15  # News contributes up to 15%
        
        # Clip to valid range
        signal_score = max(0.0, min(1.0, base_score))  # Confidence is 0-1
        
        # Generate signal and position size from score
        signal = "HOLD"
        position_size = 0.0
        
        ENTRY_THRESHOLD = 0.25  # Confidence threshold for entry
        
        if signal_score > ENTRY_THRESHOLD:
            signal = "BUY"
            # Position size scales with confidence: 0.25→25%, 1.0→90%
            raw_size = (signal_score - ENTRY_THRESHOLD) / (1.0 - ENTRY_THRESHOLD)
            position_size = min(0.90, raw_size * 0.90)
            position_size = max(0.25, position_size)  # Minimum 25%
        
        # Exit logic: only if confidence drops significantly
        # (No explicit downtrend check - rely on low confidence)
        elif signal_score < 0.15:  # Very low confidence = exit
            signal = "SELL"
            position_size = 1.0  # Exit full position
        
        metadata = {
            "trend": trend,
            "consensus": consensus,
            "confidence": confidence,
            "news_sentiment": news_sentiment,
            "signal_score": signal_score
        }
        
        return signal, position_size, metadata
    
    def execute_order(self, ticker: str, signal: str, position_size: float,
                     current_price: float, current_date: pd.Timestamp) -> Dict:
        """Execute buy/sell order"""
        
        current_shares = self.positions[ticker]
        current_cash = self.cash[ticker]
        
        order = {
            "date": current_date,
            "ticker": ticker,
            "signal": signal,
            "price": current_price,
            "action": None,
            "shares": 0,
            "value": 0.0,
            "cash_before": current_cash,
            "shares_before": current_shares
        }
        
        if signal == "BUY" and current_shares == 0:
            # Buy: use position_size of available cash
            cash_to_invest = current_cash * position_size
            shares_to_buy = cash_to_invest / current_price
            
            self.positions[ticker] = shares_to_buy
            self.cash[ticker] = current_cash - cash_to_invest
            
            order["action"] = "BUY"
            order["shares"] = shares_to_buy
            order["value"] = cash_to_invest
            
        elif signal == "SELL" and current_shares > 0:
            # Sell: exit full position
            cash_from_sale = current_shares * current_price
            
            self.cash[ticker] = current_cash + cash_from_sale
            self.positions[ticker] = 0.0
            
            order["action"] = "SELL"
            order["shares"] = current_shares
            order["value"] = cash_from_sale
        
        else:
            order["action"] = "HOLD"
        
        order["cash_after"] = self.cash[ticker]
        order["shares_after"] = self.positions[ticker]
        
        return order
    
    def calculate_portfolio_value(self, date: pd.Timestamp, 
                                  data_dict: Dict[str, pd.DataFrame]) -> float:
        """Calculate total portfolio value on given date"""
        total = 0.0
        
        for ticker in self.tickers:
            # Cash
            total += self.cash[ticker]
            
            # Shares value
            if self.positions[ticker] > 0:
                try:
                    # Get price for this date
                    ticker_data = data_dict[ticker]
                    price_row = ticker_data[ticker_data.index == date]
                    if len(price_row) > 0:
                        price_val = price_row['Close'].iloc[0]
                        price = float(price_val.item()) if hasattr(price_val, 'item') else float(price_val)
                        total += self.positions[ticker] * price
                except:
                    pass  # If price not available, ignore shares value
        
        return total
    
    def run(self) -> Dict:
        """Run day-by-day backtest"""
        print(f"\n{'='*70}")
        print(f"🚀 RUNNING REALISTIC BACKTEST")
        print(f"{'='*70}\n")
        
        # Download data
        data_dict = self.download_data()
        
        if len(data_dict) == 0:
            print("❌ No data downloaded!")
            return {}
        
        # Get trading days
        all_dates = set()
        for df in data_dict.values():
            all_dates.update(df.index)
        
        trading_days = sorted([d for d in all_dates 
                              if self.start_date <= d <= self.end_date])
        
        print(f"\n📅 Trading days: {len(trading_days)}")
        print(f"   First: {trading_days[0].strftime('%Y-%m-%d')}")
        print(f"   Last: {trading_days[-1].strftime('%Y-%m-%d')}")
        
        # Day-by-day simulation
        print(f"\n{'='*70}")
        print(f"DAY-BY-DAY SIMULATION")
        print(f"{'='*70}\n")
        
        for i, current_date in enumerate(trading_days):
            date_str = current_date.strftime("%Y-%m-%d")
            
            # Process each ticker
            for ticker in self.tickers:
                if ticker not in data_dict:
                    continue
                
                ticker_data = data_dict[ticker]
                
                # Get current price (open of today)
                price_row = ticker_data[ticker_data.index == current_date]
                if len(price_row) == 0:
                    continue
                
                price_val = price_row['Open'].iloc[0]
                current_price = float(price_val.item()) if hasattr(price_val, 'item') else float(price_val)
                
                # Get signal (using data up to yesterday)
                signal, position_size, metadata = self.get_signal(
                    ticker, current_date, ticker_data
                )
                
                # Execute order
                order = self.execute_order(
                    ticker, signal, position_size, current_price, current_date
                )
                
                # Record trade if action taken
                if order["action"] in ["BUY", "SELL"]:
                    order["metadata"] = metadata
                    self.trades.append(order)
                    
                    action_emoji = "🟢" if order["action"] == "BUY" else "🔴"
                    print(
                        f"{date_str} {action_emoji} {ticker:<12} "
                        f"{order['action']:<4} {order['shares']:>8.2f} shares @ "
                        f"R${current_price:>7.2f} = R${order['value']:>10,.2f}"
                    )
            
            # Record daily portfolio value
            portfolio_value = self.calculate_portfolio_value(current_date, data_dict)
            self.portfolio_history.append({
                "date": current_date,
                "value": portfolio_value
            })
        
        # Calculate final results
        results = self._calculate_results(data_dict)
        
        return results
    
    def _calculate_results(self, data_dict: Dict[str, pd.DataFrame]) -> Dict:
        """Calculate final performance metrics"""
        print(f"\n{'='*70}")
        print(f"📊 CALCULATING RESULTS")
        print(f"{'='*70}\n")
        
        # Final portfolio value
        final_value = self.portfolio_history[-1]["value"]
        initial_value = self.total_capital
        
        total_return_pct = ((final_value - initial_value) / initial_value) * 100
        
        # IBOV comparison
        ibov = yf.download(
            "^BVSP",
            start=self.start_date.strftime("%Y-%m-%d"),
            end=(self.end_date + timedelta(days=1)).strftime("%Y-%m-%d"),
            progress=False
        )
        
        # Flatten MultiIndex columns if present
        if isinstance(ibov.columns, pd.MultiIndex):
            ibov.columns = ibov.columns.get_level_values(0)
        
        ibov_start_val = ibov['Close'].iloc[0]
        ibov_start = float(ibov_start_val.item()) if hasattr(ibov_start_val, 'item') else float(ibov_start_val)
        ibov_end_val = ibov['Close'].iloc[-1]
        ibov_end = float(ibov_end_val.item()) if hasattr(ibov_end_val, 'item') else float(ibov_end_val)
        ibov_return_pct = ((ibov_end - ibov_start) / ibov_start) * 100
        
        # Per-ticker breakdown
        ticker_results = {}
        for ticker in self.tickers:
            if ticker not in data_dict:
                continue
            
            ticker_trades = [t for t in self.trades if t["ticker"] == ticker]
            
            # Calculate ticker return
            final_cash = self.cash[ticker]
            final_shares = self.positions[ticker]
            
            # Get final price
            try:
                final_price_row = data_dict[ticker][
                    data_dict[ticker].index == self.portfolio_history[-1]["date"]
                ]
                price_val = final_price_row['Close'].iloc[0]
                final_price = float(price_val.item()) if hasattr(price_val, 'item') else float(price_val)
            except:
                final_price = 0.0
            
            final_ticker_value = final_cash + (final_shares * final_price)
            ticker_return_pct = ((final_ticker_value - self.initial_capital_per_ticker) / 
                                self.initial_capital_per_ticker) * 100
            
            ticker_results[ticker] = {
                "initial": self.initial_capital_per_ticker,
                "final": final_ticker_value,
                "return_pct": ticker_return_pct,
                "trades": len(ticker_trades),
                "final_cash": final_cash,
                "final_shares": final_shares
            }
        
        results = {
            "initial_capital": initial_value,
            "final_value": final_value,
            "total_return_pct": total_return_pct,
            "ibov_return_pct": ibov_return_pct,
            "vs_ibov": total_return_pct - ibov_return_pct,
            "total_trades": len(self.trades),
            "ticker_results": ticker_results,
            "portfolio_history": self.portfolio_history,
            "trades": self.trades
        }
        
        return results
    
    def print_results(self, results: Dict):
        """Print formatted results"""
        print(f"\n{'='*70}")
        print(f"🎯 FINAL RESULTS")
        print(f"{'='*70}\n")
        
        print(f"💰 Portfolio Performance:")
        print(f"   Initial Capital: R$ {results['initial_capital']:>12,.2f}")
        print(f"   Final Value:     R$ {results['final_value']:>12,.2f}")
        print(f"   Return:          {results['total_return_pct']:>12.2f}%\n")
        
        print(f"📊 Benchmark Comparison:")
        print(f"   IBOV Return:     {results['ibov_return_pct']:>12.2f}%")
        print(f"   System vs IBOV:  {results['vs_ibov']:>12.2f}%\n")
        
        print(f"📈 Per-Ticker Results:\n")
        print(f"   {'Ticker':<12} {'Initial':>12} {'Final':>12} {'Return':>10} {'Trades':>7}")
        print(f"   {'-'*66}")
        
        for ticker, data in results['ticker_results'].items():
            print(
                f"   {ticker:<12} "
                f"R${data['initial']:>10,.2f} "
                f"R${data['final']:>10,.2f} "
                f"{data['return_pct']:>9.2f}% "
                f"{data['trades']:>7}"
            )
        
        print(f"\n   Total Trades: {results['total_trades']}")
        print(f"\n{'='*70}\n")


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--with-news", action="store_true", help="Enable news analysis")
    args = parser.parse_args()
    
    # Run backtest
    backtester = RealtimeBacktester(
        tickers=TICKERS,
        start_date=START_DATE,
        end_date=END_DATE,
        initial_capital=INITIAL_CAPITAL_PER_TICKER,
        use_news=args.with_news
    )
    
    results = backtester.run()
    
    if results:
        backtester.print_results(results)
        
        # Save results
        output_file = "realtime_backtest_results.json"
        with open(output_file, 'w') as f:
            # Convert dates to strings for JSON serialization
            json_results = results.copy()
            json_results['portfolio_history'] = [
                {"date": h["date"].strftime("%Y-%m-%d"), "value": h["value"]}
                for h in results['portfolio_history']
            ]
            json_results['trades'] = [
                {**t, "date": t["date"].strftime("%Y-%m-%d")}
                for t in results['trades']
            ]
            json.dump(json_results, f, indent=2)
        
        print(f"💾 Results saved to {output_file}")


if __name__ == "__main__":
    main()
