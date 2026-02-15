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
import fcntl
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
import numpy as np

from src.signals.trend_detector_v2 import TrendDetectorV2
from src.news.filtered_news_client import FilteredNewsClient
from src.risk.exit_manager import ExitManager, Position
from src.analysis.decision_logger import DecisionLogger
from src.analysis.signal_analyzer import SignalAnalyzer

# 18 IBOV tickers (will expand later)
TICKERS = [
    "PETR4.SA", "VALE3.SA", "ITUB4.SA", "BBDC4.SA", "BBAS3.SA",
    "ABEV3.SA", "B3SA3.SA", "SUZB3.SA", "RENT3.SA", "WEGE3.SA",
    "MGLU3.SA", "PCAR3.SA", "LREN3.SA", "RAIZ4.SA", "GGBR4.SA",
    "ASAI3.SA", "JBSS3.SA", "RDOR3.SA"
]

POSITIONS_FILE = "active_positions.json"
HISTORY_FILE = "position_history.json"


def safe_json_read_write(filename: str, operation: str, data=None, max_retries: int = 5):
    """
    Safe JSON read/write with file locking to prevent race conditions
    
    Args:
        filename: JSON file path
        operation: 'read' or 'write'
        data: Data to write (if operation='write')
        max_retries: Maximum retry attempts
        
    Returns:
        Loaded data if operation='read', None if operation='write'
    """
    for attempt in range(max_retries):
        try:
            if operation == 'read':
                if not os.path.exists(filename):
                    return {} if filename == POSITIONS_FILE else []
                
                with open(filename, 'r') as f:
                    fcntl.flock(f, fcntl.LOCK_SH)  # Shared lock for reading
                    try:
                        return json.load(f)
                    finally:
                        fcntl.flock(f, fcntl.LOCK_UN)
            
            elif operation == 'write':
                # Write to temp file first
                temp_file = f"{filename}.tmp"
                with open(temp_file, 'w') as f:
                    fcntl.flock(f, fcntl.LOCK_EX)  # Exclusive lock for writing
                    try:
                        json.dump(data, f, indent=2)
                        f.flush()
                        os.fsync(f.fileno())  # Ensure data is written to disk
                    finally:
                        fcntl.flock(f, fcntl.LOCK_UN)
                
                # Atomic rename
                os.rename(temp_file, filename)
                return None
                
        except (IOError, OSError) as e:
            if attempt < max_retries - 1:
                time.sleep(0.1 * (attempt + 1))  # Exponential backoff
            else:
                raise e
    
    raise RuntimeError(f"Failed to {operation} {filename} after {max_retries} attempts")


class ProductionRunnerV2:
    """
    Production runner with intelligent exit management
    """
    
    def __init__(self, use_news: bool = True, use_reasoning: bool = True):
        self.trend_detector = TrendDetectorV2()
        self.exit_manager = ExitManager()
        self.use_news = use_news
        self.use_reasoning = use_reasoning
        
        if use_news:
            self.news_client = FilteredNewsClient(cache_minutes=10)
        
        if use_reasoning:
            self.decision_logger = DecisionLogger()
            self.signal_analyzer = SignalAnalyzer()
        
        # Load active positions
        self.active_positions = self._load_positions()
        
        print(f"✅ Sistema V2 inicializado (news={'ON' if use_news else 'OFF'}, reasoning={'ON' if use_reasoning else 'OFF'})")
        if self.active_positions:
            print(f"📊 {len(self.active_positions)} posições ativas carregadas")
    
    def _load_positions(self) -> Dict[str, Position]:
        """Load active positions from file with safe locking"""
        try:
            data = safe_json_read_write(POSITIONS_FILE, 'read')
            
            # Validate JSON structure
            if not isinstance(data, dict):
                print(f"⚠️ Invalid positions file format (expected dict, got {type(data)})")
                return {}
            
            # Convert JSON to Position objects
            positions = {}
            for ticker, pos_data in data.items():
                try:
                    positions[ticker] = Position(**pos_data)
                except Exception as e:
                    print(f"⚠️ Skipping invalid position for {ticker}: {e}")
            
            return positions
        except Exception as e:
            print(f"⚠️ Error loading positions: {e}")
            return {}
    
    def _save_positions(self):
        """Save active positions to file with safe locking"""
        try:
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
            
            safe_json_read_write(POSITIONS_FILE, 'write', data)
                
        except Exception as e:
            print(f"⚠️ Error saving positions: {e}")
    
    def _log_exit(self, position: Position, exit_price: float, exit_percentage: float, reason: str):
        """Log position exit to history"""
        try:
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
                
        except Exception as e:
            print(f"⚠️ Error logging exit for {position.ticker}: {e}")
    
    def get_data(self, ticker: str, days: int = 120) -> Optional[pd.DataFrame]:
        """Download recent data with error handling"""
        try:
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days)
            
            data = yf.download(
                ticker,
                start=start_date.strftime("%Y-%m-%d"),
                end=end_date.strftime("%Y-%m-%d"),
                progress=False
            )
            
            # Validate data
            if data is None or data.empty:
                print(f"    ⚠️ No data returned for {ticker}")
                return None
            
            if len(data) < 50:
                print(f"    ⚠️ Insufficient data for {ticker}: {len(data)} days (need >= 50)")
                return None
            
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
            
            # Validate required columns
            required_cols = ['Open', 'High', 'Low', 'Close', 'Volume']
            missing_cols = [col for col in required_cols if col not in data.columns]
            if missing_cols:
                print(f"    ⚠️ Missing columns for {ticker}: {missing_cols}")
                return None
            
            # Check for NaN values
            if data[required_cols].isna().any().any():
                print(f"    ⚠️ Data contains NaN values for {ticker}, forward-filling...")
                data = data.fillna(method='ffill')
            
            return data
            
        except Exception as e:
            print(f"    ❌ Error fetching data for {ticker}: {e}")
            return None
    
    def get_news_sentiment(self, ticker: str) -> float:
        """Get sentiment from last 48 hours with weighted average"""
        if not self.use_news:
            return 0.0
        
        try:
            result = self.news_client.get_ticker_sentiment(ticker, hours_back=48)
            return result.get('sentiment', 0.0)
        except Exception as e:
            print(f"    ⚠️ News error: {e}")
            return 0.0
    
    def analyze_ticker(self, ticker: str, previous_trend: Optional[str] = None) -> Dict:
        """Analyze single ticker with exit management"""
        try:
            # Download data
            data = self.get_data(ticker)
            
            if data is None or len(data) < 50:
                return None
            
            # Current price
            price_val = data['Close'].iloc[-1]
            current_price = float(price_val.item()) if hasattr(price_val, 'item') else float(price_val)
            
            # Validate price
            if pd.isna(current_price) or current_price <= 0:
                print(f"  ⚠️ Invalid price for {ticker}: {current_price}")
                return None
            
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
            
            # Boost confidence if positive news BEFORE analysis
            original_confidence = confidence
            if self.use_news and news_sentiment > 0.1 and trend == "bullish":
                confidence = min(confidence + 0.15, 1.0)
                print(f"  📰 News boost: confidence {original_confidence:.2f} → {confidence:.2f}")
            
            # Generate detailed reasoning (if enabled) - WITH BOOSTED CONFIDENCE
            reasoning = None
            if self.use_reasoning:
                try:
                    # Pass the trend_result with updated confidence
                    trend_result_updated = trend_result.copy()
                    trend_result_updated['confidence'] = confidence
                    
                    signal, decision = self.signal_analyzer.analyze_signal_with_trend(
                        ticker=ticker,
                        df=data,
                        current_price=current_price,
                        trend_result=trend_result_updated,
                        news_sentiment=news_sentiment,
                    )
                    self.decision_logger.log_decision(decision)
                    reasoning = decision.reason.primary_reason
                except Exception as e:
                    print(f"  ⚠️ Reasoning error for {ticker}: {e}")
                    reasoning = None
            
            # Check if we have an active position
            if ticker in self.active_positions:
                result = self._check_exit(ticker, data, trend, previous_trend, news_sentiment, current_price)
            else:
                result = self._check_entry(ticker, data, trend, confidence, news_sentiment, current_price)
            
            # Add reasoning to result
            if result and reasoning:
                result['reasoning'] = reasoning
            
            return result
            
        except Exception as e:
            print(f"  ❌ Error analyzing {ticker}: {e}")
            return None
    
    def _check_entry(self, ticker: str, data: pd.DataFrame, trend: str, confidence: float, news_sentiment: float, current_price: float) -> Dict:
        """Check for entry signal"""
        signal = "HOLD"
        position_size = 0.0
        action = None
        
        # Entry condition: bullish trend with confidence > 0.35
        if trend == "bullish" and confidence > 0.35:
            # Calculate position size based on confidence (already boosted if news positive)
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
        else:
            # Handle case: tighten stop without exiting (e.g. moderately negative news)
            if exit_signal.new_stop_loss:
                old_stop = position.stop_loss
                position.stop_loss = exit_signal.new_stop_loss
                self.active_positions[ticker] = position
                self._save_positions()
                print(f"  🛡️  Stop loss tightened: R${old_stop:.2f} → R${position.stop_loss:.2f}")
        
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
    
    def get_data_bulk(self, tickers: List[str], days: int = 120) -> Dict[str, pd.DataFrame]:
        """Download multiple tickers in parallel for better performance"""
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        print(f"📥 Downloading {len(tickers)} tickers in parallel...")
        
        # Download all at once (yfinance supports multiple tickers)
        try:
            data_bulk = yf.download(
                tickers,
                start=start_date.strftime("%Y-%m-%d"),
                end=end_date.strftime("%Y-%m-%d"),
                group_by='ticker',
                threads=True,  # Enable parallel downloads
                progress=False
            )
            
            result = {}
            
            # Process each ticker
            for ticker in tickers:
                try:
                    if len(tickers) == 1:
                        # Single ticker returns without ticker level
                        ticker_data = data_bulk
                    else:
                        # Multiple tickers are grouped by ticker
                        ticker_data = data_bulk[ticker]
                    
                    # Validate data
                    if ticker_data.empty or len(ticker_data) < 50:
                        print(f"  ⚠️ Insufficient data for {ticker}")
                        continue
                    
                    # Create DataFrame with standard columns
                    df = pd.DataFrame({
                        'Open': ticker_data['Open'],
                        'High': ticker_data['High'],
                        'Low': ticker_data['Low'],
                        'Close': ticker_data['Close'],
                        'Volume': ticker_data['Volume']
                    })
                    
                    # Check for NaN values and forward fill
                    if df.isna().any().any():
                        df = df.ffill()
                    
                    result[ticker] = df
                    
                except Exception as e:
                    print(f"  ❌ Error processing {ticker}: {e}")
            
            print(f"✅ Downloaded {len(result)}/{len(tickers)} tickers successfully")
            return result
            
        except Exception as e:
            print(f"❌ Bulk download failed: {e}")
            # Fallback to sequential download
            return self._download_sequential(tickers, days)
    
    def _download_sequential(self, tickers: List[str], days: int) -> Dict[str, pd.DataFrame]:
        """Fallback sequential download if bulk fails"""
        result = {}
        for ticker in tickers:
            data = self.get_data(ticker, days)
            if data is not None:
                result[ticker] = data
        return result
    
    def run(self, tickers: List[str] = None, previous_trends: Dict[str, str] = None):
        """Run analysis with parallel downloads"""
        if tickers is None:
            tickers = TICKERS
        
        if previous_trends is None:
            previous_trends = {}
        
        print(f"\n{'='*70}")
        print(f"🚀 PRODUÇÃO V2 - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        print(f"{'='*70}\n")
        
        # Download all data in parallel first
        start_time = time.time()
        all_data = self.get_data_bulk(tickers)
        download_time = time.time() - start_time
        print(f"⏱️  Download time: {download_time:.1f}s\n")
        
        results = []
        
        # Analyze each ticker with pre-downloaded data
        for ticker in tickers:
            if ticker not in all_data:
                print(f"📊 {ticker}... SKIP (no data)")
                continue
                
            print(f"📊 {ticker}...", end=" ")
            prev_trend = previous_trends.get(ticker)
            
            # Call modified analyze_ticker that accepts pre-downloaded data
            result = self.analyze_ticker_with_data(ticker, all_data[ticker], prev_trend)
            
            if result:
                status = result.get('action', result['signal'])
                print(f"{status} ({result['trend']})")
                results.append(result)
            else:
                print("SKIP")
        
        # Summary
        self._print_summary(results)
        
        return results
    
    def analyze_ticker_with_data(self, ticker: str, data: pd.DataFrame, previous_trend: Optional[str] = None) -> Dict:
        """Analyze ticker with pre-downloaded data"""
        try:
            # Current price
            price_val = data['Close'].iloc[-1]
            current_price = float(price_val.item()) if hasattr(price_val, 'item') else float(price_val)
            
            # Validate price
            if pd.isna(current_price) or current_price <= 0:
                print(f"  ⚠️ Invalid price for {ticker}: {current_price}")
                return None
            
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
            
            # Boost confidence if positive news BEFORE analysis
            original_confidence = confidence
            if self.use_news and news_sentiment > 0.1 and trend == "bullish":
                confidence = min(confidence + 0.15, 1.0)
                print(f"  📰 News boost: confidence {original_confidence:.2f} → {confidence:.2f}")
            
            # Generate detailed reasoning (if enabled) - WITH BOOSTED CONFIDENCE
            reasoning = None
            if self.use_reasoning:
                try:
                    # Pass the trend_result with updated confidence
                    trend_result_updated = trend_result.copy()
                    trend_result_updated['confidence'] = confidence
                    
                    signal, decision = self.signal_analyzer.analyze_signal_with_trend(
                        ticker=ticker,
                        df=data,
                        current_price=current_price,
                        trend_result=trend_result_updated,
                        news_sentiment=news_sentiment,
                    )
                    self.decision_logger.log_decision(decision)
                    reasoning = decision.reason.primary_reason
                except Exception as e:
                    print(f"  ⚠️ Reasoning error for {ticker}: {e}")
                    reasoning = None
            
            # Check if we have an active position
            if ticker in self.active_positions:
                result = self._check_exit(ticker, data, trend, previous_trend, news_sentiment, current_price)
            else:
                result = self._check_entry(ticker, data, trend, confidence, news_sentiment, current_price)
            
            # Add reasoning to result
            if result and reasoning:
                result['reasoning'] = reasoning
            
            return result
            
        except Exception as e:
            print(f"  ❌ Error analyzing {ticker}: {e}")
            return None
    
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
