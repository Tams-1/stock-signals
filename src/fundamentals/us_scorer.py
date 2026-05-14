"""
US Market Fundamental Scorer based on yfinance .info data.

Implements fundamental scoring adapted for US equities:
- Value scoring (P/E, P/B, P/S, EV/EBITDA)
- Quality scoring (ROE, ROIC, profit margins, debt/equity)
- Growth scoring (revenue growth, EPS growth)
- Graham-style defensive criteria

Data source: yfinance Ticker.info (free, no API key needed)
"""

from dataclasses import dataclass
from typing import Optional, Dict, List
import math


@dataclass
class USFundamentalScore:
    """Combined fundamental score for US equities."""
    ticker: str

    # Composite scores (0-100)
    value_score: float
    quality_score: float
    growth_score: float
    composite_score: float

    # Grade
    grade: str  # A, B, C, D, F

    # Flags
    is_value_pick: bool
    is_quality_pick: bool
    is_avoid: bool

    # Raw metrics
    pe_ratio: Optional[float]
    forward_pe: Optional[float]
    pb_ratio: Optional[float]
    ps_ratio: Optional[float]
    ev_ebitda: Optional[float]
    dividend_yield: Optional[float]
    roe: Optional[float]
    profit_margins: Optional[float]
    operating_margins: Optional[float]
    debt_equity: Optional[float]
    current_ratio: Optional[float]
    revenue_growth: Optional[float]
    eps: Optional[float]
    market_cap: Optional[float]
    beta: Optional[float]

    # Text feedback
    strengths: List[str]
    weaknesses: List[str]

    # Sector
    sector: Optional[str]
    industry: Optional[str]
    name: Optional[str]


class USFundamentalScorer:
    """
    Scores US equities based on fundamental data from yfinance.

    Uses sector-adjusted thresholds since different sectors have
    vastly different normal valuation ranges (e.g., tech vs utilities).
    """

    # Sector PE reference ranges
    SECTOR_PE_RANGES = {
        'Technology': (20, 35),
        'Healthcare': (15, 30),
        'Financial Services': (10, 20),
        'Consumer Cyclical': (12, 25),
        'Consumer Defensive': (18, 30),
        'Energy': (8, 18),
        'Basic Materials': (10, 22),
        'Industrials': (15, 28),
        'Utilities': (15, 25),
        'Real Estate': (15, 30),
        'Communication Services': (18, 30),
    }

    DEFAULT_PE_RANGE = (12, 25)

    @staticmethod
    def _coerce(value, default: float = 50.0) -> float:
        try:
            if value is None:
                return default
            numeric = float(value)
        except (TypeError, ValueError):
            return default
        if not math.isfinite(numeric):
            return default
        return numeric

    @staticmethod
    def _coerce_metric(value) -> Optional[float]:
        try:
            if value is None:
                return None
            numeric = float(value)
        except (TypeError, ValueError):
            return None
        if not math.isfinite(numeric):
            return None
        return numeric

    def _get_sector_pe_range(self, sector: Optional[str]) -> tuple:
        if sector is None:
            return self.DEFAULT_PE_RANGE
        for key, rng in self.SECTOR_PE_RANGES.items():
            if key.lower() in sector.lower():
                return rng
        return self.DEFAULT_PE_RANGE

    def _score_value(self, raw: Dict, sector: Optional[str]) -> float:
        """Score valuation (0-100, higher = cheaper/more attractive)."""
        pe_min, pe_max = self._get_sector_pe_range(sector)
        score = 50  # Neutral baseline

        pe = self._coerce_metric(raw.get('pe_ratio') or raw.get('trailingPE'))
        forward_pe = self._coerce_metric(raw.get('forward_pe') or raw.get('forwardPE'))
        pb = self._coerce_metric(raw.get('pb_ratio') or raw.get('priceToBook'))
        ps = self._coerce_metric(raw.get('ps_ratio') or raw.get('priceToSalesTrailing12Months'))
        ev_ebitda = self._coerce_metric(raw.get('ev_ebitda') or raw.get('enterpriseToEbitda'))

        # P/E scoring (sector-adjusted)
        if pe is not None and pe > 0:
            if pe < pe_min:
                score += 25  # Cheap relative to sector
            elif pe < (pe_min + pe_max) / 2:
                score += 10  # Fair
            elif pe < pe_max:
                score -= 10  # Slightly expensive
            else:
                score -= 25  # Expensive

        # Forward P/E bonus if lower than trailing (earnings improving)
        if forward_pe is not None and pe is not None and pe > 0:
            if forward_pe < pe * 0.85:
                score += 10  # Earnings growing into valuation

        # P/B scoring
        if pb is not None and pb > 0:
            if pb < 1.5:
                score += 15
            elif pb < 3:
                score += 5
            elif pb > 8:
                score -= 10

        # P/S scoring
        if ps is not None and ps > 0:
            if ps < 2:
                score += 10
            elif ps > 10:
                score -= 15

        # EV/EBITDA scoring
        if ev_ebitda is not None and ev_ebitda > 0:
            if ev_ebitda < 10:
                score += 10
            elif ev_ebitda > 20:
                score -= 10

        return max(0, min(100, score))

    def _score_quality(self, raw: Dict) -> float:
        """Score business quality (0-100, higher = better quality)."""
        score = 50

        roe = self._coerce_metric(raw.get('roe') or raw.get('returnOnEquity'))
        profit_margins = self._coerce_metric(raw.get('profit_margins') or raw.get('profitMargins'))
        op_margins = self._coerce_metric(raw.get('operating_margins') or raw.get('operatingMargins'))
        debt_equity = self._coerce_metric(raw.get('debt_equity') or raw.get('debtToEquity'))
        current_ratio = self._coerce_metric(raw.get('current_ratio') or raw.get('currentRatio'))

        # ROE scoring
        if roe is not None:
            if roe > 0.30:
                score += 20  # Exceptional
            elif roe > 0.20:
                score += 15  # Great
            elif roe > 0.15:
                score += 10  # Good
            elif roe > 0.10:
                score += 5   # OK
            elif roe < 0:
                score -= 20  # Negative ROE

        # Profit margins
        if profit_margins is not None:
            if profit_margins > 0.20:
                score += 15
            elif profit_margins > 0.10:
                score += 10
            elif profit_margins > 0.05:
                score += 5
            elif profit_margins < 0:
                score -= 20

        # Operating margins (premium for high op margins)
        if op_margins is not None:
            if op_margins > 0.25:
                score += 10
            elif op_margins > 0.15:
                score += 5
            elif op_margins < 0:
                score -= 15

        # Debt/Equity (lower = safer)
        if debt_equity is not None:
            if debt_equity < 0.3:
                score += 10  # Low debt
            elif debt_equity < 1.0:
                score += 5
            elif debt_equity > 2.0:
                score -= 10  # High leverage
            elif debt_equity > 5.0:
                score -= 20  # Very high leverage

        # Current ratio (liquidity)
        if current_ratio is not None:
            if 1.5 <= current_ratio <= 3.0:
                score += 10  # Sweet spot
            elif current_ratio < 1.0:
                score -= 10  # Liquidity risk

        return max(0, min(100, score))

    def _score_growth(self, raw: Dict) -> float:
        """Score growth metrics (0-100, higher = stronger growth)."""
        score = 50

        rev_growth = self._coerce_metric(raw.get('revenue_growth') or raw.get('revenueGrowth'))
        earnings_growth = self._coerce_metric(raw.get('earnings_growth') or raw.get('earningsGrowth'))
        eps = self._coerce_metric(raw.get('eps') or raw.get('trailingEps'))

        # Revenue growth
        if rev_growth is not None:
            if rev_growth > 0.30:
                score += 25
            elif rev_growth > 0.15:
                score += 15
            elif rev_growth > 0.05:
                score += 8
            elif rev_growth < 0:
                score -= 15

        # Earnings growth
        if earnings_growth is not None:
            if earnings_growth > 0.30:
                score += 20
            elif earnings_growth > 0.15:
                score += 12
            elif earnings_growth > 0.05:
                score += 5
            elif earnings_growth < 0:
                score -= 15

        # Positive EPS
        if eps is not None:
            if eps > 5:
                score += 5
            elif eps < 0:
                score -= 10

        return max(0, min(100, score))

    def _get_grade(self, composite: float) -> str:
        if composite >= 80:
            return 'A'
        elif composite >= 65:
            return 'B'
        elif composite >= 50:
            return 'C'
        elif composite >= 35:
            return 'D'
        else:
            return 'F'

    def score(self, ticker: str, raw_data: Dict) -> USFundamentalScore:
        """
        Score a US stock using raw yfinance info dict.

        Args:
            ticker: Stock ticker (e.g., 'AAPL')
            raw_data: Output from yfinance.Ticker.info or USDataClient.get_fundamentals()

        Returns:
            USFundamentalScore with all scoring components
        """
        sector = raw_data.get('sector')
        name = raw_data.get('name') or raw_data.get('shortName') or raw_data.get('longName') or ticker

        value_score = self._score_value(raw_data, sector)
        quality_score = self._score_quality(raw_data)
        growth_score = self._score_growth(raw_data)

        # Composite: value 30%, quality 40%, growth 30%
        composite = value_score * 0.30 + quality_score * 0.40 + growth_score * 0.30
        grade = self._get_grade(composite)

        # Flags
        is_value_pick = value_score >= 70 and quality_score >= 50
        is_quality_pick = quality_score >= 75 and growth_score >= 40
        is_avoid = value_score < 35 and quality_score < 35

        # Strengths & weaknesses
        strengths = []
        weaknesses = []

        pe = self._coerce_metric(raw_data.get('pe_ratio') or raw_data.get('trailingPE'))
        roe = self._coerce_metric(raw_data.get('roe') or raw_data.get('returnOnEquity'))
        profit_margins = self._coerce_metric(raw_data.get('profit_margins') or raw_data.get('profitMargins'))
        rev_growth = self._coerce_metric(raw_data.get('revenue_growth') or raw_data.get('revenueGrowth'))
        debt_equity = self._coerce_metric(raw_data.get('debt_equity') or raw_data.get('debtToEquity'))

        if is_value_pick:
            strengths.append("Value play: Attractive valuation")
        if is_quality_pick:
            strengths.append("Quality play: High ROE & margins")
        if value_score >= 80:
            strengths.append("Deep value: Very cheap relative to fundamentals")
        if quality_score >= 80:
            strengths.append("Excellent quality: Industry-leading profitability")
        if growth_score >= 75:
            strengths.append("Strong growth: Double-digit revenue growth")

        if is_avoid:
            weaknesses.append("AVOID: Poor quality and expensive")
        if pe is not None and pe > 30:
            weaknesses.append(f"Expensive: P/E of {pe:.1f}x")
        if roe is not None and roe < 0.05:
            weaknesses.append("Low ROE: Poor capital efficiency")
        if profit_margins is not None and profit_margins < 0:
            weaknesses.append("Negative profit margins")
        if debt_equity is not None and debt_equity > 3:
            weaknesses.append("High leverage")
        if rev_growth is not None and rev_growth < 0:
            weaknesses.append("Declining revenue")
        if quality_score < 40:
            weaknesses.append("Weak business quality")

        return USFundamentalScore(
            ticker=ticker,
            value_score=round(value_score, 1),
            quality_score=round(quality_score, 1),
            growth_score=round(growth_score, 1),
            composite_score=round(composite, 1),
            grade=grade,
            is_value_pick=is_value_pick,
            is_quality_pick=is_quality_pick,
            is_avoid=is_avoid,
            pe_ratio=self._coerce_metric(raw_data.get('pe_ratio') or raw_data.get('trailingPE')),
            forward_pe=self._coerce_metric(raw_data.get('forward_pe') or raw_data.get('forwardPE')),
            pb_ratio=self._coerce_metric(raw_data.get('pb_ratio') or raw_data.get('priceToBook')),
            ps_ratio=self._coerce_metric(raw_data.get('ps_ratio') or raw_data.get('priceToSalesTrailing12Months')),
            ev_ebitda=self._coerce_metric(raw_data.get('ev_ebitda') or raw_data.get('enterpriseToEbitda')),
            dividend_yield=self._coerce_metric(raw_data.get('div_yield') or raw_data.get('dividendYield')),
            roe=roe,
            profit_margins=profit_margins,
            operating_margins=self._coerce_metric(raw_data.get('operating_margins') or raw_data.get('operatingMargins')),
            debt_equity=debt_equity,
            current_ratio=self._coerce_metric(raw_data.get('current_ratio') or raw_data.get('currentRatio')),
            revenue_growth=rev_growth,
            eps=self._coerce_metric(raw_data.get('eps') or raw_data.get('trailingEps')),
            market_cap=self._coerce_metric(raw_data.get('market_cap') or raw_data.get('marketCap')),
            beta=self._coerce_metric(raw_data.get('beta')),
            strengths=strengths,
            weaknesses=weaknesses,
            sector=sector,
            industry=raw_data.get('industry'),
            name=name,
        )


def format_us_fundamental_score(score: USFundamentalScore) -> str:
    """Format US fundamental score for display."""
    lines = []
    grade_emoji = {'A': '🟢', 'B': '🟢', 'C': '🟡', 'D': '🔴', 'F': '🔴'}
    emoji = grade_emoji.get(score.grade, '❓')

    lines.append(f"{emoji} {score.ticker} - {score.name or ''}")
    lines.append(f"Grade: {score.grade} | Composite: {score.composite_score:.0f}")
    lines.append(f"Value: {score.value_score:.0f} | Quality: {score.quality_score:.0f} | Growth: {score.growth_score:.0f}")

    metrics = []
    if score.pe_ratio:
        metrics.append(f"P/E: {score.pe_ratio:.1f}")
    if score.pb_ratio:
        metrics.append(f"P/B: {score.pb_ratio:.2f}")
    if score.roe is not None:
        metrics.append(f"ROE: {score.roe*100:.1f}%")
    if score.dividend_yield is not None:
        metrics.append(f"Div: {score.dividend_yield*100:.2f}%")

    if metrics:
        lines.append(" | ".join(metrics))

    if score.strengths:
        for s in score.strengths:
            lines.append(f"  ✅ {s}")
    if score.weaknesses:
        for w in score.weaknesses:
            lines.append(f"  ⚠️ {w}")

    if score.sector:
        lines.append(f"  Sector: {score.sector}")

    return "\n".join(lines)
