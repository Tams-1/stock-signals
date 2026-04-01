import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.alerts.alert_generator import generate_trading_alerts
from src.alerts.delivery import build_actionable_alert, deliver_trading_alerts


def _sample_result(signal: str = "BUY"):
    return {
        "ticker": "PRIO3.SA",
        "price": 66.21,
        "signal": signal,
        "trend": "UPTREND",
        "confidence": 0.93,
        "fusion_confidence": 0.62,
        "fused_score": 0.34,
        "news_sentiment": 0.15,
        "position_size": 0.35,
        "conviction": 0.76,
        "fundamentals": {
            "fundamental_grade": "D",
            "composite_score": 76.2,
        },
        "news_articles": [
            {"title": "PRIO3 extends production guidance", "source": "Valor"},
            {"title": "Oil output remains resilient", "source": "Reuters"},
        ],
        "technical_indicators": {
            "rsi": 62.7,
            "macd": 4.09,
            "macd_signal": 3.89,
            "price_vs_50d": 17.8,
            "volume_vs_avg": 129.4,
        },
        "risk_levels": {
            "entry": 66.21,
            "stop_loss": 60.00,
            "target_1": 78.63,
            "target_2": 84.84,
        },
    }


def test_build_actionable_alert_matches_generator_output():
    results = [_sample_result()]

    alert = build_actionable_alert(results, top_n=5)

    assert alert == generate_trading_alerts(results, top_n=5)


def test_build_actionable_alert_returns_none_for_hold_only():
    results = [_sample_result(signal="HOLD")]

    assert build_actionable_alert(results) is None


def test_deliver_trading_alerts_writes_snapshot_and_sends_exact_payload(tmp_path, monkeypatch):
    results = [_sample_result()]
    sent_messages = []

    def fake_send(token: str, chat_id: str, text: str, timeout: int = 30):
        sent_messages.append((token, chat_id, text, timeout))
        return {"ok": True}

    monkeypatch.setattr("src.alerts.delivery.send_telegram_text", fake_send)

    snapshot = tmp_path / "market_alert.txt"
    delivery = deliver_trading_alerts(
        results=results,
        token="test-token",
        chat_id="test-chat",
        output_path=str(snapshot),
    )

    expected_alert = generate_trading_alerts(results, top_n=5)
    assert delivery["alert"] == expected_alert
    assert delivery["chunks"] == 1
    assert sent_messages == [("test-token", "test-chat", expected_alert, 30)]
    assert snapshot.read_text(encoding="utf-8") == expected_alert
