"""
Production real-time signal monitor daemon.
Runs every minute to detect signals on all 100 stocks.
Correlates technical signals with news sentiment.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

import yfinance as yf
import pandas as pd
import sqlite3
import json
from datetime import datetime, timedelta
import time

from signals.information_flow import InformationFlowDetector
from signals.momentum_reversal import MomentumReversalDetector
from data.news_sentiment import NewsSentimentAnalyzer

class SignalDaemon:
    """Production daemon for real-time stock signal detection."""
    
    def __init__(self, db_path='stock_signals.db', api_key='demo'):
        self.db_path = db_path
        self.info_detector = InformationFlowDetector()
        self.mom_detector = MomentumReversalDetector()
        self.news_analyzer = NewsSentimentAnalyzer(api_key=api_key)
        self._init_db()
    
    def _init_db(self):
        """Initialize database tables."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS ohlcv (
                ticker TEXT,
                timestamp TEXT,
                open REAL,
                high REAL,
                low REAL,
                close REAL,
                volume REAL,
                PRIMARY KEY (ticker, timestamp)
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS signals_realtime (
                id INTEGER PRIMARY KEY,
                ticker TEXT,
                timestamp TEXT,
                signal_type TEXT,
                strength REAL,
                direction TEXT,
                explanation TEXT,
                news_sentiment TEXT,
                confidence REAL,
                created_at TEXT
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS alerts (
                id INTEGER PRIMARY KEY,
                ticker TEXT,
                timestamp TEXT,
                signals TEXT,
                news_summary TEXT,
                confidence REAL,
                action TEXT,
                created_at TEXT
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def fetch_1min_data(self, ticker):
        """Fetch 1-minute OHLCV for signal detection."""
        try:
            # Get last 60 minutes of 1-min bars
            data = yf.download(ticker, period='60m', interval='1m', progress=False)
            return data
        except Exception as e:
            return None
    
    def fetch_daily_data(self, ticker, days=20):
        """Fetch daily data for context."""
        try:
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days)
            data = yf.download(ticker, start=start_date, end=end_date, progress=False)
            return data
        except Exception as e:
            return None
    
    def detect_signals(self, ticker, intraday_data, daily_data):
        """Detect signals on intraday and daily data."""
        signals = []
        
        # Use daily data for signal detection (more stable)
        if daily_data is not None and len(daily_data) >= 20:
            # Information flow
            info_sigs = self.info_detector.run_all(daily_data)
            for sig_type, strength, explanation in info_sigs:
                signals.append({
                    'type': sig_type,
                    'strength': strength,
                    'direction': None,
                    'explanation': explanation,
                    'source': 'technical'
                })
            
            # Momentum/reversal
            mom_sigs = self.mom_detector.run_all(daily_data)
            for sig_type, strength, direction, explanation in mom_sigs:
                signals.append({
                    'type': sig_type,
                    'strength': strength,
                    'direction': direction,
                    'explanation': explanation,
                    'source': 'technical'
                })
        
        return signals
    
    def assess_confidence(self, signals, news_sentiment):
        """
        Assess overall confidence by combining technical signals + news sentiment.
        Higher confidence = multiple signals + supportive news.
        """
        if not signals:
            return 0, "No signals"
        
        # Count signals and average strength
        avg_strength = sum(s['strength'] for s in signals) / len(signals)
        signal_count = len(signals)
        
        # Check if signals agree (same direction)
        directions = [s['direction'] for s in signals if s['direction']]
        if directions:
            same_direction = all(d == directions[0] for d in directions)
        else:
            same_direction = False
        
        # Combine with news sentiment
        confidence = avg_strength
        
        if news_sentiment:
            news_strength, news_direction, news_exp = news_sentiment
            
            # Boost confidence if news agrees with signal direction
            if signal_count > 0 and news_strength > 0:
                if same_direction and directions and directions[0] == news_direction:
                    confidence = min((confidence + news_strength) / 2 * 1.3, 1.0)  # 30% boost
                    status = f"Confirmed: {signal_count} signals + {news_direction} news"
                else:
                    status = f"Mixed: {signal_count} signals, {news_direction} news"
            else:
                status = f"{signal_count} signals (no news context)"
        else:
            status = f"{signal_count} signals (no news yet)"
        
        return confidence, status
    
    def scan_ticker(self, ticker, fetch_news=False):
        """Scan a single ticker for signals."""
        try:
            # Fetch data
            daily_data = self.fetch_daily_data(ticker, days=30)
            
            if daily_data is None or len(daily_data) < 20:
                return None
            
            # Detect technical signals
            signals = self.detect_signals(ticker, None, daily_data)
            
            # Fetch and analyze news
            news_sentiment = None
            if fetch_news and signals:  # Only fetch news if we have signals
                articles = self.news_analyzer.fetch_news(ticker, days=1)
                if articles:
                    news_strength, news_dir, news_exp = self.news_analyzer.get_sentiment_signal(ticker, articles)
                    if news_strength > 0:
                        news_sentiment = (news_strength, news_dir, news_exp)
                        self.news_analyzer.store_news(ticker, articles)
            
            # Assess overall confidence
            confidence, status = self.assess_confidence(signals, news_sentiment)
            
            if signals and confidence > 0.4:  # Only alert on moderate+ confidence
                return {
                    'ticker': ticker,
                    'timestamp': datetime.now().isoformat(),
                    'signals': signals,
                    'news_sentiment': news_sentiment,
                    'confidence': confidence,
                    'status': status
                }
        except Exception as e:
            print(f"Error scanning {ticker}: {e}")
        
        return None
    
    def run_scan(self, tickers, fetch_news=False):
        """Run a full scan on all tickers."""
        print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Scanning {len(tickers)} stocks...")
        
        alerts = []
        
        for i, ticker in enumerate(tickers):
            result = self.scan_ticker(ticker, fetch_news=fetch_news)
            
            if result:
                alerts.append(result)
                
                print(f"\n🚨 {ticker} | Confidence: {result['confidence']:.2f}")
                print(f"   Status: {result['status']}")
                
                for sig in result['signals']:
                    print(f"   - [{sig['type']}] {sig['strength']:.2f}: {sig['explanation']}")
                
                if result['news_sentiment']:
                    _, direction, news_exp = result['news_sentiment']
                    print(f"   📰 News: {news_exp}")
        
        return alerts
    
    def save_alerts(self, alerts):
        """Save alerts to database."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        now = datetime.now().isoformat()
        
        for alert in alerts:
            signals_json = json.dumps(alert['signals'])
            news_json = json.dumps(alert['news_sentiment']) if alert['news_sentiment'] else None
            
            cursor.execute('''
                INSERT INTO alerts 
                (ticker, timestamp, signals, news_summary, confidence, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                alert['ticker'],
                alert['timestamp'],
                signals_json,
                news_json,
                alert['confidence'],
                now
            ))
        
        conn.commit()
        conn.close()

def run_continuous_monitor(tickers, interval_seconds=60, fetch_news=True):
    """Run daemon continuously (every minute)."""
    daemon = SignalDaemon()
    
    print(f"Starting stock signal daemon...")
    print(f"Monitoring {len(tickers)} stocks every {interval_seconds} seconds")
    print(f"News sentiment analysis: {'ENABLED' if fetch_news else 'DISABLED'}")
    
    iteration = 0
    while True:
        iteration += 1
        try:
            alerts = daemon.run_scan(tickers, fetch_news=fetch_news)
            if alerts:
                daemon.save_alerts(alerts)
                print(f"\n✅ {len(alerts)} alerts saved")
        except KeyboardInterrupt:
            print("\n\nDaemon stopped.")
            break
        except Exception as e:
            print(f"Scan error: {e}")
        
        print(f"\nNext scan in {interval_seconds} seconds... (iteration {iteration})")
        time.sleep(interval_seconds)

if __name__ == '__main__':
    # Load tickers
    tickers_file = Path(__file__).parent.parent / 'configs/top_100_tickers.txt'
    with open(tickers_file) as f:
        tickers = [line.strip() for line in f if line.strip()]
    
    # Run for first 10 tickers (testing)
    # Use `run_continuous_monitor(tickers, interval_seconds=60)` for production
    daemon = SignalDaemon()
    alerts = daemon.run_scan(tickers[:10], fetch_news=False)
    
    print(f"\n\nTotal alerts: {len(alerts)}")
    if alerts:
        daemon.save_alerts(alerts)
