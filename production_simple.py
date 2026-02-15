#!/usr/bin/env python3
"""
Simplified Production Runner - Working version
Generates buy/sell signals for IBOV stocks using validated backtest logic
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
import argparse
from typing import Dict, List

from src.signals.trend_detector_v2 import TrendDetectorV2
from src.news.free_news_client import FreeNewsClient

# 18 IBOV tickers
TICKERS = [
    "PETR4.SA", "VALE3.SA", "ITUB4.SA", "BBDC4.SA", "BBAS3.SA",
    "ABEV3.SA", "B3SA3.SA", "SUZB3.SA", "RENT3.SA", "WEGE3.SA",
    "MGLU3.SA", "PCAR3.SA", "LREN3.SA", "RAIZ4.SA", "GGBR4.SA",
    "ASAI3.SA", "JBSS3.SA", "RDOR3.SA"
]

class SimpleProductionRunner:
    """Simple production runner using only validated TrendDetectorV2"""
    
    def __init__(self, use_news: bool = True):
        self.trend_detector = TrendDetectorV2()
        self.use_news = use_news
        if use_news:
            self.news_client = FreeNewsClient()
        
        print(f"✅ Sistema inicializado (news={'ON' if use_news else 'OFF'})")
    
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
    
    def analyze_ticker(self, ticker: str) -> Dict:
        """Analyze single ticker"""
        try:
            # Download data
            data = self.get_data(ticker)
            
            if len(data) < 50:
                return None
            
            # Current price
            price_val = data['Close'].iloc[-1]
            current_price = float(price_val.item()) if hasattr(price_val, 'item') else float(price_val)
            
            # Trend detection (core validated logic)
            trend_result = self.trend_detector.detect_trend(data)
            consensus = trend_result.get('consensus', 'unknown')
            confidence = trend_result.get('confidence', 0.0)
            
            # Map consensus to simple trend
            if consensus in ['uptrend', 'bull_pullback']:
                trend = "uptrend"
            elif consensus in ['downtrend', 'bear_bounce']:
                trend = "downtrend"
            else:
                trend = "neutral"
            
            # News sentiment (if enabled)
            news_sentiment = self.get_news_sentiment(ticker)
            
            # Simple signal logic (validated in backtest)
            signal = "HOLD"
            position_size = 0.0
            conviction = 0.0
            
            if trend == "uptrend" and confidence > 0.35:
                # Add news boost if positive
                if self.use_news and news_sentiment > 0.1:
                    signal = "BUY"
                    conviction = 0.7 + (news_sentiment * 0.3)  # 0.7-1.0 range
                    position_size = 0.70  # High conviction
                else:
                    signal = "BUY"
                    conviction = confidence
                    position_size = 0.50  # Medium conviction
            elif trend == "downtrend" and confidence > 0.35:
                signal = "SELL"
                conviction = -confidence
                position_size = 1.0  # Exit
            
            return {
                "ticker": ticker,
                "price": current_price,
                "trend": trend,
                "news_sentiment": news_sentiment,
                "signal": signal,
                "conviction": conviction,
                "position_size": position_size
            }
            
        except Exception as e:
            print(f"  ❌ Error: {e}")
            return None
    
    def run(self, tickers: List[str] = None):
        """Run analysis"""
        if tickers is None:
            tickers = TICKERS
        
        print(f"\n{'='*70}")
        print(f"🚀 PRODUÇÃO - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        print(f"{'='*70}\n")
        
        results = []
        
        for ticker in tickers:
            print(f"📊 {ticker}...", end=" ")
            result = self.analyze_ticker(ticker)
            if result:
                print(f"{result['signal']} ({result['trend']})")
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
        
        # Sort by conviction
        results_sorted = sorted(results, key=lambda x: abs(x['conviction']), reverse=True)
        
        print(f"\n{'='*70}")
        print(f"📊 RESUMO - {len(results)} tickers")
        print(f"{'='*70}\n")
        
        # Header
        print(f"{'Ticker':<10} {'Preço':>8} {'Sinal':<6} {'Trend':<10} {'News':>6} {'Pos%':>5}")
        print(f"{'-'*70}")
        
        # Rows
        for r in results_sorted:
            signal_emoji = {
                "BUY": "🟢",
                "SELL": "🔴",
                "HOLD": "⚪"
            }[r['signal']]
            
            pos_pct = f"{r['position_size']*100:.0f}%" if r['position_size'] > 0 else "-"
            news_str = f"{r['news_sentiment']:+.2f}" if self.use_news else "N/A"
            
            print(
                f"{r['ticker']:<10} "
                f"R${r['price']:>7.2f} "
                f"{signal_emoji} {r['signal']:<4} "
                f"{r['trend']:<10} "
                f"{news_str:>6} "
                f"{pos_pct:>5}"
            )
        
        # Stats
        buy = [r for r in results if r['signal'] == "BUY"]
        sell = [r for r in results if r['signal'] == "SELL"]
        
        print(f"\n{'-'*70}")
        print(f"🟢 BUY: {len(buy)} | 🔴 SELL: {len(sell)} | ⚪ HOLD: {len(results) - len(buy) - len(sell)}")
        print(f"{'='*70}\n")


def main():
    parser = argparse.ArgumentParser(description="Simple Production Runner")
    parser.add_argument("--ticker", type=str, help="Single ticker (ex: PETR4.SA)")
    parser.add_argument("--no-news", action="store_true", help="Disable news (faster)")
    
    args = parser.parse_args()
    
    runner = SimpleProductionRunner(use_news=not args.no_news)
    
    if args.ticker:
        runner.run(tickers=[args.ticker])
    else:
        runner.run()


if __name__ == "__main__":
    main()
