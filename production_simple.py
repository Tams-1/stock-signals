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

# IBOV Active Tickers (65 valid stocks - delisted removed)
IBOV_TICKERS = [
    'PETR4.SA', 'VALE3.SA', 'ITUB4.SA', 'BBDC4.SA', 'BBAS3.SA', 'ABEV3.SA',
    'B3SA3.SA', 'SUZB3.SA', 'RENT3.SA', 'WEGE3.SA', 'MGLU3.SA', 'PCAR3.SA',
    'LREN3.SA', 'RAIZ4.SA', 'GGBR4.SA', 'ASAI3.SA', 'RDOR3.SA',
    'PETR3.SA', 'ITSA4.SA', 'BBDC3.SA', 'CMIG4.SA', 'ENGI11.SA', 'EQTL3.SA',
    'GGPS3.SA', 'GOAU4.SA', 'HAPV3.SA', 'HYPE3.SA', 'IGTI11.SA',
    'IRBR3.SA', 'KLBN11.SA', 'LWSA3.SA', 'MRVE3.SA', 'MULT3.SA',
    'PRIO3.SA', 'QUAL3.SA', 'RAIL3.SA', 'RADL3.SA',
    'SANB11.SA', 'SBSP3.SA', 'SMTO3.SA', 'TAEE11.SA', 'TIMS3.SA',
    'TOTS3.SA', 'UGPA3.SA', 'USIM5.SA', 'VBBR3.SA', 'VIVT3.SA',
    'YDUQ3.SA', 'AZUL4.SA', 'BPAC11.SA', 'CASH3.SA',
    'COGN3.SA', 'CPFE3.SA', 'CSAN3.SA', 'CVCB3.SA',
    'ECOR3.SA', 'FLRY3.SA', 'RECV3.SA', 'BEEF3.SA', 'CYRE3.SA', 'DXCO3.SA',
    'SLCE3.SA', 'VIVA3.SA', 'ALOS3.SA', 'ALPA4.SA'
]

SMLL_TICKERS = [
    'AURE3.SA', 'BMOB3.SA', 'BRAP4.SA', 'CMIN3.SA', 'DIRR3.SA', 'ESPA3.SA',
    'EVEN3.SA', 'GRND3.SA', 'IFCM3.SA', 'KEPL3.SA', 'LAVV3.SA', 'LEVE3.SA',
    'MDIA3.SA', 'MILS3.SA', 'ODPV3.SA', 'ORVR3.SA', 'POMO4.SA', 'POSI3.SA',
    'PSSA3.SA', 'PTBL3.SA', 'RAPT4.SA', 'SAPR11.SA', 'SEQL3.SA', 'SIMH3.SA',
    'TEND3.SA', 'TGMA3.SA', 'TRIS3.SA', 'UNIP6.SA', 'VLID3.SA',
    'AMBP3.SA', 'AMAR3.SA', 'BMGB4.SA', 'BRKM5.SA', 'CSED3.SA',
    'DESK3.SA', 'EZTC3.SA', 'FESA4.SA', 'GGBR3.SA', 'GMAT3.SA', 'HBOR3.SA',
    'JHSF3.SA', 'JSLG3.SA', 'LIGT3.SA', 'LPSB3.SA', 'MTRE3.SA',
    'ONCO3.SA', 'OPCT3.SA', 'PINE4.SA', 'PRNR3.SA', 'RANI3.SA', 'ROMI3.SA',
    'SEER3.SA', 'SGPS3.SA', 'SOJA3.SA', 'TCSA3.SA',
    'TFCO4.SA', 'TUPY3.SA', 'UCAS3.SA', 'VULC3.SA', 'WIZC3.SA', 'ALUP11.SA',
    'AZZA3.SA', 'BLAU3.SA',
    'CEAB3.SA', 'CGRA4.SA', 'CTSA3.SA', 'FHER3.SA',
    'FRAS3.SA', 'GFSA3.SA', 'HETA4.SA', 'INTB3.SA', 'JFEN3.SA',
    'LOGN3.SA', 'LOGG3.SA', 'MEAL3.SA',
    'MELK3.SA', 'MGEL4.SA', 'MOVI3.SA', 'MRSA3B.SA', 'NEOE3.SA', 'PGMN3.SA',
    'PLPL3.SA', 'PRNR3.SA', 'SHUL4.SA', 'SYNE3.SA'
]

TICKERS = IBOV_TICKERS + SMLL_TICKERS  # 184 total

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
    
    def get_news_sentiment(self, ticker: str) -> dict:
        """Get sentiment from last 3 days (newsdata.io + cache)"""
        if not self.use_news:
            return {"sentiment": 0.0, "articles": [], "dates": []}
        
        try:
            sentiments = []
            dates = []
            
            # Fetch sentiment for last 3 days using FreeNewsClient
            # (which handles newsdata.io + Investing.com fallback + caching)
            for days_ago in range(3):
                date = (datetime.now() - timedelta(days=days_ago)).strftime("%Y-%m-%d")
                sent = self.news_client.get_sentiment(ticker, date)
                sentiments.append(sent)
                dates.append(date)
            
            avg_sentiment = sum(sentiments) / len(sentiments) if sentiments else 0.0
            
            return {
                "sentiment": avg_sentiment,
                "articles": [],  # Already cached in news_client.cache
                "dates": dates,
                "daily_scores": dict(zip(dates, sentiments))
            }
        except Exception as e:
            print(f"    ⚠️ News error: {e}")
            return {"sentiment": 0.0, "articles": [], "dates": []}
    
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
            
            # Print trend details
            print(f"\n     [TREND] {consensus} @ {confidence:.1%} confidence")
            
            # Map consensus to simple trend
            if consensus in ['uptrend', 'bull_pullback']:
                trend = "uptrend"
            elif consensus in ['downtrend', 'bear_bounce']:
                trend = "downtrend"
            else:
                trend = "neutral"
            
            # News sentiment (if enabled)
            if self.use_news:
                print(f"     [NEWS] newsdata.io...", end=" ", flush=True)
            
            news_data = self.get_news_sentiment(ticker)
            news_sentiment = news_data.get("sentiment", 0.0)
            news_articles = news_data.get("articles", [])
            
            if self.use_news and news_articles:
                print(f"✅ {len(news_articles)} articles, sentiment: {news_sentiment:+.2f}")
            elif self.use_news:
                print(f"⚠️  No articles found, sentiment: {news_sentiment:+.2f}")
            
            # Improved signal logic with higher threshold and proportional sizing
            signal = "HOLD"
            position_size = 0.0
            conviction = 0.0
            
            # Minimum confidence threshold: 50% (more conservative)
            MIN_CONFIDENCE = 0.50
            
            if trend == "uptrend" and confidence >= MIN_CONFIDENCE:
                signal = "BUY"
                conviction = confidence
                
                # Proportional position sizing based on confidence
                if confidence >= 0.90:
                    position_size = 0.80  # Very high confidence
                elif confidence >= 0.75:
                    position_size = 0.60  # High confidence
                elif confidence >= 0.60:
                    position_size = 0.40  # Medium-high confidence
                else:  # 0.50-0.60
                    position_size = 0.20  # Medium confidence
                
                # News boost: +10-20% position size if positive sentiment
                if self.use_news and news_sentiment > 0.1:
                    boost = news_sentiment * 0.20  # Up to 20% boost
                    position_size = min(1.0, position_size + boost)
                    conviction = min(1.0, conviction + (news_sentiment * 0.1))
                    
            elif trend == "downtrend" and confidence >= MIN_CONFIDENCE:
                signal = "SELL"
                conviction = -confidence
                position_size = 1.0  # Exit completely
            
            return {
                "ticker": ticker,
                "price": current_price,
                "trend": trend,
                "news_sentiment": news_sentiment,
                "news_articles": news_articles,
                "signal": signal,
                "conviction": conviction,
                "position_size": position_size
            }
            
        except Exception as e:
            print(f"  ❌ Error: {e}")
            return None
    
    def get_top_movers(self, results: List[Dict], top_n: int = 10) -> List[str]:
        """
        Identify top movers from analysis results.
        
        Used for smart news fetching: fetch fresh news only for high-conviction signals.
        
        Args:
            results: List of analysis results
            top_n: Number of top movers to return
        
        Returns:
            List of top mover tickers
        """
        if not results:
            return []
        
        # Sort by absolute conviction (both BUY and SELL signals matter)
        sorted_results = sorted(results, key=lambda x: abs(x.get('conviction', 0)), reverse=True)
        
        # Get top N tickers
        top_movers = [r['ticker'] for r in sorted_results[:top_n]]
        
        print(f"\n📊 Top {top_n} Movers (for smart news refresh):")
        for i, ticker in enumerate(top_movers, 1):
            result = next(r for r in sorted_results if r['ticker'] == ticker)
            print(f"   [{i}] {ticker} - {result['signal']} ({result['trend']}, conviction: {result['conviction']:.2f})")
        
        return top_movers
    
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
        
        # News details (if enabled)
        if self.use_news:
            print(f"\n{'='*70}")
            print(f"📰 NEWS ANALYSIS DETAILS")
            print(f"{'='*70}\n")
            
            for r in results_sorted:
                articles = r.get('news_articles', [])
                sentiment = r.get('news_sentiment', 0.0)
                
                if articles:
                    print(f"📊 {r['ticker']} - Sentiment: {sentiment:+.2f} ({len(articles)} articles)")
                    for i, article in enumerate(articles[:3], 1):  # Show top 3 articles
                        title = article.get('title', 'No title')[:70]
                        art_sentiment = article.get('sentiment', 0.0)
                        date = article.get('date', 'N/A')
                        print(f"   [{i}] ({art_sentiment:+.2f}) {title}...")
                        print(f"       Date: {date} | Source: {article.get('source', 'unknown')}")
                    if len(articles) > 3:
                        print(f"   ... and {len(articles) - 3} more articles")
                else:
                    print(f"📊 {r['ticker']} - No news found (Sentiment: {sentiment:+.2f})")
                print()


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
