"""
Backtest signal detection on historical data.
Measure signal quality: how often do signals precede significant moves?
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
from src.signals.information_flow import InformationFlowDetector
from src.signals.momentum_reversal import MomentumReversalDetector

class SignalBacktest:
    """Backtest signals on historical data."""
    
    def __init__(self, lookback_days=252, test_days=30):
        self.lookback_days = lookback_days
        self.test_days = test_days
        self.info_detector = InformationFlowDetector()
        self.mom_detector = MomentumReversalDetector()
    
    def test_ticker(self, ticker, start_date, end_date):
        """Test signal detection on historical data for a ticker."""
        print(f"\nBacktesting {ticker}...")
        
        try:
            data = yf.download(ticker, start=start_date, end=end_date, progress=False)
        except:
            print(f"  Failed to fetch {ticker}")
            return None
        
        if len(data) < 50:
            return None
        
        signals_detected = []
        price_moves = []
        
        # Slide a window through the data
        window_size = 20
        for i in range(window_size, len(data) - self.test_days):
            window = data.iloc[i-window_size:i]
            
            # Detect signals
            info_sigs = self.info_detector.run_all(window)
            mom_sigs = self.mom_detector.run_all(window)
            
            has_signal = len(info_sigs) > 0 or len(mom_sigs) > 0
            
            if has_signal:
                # Measure future price move
                signal_date = window.index[-1]
                future_close = data.iloc[i + self.test_days]['Close']
                current_close = window.iloc[-1]['Close']
                future_move = (future_close - current_close) / current_close
                
                signals_detected.append({
                    'date': signal_date,
                    'info_signals': len(info_sigs),
                    'mom_signals': len(mom_sigs),
                    'total_signals': len(info_sigs) + len(mom_sigs),
                    'future_move_pct': future_move * 100
                })
        
        if not signals_detected:
            print(f"  No signals detected")
            return None
        
        # Analyze results
        df = pd.DataFrame(signals_detected)
        avg_move = df['future_move_pct'].mean()
        positive_moves = (df['future_move_pct'] > 0).sum()
        accuracy = positive_moves / len(df) * 100
        
        print(f"  Signals: {len(df)} detected")
        print(f"  Accuracy (upside): {accuracy:.1f}%")
        print(f"  Avg move: {avg_move:.2f}%")
        print(f"  Max move: {df['future_move_pct'].max():.2f}%")
        print(f"  Min move: {df['future_move_pct'].min():.2f}%")
        
        return {
            'ticker': ticker,
            'signals_count': len(df),
            'accuracy': accuracy,
            'avg_move': avg_move,
            'data': df
        }
    
    def run_backtest(self, tickers, test_months=6):
        """Run backtest on multiple tickers."""
        end_date = datetime.now()
        start_date = end_date - timedelta(days=30 * test_months)
        
        print(f"Backtesting {len(tickers)} stocks from {start_date.date()} to {end_date.date()}...")
        print(f"Testing {self.test_days}-day forward returns on signal days\n")
        
        results = []
        for i, ticker in enumerate(tickers):
            if (i + 1) % 10 == 0:
                print(f"Progress: {i + 1}/{len(tickers)}...")
            
            result = self.test_ticker(ticker, start_date, end_date)
            if result:
                results.append(result)
        
        # Summary
        print("\n" + "=" * 70)
        print("BACKTEST SUMMARY")
        print("=" * 70)
        
        if results:
            df_summary = pd.DataFrame([{
                'ticker': r['ticker'],
                'signals': r['signals_count'],
                'accuracy': r['accuracy'],
                'avg_move': r['avg_move']
            } for r in results])
            
            df_summary = df_summary.sort_values('avg_move', ascending=False)
            print(df_summary.to_string())
            
            print(f"\nAverage accuracy: {df_summary['accuracy'].mean():.1f}%")
            print(f"Average move: {df_summary['avg_move'].mean():.2f}%")
            print(f"Total signals: {df_summary['signals'].sum()}")
        
        return results

if __name__ == '__main__':
    backtest = SignalBacktest(test_days=5)
    
    # Test on a few tickers
    test_tickers = ['AAPL', 'MSFT', 'NVDA', 'TSLA', 'GOOGL']
    results = backtest.run_backtest(test_tickers, test_months=3)
