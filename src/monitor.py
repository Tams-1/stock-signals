"""
Real-time stock signal monitor.
Detects important signals based on SOTA value investing and technical analysis.
"""

import yfinance as yf
import pandas as pd
import sqlite3
import json
from datetime import datetime, timedelta
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent))

from signals.information_flow import InformationFlowDetector
from signals.momentum_reversal import MomentumReversalDetector

class StockSignalMonitor:
    """Monitor S&P500 stocks for important signals."""
    
    def __init__(self, db_path='stock_signals.db', lookback_days=30):
        self.db_path = db_path
        self.lookback_days = lookback_days
        self.info_detector = InformationFlowDetector(lookback_period=20)
        self.mom_detector = MomentumReversalDetector(lookback_period=20)
        self._init_db()
    
    def _init_db(self):
        """Initialize SQLite database for storing data."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Price/volume table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS ohlcv (
                ticker TEXT,
                date TEXT,
                open REAL,
                high REAL,
                low REAL,
                close REAL,
                volume REAL,
                PRIMARY KEY (ticker, date)
            )
        ''')
        
        # Signals table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS signals (
                id INTEGER PRIMARY KEY,
                ticker TEXT,
                date TEXT,
                signal_type TEXT,
                strength REAL,
                direction TEXT,
                explanation TEXT,
                timestamp TEXT
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def fetch_stock_data(self, ticker, lookback_days=None):
        """Fetch OHLCV data for a stock."""
        if lookback_days is None:
            lookback_days = self.lookback_days
        
        end_date = datetime.now()
        start_date = end_date - timedelta(days=lookback_days)
        
        try:
            data = yf.download(ticker, start=start_date, end=end_date, progress=False)
            return data
        except Exception as e:
            print(f"Error fetching {ticker}: {e}")
            return None
    
    def store_ohlcv(self, ticker, data):
        """Store OHLCV data in database."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        for date, row in data.iterrows():
            cursor.execute('''
                INSERT OR REPLACE INTO ohlcv 
                (ticker, date, open, high, low, close, volume)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                ticker,
                date.strftime('%Y-%m-%d'),
                float(row['Open']),
                float(row['High']),
                float(row['Low']),
                float(row['Close']),
                float(row['Volume'])
            ))
        
        conn.commit()
        conn.close()
    
    def detect_signals(self, ticker, data):
        """Run all signal detectors on a stock."""
        if data is None or len(data) < 20:
            return []
        
        all_signals = []
        
        # Information flow signals
        info_signals = self.info_detector.run_all(data)
        for signal_type, strength, explanation in info_signals:
            all_signals.append({
                'type': signal_type,
                'strength': strength,
                'direction': None,
                'explanation': explanation
            })
        
        # Momentum/reversal signals
        mom_signals = self.mom_detector.run_all(data)
        for signal_type, strength, direction, explanation in mom_signals:
            all_signals.append({
                'type': signal_type,
                'strength': strength,
                'direction': direction,
                'explanation': explanation
            })
        
        return all_signals
    
    def store_signals(self, ticker, signals):
        """Store detected signals in database."""
        if not signals:
            return
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        now = datetime.now()
        today = now.strftime('%Y-%m-%d')
        
        for signal in signals:
            cursor.execute('''
                INSERT INTO signals 
                (ticker, date, signal_type, strength, direction, explanation, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                ticker,
                today,
                signal['type'],
                signal['strength'],
                signal['direction'],
                signal['explanation'],
                now.isoformat()
            ))
        
        conn.commit()
        conn.close()
    
    def run_monitor(self, tickers, verbose=True):
        """Run monitor on a list of tickers."""
        all_signals = []
        
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Scanning {len(tickers)} stocks...")
        
        for i, ticker in enumerate(tickers):
            if (i + 1) % 20 == 0:
                print(f"  Processed {i + 1}/{len(tickers)}...")
            
            # Fetch data
            data = self.fetch_stock_data(ticker)
            if data is None or len(data) < 20:
                continue
            
            # Store data
            self.store_ohlcv(ticker, data)
            
            # Detect signals
            signals = self.detect_signals(ticker, data)
            if signals:
                self.store_signals(ticker, signals)
                
                for signal in signals:
                    all_signals.append({
                        'ticker': ticker,
                        'signal': signal
                    })
                
                if verbose:
                    print(f"\n🚨 {ticker}: {len(signals)} signal(s)")
                    for sig in signals:
                        print(f"   [{sig['type']}] Strength: {sig['strength']:.2f} | {sig['explanation']}")
        
        return all_signals
    
    def get_signals_summary(self):
        """Get summary of recent signals."""
        conn = sqlite3.connect(self.db_path)
        query = '''
            SELECT ticker, signal_type, strength, direction, explanation, timestamp
            FROM signals
            WHERE date = ?
            ORDER BY strength DESC
        '''
        
        today = datetime.now().strftime('%Y-%m-%d')
        df = pd.read_sql_query(query, conn, params=(today,))
        conn.close()
        
        return df

if __name__ == '__main__':
    # Load tickers
    tickers_file = '/home/ulluboz/.openclaw/workspace/stock-signals/configs/top_100_tickers.txt'
    with open(tickers_file) as f:
        tickers = [line.strip() for line in f if line.strip()]
    
    # Run monitor
    monitor = StockSignalMonitor()
    signals = monitor.run_monitor(tickers[:10])  # Start with first 10 for testing
    
    print(f"\n\nTotal signals detected: {len(signals)}")
    print("\nSignals summary:")
    summary = monitor.get_signals_summary()
    print(summary)
