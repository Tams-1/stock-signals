#!/usr/bin/env python3
import sys
sys.path.insert(0, '.')
from src.fundamentals.integration import FundamentalIntegrator
from production_simple import SimpleProductionRunner
import json

# Load fundamentals
with open('data/fundamentals/fundamentals_cache.json', 'r') as f:
    cache = json.load(f)

data = cache.get('data', {})
raw = data.get('SLCE3', {})

print('=== SLCE3 - SAO MARTINHO ===')
print(f"Company: {raw.get('company_name', 'N/A')}")
print(f"Sector: {raw.get('sector', 'N/A')} > {raw.get('subsector', 'N/A')}")
print(f"Market Cap: R${raw.get('market_cap', 0):,.0f}M")

print(f"\n📊 VALUATION")
print(f"  P/E: {raw.get('pe_ratio', 'N/A')}")
print(f"  P/B: {raw.get('pb_ratio', 'N/A')}")
print(f"  EV/EBITDA: {raw.get('ev_ebitda', 'N/A')}")
print(f"  P/S: {raw.get('ps_ratio', 'N/A')}")

print(f"\n📈 QUALITY")
print(f"  ROE: {raw.get('roe', 'N/A')}%")
print(f"  ROIC: {raw.get('roic', 'N/A')}%")
print(f"  EBIT Margin: {raw.get('ebit_margin', 'N/A')}%")
print(f"  Net Margin: {raw.get('net_margin', 'N/A')}%")
print(f"  Debt/Equity: {raw.get('debt_equity', 'N/A')}")

print(f"\n💰 RETURNS")
print(f"  Div Yield: {raw.get('div_yield', 'N/A')}%")
print(f"  Revenue Growth 5y: {raw.get('revenue_growth_5y', 'N/A')}%")

# Net Debt/EBITDA
net_debt = raw.get('net_debt', 0)
ebit = raw.get('ebit', 0)

print(f"\n📉 DEBT ANALYSIS")
print(f"  Net Debt: R${net_debt:,.0f}M")
print(f"  EBIT: R${ebit:,.0f}M")

if isinstance(net_debt, (int, float)) and isinstance(ebit, (int, float)) and ebit > 0:
    ebitda_est = ebit * 1.15
    net_debt_ebitda = net_debt / ebitda_est
    print(f"  Net Debt/EBITDA (est): {net_debt_ebitda:.1f}x", end='')
    if net_debt_ebitda > 4:
        print(' ⚠️ HIGH LEVERAGE')
    elif net_debt_ebitda > 3:
        print(' ⚠️ Elevated')
    elif net_debt_ebitda > 2:
        print(' ⚠️ Moderate')
    else:
        print(' ✅ Conservative')

integrator = FundamentalIntegrator()
integrator.load_fundamentals()
score = integrator.get_fundamental_score('SLCE3')

if score:
    print(f"\n🎯 MODEL SCORES")
    print(f"  Composite: {score.get('composite_score', 0):.1f}")
    print(f"  Value: {score.get('value_score', 0):.1f}")
    print(f"  Quality: {score.get('quality_score', 0):.1f}")
    print(f"  Strengths: {score.get('strengths', [])}")
    print(f"  Weaknesses: {score.get('weaknesses', [])}")

# Run technical analysis
print(f"\n📉 TECHNICAL ANALYSIS")
runner = SimpleProductionRunner(use_news=False, use_fundamentals=True, n_workers=1)
results = runner.run(tickers=['SLCE3.SA'], parallel=False)

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
    features = r.get('features', {})
    print(f"  Volatility: {features.get('volatility_regime', 'N/A')}")
    print(f"  Position Size: {r.get('position_size', 0)*100:.0f}%")
