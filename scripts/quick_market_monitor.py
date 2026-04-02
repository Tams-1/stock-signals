#!/usr/bin/env python3
"""
Quick market monitor — default scheduled production path.

Loads the top 50 liquid tickers from ``data/top_50_tickers.json`` (with a small
hardcoded fallback if the file is missing or invalid), runs ``SimpleProductionRunner``
with **fundamentals on** and **news off** (``use_news=False``) to avoid news API
rate limits, then prints ``generate_trading_alerts`` output.

Typical automation: Mon–Fri at **09:00, 14:00, 16:00** ``America/Sao_Paulo`` via
cron or OpenClaw (host timezone must match your intent).
"""

import sys
import os
import json
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import production runner
from production_simple import SimpleProductionRunner

def load_tickers():
    """Load top 50 tickers from optimized list."""
    config_path = Path(__file__).parent.parent / 'data' / 'top_50_tickers.json'
    fallback_tickers = [
        'PETR4.SA', 'VALE3.SA', 'ITUB4.SA', 'BBDC4.SA', 'BBAS3.SA',
        'ABEV3.SA', 'B3SA3.SA', 'WEGE3.SA', 'RENT3.SA', 'SUZB3.SA'
    ]

    if not config_path.exists():
        print("⚠️ top_50_tickers.json not found, using fallback")
        return fallback_tickers

    try:
        with open(config_path, 'r') as f:
            data = json.load(f)
    except json.JSONDecodeError:
        print("⚠️ top_50_tickers.json is malformed, using fallback")
        return fallback_tickers

    if not isinstance(data, dict):
        print("⚠️ top_50_tickers.json has invalid structure, using fallback")
        return fallback_tickers

    tickers = data.get('top_50', [])
    if not isinstance(tickers, list) or not tickers:
        print("⚠️ top_50_tickers.json has no valid tickers, using fallback")
        return fallback_tickers

    # Add .SA suffix for Yahoo Finance
    normalized_tickers = [
        f"{t}.SA" if not t.endswith('.SA') else t
        for t in tickers
        if isinstance(t, str) and t.strip()
    ]
    if not normalized_tickers:
        print("⚠️ top_50_tickers.json has no valid tickers, using fallback")
        return fallback_tickers

    return normalized_tickers

def main():
    tickers = load_tickers()
    print(f"🚀 QUICK MONITOR - {len(tickers)} tickers (optimized)")

    runner = SimpleProductionRunner(
        use_news=False,      # Skip news to avoid rate limits
        use_fundamentals=True, # Keep fundamentals for quality signals
        n_workers=4          # Reduce workers for stability
    )

    results = runner.run(tickers=tickers, parallel=True)

    if not results:
        print("\n❌ No actionable signals found")
        return "NO_SIGNALS"

    # Generate alerts
    from src.alerts.alert_generator import generate_trading_alerts
    alerts = generate_trading_alerts(results)

    if isinstance(alerts, str) and alerts.strip():
        print("\n✅ Alerts generated")
        return alerts

    print("\n❌ No alerts generated")
    return "NO_SIGNALS"

if __name__ == "__main__":
    main()
