#!/usr/bin/env python3
import sys
sys.path.append('.')

from production_simple import SimpleProductionRunner

runner = SimpleProductionRunner(use_news=True, use_fundamentals=True, n_workers=4)

# Focus on major liquid stocks
key_tickers = ['PETR4.SA', 'VALE3.SA', 'ITUB4.SA', 'BBDC4.SA', 'BBAS3.SA', 'ABEV3.SA', 'B3SA3.SA', 'WEGE3.SA', 'SUZB3.SA', 'RENT3.SA']

results = runner.run(tickers=key_tickers, parallel=False)

# Filter for actionable signals
actionable = [r for r in results if r['signal'] in ('BUY', 'STRONG_BUY', 'SELL', 'STRONG_SELL')]

print('\n' + '='*70)
print('ACTIONABLE SIGNALS FOR BR MARKET')
print('='*70 + '\n')

if actionable:
    for r in actionable:
        fund = r.get('fundamentals', {})
        print(f'{r["ticker"]}: {r["signal"]} @ R${r["price"]:.2f}')
        print(f'  Trend: {r["trend"]} | Conviction: {r["conviction"]:.2f} | Position: {r["position_size"]*100:.0f}%')
        if fund:
            print(f'  Fundamentals - P/E: {fund.get("pe_ratio", "N/A"):.1f} | P/B: {fund.get("pb_ratio", 0):.2f} | ROE: {fund.get("roe", 0):.1f}% | Div: {fund.get("div_yield", 0):.1f}%')
            if fund.get('strengths'):
                print(f'  Strengths: {", ".join(fund["strengths"][:2])}')
            if fund.get('action_notes'):
                for note in fund['action_notes'][:2]:
                    print(f'  Note: {note}')
        print()
else:
    print('NO ACTIONABLE SIGNALS')
    print('All analyzed stocks returned HOLD signals.')
    print('\nSummary:')
    buy = [r for r in results if r['signal'] == 'BUY']
    sell = [r for r in results if r['signal'] == 'SELL']
    hold = [r for r in results if r['signal'] == 'HOLD']
    print(f'  BUY: {len(buy)} | SELL: {len(sell)} | HOLD: {len(hold)}')
