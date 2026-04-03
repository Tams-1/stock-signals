#!/usr/bin/env python3
"""
Format ranked trading signals as a single text block (e.g. Telegram or logs).

Deduplicates same-issuer lines (e.g. PETR3 vs PETR4), then builds a concise
summary of top opportunities and risk notes from production result dicts.
"""

from typing import List, Dict
from datetime import datetime
import re
import math


def _get_ticker_group(ticker: str) -> str:
    """
    Get the base ticker group (e.g., PETR from PETR3/PETR4).
    
    Args:
        ticker: Full ticker string (e.g., 'PETR4.SA' or 'PETR4')
    
    Returns:
        Base ticker group (e.g., 'PETR')
    """
    # Remove .SA suffix
    ticker = ticker.replace('.SA', '')
    
    # Extract base (remove trailing digits)
    match = re.match(r'^([A-Z]+)', ticker)
    if match:
        return match.group(1)
    return ticker


def _deduplicate_ticker_groups(results: List[Dict]) -> List[Dict]:
    """
    Remove duplicate tickers from the same group, keeping the best one.
    
    For example, if both PETR3 and PETR4 appear, keeps only the one with
    higher conviction (or better fundamentals if tied).
    
    Args:
        results: List of analysis results
    
    Returns:
        Deduplicated list with only one ticker per group
    """
    groups = {}
    
    for r in results:
        ticker = r.get('ticker', '')
        group = _get_ticker_group(ticker)
        
        if group not in groups:
            groups[group] = r
        else:
            # Compare with existing - keep the better one
            existing = groups[group]
            
            # Priority: conviction > position_size > composite_score
            existing_conv = abs(existing.get('conviction', 0))
            new_conv = abs(r.get('conviction', 0))
            
            if new_conv > existing_conv:
                groups[group] = r
            elif new_conv == existing_conv:
                # Tie-breaker: position size (Kelly)
                existing_pos = existing.get('position_size', 0)
                new_pos = r.get('position_size', 0)
                
                if new_pos > existing_pos:
                    groups[group] = r
                elif new_pos == existing_pos:
                    # Final tie-breaker: fundamental score
                    existing_score = existing.get('fundamentals', {}).get('composite_score', 0)
                    new_score = r.get('fundamentals', {}).get('composite_score', 0)
                    
                    if new_score > existing_score:
                        groups[group] = r
    
    return list(groups.values())


def _signal_emoji(signal: str) -> str:
    return {
        "STRONG_BUY": "🚀",
        "BUY": "🟢",
        "HOLD": "🟡",
        "SELL": "🔴",
        "STRONG_SELL": "💀",
    }.get(signal, "⚪")


def _number_emoji(index: int) -> str:
    emojis = ['1️⃣', '2️⃣', '3️⃣', '4️⃣', '5️⃣']
    return emojis[index - 1] if 0 < index <= len(emojis) else f"{index}."


def _format_source_article(article: Dict) -> str:
    title = article.get('title', '').strip()
    source = article.get('source') or article.get('source_publication') or 'Unknown'
    if not title:
        return ""
    return f"{title} ({source})"


def _top_headlines(result: Dict, limit: int = 2) -> List[str]:
    articles = result.get('news_articles') or []
    formatted = []

    for article in articles:
        headline = _format_source_article(article)
        if headline:
            formatted.append(headline)
        if len(formatted) >= limit:
            return formatted

    for headline in result.get('news_headlines', [])[:limit]:
        if headline:
            formatted.append(headline)

    return formatted[:limit]


def _describe_fusion(score: float) -> str:
    if score >= 0.35:
        return "Strong bullish alignment"
    if score >= 0.15:
        return "Bullish alignment"
    if score <= -0.35:
        return "Strong bearish divergence"
    if score <= -0.15:
        return "Bearish divergence"
    return "Mixed/neutral setup"


def _news_impact_text(sentiment: float) -> str:
    position_multiplier = 0.5 + (1 / (1 + math.exp(-5 * sentiment)))
    position_delta = (position_multiplier - 1.0) * 100
    if sentiment > 0.10:
        return f"✅ Positive news boost ({position_delta:+.0f}% position)"
    if sentiment < -0.10:
        return f"⚠️ Negative news headwind ({position_delta:+.0f}% position)"
    return "😐 Neutral news (no material impact)"


def _conviction_label(position_pct: float) -> str:
    if position_pct >= 50:
        return "VERY HIGH"
    if position_pct >= 30:
        return "HIGH"
    if position_pct >= 15:
        return "MEDIUM"
    return "LOW"


def _watch_warnings(result: Dict) -> List[str]:
    technicals = result.get('technical_indicators', {})
    warnings = []

    price_vs_50d = technicals.get('price_vs_50d')
    if price_vs_50d is not None:
        if price_vs_50d > 0:
            warnings.append("Price closes back below the 50-day MA -> exit or tighten stop-loss")
        else:
            warnings.append("Price fails to reclaim the 50-day MA -> bullish thesis weakens")

    rsi = technicals.get('rsi')
    if rsi is not None:
        if rsi >= 70:
            warnings.append("RSI rolls back below 70 after overbought conditions -> take partial profits")
        elif rsi >= 60:
            warnings.append("RSI loses 55-60 momentum zone -> trend strength is fading")
        else:
            warnings.append("RSI breaks below 50 -> momentum confirmation is gone")

    macd = technicals.get('macd')
    macd_signal = technicals.get('macd_signal')
    if macd is not None and macd_signal is not None and macd <= macd_signal:
        warnings.append("MACD bearish crossover -> momentum confirmation has flipped")

    volume_vs_avg = technicals.get('volume_vs_avg')
    if volume_vs_avg is not None and volume_vs_avg < 70:
        warnings.append("Volume stays below 70% of the 20-day average -> breakout may fail")

    if not warnings:
        warnings.append("Close loses the recent breakout zone -> wait for a fresh confirmation candle")

    deduped = []
    for warning in warnings:
        if warning not in deduped:
            deduped.append(warning)

    return deduped[:2]


def generate_trading_alerts(results: List[Dict], top_n: int = 5) -> str:
    """
    Build a human-readable alert string from a list of per-ticker result dicts.

    Args:
        results: Analysis rows from ``SimpleProductionRunner`` / related runners
        top_n: Max number of top conviction names to expand in detail

    Returns:
        Multi-line formatted message suitable for chat or stdout
    """
    if not results:
        return "📊 No trading signals at this time."
    
    # Sort by conviction
    sorted_results = sorted(results, key=lambda x: abs(x.get('conviction', 0)), reverse=True)
    
    # Deduplicate ticker groups (PETR3/PETR4 -> keep best one)
    sorted_results = _deduplicate_ticker_groups(sorted_results)
    
    # Re-sort after deduplication
    sorted_results = sorted(sorted_results, key=lambda x: abs(x.get('conviction', 0)), reverse=True)
    
    # Filter to actionable signals
    buy_signals = [r for r in sorted_results if r['signal'] in ['STRONG_BUY', 'BUY']][:top_n]
    sell_signals = [r for r in sorted_results if r['signal'] in ['STRONG_SELL', 'SELL']][:3]
    
    lines = []
    lines.append("🚨 TOP TRADING OPPORTUNITIES")
    lines.append(f"Generated: {datetime.now().strftime('%H:%M:%S')}")
    lines.append("")
    
    # BUY signals
    for i, r in enumerate(buy_signals, 1):
        fund = r.get('fundamentals', {})
        num_emoji = _number_emoji(i)
        ticker = r['ticker'].replace('.SA', '')
        signal_label = r['signal'].replace('_', ' ')
        trend = r.get('trend', 'UNKNOWN')
        confidence = r.get('confidence', 0.0)
        fused_score = r.get('fused_score', 0.0)
        news_sentiment = r.get('news_sentiment', 0.0)
        headlines = _top_headlines(r)
        position_pct = r.get('position_size', 0.0) * 100

        lines.append(f"{num_emoji}  {ticker} - {signal_label} {_signal_emoji(r['signal'])}")
        # Show price with stale indicator if needed
        price_str = f"R${r['price']:.2f}"
        if r.get('is_price_stale'):
            price_str += " ⚠️ PREV CLOSE"
        lines.append(f"    Price: {price_str}")
        lines.append("    └─ Drivers:")
        lines.append(f"       • Trend: {trend} ({confidence:.0%} confidence)")
        lines.append(f"       • Fusion: {_describe_fusion(fused_score)} ({fused_score:+.2f})")
        lines.append(f"       • News: {news_sentiment:+.2f} sentiment")
        lines.append(f"         {_news_impact_text(news_sentiment)}")

        if headlines:
            lines.append("         📰 Headlines:")
            for headline in headlines:
                lines.append(f"            • {headline}")

        if fund:
            grade = fund.get('fundamental_grade', 'N/A')
            comp = fund.get('composite_score')
            if comp is not None:
                lines.append(f"       • Fundamentals: Grade {grade} | Composite {comp:.0f}")
            else:
                lines.append(f"       • Fundamentals: Grade {grade}")

        lines.append(
            f"       • Position: {position_pct:.0f}% "
            f"({_conviction_label(position_pct)} conviction)"
        )

        risk_levels = r.get('risk_levels', {})
        if risk_levels:
            lines.append("    └─ Levels:")
            lines.append(
                f"       Entry: R${risk_levels.get('entry', r['price']):.2f} | "
                f"Stop: R${risk_levels.get('stop_loss', r['price']):.2f}"
            )
            lines.append(
                f"       Targets: R${risk_levels.get('target_1', r['price']):.2f} (2:1) | "
                f"R${risk_levels.get('target_2', r['price']):.2f} (3:1)"
            )

        lines.append("    └─ Watch for:")
        for warning in _watch_warnings(r):
            lines.append(f"       ⚠️ {warning}")
        lines.append("")
    
    # Summary
    lines.append("=" * 70)
    lines.append(f"📊 Summary: {len(buy_signals)} BUY signals | {len(sell_signals)} SELL signals")
    lines.append("=" * 70)
    
    # SELL signals (compact)
    if sell_signals:
        lines.append("")
        lines.append("🔴 SELL SIGNALS:")
        for r in sell_signals:
            fund = r.get('fundamentals', {})
            grade = fund.get('fundamental_grade', 'N/A') if fund else 'N/A'
            fused_score = r.get('fused_score', 0.0)
            lines.append(
                f"  • {r['ticker'].replace('.SA', '')} - {r['signal']} "
                f"| Trend: {r['trend']} | Fusion: {fused_score:+.2f} | Grade: {grade}"
            )
    
    return "\n".join(lines)


def generate_fundamental_report(results: List[Dict], category: str = "value") -> str:
    """
    Generate a fundamental-focused report.
    
    Args:
        results: List of analysis results
        category: "value", "quality", or "momentum"
    
    Returns:
        Formatted string for Telegram
    """
    if not results:
        return "📊 No results to report."
    
    lines = []
    lines.append(f"📊 {category.upper()} STOCKS REPORT")
    lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append("")
    
    # Filter by category
    filtered = []
    for r in results:
        fund = r.get('fundamentals', {})
        if not fund:
            continue
        
        if category == "value" and fund.get('is_value_pick'):
            filtered.append(r)
        elif category == "quality" and fund.get('is_quality_pick'):
            filtered.append(r)
        elif category == "momentum" and fund.get('is_momentum_pick'):
            filtered.append(r)
    
    # Sort by composite score
    filtered.sort(key=lambda x: x.get('fundamentals', {}).get('composite_score', 0), reverse=True)
    
    if not filtered:
        lines.append(f"No {category} stocks found in current analysis.")
        return "\n".join(lines)
    
    for i, r in enumerate(filtered[:10], 1):
        fund = r.get('fundamentals', {})
        
        lines.append(f"{i:2}. {r['ticker'].replace('.SA', '')} - Grade {fund.get('fundamental_grade')}")
        lines.append(f"    Value: {fund.get('value_score', 0):.0f} | Quality: {fund.get('quality_score', 0):.0f} | Growth: {fund.get('growth_score', 0):.0f}")
        
        if fund.get('pe_ratio'):
            lines.append(f"    P/E: {fund['pe_ratio']:.1f} | P/B: {fund.get('pb_ratio', 0):.2f} | ROE: {fund.get('roe', 0):.1f}%")
        
        if fund.get('strengths'):
            lines.append(f"    ✅ {', '.join(fund['strengths'][:2])}")
        
        lines.append("")
    
    return "\n".join(lines)


if __name__ == "__main__":
    # Test with sample data
    sample = [
        {
            'ticker': 'PETR4.SA',
            'price': 37.97,
            'signal': 'BUY',
            'trend': 'uptrend',
            'confidence': 0.75,
            'position_size': 0.45,
            'fundamentals': {
                'fundamental_grade': 'A',
                'value_score': 85,
                'quality_score': 70,
                'growth_score': 55,
                'pe_ratio': 6.31,
                'pb_ratio': 1.16,
                'roe': 18.3,
                'div_yield': 8.5,
                'strengths': ['Low P/E (6.3)', 'High dividend yield (8.5%)'],
                'action_notes': ['💡 QUALITY MOMENTUM: High quality in uptrend']
            }
        }
    ]
    
    print(generate_trading_alerts(sample))