#!/usr/bin/env python3
import sys
sys.path.insert(0, '.')
import json

with open('data/fundamentals/fundamentals_cache.json', 'r') as f:
    cache = json.load(f)

data = cache.get('data', {})

top_picks = ['PETR4', 'CMIG4', 'SBSP3', 'SMTO3', 'NEOE3', 'MDNE3']

print('=== DEBT METRICS COMPARISON ===\n')
print(f"{'Ticker':<8} {'D/E':<8} {'EV/EBITDA':<12} {'Net Debt':<15} {'EBIT':<15}")
print('-' * 60)

for ticker in top_picks:
    raw = data.get(ticker, {})
    de = raw.get('debt_equity', 'N/A')
    ev_ebitda = raw.get('ev_ebitda', 'N/A')
    net_debt = raw.get('net_debt', 'N/A')
    ebit = raw.get('ebit', 'N/A')
    
    print(f"{ticker:<8} {de:<8} {ev_ebitda:<12} R${net_debt:>10,.0f}M  R${ebit:>10,.0f}M")
    
    # Calculate Net Debt / EBITDA ratio if we have the data
    if isinstance(net_debt, (int, float)) and isinstance(ebit, (int, float)) and ebit > 0:
        ebitda_est = ebit * 1.15  # typical depreciation ~15% of EBIT
        net_debt_ebitda = net_debt / ebitda_est
        print(f"         => Net Debt/EBITDA (est): {net_debt_ebitda:.1f}x", end="")
        
        # Risk assessment
        if net_debt_ebitda > 4:
            print(" ⚠️ HIGH LEVERAGE")
        elif net_debt_ebitda > 3:
            print(" ⚠️ Elevated")
        elif net_debt_ebitda > 2:
            print(" ⚠️ Moderate")
        else:
            print(" ✅ Conservative")
    print()
