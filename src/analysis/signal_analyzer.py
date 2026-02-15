"""
Signal Analyzer - Automatically analyzes signals and generates detailed reasoning
Integrates with TrendDetectorV2 and calculates all technical indicators
"""

import pandas as pd
import numpy as np
from typing import Dict, Optional, List, Tuple
from datetime import datetime

from src.signals.trend_detector_v2 import TrendDetectorV2
from src.analysis.decision_logger import (
    DecisionLogger, SignalDecision, TechnicalIndicators,
    DecisionReason, create_simple_reason
)


class SignalAnalyzer:
    """
    Analyzes trading signals and generates detailed explanations
    """
    
    def __init__(self):
        self.trend_detector = TrendDetectorV2()
        self.logger = DecisionLogger()
        self.previous_signals = {}  # ticker -> last signal
    
    def calculate_indicators(self, df: pd.DataFrame) -> TechnicalIndicators:
        """
        Calculate all technical indicators from price data
        """
        close = df['Close']
        high = df['High']
        low = df['Low']
        volume = df['Volume']
        
        # Moving averages
        ma_20 = close.rolling(20).mean().iloc[-1]
        ma_50 = close.rolling(50).mean().iloc[-1]
        ma_200 = close.rolling(200).mean().iloc[-1] if len(close) >= 200 else ma_50
        
        # MA relationships
        ma_20_vs_50 = "above" if ma_20 > ma_50 else "below"
        ma_50_vs_200 = "above" if ma_50 > ma_200 else "below"
        
        # Check for crossovers
        if len(close) >= 2:
            ma_20_prev = close.rolling(20).mean().iloc[-2]
            ma_50_prev = close.rolling(50).mean().iloc[-2]
            
            if ma_20_prev <= ma_50_prev and ma_20 > ma_50:
                ma_20_vs_50 = "crossing_up"
            elif ma_20_prev >= ma_50_prev and ma_20 < ma_50:
                ma_20_vs_50 = "crossing_down"
        
        # RSI
        delta = close.diff()
        gain = (delta.where(delta > 0, 0)).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        rsi_14 = rsi.iloc[-1]
        
        # MACD
        ema_12 = close.ewm(span=12).mean()
        ema_26 = close.ewm(span=26).mean()
        macd = (ema_12 - ema_26).iloc[-1]
        macd_signal = (ema_12 - ema_26).ewm(span=9).mean().iloc[-1]
        macd_histogram = macd - macd_signal
        
        # ATR
        tr1 = high - low
        tr2 = abs(high - close.shift())
        tr3 = abs(low - close.shift())
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr_14 = tr.rolling(14).mean().iloc[-1]
        
        # Bollinger Bands
        bb_ma = close.rolling(20).mean()
        bb_std = close.rolling(20).std()
        bb_upper = (bb_ma + 2 * bb_std).iloc[-1]
        bb_lower = (bb_ma - 2 * bb_std).iloc[-1]
        
        current_price = close.iloc[-1]
        bb_range = bb_upper - bb_lower
        if current_price > bb_ma.iloc[-1] + 0.7 * bb_std.iloc[-1]:
            bb_position = "near_upper"
        elif current_price < bb_ma.iloc[-1] - 0.7 * bb_std.iloc[-1]:
            bb_position = "near_lower"
        else:
            bb_position = "middle"
        
        # Volume
        volume_avg_20 = volume.rolling(20).mean().iloc[-1]
        volume_current = volume.iloc[-1]
        volume_ratio = volume_current / volume_avg_20 if volume_avg_20 > 0 else 1.0
        
        # Price vs MAs
        price_vs_20ma = ((current_price - ma_20) / ma_20) * 100
        price_vs_50ma = ((current_price - ma_50) / ma_50) * 100
        
        # Support/Resistance (simplified - last 50 days)
        recent_lows = low.tail(50)
        recent_highs = high.tail(50)
        
        support_level = recent_lows.min() if current_price > recent_lows.min() else None
        resistance_level = recent_highs.max() if current_price < recent_highs.max() else None
        
        # ADX (simplified approximation)
        # Proper ADX is complex, using a simple momentum proxy
        returns = close.pct_change().abs()
        adx_approx = returns.rolling(14).mean().iloc[-1] * 100
        
        if adx_approx > 25:
            trend_strength = "strong"
        elif adx_approx > 15:
            trend_strength = "moderate"
        else:
            trend_strength = "weak"
        
        return TechnicalIndicators(
            ma_20=float(ma_20),
            ma_50=float(ma_50),
            ma_200=float(ma_200),
            ma_20_vs_50=ma_20_vs_50,
            ma_50_vs_200=ma_50_vs_200,
            rsi_14=float(rsi_14) if not pd.isna(rsi_14) else 50.0,
            macd=float(macd),
            macd_signal=float(macd_signal),
            macd_histogram=float(macd_histogram),
            atr_14=float(atr_14),
            bollinger_upper=float(bb_upper),
            bollinger_lower=float(bb_lower),
            bollinger_position=bb_position,
            volume_avg_20=float(volume_avg_20),
            volume_current=float(volume_current),
            volume_ratio=float(volume_ratio),
            price_vs_20ma=float(price_vs_20ma),
            price_vs_50ma=float(price_vs_50ma),
            support_level=float(support_level) if support_level else None,
            resistance_level=float(resistance_level) if resistance_level else None,
            adx=float(adx_approx),
            trend_strength=trend_strength
        )
    
    def generate_reasoning(
        self,
        ticker: str,
        trend: str,
        confidence: float,
        consensus: str,
        indicators: TechnicalIndicators,
        signal: str,
        news_sentiment: Optional[float] = None
    ) -> DecisionReason:
        """
        Generate detailed reasoning for a signal
        """
        primary_reasons = []
        secondary_reasons = []
        risk_factors = []
        confidence_factors = {}
        
        # Analyze trend
        if trend == "bullish":
            if indicators.ma_20_vs_50 == "crossing_up":
                primary_reasons.append("Golden cross detectado: MA20 cruzou acima da MA50")
            elif indicators.ma_20_vs_50 == "above":
                primary_reasons.append(f"Tendência bullish confirmada: MA20 acima da MA50")
            
            if indicators.ma_50_vs_200 == "above":
                secondary_reasons.append("MA50 acima da MA200 confirma tendência de longo prazo")
            
            confidence_factors["Tendência (50-day)"] = 0.40
            
        elif trend == "bearish":
            if indicators.ma_20_vs_50 == "crossing_down":
                primary_reasons.append("Death cross detectado: MA20 cruzou abaixo da MA50")
            elif indicators.ma_20_vs_50 == "below":
                primary_reasons.append("Tendência bearish: MA20 abaixo da MA50")
            
            confidence_factors["Tendência (50-day)"] = 0.40
            
        else:  # neutral
            primary_reasons.append("Mercado lateral: sem tendência definida")
            confidence_factors["Tendência (50-day)"] = 0.20
        
        # Analyze momentum
        if indicators.rsi_14 > 70:
            risk_factors.append(f"RSI sobrecomprado ({indicators.rsi_14:.0f}) - possível correção")
        elif indicators.rsi_14 > 60:
            secondary_reasons.append(f"RSI em {indicators.rsi_14:.0f} indica momentum forte")
            confidence_factors["Momentum (RSI)"] = 0.15
        elif indicators.rsi_14 < 30:
            if signal == "BUY":
                secondary_reasons.append(f"RSI sobrevendido ({indicators.rsi_14:.0f}) - oportunidade de compra")
        elif indicators.rsi_14 < 40:
            risk_factors.append(f"RSI fraco ({indicators.rsi_14:.0f}) - momentum negativo")
        
        # MACD
        if indicators.macd > indicators.macd_signal and indicators.macd_histogram > 0:
            secondary_reasons.append("MACD positivo e cruzando para cima")
            confidence_factors["MACD"] = 0.10
        elif indicators.macd < indicators.macd_signal:
            risk_factors.append("MACD negativo indica possível reversão")
        
        # Volume
        if indicators.volume_ratio > 1.5:
            secondary_reasons.append(f"Volume {indicators.volume_ratio:.1f}x acima da média - confirmação forte")
            confidence_factors["Volume"] = 0.15
        elif indicators.volume_ratio > 1.2:
            secondary_reasons.append(f"Volume {indicators.volume_ratio:.1f}x acima da média")
            confidence_factors["Volume"] = 0.10
        elif indicators.volume_ratio < 0.7:
            risk_factors.append("Volume abaixo da média - falta confirmação")
        
        # Price action
        if abs(indicators.price_vs_20ma) > 5:
            if indicators.price_vs_20ma > 0:
                risk_factors.append(f"Preço {indicators.price_vs_20ma:.1f}% acima da MA20 - possível correção")
            else:
                if signal == "BUY":
                    secondary_reasons.append(f"Preço {abs(indicators.price_vs_20ma):.1f}% abaixo da MA20 - desconto")
        
        # Support/Resistance
        if indicators.resistance_level and signal == "BUY":
            risk_factors.append(f"Resistência em R$ {indicators.resistance_level:.2f} pode limitar alta")
        
        if indicators.support_level and signal == "SELL":
            risk_factors.append(f"Suporte em R$ {indicators.support_level:.2f} pode segurar queda")
        
        # News sentiment
        if news_sentiment is not None:
            if news_sentiment > 0.6:
                secondary_reasons.append(f"Notícias muito positivas (sentiment: {news_sentiment:+.2f})")
                confidence_factors["Notícias"] = 0.10
            elif news_sentiment < -0.6:
                risk_factors.append(f"Notícias negativas (sentiment: {news_sentiment:+.2f})")
        
        # Trend strength
        if indicators.trend_strength == "weak":
            risk_factors.append("Tendência fraca - sinal menos confiável")
        elif indicators.trend_strength == "strong":
            secondary_reasons.append("Tendência forte (ADX alto)")
            confidence_factors["Força da tendência"] = 0.10
        
        # Select primary reason
        if not primary_reasons:
            primary_reasons.append("Análise técnica sugere manutenção da posição atual")
        
        primary_reason = primary_reasons[0]
        
        # Technical summary
        summary_parts = []
        
        if signal == "BUY":
            summary_parts.append(f"Setup de compra com confiança de {confidence:.0%}.")
            if indicators.support_level:
                summary_parts.append(f"Suporte identificado em R$ {indicators.support_level:.2f}.")
            if len(risk_factors) > 0:
                summary_parts.append(f"Atenção a {len(risk_factors)} fator(es) de risco.")
        elif signal == "SELL":
            summary_parts.append(f"Sinal de venda com confiança de {confidence:.0%}.")
        else:
            summary_parts.append("Aguardar melhor definição de tendência antes de operar.")
        
        technical_summary = " ".join(summary_parts)
        
        return create_simple_reason(
            primary=primary_reason,
            secondary=secondary_reasons,
            risks=risk_factors,
            confidence_factors=confidence_factors,
            summary=technical_summary
        )
    
    def analyze_signal(
        self,
        ticker: str,
        df: pd.DataFrame,
        current_price: float,
        news_sentiment: Optional[float] = None,
        news_count: Optional[int] = None,
        news_summary: Optional[str] = None
    ) -> Tuple[str, SignalDecision]:
        """
        Analyze a ticker and generate complete signal with reasoning
        
        Returns:
            (signal, decision): Signal ("BUY", "SELL", "HOLD") and full decision object
        """
        # Get trend analysis
        trend_result = self.trend_detector.detect_trend(df)
        consensus = trend_result.get('consensus', 'unknown')
        confidence = trend_result.get('confidence', 0.0)
        
        # Map consensus to trend
        if consensus in ['uptrend', 'bull_pullback']:
            trend = "bullish"
        elif consensus in ['downtrend', 'bear_bounce']:
            trend = "bearish"
        else:
            trend = "neutral"
        
        # Calculate indicators
        indicators = self.calculate_indicators(df)
        
        # Determine signal
        if trend == "bullish" and confidence > 0.35:
            signal = "BUY"
        elif trend == "bearish" and confidence > 0.35:
            signal = "SELL"
        else:
            signal = "HOLD"
        
        # Check for signal change
        previous_signal = self.previous_signals.get(ticker, "HOLD")
        signal_changed = (previous_signal != signal)
        self.previous_signals[ticker] = signal
        
        # Generate reasoning
        reason = self.generate_reasoning(
            ticker, trend, confidence, consensus,
            indicators, signal, news_sentiment
        )
        
        # Calculate stop loss and take profit levels
        stop_loss = None
        take_profit_levels = None
        
        if signal == "BUY":
            # Stop loss at 2x ATR below entry
            stop_loss = current_price - (2 * indicators.atr_14)
            
            # Take profit levels
            take_profit_levels = [
                current_price * 1.05,  # +5%
                current_price * 1.10,  # +10%
                current_price * 1.15,  # +15%
            ]
        
        # Create decision object
        decision = SignalDecision(
            ticker=ticker,
            timestamp=datetime.now().strftime("%H:%M:%S"),
            date=datetime.now().strftime("%Y-%m-%d"),
            previous_signal=previous_signal,
            current_signal=signal,
            signal_changed=signal_changed,
            trend=trend,
            confidence=confidence,
            consensus=consensus,
            indicators=indicators,
            reason=reason,
            current_price=current_price,
            entry_price=current_price if signal == "BUY" else None,
            stop_loss=stop_loss,
            take_profit_levels=take_profit_levels,
            news_sentiment=news_sentiment,
            news_count=news_count,
            news_summary=news_summary
        )
        
        # Log the decision
        self.logger.log_decision(decision)
        
        return signal, decision


# Example usage
if __name__ == "__main__":
    import yfinance as yf
    
    analyzer = SignalAnalyzer()
    
    # Download data
    ticker = "WEGE3.SA"
    df = yf.download(ticker, period="6mo", progress=False)
    
    # Flatten MultiIndex if needed
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [col[0] for col in df.columns.values]
    
    current_price = df['Close'].iloc[-1]
    
    # Analyze
    signal, decision = analyzer.analyze_signal(
        ticker=ticker,
        df=df,
        current_price=float(current_price),
        news_sentiment=0.45,
        news_count=2,
        news_summary="Resultados trimestrais positivos"
    )
    
    print(f"Signal: {signal}\n")
    print(analyzer.logger.format_decision_report(decision))
