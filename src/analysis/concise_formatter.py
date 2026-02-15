"""
Concise Formatter - Ultra-short signal summaries
Just the essentials: signal, main reason, 1-2 key factors
"""

from typing import Dict
from src.analysis.decision_logger import SignalDecision


def format_concise_alert(decision: SignalDecision) -> str:
    """
    Format a very concise alert with just the essentials
    
    Returns a 2-3 line summary with:
    - Signal change
    - Main reason
    - Key factor (price/stop loss)
    """
    ticker = decision.ticker
    prev = decision.previous_signal
    curr = decision.current_signal
    
    # Emoji for signal
    if curr == "BUY":
        emoji = "🟢"
    elif curr == "SELL":
        emoji = "🔴"
    else:
        emoji = "⚪"
    
    # Main reason (keep it short)
    reason = decision.reason.primary_reason
    
    # Shorten common phrases
    reason = reason.replace("Tendência bullish confirmada: ", "Bullish: ")
    reason = reason.replace("Tendência bearish: ", "Bearish: ")
    reason = reason.replace("confirmada", "")
    reason = reason.replace("detectado", "")
    
    # Build concise alert
    lines = []
    lines.append(f"{emoji} {ticker}: {prev} → {curr}")
    lines.append(f"   {reason}")
    
    # Add key context
    if curr == "BUY":
        stop = decision.stop_loss
        tp1 = decision.take_profit_levels[0] if decision.take_profit_levels else None
        
        lines.append(f"   Entrada: R$ {decision.current_price:.2f} | Stop: R$ {stop:.2f}")
        if tp1:
            lines.append(f"   Alvo: R$ {tp1:.2f} (+{((tp1/decision.current_price - 1)*100):.1f}%)")
    
    elif curr == "SELL":
        lines.append(f"   Preço: R$ {decision.current_price:.2f}")
    
    # Add confidence
    conf_pct = decision.confidence * 100
    lines.append(f"   Confiança: {conf_pct:.0f}%")
    
    return "\n".join(lines)


def format_concise_report(decision: SignalDecision) -> str:
    """
    Format a concise report (not as short as alert, but much shorter than full)
    
    ~10-15 lines max with essentials
    """
    ticker = decision.ticker
    
    lines = []
    lines.append(f"\n{'='*60}")
    lines.append(f"📊 {ticker} - {decision.current_signal}")
    lines.append(f"{'='*60}")
    
    # Signal change
    if decision.signal_changed:
        lines.append(f"🔔 {decision.previous_signal} → {decision.current_signal}")
    
    # Main reason
    lines.append(f"\n✅ RAZÃO: {decision.reason.primary_reason}")
    
    # Key factors
    if decision.reason.secondary_reasons:
        lines.append(f"\n🔸 APOIO:")
        # Only show top 2
        for reason in decision.reason.secondary_reasons[:2]:
            lines.append(f"   • {reason}")
    
    # Risks (only if present)
    if decision.reason.risk_factors:
        lines.append(f"\n⚠️ RISCOS:")
        # Only show top 2
        for risk in decision.reason.risk_factors[:2]:
            lines.append(f"   • {risk}")
    
    # Key indicators (compact)
    ind = decision.indicators
    lines.append(f"\n📊 INDICADORES:")
    lines.append(f"   Preço: R$ {decision.current_price:.2f} | RSI: {ind.rsi_14:.0f} | MACD: {ind.macd:.2f}")
    lines.append(f"   Volume: {ind.volume_ratio:.2f}x | Conf: {decision.confidence:.0%}")
    
    # Levels (if BUY)
    if decision.current_signal == "BUY" and decision.stop_loss:
        lines.append(f"\n💰 NÍVEIS:")
        lines.append(f"   Entrada: R$ {decision.current_price:.2f}")
        lines.append(f"   Stop: R$ {decision.stop_loss:.2f} ({((decision.stop_loss/decision.current_price - 1)*100):.1f}%)")
        
        if decision.take_profit_levels:
            tp1, tp2, tp3 = decision.take_profit_levels
            lines.append(f"   Alvos: R$ {tp1:.2f} / R$ {tp2:.2f} / R$ {tp3:.2f}")
    
    lines.append(f"{'='*60}\n")
    
    return "\n".join(lines)


# Convenience function
def format_telegram_alert(decision: SignalDecision) -> str:
    """
    Format for Telegram - ultra concise, 3-4 lines max
    """
    ticker = decision.ticker
    signal = decision.current_signal
    reason = decision.reason.primary_reason
    
    # Shorten reason
    reason = reason.replace("Tendência bullish confirmada: ", "")
    reason = reason.replace("Tendência bearish: ", "")
    reason = reason.replace("confirmada", "").replace("detectado", "")
    
    # Emoji
    emoji = {"BUY": "🟢", "SELL": "🔴", "HOLD": "⚪"}[signal]
    
    alert = f"{emoji} {ticker}: {decision.previous_signal} → {signal}\n"
    alert += f"Razão: {reason}\n"
    
    if signal == "BUY":
        alert += f"Entrada R$ {decision.current_price:.2f} | Stop R$ {decision.stop_loss:.2f} | Conf {decision.confidence:.0%}"
    else:
        alert += f"Preço R$ {decision.current_price:.2f} | Conf {decision.confidence:.0%}"
    
    return alert


# Example usage
if __name__ == "__main__":
    from src.analysis.decision_logger import (
        SignalDecision, TechnicalIndicators, create_simple_reason
    )
    
    # Create example decision
    indicators = TechnicalIndicators(
        ma_20=52.50, ma_50=51.00, ma_200=48.00,
        ma_20_vs_50="above", ma_50_vs_200="above",
        rsi_14=65.0, macd=0.85, macd_signal=0.70, macd_histogram=0.15,
        atr_14=2.50, bollinger_upper=55.00, bollinger_lower=49.00,
        bollinger_position="middle", volume_avg_20=5000000,
        volume_current=7500000, volume_ratio=1.5,
        price_vs_20ma=2.5, price_vs_50ma=4.0,
        support_level=50.00, resistance_level=55.00,
        adx=28.0, trend_strength="moderate"
    )
    
    reason = create_simple_reason(
        primary="Tendência bullish confirmada: MA20 acima de MA50",
        secondary=[
            "RSI em 65 indica momentum forte",
            "Volume 50% acima da média"
        ],
        risks=[
            "Resistência forte em R$ 55.00"
        ],
        confidence_factors={"Tendência": 0.40, "Volume": 0.20},
        summary="Setup bullish de qualidade"
    )
    
    decision = SignalDecision(
        ticker="WEGE3.SA",
        timestamp="10:03:45",
        date="2026-02-17",
        previous_signal="HOLD",
        current_signal="BUY",
        signal_changed=True,
        trend="bullish",
        confidence=0.87,
        consensus="uptrend",
        indicators=indicators,
        reason=reason,
        current_price=53.80,
        entry_price=53.80,
        stop_loss=50.00,
        take_profit_levels=[56.50, 59.50, 62.50],
        news_sentiment=None,
        news_count=None,
        news_summary=None
    )
    
    print("=== TELEGRAM ALERT (Ultra conciso) ===")
    print(format_telegram_alert(decision))
    
    print("\n=== CONCISE ALERT (Detalhado mas curto) ===")
    print(format_concise_alert(decision))
    
    print("\n=== CONCISE REPORT (Médio) ===")
    print(format_concise_report(decision))
