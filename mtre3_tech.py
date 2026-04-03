#!/usr/bin/env python3
import sys
sys.path.insert(0, '.')
from production_simple import SimpleProductionRunner

runner = SimpleProductionRunner(use_news=False, use_fundamentals=False, n_workers=1)
results = runner.run(tickers=['MTRE3.SA'], parallel=False)

if results:
    r = results[0]
    print('=== MTRE3 TECHNICAL ANALYSIS ===')
    print(f"Price: R${r.get('price', 0):.2f}")
    print(f"Trend: {r.get('trend', 'N/A')} ({r.get('confidence', 0)*100:.0f}% confidence)")
    print(f"Signal: {r.get('signal', 'N/A')}")
    tech = r.get('technical_indicators', {})
    print(f"RSI: {tech.get('rsi', 0):.1f}")
    print(f"MACD: {tech.get('macd', 0):.2f}")
    print(f"vs 50d MA: {tech.get('price_vs_50d', 0):+.1f}%")
    print(f"vs 20d MA: {tech.get('price_vs_20d', 0):+.1f}%")
    print(f"Volume vs Avg: {tech.get('volume_vs_avg', 0):.1f}%")
    features = r.get('features', {})
    print(f"Volatility Regime: {features.get('volatility_regime', 'N/A')}")
    print(f"Unusual Volume: {features.get('unusual_volume', False)}")
