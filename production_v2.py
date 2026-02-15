#!/usr/bin/env python3
"""
Production Runner V2 - With Intelligent Exit Management
Implements: Stop loss, Take profit, Trailing stops, Regime exits, News-based exits
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import yfinance as yf
import pandas as pd
import json
from datetime import datetime, timedelta
import argparse
from typing import Dict, List, Optional

from src.signals.trend_detector_v2 import TrendDetectorV2
from src.news.free_news_client import FreeNewsClient
from src.risk.exit_manager import ExitManager, Position

# 18 IBOV tickers (will expand later)
TICKERS = [
    "PETR4.SA", "VALE3.SA", "ITUB4.SA", "BBDC4.SA", "BBAS3.SA",
    "ABEV3.SA", "B3SA3.SA", "SUZB3.SA", "RENT3.SA", "WEGE3.SA",
    "MGLU3.SA", "PCAR3.SA", "LREN3.SA", "RAIZ4.SA", "GGBR4.SA",
    "ASAI3.SA", "JBSS3.SA", "RDOR3.SA"
]

POSITIONS_FILE = "active_positions.json"
HISTORY_FILE = "position_history.json"


class ProductionRunnerV2:
    """
    Production runner with intelligent exit management
    """
    
    def __init__(self, use_news: bool = True):
        self.trend_detector = TrendDetectorV2()
        self.exit_manager = ExitManager()
        self.use_news = use_news
        
        if use_news:
            self.news_client = FreeNewsClient()
        
        # Load active positions
        self.active_positions = self._load_positions()
        
        print(f"✅ Sistema V2 inicializado (news={'ON' if use_news else 'OFF'})")
        if self.active_positions:
            print(f"📊 {len(self.active_positions)} posições ativas carregadas")
    
    def _load_positions(self) -> Dict[str, Position]:
        """Load active positions from file"""
        if not os.path.exists(POSITIONS_FILE):
            return {}
        
        try:
            with open(POSITIONS_FILE, 'r') as f:
                data = json.load(f)
            
            # Convert JSON to Position objects
            positions = {}
            for ticker, pos_data in data.items():
                positions[ticker] = Position(**pos_data)
            
            return positions
        except Exception as e:
            print(f"⚠️ Error loading positions: {e}")
            return {}
    
    def _save_positions(self):
        """Save active positions to file"""
        data = {}
        for ticker, pos in self.active_positions.items():
            data[ticker] = {
                'ticker': pos.ticker,
                'entry_price': pos.entry_price,
                'entry_date': pos.entry_date,
                'size': pos.size,
                'current_price': pos.current_price,
                'highest_price': pos.highest_price,
                'stop_loss': pos.stop_loss,
                'trailing_stop_active': pos.trailing_stop_active,
                'trailing_stop_price': pos.trailing_stop_price,
            }
        
        with open(POSITIONS_FILE, 'w') as f:
            json.dump(data, f, indent=2)
    
    def _log_exit(self, position: Position, exit_price: float, exit_percentage: float, reason: str):
        """Log position exit to history"""
        if not os.path.exists(HISTORY_FILE):
            history = []
        else:
            with open(HISTORY_FILE, 'r') as f:
                history = json.load(f)
        
        gain = (exit_price - position.entry_price) / position.entry_price
        
        history.append({
            'ticker': position.ticker,
            'entry_date': position.entry_date,
            'entry_price': position.entry_price,
            'exit_date': datetime.now().strftime("%Y-%m-%d"),
            'exit_price': exit_price,
            'exit_percentage': exit_percentage,
            'gain': gain,
            'reason': reason,
        })
        
        with open(HISTORY_FILE, 'w') as f:
            json.dump(history, f, indent=2)
    
    def get_data(self, ticker: str, days: int = 120) -> pd.DataFrame:
        """Download recent data"""
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        data = yf.download(
            ticker,
            start=start_date.strftime("%Y-%m-%d"),
            end=end_date.strftime("%Y-%m-%d"),
            progress=False
        )
        
        # Flatten MultiIndex columns if needed
        if isinstance(data.columns, pd.MultiIndex):
            data.columns = ['_'.join(col).strip('_') if col[1] else col[0] for col in data.columns.values]
            data = data.rename(columns={
                f'Open_{ticker}': 'Open',
                f'High_{ticker}': 'High',
                f'Low_{ticker}': 'Low',
                f'Close_{ticker}': 'Close',
                f'Volume_{ticker}': 'Volume',
            })
        
        return data
    
    def get_news_sentiment(self, ticker: str) -> float:
        """Get average sentiment from last 3 days"""
        if not self.use_news:
            return 0.0
        
        try:
            sentiments = []
            for days_ago in range(3):
                date = (datetime.now() - timedelta(days=days_ago)).strftime("%Y-%m-%d")
                sent = self.news_client.get_sentiment(ticker, date)
                sentiments.append(sent)
            
            return sum(sentiments) / len(sentiments) if sentiments else 0.0
        except Exception as e:
            print(f"    ⚠️ News error: {e}")
            return 0.0
    
    def analyze_ticker(self, ticker: str, previous_trend: Optional[str] = None) -> Dict:
        """Analyze single ticker with exit management"""
        try:
            # Download data
            data = self.get_data(ticker)
            
            if len(data) < 50:
                return None
            
            # Current price
            price_val = data['Close'].iloc[-1]
            current_price = float(price_val.item()) if hasattr(price_val, 'item') else float(price_val)
            
            # Trend detection
            trend_result = self.trend_detector.detect_trend(data)
            consensus = trend_result.get('consensus', 'unknown')
            confidence = trend_result.get('confidence', 0.0)
            
            # Map consensus to simple trend
            if consensus in ['uptrend', 'bull_pullback']:
                trend = "bullish"
            elif consensus in ['downtrend', 'bear_bounce']:
                trend = "bearish"
            else:
                trend = "neutral"
            
            # News sentiment (if enabled)
            news_sentiment = self.get_news_sentiment(ticker)
            
            # Check if we have an active position
            if ticker in self.active_positions:
                return self._check_exit(ticker, data, trend, previous_trend, news_sentiment, current_price)
            else:
                return self._check_entry(ticker, data, trend, confidence, news_sentiment, current_price)
            
        except Exception as e:
            print(f"  ❌ Error: {e}")
            return None
    
    def _check_entry(self, ticker: str, data: pd.DataFrame, trend: str, confidence: float, news_sentiment: float, current_price: float) -> Dict:
        """Check for entry signal"""
        signal = "HOLD"
        position_size = 0.0
        action = None
        
        # Entry condition: bullish trend with confidence > 0.35
        if trend == "bullish" and confidence > 0.35:
            # Calculate position size based on confidence
            position_size = self.exit_manager.calculate_position_size(confidence)
            
            # Boost confidence if positive news
            if self.use_news and news_sentiment > 0.1:
                confidence = min(confidence + 0.15, 1.0)
                position_size = self.exit_manager.calculate_position_size(confidence)
            
            if position_size > 0:
                signal = "BUY"
                action = "ENTER"
                
                # Create new position
                position = self.exit_manager.initialize_position(
                    ticker=ticker,
                    entry_price=current_price,
                    entry_date=datetime.now().strftime("%Y-%m-%d"),
                    size=position_size,
                    df=data,
                )
                
                self.active_positions[ticker] = position
                self._save_positions()
        
        result = {
            "ticker": ticker,
            "price": current_price,
            "trend": trend,
            "confidence": confidence,
            "news_sentiment": news_sentiment,
            "signal": signal,
            "position_size": position_size,
            "action": action,
        }
        
        # Include position details if just entered
        if ticker in self.active_positions:
            pos = self.active_positions[ticker]
            result.update({
                "entry_price": pos.entry_price,
                "gain": 0.0,
                "stop_loss": pos.stop_loss,
                "trailing_active": pos.trailing_stop_active,
            })
        
        return result
    
    def _check_exit(self, ticker: str, data: pd.DataFrame, trend: str, previous_trend: Optional[str], news_sentiment: float, current_price: float) -> Dict:
        """Check for exit signal on active position"""
        position = self.active_positions[ticker]
        
        # Update position with current price
        position = self.exit_manager.update_position(position, current_price, data)
        self.active_positions[ticker] = position
        
        # Check exit conditions
        prev_trend = previous_trend or "bullish"  # Assume bullish if not provided
        exit_signal = self.exit_manager.check_exit(
            position=position,
            current_trend=trend,
            previous_trend=prev_trend,
            news_sentiment=news_sentiment,
        )
        
        signal = "HOLD"
        action = None
        exit_percentage = 0.0
        exit_reason = None
        
        if exit_signal.should_exit:
            signal = "SELL"
            action = "EXIT"
            exit_percentage = exit_signal.exit_percentage
            exit_reason = exit_signal.reason.value
            
            # Log the exit
            self._log_exit(position, current_price, exit_percentage, exit_reason)
            
            # Remove or adjust position
            if exit_percentage >= 1.0:
                # Full exit
                del self.active_positions[ticker]
            else:
                # Partial exit - reduce size
                position.size *= (1.0 - exit_percentage)
                
                # Update stop loss if provided
                if exit_signal.new_stop_loss:
                    position.stop_loss = exit_signal.new_stop_loss
                
                self.active_positions[ticker] = position
            
            self._save_positions()
        
        # Calculate gain
        gain = (current_price - position.entry_price) / position.entry_price
        
        return {
            "ticker": ticker,
            "price": current_price,
            "trend": trend,
            "news_sentiment": news_sentiment,
            "signal": signal,
            "position_size": position.size,
            "action": action,
            "exit_percentage": exit_percentage,
            "exit_reason": exit_reason,
            "entry_price": position.entry_price,
            "gain": gain,
            "stop_loss": position.stop_loss,
            "trailing_active": position.trailing_stop_active,
        }
    
    def run(self, tickers: List[str] = None, previous_trends: Dict[str, str] = None):
        """Run analysis"""
        if tickers is None:
            tickers = TICKERS
        
        if previous_trends is None:
            previous_trends = {}
        
        print(f"\n{'='*70}")
        print(f"🚀 PRODUÇÃO V2 - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        print(f"{'='*70}\n")
        
        results = []
        
        for ticker in tickers:
            print(f"📊 {ticker}...", end=" ")
            prev_trend = previous_trends.get(ticker)
            result = self.analyze_ticker(ticker, prev_trend)
            
            if result:
                status = result.get('action', result['signal'])
                print(f"{status} ({result['trend']})")
                results.append(result)
            else:
                print("SKIP")
        
        # Summary
        self._print_summary(results)
        
        return results
    
    def _print_summary(self, results: List[Dict]):
        """Print final table"""
        if not results:
            print("\n❌ No results")
            return
        
        print(f"\n{'='*70}")
        print(f"📊 RESUMO - {len(results)} tickers")
        print(f"{'='*70}\n")
        
        # Active positions
        active = [r for r in results if r['ticker'] in self.active_positions]
        if active:
            print(f"🟢 POSIÇÕES ATIVAS ({len(active)}):")
            print(f"{'-'*70}")
            for r in active:
                gain_pct = r.get('gain', 0) * 100
                gain_emoji = "📈" if gain_pct > 0 else "📉"
                
                print(f"  {r['ticker']:<10} "
                      f"R${r['price']:>7.2f} "
                      f"{gain_emoji} {gain_pct:>+6.2f}% "
                      f"Stop: R${r.get('stop_loss', 0):.2f} "
                      f"{'(Trailing)' if r.get('trailing_active') else ''}")
            print()
        
        # New signals
        entries = [r for r in results if r.get('action') == 'ENTER']
        exits = [r for r in results if r.get('action') == 'EXIT']
        
        if entries:
            print(f"🚀 NOVAS ENTRADAS ({len(entries)}):")
            print(f"{'-'*70}")
            for r in entries:
                print(f"  {r['ticker']:<10} "
                      f"R${r['price']:>7.2f} "
                      f"Size: {r['position_size']*100:.0f}% "
                      f"Conf: {r['confidence']:.2f}")
            print()
        
        if exits:
            print(f"🛑 SAÍDAS ({len(exits)}):")
            print(f"{'-'*70}")
            for r in exits:
                gain_pct = r.get('gain', 0) * 100
                exit_pct = r.get('exit_percentage', 0) * 100
                reason = r.get('exit_reason', 'unknown')
                
                print(f"  {r['ticker']:<10} "
                      f"R${r['price']:>7.2f} "
                      f"{gain_pct:>+6.2f}% "
                      f"Exit: {exit_pct:.0f}% "
                      f"({reason})")
            print()
        
        print(f"{'='*70}\n")


def main():
    parser = argparse.ArgumentParser(description="Production Runner V2")
    parser.add_argument("--ticker", type=str, help="Single ticker (ex: PETR4.SA)")
    parser.add_argument("--no-news", action="store_true", help="Disable news (faster)")
    
    args = parser.parse_args()
    
    runner = ProductionRunnerV2(use_news=not args.no_news)
    
    if args.ticker:
        runner.run(tickers=[args.ticker])
    else:
        runner.run()


if __name__ == "__main__":
    main()
