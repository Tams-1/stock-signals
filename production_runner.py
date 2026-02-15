#!/usr/bin/env python3
"""
Production Runner - Sistema de sinais em tempo real
Executa diariamente para gerar sinais de compra/venda com conviction scoring

Uso:
    python3 production_runner.py [--ticker PETR4.SA] [--days 7]
    
    --ticker: Analisar ticker específico (default: todos os 18 IBOV)
    --days: Janela de notícias (default: 7 dias)
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
import argparse
from typing import Dict, List, Tuple

from src.signals.trend_detector_v2 import TrendDetectorV2
from src.signals.momentum_detector import MomentumDetector
from src.news.free_news_client import FreeNewsClient
from src.signals.regime_detector import RegimeDetector
from src.signals.conviction_scorer import ConvictionScorer

# 18 IBOV tickers
TICKERS = [
    "PETR4.SA", "VALE3.SA", "ITUB4.SA", "BBDC4.SA", "BBAS3.SA",
    "ABEV3.SA", "B3SA3.SA", "SUZB3.SA", "RENT3.SA", "WEGE3.SA",
    "MGLU3.SA", "PCAR3.SA", "LREN3.SA", "RAIZ4.SA", "GGBR4.SA",
    "ASAI3.SA", "JBSS3.SA", "RDOR3.SA"
]

class ProductionRunner:
    """Produção: sinais diários com conviction scoring"""
    
    def __init__(self, lookback_days: int = 120, news_window_days: int = 7):
        self.lookback_days = lookback_days
        self.news_window_days = news_window_days
        
        # Initialize components
        self.trend_detector = TrendDetectorV2()
        self.momentum_detector = MomentumDetector()
        self.news_client = FreeNewsClient()
        self.regime_detector = RegimeDetector()
        self.conviction_scorer = ConvictionScorer()
        
        print(f"✅ Sistema inicializado (lookback={lookback_days}d, news_window={news_window_days}d)")
    
    def get_recent_data(self, ticker: str) -> pd.DataFrame:
        """Baixa dados recentes do ticker"""
        end_date = datetime.now()
        start_date = end_date - timedelta(days=self.lookback_days)
        
        data = yf.download(
            ticker,
            start=start_date.strftime("%Y-%m-%d"),
            end=end_date.strftime("%Y-%m-%d"),
            progress=False
        )
        
        return data
    
    def get_technical_signals(self, ticker: str, data: pd.DataFrame) -> Dict:
        """Calcula sinais técnicos (trend + momentum)"""
        if len(data) < 50:
            return {"trend": None, "momentum": None, "score": 0.0}
        
        # Trend (TrendDetectorV2)
        trend = self.trend_detector.detect_trend(data)
        
        # Momentum
        momentum_result = self.momentum_detector.detect_momentum(data)
        momentum = momentum_result.get("signal", "neutral")
        
        # Combined score
        trend_score = 1.0 if trend == "uptrend" else (-1.0 if trend == "downtrend" else 0.0)
        momentum_score = 1.0 if momentum == "bullish" else (-1.0 if momentum == "bearish" else 0.0)
        
        tech_score = (trend_score + momentum_score) / 2
        
        return {
            "trend": trend,
            "momentum": momentum,
            "score": tech_score
        }
    
    def get_news_sentiment(self, ticker: str) -> float:
        """Busca sentiment de notícias recentes (últimos N dias)"""
        end_date = datetime.now()
        start_date = end_date - timedelta(days=self.news_window_days)
        
        try:
            sentiment = self.news_client.get_sentiment(
                ticker,
                start_date.strftime("%Y-%m-%d"),
                end_date.strftime("%Y-%m-%d")
            )
            return sentiment
        except Exception as e:
            print(f"  ⚠️ Erro buscando news para {ticker}: {e}")
            return 0.0
    
    def get_regime(self, data: pd.DataFrame) -> str:
        """Detecta regime de mercado"""
        if len(data) < 50:
            return "neutral"
        
        return self.regime_detector.detect_regime(data)
    
    def analyze_ticker(self, ticker: str) -> Dict:
        """Análise completa de um ticker"""
        print(f"\n{'='*60}")
        print(f"📊 Analisando {ticker}")
        print(f"{'='*60}")
        
        # 1. Download data
        print("  📥 Baixando dados...")
        data = self.get_recent_data(ticker)
        
        if len(data) < 50:
            print(f"  ❌ Dados insuficientes ({len(data)} dias)")
            return None
        
        current_price = data['Close'].iloc[-1]
        if hasattr(current_price, 'item'):
            current_price = current_price.item()
        
        # 2. Technical signals
        print("  📈 Calculando sinais técnicos...")
        tech = self.get_technical_signals(ticker, data)
        
        # 3. News sentiment
        print(f"  📰 Buscando notícias (últimos {self.news_window_days} dias)...")
        news_sentiment = self.get_news_sentiment(ticker)
        
        # 4. Regime
        print("  🌐 Detectando regime...")
        regime = self.get_regime(data)
        
        # 5. Conviction score
        print("  🎯 Calculando conviction...")
        
        # Build signals dict for ConvictionScorer
        signals = {
            "technical": tech["score"],
            "news": news_sentiment,
            "regime": 1.0 if regime == "uptrend" else (-1.0 if regime == "downtrend" else 0.0)
        }
        
        conviction = self.conviction_scorer.calculate_conviction(signals)
        
        # 6. Decision
        signal = "HOLD"
        position_size = 0.0
        
        if conviction["conviction_score"] >= 0.40:
            signal = "BUY"
            # Position sizing based on conviction
            if conviction["conviction_score"] >= 0.80:
                position_size = 0.70  # High conviction
            elif conviction["conviction_score"] >= 0.60:
                position_size = 0.50  # Medium conviction
            else:
                position_size = 0.25  # Low conviction
        elif conviction["conviction_score"] <= -0.40:
            signal = "SELL"
            position_size = 1.0  # Exit full position
        
        # 7. Results
        result = {
            "ticker": ticker,
            "date": datetime.now().strftime("%Y-%m-%d"),
            "price": current_price,
            "trend": tech["trend"],
            "momentum": tech["momentum"],
            "news_sentiment": news_sentiment,
            "regime": regime,
            "conviction_score": conviction["conviction_score"],
            "conviction_level": conviction["conviction_level"],
            "signal": signal,
            "position_size": position_size,
            "components": conviction["components"]
        }
        
        # Print summary
        self._print_summary(result)
        
        return result
    
    def _print_summary(self, result: Dict):
        """Imprime resumo formatado"""
        print(f"\n{'─'*60}")
        print(f"📊 RESUMO: {result['ticker']}")
        print(f"{'─'*60}")
        print(f"  Preço atual: R$ {result['price']:.2f}")
        print(f"  Trend: {result['trend']}")
        print(f"  Momentum: {result['momentum']}")
        print(f"  News sentiment: {result['news_sentiment']:+.2f}")
        print(f"  Regime: {result['regime']}")
        print(f"\n  📊 Conviction: {result['conviction_score']:.2f} ({result['conviction_level']})")
        print(f"     • Technical: {result['components']['technical']:.2f}")
        print(f"     • News: {result['components']['news']:.2f}")
        print(f"     • Regime: {result['components']['regime']:.2f}")
        
        # Signal with emoji
        signal_emoji = {
            "BUY": "🟢",
            "SELL": "🔴",
            "HOLD": "⚪"
        }
        
        print(f"\n  {signal_emoji[result['signal']]} SINAL: {result['signal']}")
        if result['signal'] == "BUY":
            print(f"     Tamanho recomendado: {result['position_size']*100:.0f}% do capital")
        elif result['signal'] == "SELL":
            print(f"     Fechar posição completa")
        
        print(f"{'─'*60}\n")
    
    def run(self, tickers: List[str] = None):
        """Executa análise para lista de tickers"""
        if tickers is None:
            tickers = TICKERS
        
        print(f"\n{'='*60}")
        print(f"🚀 PRODUCTION RUNNER - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        print(f"{'='*60}")
        print(f"Analisando {len(tickers)} tickers...")
        
        results = []
        
        for ticker in tickers:
            try:
                result = self.analyze_ticker(ticker)
                if result:
                    results.append(result)
            except Exception as e:
                print(f"  ❌ Erro analisando {ticker}: {e}")
                continue
        
        # Summary table
        self._print_final_summary(results)
        
        return results
    
    def _print_final_summary(self, results: List[Dict]):
        """Imprime tabela final com todos os sinais"""
        if not results:
            print("\n❌ Nenhum resultado válido")
            return
        
        print(f"\n{'='*80}")
        print(f"📊 RESUMO FINAL - {len(results)} tickers analisados")
        print(f"{'='*80}")
        
        # Sort by conviction score (descending)
        results_sorted = sorted(results, key=lambda x: x['conviction_score'], reverse=True)
        
        # Print table
        print(f"\n{'Ticker':<10} {'Preço':>8} {'Signal':<6} {'Conv':<6} {'Pos%':<6} {'Trend':<10} {'News':<6}")
        print(f"{'-'*80}")
        
        for r in results_sorted:
            signal_symbol = {"BUY": "🟢", "SELL": "🔴", "HOLD": "⚪"}[r['signal']]
            pos_pct = f"{r['position_size']*100:.0f}%" if r['position_size'] > 0 else "-"
            
            print(
                f"{r['ticker']:<10} "
                f"R${r['price']:>7.2f} "
                f"{signal_symbol} {r['signal']:<4} "
                f"{r['conviction_score']:>5.2f} "
                f"{pos_pct:>5} "
                f"{r['trend']:<10} "
                f"{r['news_sentiment']:>5.2f}"
            )
        
        # Stats
        buy_signals = [r for r in results if r['signal'] == "BUY"]
        sell_signals = [r for r in results if r['signal'] == "SELL"]
        
        print(f"\n{'─'*80}")
        print(f"  🟢 BUY: {len(buy_signals)} | 🔴 SELL: {len(sell_signals)} | ⚪ HOLD: {len(results) - len(buy_signals) - len(sell_signals)}")
        print(f"{'='*80}\n")


def main():
    parser = argparse.ArgumentParser(description="Production Runner - Sinais diários")
    parser.add_argument("--ticker", type=str, help="Ticker específico (ex: PETR4.SA)")
    parser.add_argument("--days", type=int, default=7, help="Janela de notícias em dias (default: 7)")
    
    args = parser.parse_args()
    
    # Initialize runner
    runner = ProductionRunner(news_window_days=args.days)
    
    # Run analysis
    if args.ticker:
        runner.run(tickers=[args.ticker])
    else:
        runner.run()


if __name__ == "__main__":
    main()
