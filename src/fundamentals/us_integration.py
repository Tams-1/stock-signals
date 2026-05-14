"""
US Market Fundamental Integration.

Combines fundamental analysis from USFundamentalScorer with
technical analysis from the stock signals engine.

Data source: yfinance Ticker.info (free, via USDataClient).
"""

from dataclasses import dataclass
from typing import Optional, Dict, List
from pathlib import Path
import json
import math

from src.us_data_client import USDataClient
from src.fundamentals.us_scorer import USFundamentalScorer, USFundamentalScore


@dataclass
class USIntegratedScore:
    """Combined technical + fundamental score for US equities."""
    ticker: str
    name: Optional[str]

    # Technical
    technical_score: float
    trend: str
    confidence: float

    # Fundamental
    fundamental_score: float
    fundamental_grade: str
    value_score: float
    quality_score: float
    growth_score: float

    # Combined
    composite_score: float
    recommendation: str

    # Flags
    is_value_pick: bool
    is_quality_pick: bool
    is_momentum_pick: bool
    is_avoid: bool

    # Metrics
    pe_ratio: Optional[float]
    pb_ratio: Optional[float]
    roe: Optional[float]
    div_yield: Optional[float]
    market_cap: Optional[float]
    sector: Optional[str]

    # Feedback
    strengths: List[str]
    weaknesses: List[str]


class USFundamentalIntegrator:
    """
    Integrates technical analysis with US fundamental data.

    Weights (configurable):
    - Technical: 50%
    - Fundamental: 50%
    """

    TECHNICAL_WEIGHT = 0.50
    FUNDAMENTAL_WEIGHT = 0.50

    STRONG_BUY_THRESHOLD = 75
    BUY_THRESHOLD = 60
    HOLD_THRESHOLD = 40
    SELL_THRESHOLD = 25

    def __init__(self):
        self.data_client = USDataClient()
        self.scorer = USFundamentalScorer()

    def integrate(self, ticker: str, technical_score: float,
                  trend: str, confidence: float) -> USIntegratedScore:
        """
        Combine technical and fundamental analysis for a US stock.

        Args:
            ticker: Stock ticker (e.g., 'AAPL')
            technical_score: Technical score (0-100)
            trend: 'UPTREND', 'DOWNTREND', 'SIDEWAYS'
            confidence: Technical confidence (0-1)

        Returns:
            USIntegratedScore
        """
        # Fetch fundamentals live from yfinance
        raw_data = self.data_client.get_fundamentals(ticker)
        fund_score = self.scorer.score(ticker, raw_data)

        # Calculate composite with regime weighting
        trend_upper = (trend or 'SIDEWAYS').upper()
        regime_weights = {
            'UPTREND': (0.60, 0.40),
            'DOWNTREND': (0.35, 0.65),
            'SIDEWAYS': (0.45, 0.55),
        }
        tech_w, fund_w = regime_weights.get(trend_upper, (0.50, 0.50))

        composite = technical_score * tech_w + fund_score.composite_score * fund_w

        # Caps and adjustments
        if fund_score.composite_score < 35:
            composite = min(composite, 60)
        if fund_score.composite_score < 30 and trend_upper == 'DOWNTREND':
            composite -= 10
        if fund_score.value_score >= 80 and trend_upper == 'SIDEWAYS':
            composite += 5

        composite = max(0, min(100, composite))

        # Recommendation
        if composite >= self.STRONG_BUY_THRESHOLD:
            recommendation = 'STRONG_BUY'
        elif composite >= self.BUY_THRESHOLD:
            recommendation = 'BUY'
        elif composite >= self.HOLD_THRESHOLD:
            recommendation = 'HOLD'
        elif composite >= self.SELL_THRESHOLD:
            recommendation = 'SELL'
        else:
            recommendation = 'STRONG_SELL'

        # Trend-respect
        if trend_upper == 'UPTREND' and recommendation in ('SELL', 'STRONG_SELL'):
            recommendation = 'HOLD'

        # Flags
        is_momentum_pick = technical_score >= 70 and fund_score.composite_score >= 45

        # Strengths
        strengths = list(fund_score.strengths) if fund_score.strengths else []
        if is_momentum_pick:
            strengths.append("Momentum play: Strong technicals")

        return USIntegratedScore(
            ticker=ticker,
            name=fund_score.name,
            technical_score=technical_score,
            trend=trend,
            confidence=confidence,
            fundamental_score=round(fund_score.composite_score, 1),
            fundamental_grade=fund_score.grade,
            value_score=fund_score.value_score,
            quality_score=fund_score.quality_score,
            growth_score=fund_score.growth_score,
            composite_score=round(composite, 1),
            recommendation=recommendation,
            is_value_pick=fund_score.is_value_pick,
            is_quality_pick=fund_score.is_quality_pick,
            is_momentum_pick=is_momentum_pick,
            is_avoid=fund_score.is_avoid,
            pe_ratio=fund_score.pe_ratio,
            pb_ratio=fund_score.pb_ratio,
            roe=fund_score.roe,
            div_yield=fund_score.dividend_yield,
            market_cap=fund_score.market_cap,
            sector=fund_score.sector,
            strengths=strengths,
            weaknesses=list(fund_score.weaknesses) if fund_score.weaknesses else [],
        )
