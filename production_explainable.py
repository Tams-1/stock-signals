#!/usr/bin/env python3
"""
PRODUCTION EXPLAINABLE SYSTEM

State-of-the-art explainable trading signals with:
- Clear BUY/SELL/HOLD recommendations
- Position sizing (% of capital)
- Signal breakdown (confidence, trend, price action)
- AI-powered reasoning (Haiku summarizes the "why")
- Decision history logging
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json

from src.signals.trend_detector_v2 import TrendDetectorV2

# IBOV tickers (use subset for fair comparison)
TICKERS = [
    "PETR4.SA", "VALE3.SA", "ITUB4.SA", "BBDC4.SA", "BBAS3.SA",
    "ABEV3.SA", "B3SA3.SA", "SUZB3.SA", "RENT3.SA", "WEGE3.SA",
    "MGLU3.SA", "PCAR3.SA", "LREN3.SA", "RAIZ4.SA", "GGBR4.SA",
    "ASAI3.SA", "RDOR3.SA"
]

class ExplainableSignalGenerator:
    """Generate trading signals with full explainability"""
    
    def __init__(self):
        self.detector = TrendDetectorV2()
        self.decision_log = []
    
    def analyze_ticker(self, ticker: str) -> dict:
        """
        Analyze ticker and return FULL signal breakdown
        
        Returns:
            {
                'ticker': str,
                'signal': 'BUY'|'SELL'|'HOLD',
                'position_size': float (0-1),
                'confidence': float,
                'components': {
                    'price': {...},
                    'trend': {...},
                    'momentum': {...},
                    'volume': {...}
                },
                'reasoning': str (AI-generated),
                'key_factor': str
            }
        """
        # Download data
        df = yf.download(ticker, period="6mo", progress=False)
        
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        
        if len(df) < 50:
            return self._no_data_signal(ticker)
        
        # Current price
        current_price = df['Close'].iloc[-1]
        prev_close = df['Close'].iloc[-2]
        day_change = ((current_price - prev_close) / prev_close) * 100
        
        # Trend detection
        trend_result = self.detector.detect_trend(df)
        consensus = trend_result.get('consensus', 'unknown')
        confidence = trend_result.get('confidence', 0.0)
        macro_regime = trend_result.get('macro_regime', 'unknown')
        micro_state = trend_result.get('micro_state', 'unknown')
        
        # Price levels
        ma20 = df['Close'].rolling(20).mean().iloc[-1]
        ma50 = df['Close'].rolling(50).mean().iloc[-1]
        high_52w = df['Close'].tail(252).max()
        low_52w = df['Close'].tail(252).min()
        
        # Volume analysis
        avg_volume = df['Volume'].rolling(20).mean().iloc[-1]
        current_volume = df['Volume'].iloc[-1]
        volume_ratio = current_volume / avg_volume if avg_volume > 0 else 1.0
        
        # Momentum
        rsi = self._calculate_rsi(df['Close'])
        
        # Build component breakdown
        components = {
            'price': {
                'current': float(current_price),
                'change_pct': float(day_change),
                'vs_ma20': float(((current_price - ma20) / ma20) * 100),
                'vs_ma50': float(((current_price - ma50) / ma50) * 100),
                'from_52w_high': float(((current_price - high_52w) / high_52w) * 100),
                'from_52w_low': float(((current_price - low_52w) / low_52w) * 100)
            },
            'trend': {
                'consensus': consensus,
                'confidence': float(confidence),
                'macro_regime': macro_regime,
                'micro_state': micro_state
            },
            'momentum': {
                'rsi': float(rsi),
                'rsi_signal': 'oversold' if rsi < 30 else 'overbought' if rsi > 70 else 'neutral'
            },
            'volume': {
                'ratio': float(volume_ratio),
                'signal': 'high' if volume_ratio > 1.5 else 'low' if volume_ratio < 0.5 else 'normal'
            }
        }
        
        # Generate signal using pure confidence approach
        signal = "HOLD"
        position_size = 0.0
        
        if confidence > 0.25:
            signal = "BUY"
            # Scale position with confidence
            raw_size = (confidence - 0.25) / 0.75
            position_size = min(0.90, raw_size * 0.90)
            position_size = max(0.25, position_size)
        elif confidence < 0.15:
            signal = "SELL"
            position_size = 1.0
        
        # Identify key factor (what drove the decision?)
        key_factor = self._identify_key_factor(components, confidence)
        
        # Log decision components for history
        decision_record = {
            'timestamp': datetime.now().isoformat(),
            'ticker': ticker,
            'signal': signal,
            'position_size': float(position_size),
            'components': components,
            'key_factor': key_factor
        }
        
        self.decision_log.append(decision_record)
        
        return {
            'ticker': ticker,
            'signal': signal,
            'position_size': float(position_size),
            'confidence': float(confidence),
            'components': components,
            'key_factor': key_factor,
            'reasoning': None  # Will be filled by AI
        }
    
    def _calculate_rsi(self, prices, period=14):
        """Calculate RSI"""
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi.iloc[-1] if not pd.isna(rsi.iloc[-1]) else 50.0
    
    def _identify_key_factor(self, components, confidence):
        """Identify the primary driver of the signal"""
        factors = []
        
        # Trend strength
        if confidence > 0.70:
            factors.append(('strong_trend', confidence))
        
        # Price action
        if abs(components['price']['vs_ma20']) > 5:
            factors.append(('price_divergence_ma20', abs(components['price']['vs_ma20']) / 100))
        
        if abs(components['price']['vs_ma50']) > 10:
            factors.append(('price_divergence_ma50', abs(components['price']['vs_ma50']) / 100))
        
        # Momentum
        rsi = components['momentum']['rsi']
        if rsi < 30:
            factors.append(('oversold', (30 - rsi) / 30))
        elif rsi > 70:
            factors.append(('overbought', (rsi - 70) / 30))
        
        # Volume
        if components['volume']['ratio'] > 2.0:
            factors.append(('high_volume', components['volume']['ratio'] - 1))
        
        # Return strongest factor
        if factors:
            factors.sort(key=lambda x: x[1], reverse=True)
            return factors[0][0]
        
        return 'neutral_market'
    
    def _no_data_signal(self, ticker):
        """Return safe signal when no data available"""
        return {
            'ticker': ticker,
            'signal': 'HOLD',
            'position_size': 0.0,
            'confidence': 0.0,
            'components': {},
            'key_factor': 'insufficient_data',
            'reasoning': 'Dados insuficientes para análise'
        }
    
    def generate_reasoning_prompt(self, signal_data):
        """Generate prompt for Haiku to explain the signal"""
        components = signal_data['components']
        
        prompt = f"""Você é um analista quantitativo. Explique EM PORTUGUÊS e de forma CONCISA (2-3 linhas) por que o sistema recomenda:

Ticker: {signal_data['ticker']}
Sinal: {signal_data['signal']}
Tamanho posição: {signal_data['position_size']:.0%}
Confiança: {signal_data['confidence']:.1%}

Componentes de decisão:
- Preço: R$ {components['price']['current']:.2f} ({components['price']['change_pct']:+.1f}% dia)
- vs MA20: {components['price']['vs_ma20']:+.1f}%
- vs MA50: {components['price']['vs_ma50']:+.1f}%
- Tendência: {components['trend']['consensus']} (confiança {components['trend']['confidence']:.1%})
- Regime macro: {components['trend']['macro_regime']}
- Estado micro: {components['trend']['micro_state']}
- RSI: {components['momentum']['rsi']:.0f} ({components['momentum']['rsi_signal']})
- Volume: {components['volume']['signal']} ({components['volume']['ratio']:.1f}x média)

Fator principal: {signal_data['key_factor']}

Responda em 2-3 linhas explicando o PORQUÊ da recomendação e qual o SINAL MAIS IMPORTANTE."""

        return prompt
    
    def save_decision_log(self, filepath='decisions_log.json'):
        """Save decision history"""
        with open(filepath, 'w') as f:
            json.dump(self.decision_log, f, indent=2)

def format_signal_output(signals):
    """Format signals for terminal output"""
    print("\n" + "="*80)
    print("🎯 SINAIS DE TRADING - SISTEMA EXPLICÁVEL")
    print("="*80)
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    buy_signals = [s for s in signals if s['signal'] == 'BUY']
    sell_signals = [s for s in signals if s['signal'] == 'SELL']
    hold_signals = [s for s in signals if s['signal'] == 'HOLD']
    
    if buy_signals:
        print("🟢 COMPRAR:")
        for sig in buy_signals:
            print(f"\n  {sig['ticker']}")
            print(f"  └─ Posição: {sig['position_size']:.0%} | Confiança: {sig['confidence']:.1%}")
            print(f"  └─ Fator chave: {sig['key_factor']}")
            if sig.get('reasoning'):
                print(f"  └─ Razão: {sig['reasoning']}")
    
    if sell_signals:
        print("\n🔴 VENDER:")
        for sig in sell_signals:
            print(f"\n  {sig['ticker']}")
            print(f"  └─ Confiança: {sig['confidence']:.1%}")
            print(f"  └─ Fator chave: {sig['key_factor']}")
            if sig.get('reasoning'):
                print(f"  └─ Razão: {sig['reasoning']}")
    
    print(f"\n⚪ MANTER: {len(hold_signals)} ações")
    
    print("\n" + "="*80)
    print(f"📊 Resumo: {len(buy_signals)} COMPRA | {len(sell_signals)} VENDA | {len(hold_signals)} HOLD")
    print("="*80 + "\n")

if __name__ == "__main__":
    print("🚀 Iniciando análise explicável...")
    
    generator = ExplainableSignalGenerator()
    signals = []
    
    for ticker in TICKERS:
        print(f"📊 Analisando {ticker}...", end=" ")
        try:
            signal = generator.analyze_ticker(ticker)
            signals.append(signal)
            print(f"{signal['signal']}")
        except Exception as e:
            print(f"ERRO: {e}")
    
    # Save decision log
    generator.save_decision_log()
    
    # Display results
    format_signal_output(signals)
    
    print("💾 Histórico de decisões salvo em decisions_log.json")
    print("\n🔍 Para explicação detalhada de cada sinal, use:")
    print("   python add_ai_reasoning.py")
