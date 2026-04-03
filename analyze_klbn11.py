#!/usr/bin/env python3
import sys
sys.path.insert(0, '.')
from production_simple import SimpleProductionRunner
from src.fundamentals.integration import FundamentalIntegrator
import json

# Load fundamentals cache
with open('data/fundamentals/fundamentals_cache.json', 'r') as f:
    fund_cache = json.load(f)

# Get KLBN11 fundamentals
data = fund_cache.get('data', {})
klbn_fund = data.get('KLBN11', {})
print('=== FUNDAMENTALS ===')
print(f"P/E: {klbn_fund.get('pe_ratio', 'N/A')}")
print(f"P/B: {klbn_fund.get('pb_ratio', 'N/A')}")
print(f"ROE: {klbn_fund.get('roe', 'N/A')}%")
print(f"ROIC: {klbn_fund.get('roic', 'N/A')}%")
print(f"Div Yield: {klbn_fund.get('div_yield', 'N/A')}%")
print(f"Debt/Equity: {klbn_fund.get('debt_equity', 'N/A')}")

# Calculate composite score
integrator = FundamentalIntegrator()
integrator.load_fundamentals()
score = integrator.get_fundamental_score('KLBN11')
print(f"\n=== COMPOSITE SCORE ===")
if score:
    print(f"Total: {score.get('composite_score', 'N/A')}")
    print(f"Grade: {score.get('fundamental_grade', 'N/A')}")
    print(f"Value Score: {score.get('value_score', 'N/A')}")
    print(f"Quality Score: {score.get('quality_score', 'N/A')}")
    print(f"Strengths: {score.get('strengths', [])}")
    print(f"Weaknesses: {score.get('weaknesses', [])}")
else:
    print("No score found")
