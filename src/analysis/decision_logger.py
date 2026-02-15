"""
Decision Logger - Tracks and explains all trading decisions
Stores all indicators analyzed and provides detailed reasoning for each signal change
"""

from dataclasses import dataclass, asdict
from typing import Dict, List, Optional
from datetime import datetime
import json


@dataclass
class TechnicalIndicators:
    """All technical indicators analyzed"""
    # Trend indicators
    ma_20: float
    ma_50: float
    ma_200: float
    ma_20_vs_50: str  # "above", "below", "crossing_up", "crossing_down"
    ma_50_vs_200: str
    
    # Momentum
    rsi_14: float
    macd: float
    macd_signal: float
    macd_histogram: float
    
    # Volatility
    atr_14: float
    bollinger_upper: float
    bollinger_lower: float
    bollinger_position: str  # "near_upper", "near_lower", "middle"
    
    # Volume
    volume_avg_20: float
    volume_current: float
    volume_ratio: float  # current/avg
    
    # Price action
    price_vs_20ma: float  # percentage
    price_vs_50ma: float
    support_level: Optional[float]
    resistance_level: Optional[float]
    
    # Trend strength
    adx: float  # Average Directional Index
    trend_strength: str  # "strong", "moderate", "weak"


@dataclass
class DecisionReason:
    """Detailed reasoning for a decision"""
    primary_reason: str  # Main reason for the signal
    secondary_reasons: List[str]  # Supporting factors
    risk_factors: List[str]  # Things to watch out for
    confidence_breakdown: Dict[str, float]  # What contributed to confidence
    technical_summary: str  # Human-readable summary


@dataclass
class SignalDecision:
    """Complete signal decision with full context"""
    ticker: str
    timestamp: str
    date: str
    
    # Signal info
    previous_signal: str
    current_signal: str
    signal_changed: bool
    
    # Trend analysis
    trend: str  # "bullish", "bearish", "neutral"
    confidence: float
    consensus: str  # from TrendDetectorV2
    
    # Technical indicators
    indicators: TechnicalIndicators
    
    # Decision reasoning
    reason: DecisionReason
    
    # Price context
    current_price: float
    entry_price: Optional[float]
    stop_loss: Optional[float]
    take_profit_levels: Optional[List[float]]
    
    # News context (if available)
    news_sentiment: Optional[float]
    news_count: Optional[int]
    news_summary: Optional[str]


class DecisionLogger:
    """
    Logs and explains all trading decisions
    """
    
    def __init__(self, log_file: str = "decision_log.json"):
        self.log_file = log_file
        self.decisions = []
        self._load_history()
    
    def _load_history(self):
        """Load previous decisions"""
        try:
            with open(self.log_file, 'r') as f:
                data = json.load(f)
                self.decisions = data.get('decisions', [])
        except FileNotFoundError:
            self.decisions = []
    
    def _save_history(self):
        """Save decision history"""
        data = {
            'last_updated': datetime.now().isoformat(),
            'total_decisions': len(self.decisions),
            'decisions': self.decisions
        }
        
        with open(self.log_file, 'w') as f:
            json.dump(data, f, indent=2)
    
    def log_decision(self, decision: SignalDecision):
        """Log a trading decision"""
        self.decisions.append(asdict(decision))
        self._save_history()
    
    def get_latest_decision(self, ticker: str) -> Optional[Dict]:
        """Get the most recent decision for a ticker"""
        for decision in reversed(self.decisions):
            if decision['ticker'] == ticker:
                return decision
        return None
    
    def format_decision_report(self, decision: SignalDecision) -> str:
        """
        Format a decision into a detailed human-readable report
        """
        report = []
        
        # Header
        report.append(f"\n{'='*70}")
        report.append(f"📊 ANÁLISE DETALHADA - {decision.ticker}")
        report.append(f"{'='*70}")
        report.append(f"Data: {decision.date} {decision.timestamp}")
        report.append(f"Preço: R$ {decision.current_price:.2f}")
        
        # Signal change
        if decision.signal_changed:
            report.append(f"\n🔔 MUDANÇA DE SINAL: {decision.previous_signal} → {decision.current_signal}")
        else:
            report.append(f"\n📍 Sinal mantido: {decision.current_signal}")
        
        # Trend analysis
        report.append(f"\n📈 TENDÊNCIA:")
        report.append(f"   Status: {decision.trend} (confiança: {decision.confidence:.2%})")
        report.append(f"   Consenso: {decision.consensus}")
        
        # Primary reason
        report.append(f"\n✅ RAZÃO PRINCIPAL:")
        report.append(f"   {decision.reason.primary_reason}")
        
        # Secondary reasons
        if decision.reason.secondary_reasons:
            report.append(f"\n🔸 FATORES DE APOIO:")
            for reason in decision.reason.secondary_reasons:
                report.append(f"   • {reason}")
        
        # Risk factors
        if decision.reason.risk_factors:
            report.append(f"\n⚠️  FATORES DE RISCO:")
            for risk in decision.reason.risk_factors:
                report.append(f"   • {risk}")
        
        # Technical indicators
        ind = decision.indicators
        report.append(f"\n📊 INDICADORES TÉCNICOS:")
        report.append(f"   Médias Móveis:")
        report.append(f"      MA20: R$ {ind.ma_20:.2f} ({ind.ma_20_vs_50})")
        report.append(f"      MA50: R$ {ind.ma_50:.2f} ({ind.ma_50_vs_200})")
        report.append(f"      MA200: R$ {ind.ma_200:.2f}")
        
        report.append(f"\n   Momentum:")
        report.append(f"      RSI(14): {ind.rsi_14:.1f} {self._interpret_rsi(ind.rsi_14)}")
        report.append(f"      MACD: {ind.macd:.2f} (sinal: {ind.macd_signal:.2f})")
        report.append(f"      Histograma: {ind.macd_histogram:.2f}")
        
        report.append(f"\n   Volatilidade:")
        report.append(f"      ATR(14): R$ {ind.atr_14:.2f}")
        report.append(f"      Bollinger: {ind.bollinger_position}")
        
        report.append(f"\n   Volume:")
        report.append(f"      Atual: {ind.volume_current:,.0f}")
        report.append(f"      Média(20): {ind.volume_avg_20:,.0f}")
        report.append(f"      Relação: {ind.volume_ratio:.2f}x")
        
        report.append(f"\n   Força da Tendência:")
        report.append(f"      ADX: {ind.adx:.1f} ({ind.trend_strength})")
        
        # Support/Resistance
        if ind.support_level or ind.resistance_level:
            report.append(f"\n   Níveis Chave:")
            if ind.support_level:
                report.append(f"      Suporte: R$ {ind.support_level:.2f}")
            if ind.resistance_level:
                report.append(f"      Resistência: R$ {ind.resistance_level:.2f}")
        
        # Confidence breakdown
        report.append(f"\n🎯 COMPOSIÇÃO DA CONFIANÇA:")
        for factor, weight in decision.reason.confidence_breakdown.items():
            report.append(f"   {factor}: {weight:.1%}")
        
        # Entry/Exit levels (if applicable)
        if decision.current_signal == "BUY" and decision.stop_loss:
            report.append(f"\n💰 NÍVEIS DE OPERAÇÃO:")
            report.append(f"   Entrada sugerida: R$ {decision.current_price:.2f}")
            report.append(f"   Stop Loss: R$ {decision.stop_loss:.2f} ({(decision.stop_loss/decision.current_price - 1)*100:.1f}%)")
            
            if decision.take_profit_levels:
                report.append(f"   Take Profit:")
                for i, tp in enumerate(decision.take_profit_levels, 1):
                    report.append(f"      TP{i}: R$ {tp:.2f} ({(tp/decision.current_price - 1)*100:.1f}%)")
        
        # News context
        if decision.news_sentiment is not None:
            report.append(f"\n📰 CONTEXTO DE NOTÍCIAS:")
            report.append(f"   Sentiment: {decision.news_sentiment:+.2f}")
            report.append(f"   Artigos: {decision.news_count}")
            if decision.news_summary:
                report.append(f"   Resumo: {decision.news_summary}")
        
        # Technical summary
        report.append(f"\n📋 RESUMO TÉCNICO:")
        report.append(f"   {decision.reason.technical_summary}")
        
        report.append(f"\n{'='*70}\n")
        
        return "\n".join(report)
    
    def _interpret_rsi(self, rsi: float) -> str:
        """Interpret RSI value"""
        if rsi > 70:
            return "(sobrecomprado)"
        elif rsi > 60:
            return "(forte)"
        elif rsi > 40:
            return "(neutro)"
        elif rsi > 30:
            return "(fraco)"
        else:
            return "(sobrevendido)"
    
    def get_signal_changes_today(self) -> List[Dict]:
        """Get all signal changes that happened today"""
        today = datetime.now().strftime("%Y-%m-%d")
        
        changes = []
        for decision in self.decisions:
            if decision['date'] == today and decision['signal_changed']:
                changes.append(decision)
        
        return changes
    
    def format_daily_summary(self) -> str:
        """Format a summary of today's signal changes"""
        changes = self.get_signal_changes_today()
        
        if not changes:
            return "📊 Nenhuma mudança de sinal hoje."
        
        summary = []
        summary.append(f"\n📊 RESUMO DAS MUDANÇAS DE HOJE ({len(changes)} sinais)")
        summary.append(f"{'='*70}\n")
        
        for change in changes:
            ticker = change['ticker']
            prev = change['previous_signal']
            curr = change['current_signal']
            reason = change['reason']['primary_reason']
            
            emoji = "🟢" if curr == "BUY" else "🔴" if curr == "SELL" else "⚪"
            
            summary.append(f"{emoji} {ticker}: {prev} → {curr}")
            summary.append(f"   Razão: {reason}\n")
        
        return "\n".join(summary)


# Convenience function for creating a simple reason
def create_simple_reason(
    primary: str,
    secondary: List[str] = None,
    risks: List[str] = None,
    confidence_factors: Dict[str, float] = None,
    summary: str = ""
) -> DecisionReason:
    """Helper to create a DecisionReason"""
    return DecisionReason(
        primary_reason=primary,
        secondary_reasons=secondary or [],
        risk_factors=risks or [],
        confidence_breakdown=confidence_factors or {},
        technical_summary=summary
    )


# Example usage
if __name__ == "__main__":
    # Example: Create a decision log entry
    logger = DecisionLogger()
    
    # Simulate indicators
    indicators = TechnicalIndicators(
        ma_20=52.50,
        ma_50=51.00,
        ma_200=48.00,
        ma_20_vs_50="above",
        ma_50_vs_200="above",
        rsi_14=65.0,
        macd=0.85,
        macd_signal=0.70,
        macd_histogram=0.15,
        atr_14=2.50,
        bollinger_upper=55.00,
        bollinger_lower=49.00,
        bollinger_position="middle",
        volume_avg_20=5000000,
        volume_current=7500000,
        volume_ratio=1.5,
        price_vs_20ma=2.5,
        price_vs_50ma=4.0,
        support_level=50.00,
        resistance_level=55.00,
        adx=28.0,
        trend_strength="moderate"
    )
    
    reason = create_simple_reason(
        primary="Tendência bullish confirmada com MA20 acima de MA50 e MA50 acima de MA200 (golden cross)",
        secondary=[
            "RSI em 65 indica momentum forte sem sobrecompra",
            "MACD positivo e cruzando para cima",
            "Volume 50% acima da média confirmando movimento",
            "Preço rompeu resistência de R$ 52.00"
        ],
        risks=[
            "Resistência forte em R$ 55.00 pode gerar reversão",
            "Mercado global volátil"
        ],
        confidence_factors={
            "Tendência (50-day)": 0.40,
            "Momentum (RSI/MACD)": 0.25,
            "Volume": 0.20,
            "Rompimento técnico": 0.15
        },
        summary="Setup bullish de alta qualidade com confirmação de volume. Entrada favorável com stop loss claro em R$ 50.00 (suporte anterior). Relação risco/retorno de 1:3 até resistência."
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
        news_sentiment=0.45,
        news_count=2,
        news_summary="Notícias positivas sobre resultados trimestrais"
    )
    
    # Log and print
    logger.log_decision(decision)
    print(logger.format_decision_report(decision))
    print(logger.format_daily_summary())
