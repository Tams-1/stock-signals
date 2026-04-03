#!/usr/bin/env python3
import sys
sys.path.insert(0, '.')
from production_simple import SimpleProductionRunner
from src.fundamentals.integration import FundamentalIntegrator
import json

# Load fundamentals
with open('data/fundamentals/fundamentals_cache.json', 'r') as f:
    cache = json.load(f)

data = cache.get('data', {})
raw = data.get('NEOE3', {})

print('=== NEOE3 - NEOENERGIA ===')
print(f"Sector: {raw.get('sector', 'N/A')} > {raw.get('subsector', 'N/A')}")
print(f"Company: {raw.get('company_name', 'N/A')}")
print(f"Market Cap: R${raw.get('market_cap', 0):,.1f}M")

print('\n📊 VALUATION')
print(f"  P/E: {raw.get('pe_ratio', 'N/A')}")
print(f"  P/B: {raw.get('pb_ratio', 'N/A')}")
print(f"  EV/EBITDA: {raw.get('ev_ebitda', 'N/A')}")
print(f"  P/S: {raw.get('ps_ratio', 'N/A')}")

print('\n📈 QUALITY')
print(f"  ROE: {raw.get('roe', 'N/A')}%")
print(f"  ROIC: {raw.get('roic', 'N/A')}%")
print(f"  EBIT Margin: {raw.get('ebit_margin', 'N/A')}%")
print(f"  Net Margin: {raw.get('net_margin', 'N/A')}%")
print(f"  Debt/Equity: {raw.get('debt_equity', 'N/A')}")

print('\n💰 RETURNS')
print(f"  Div Yield: {raw.get('div_yield', 'N/A')}%")
print(f"  Revenue Growth 5y: {raw.get('revenue_growth_5y', 'N/A')}%")

integrator = FundamentalIntegrator()
integrator.load_fundamentals()
score = integrator.get_fundamental_score('NEOE3')

if score:
    print('\n🎯 SCORES')
    print(f"  Composite: {score.get('composite_score', 0):.1f}")
    print(f"  Value: {score.get('value_score', 0):.1f}")
    print(f"  Quality: {score.get('quality_score', 0):.1f}")
    print(f"  Strengths: {score.get('strengths', [])}")
    print(f"  Weaknesses: {score.get('weaknesses', [])}")

# Run technical analysis
print('\n📉 TECHNICAL ANALYSIS')
runner = SimpleProductionRunner(use_news=False, use_fundamentals=True, n_workers=1)
results = runner.run(tickers=['NEOE3.SA'], parallel=False)

if results:
    r = results[0]
    print(f"  Price: R${r.get('price', 0):.2f}")
    print(f"  Trend: {r.get('trend', 'N/A')} ({r.get('confidence', 0)*100:.0f}% confidence)")
    print(f"  Signal: {r.get('signal', 'N/A')}")
    tech = r.get('technical_indicators', {})
    print(f"  RSI: {tech.get('rsi', 0):.1f}")
    print(f"  MACD: {tech.get('macd', 0):.2f}")
    print(f"  vs 50d MA: {tech.get('price_vs_50d', 0):+.1f}%")
    print(f"  vs 20d MA: {tech.get('price_vs_20d', 0):+.1f}%")
    print(f"\n  Position Size: {r.get('position_size', 0)*100:.0f}%")
