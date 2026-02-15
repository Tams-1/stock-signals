#!/usr/bin/env python3
"""
Market Monitor V3 - With detailed reasoning for every signal change
Logs all decisions with complete technical analysis and explanations
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List

from src.analysis.signal_analyzer import SignalAnalyzer
from src.news.filtered_news_client import FilteredNewsClient

# Load validated tickers
import json
with open("data/validated_tickers.json", 'r') as f:
    ticker_data = json.load(f)
    TICKERS = ticker_data['all_tickers']

STATE_FILE = "monitor_state_v3.json"
ALERT_FILE = "monitor_alerts.txt"


class MarketMonitorV3:
    """Market monitor with detailed decision logging"""
    
    def __init__(self, use_news: bool = True):
        self.analyzer = SignalAnalyzer()
        self.use_news = use_news
        
        if use_news:
            self.news_client = FilteredNewsClient(cache_minutes=10)
        
        print(f"✅ Monitor V3 inicializado (news={'ON' if use_news else 'OFF'})")
        print(f"📊 Monitorando {len(TICKERS)} tickers")
    
    def get_data(self, ticker: str, days: int = 120) -> pd.DataFrame:
        """Download historical data"""
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        data = yf.download(
            ticker,
            start=start_date.strftime("%Y-%m-%d"),
            end=end_date.strftime("%Y-%m-%d"),
            progress=False
        )
        
        # Flatten MultiIndex if needed
        if isinstance(data.columns, pd.MultiIndex):
            data.columns = [col[0] for col in data.columns.values]
        
        return data
    
    def get_news_context(self, ticker: str):
        """Get news sentiment and summary"""
        if not self.use_news:
            return None, None, None
        
        try:
            result = self.news_client.get_ticker_sentiment(ticker, hours_back=24)
            return (
                result['sentiment'],
                result['article_count'],
                result['summary']
            )
        except Exception as e:
            print(f"⚠️ News error for {ticker}: {e}")
            return None, None, None
    
    def monitor_ticker(self, ticker: str):
        """Monitor a single ticker and log detailed analysis"""
        try:
            # Download data
            data = self.get_data(ticker)
            
            if len(data) < 50:
                return None
            
            # Get current price
            current_price = float(data['Close'].iloc[-1])
            
            # Get news context
            news_sentiment, news_count, news_summary = self.get_news_context(ticker)
            
            # Analyze with full reasoning
            signal, decision = self.analyzer.analyze_signal(
                ticker=ticker,
                df=data,
                current_price=current_price,
                news_sentiment=news_sentiment,
                news_count=news_count,
                news_summary=news_summary
            )
            
            return {
                'ticker': ticker,
                'signal': signal,
                'changed': decision.signal_changed,
                'decision': decision,
            }
            
        except Exception as e:
            print(f"❌ Error analyzing {ticker}: {e}")
            return None
    
    def write_alert(self, alert_text: str):
        """Write alert to file"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        with open(ALERT_FILE, 'a') as f:
            f.write(f"[{timestamp}] {alert_text}\n")
    
    def run(self):
        """Run market monitor"""
        print(f"\n{'='*70}")
        print(f"🔍 Market Monitor V3 - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        print(f"{'='*70}\n")
        
        results = []
        signal_changes = []
        
        # Analyze all tickers
        for i, ticker in enumerate(TICKERS, 1):
            print(f"[{i}/{len(TICKERS)}] {ticker}...", end=" ", flush=True)
            
            result = self.monitor_ticker(ticker)
            
            if result:
                results.append(result)
                
                if result['changed']:
                    signal_changes.append(result)
                    print(f"🔔 {result['decision'].previous_signal} → {result['signal']}")
                else:
                    print(f"{result['signal']}")
            else:
                print("SKIP")
        
        # Report signal changes with detailed reasoning
        if signal_changes:
            print(f"\n{'='*70}")
            print(f"🚨 {len(signal_changes)} MUDANÇAS DE SINAL DETECTADAS")
            print(f"{'='*70}\n")
            
            for change in signal_changes:
                decision = change['decision']
                
                # Print detailed report
                report = self.analyzer.logger.format_decision_report(decision)
                print(report)
                
                # Write alert
                alert_summary = (
                    f"{decision.ticker}: {decision.previous_signal} → {decision.current_signal} | "
                    f"Razão: {decision.reason.primary_reason}"
                )
                self.write_alert(alert_summary)
        else:
            print(f"\n✅ Nenhuma mudança de sinal")
        
        # Summary
        buy_count = len([r for r in results if r['signal'] == "BUY"])
        sell_count = len([r for r in results if r['signal'] == "SELL"])
        hold_count = len([r for r in results if r['signal'] == "HOLD"])
        
        print(f"\n{'='*70}")
        print(f"📊 RESUMO")
        print(f"{'='*70}")
        print(f"🟢 BUY: {buy_count}")
        print(f"🔴 SELL: {sell_count}")
        print(f"⚪ HOLD: {hold_count}")
        print(f"🔔 Mudanças: {len(signal_changes)}")
        print(f"{'='*70}\n")


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Market Monitor V3")
    parser.add_argument("--no-news", action="store_true", help="Disable news (faster)")
    parser.add_argument("--ticker", type=str, help="Monitor single ticker")
    
    args = parser.parse_args()
    
    monitor = MarketMonitorV3(use_news=not args.no_news)
    
    if args.ticker:
        # Single ticker mode
        global TICKERS
        TICKERS = [args.ticker]
    
    monitor.run()


if __name__ == "__main__":
    main()
