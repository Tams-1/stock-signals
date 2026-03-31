import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.alerts.alert_generator import generate_trading_alerts


def test_generate_trading_alerts_matches_compact_telegram_format():
    results = [
        {
            'ticker': 'PETR4.SA',
            'price': 37.97,
            'signal': 'BUY',
            'trend': 'UPTREND',
            'confidence': 0.78,
            'fusion_confidence': 0.71,
            'fused_score': 0.34,
            'news_sentiment': 0.27,
            'position_size': 0.42,
            'conviction': 0.84,
            'fundamentals': {
                'fundamental_grade': 'A',
                'composite_score': 88.4,
            },
            'news_articles': [
                {'title': 'Petrobras expands dividend guidance', 'source': 'Reuters'},
                {'title': 'Oil prices support earnings outlook', 'source': 'Valor'},
            ],
            'technical_indicators': {
                'rsi': 67.2,
                'macd': 1.4,
                'macd_signal': 1.1,
                'price_vs_50d': 4.8,
                'volume_vs_avg': 122.0,
            },
            'risk_levels': {
                'entry': 37.97,
                'stop_loss': 34.17,
                'target_1': 45.57,
                'target_2': 49.37,
            },
        }
    ]

    alert = generate_trading_alerts(results, top_n=3)

    assert "🚨 TOP TRADING OPPORTUNITIES" in alert
    assert "1️⃣" in alert
    assert "PETR4 - BUY 🟢" in alert
    assert "Trend: UPTREND (78% confidence)" in alert
    assert "Fusion: Bullish alignment (+0.34)" in alert
    assert "News: +0.27 sentiment" in alert
    assert "• Petrobras expands dividend guidance (Reuters)" in alert
    assert "• Oil prices support earnings outlook (Valor)" in alert
    assert "Entry: R$37.97 | Stop: R$34.17" in alert
    assert "Targets: R$45.57 (2:1) | R$49.37 (3:1)" in alert
    assert "Watch for:" in alert
