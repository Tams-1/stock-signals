import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.fundamentals.integration import FundamentalIntegrator


def test_integrator_loads_raw_metrics_from_cache(tmp_path):
    data_dir = tmp_path / "data" / "fundamentals"
    data_dir.mkdir(parents=True)

    scores_path = data_dir / "fundamental_scores.json"
    raw_path = data_dir / "fundamentals_cache.json"

    scores_path.write_text(json.dumps({
        "scores": [
            {
                "ticker": "TEST3",
                "composite_score": 82,
                "grade": "A",
                "value_score": 74,
                "quality_score": 80,
                "growth_score": 60,
                "strengths": ["Low P/E"],
                "weaknesses": [],
            }
        ]
    }))

    raw_path.write_text(json.dumps({
        "data": {
            "TEST3": {
                "pe_ratio": 8.5,
                "pb_ratio": 0.9,
                "roe": 23.1,
                "roic": 18.4,
                "div_yield": 7.2,
                "debt_equity": 0.22,
            }
        }
    }))

    integrator = FundamentalIntegrator(fundamentals_path=scores_path)
    score = integrator.integrate(
        ticker="TEST3.SA",
        technical_score=78,
        trend="UPTREND",
        confidence=0.78,
    )

    assert score.pe_ratio == 8.5
    assert score.pb_ratio == 0.9
    assert score.roe == 23.1
    assert score.roic == 18.4
    assert score.debt_equity == 0.22
    assert score.is_quality_pick is True
    assert score.is_value_pick is True


def test_recommendation_thresholds_match_policy():
    integrator = FundamentalIntegrator()

    assert integrator._get_recommendation(75, "UPTREND", 80) == "STRONG_BUY"
    assert integrator._get_recommendation(60, "UPTREND", 80) == "BUY"
    assert integrator._get_recommendation(59.9, "UPTREND", 80) == "HOLD"
