#!/usr/bin/env python3
"""
Quick scan for US market — key S&P 500 mega-caps.

Usage:
  python3 quick_scan_us.py                     # Default tickers (top 25)
  python3 quick_scan_us.py --tickers AAPL TSLA  # Custom tickers
  python3 quick_scan_us.py --no-news           # Skip news fetching
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from production_us import USProductionRunner

# Mega-cap focus for quick scan
MEGA_CAPS = [
    "AAPL", "MSFT", "NVDA", "GOOGL", "AMZN", "META", "BRK-B", "LLY", "AVGO", "TSLA",
    "JPM", "V", "XOM", "UNH", "MA", "PG", "COST", "JNJ", "HD", "MRK",
    "ABBV", "CVX", "CRM", "BAC", "WMT",
]

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Quick scan US market')
    parser.add_argument('--tickers', nargs='+', default=MEGA_CAPS,
                       help='Tickers to scan (default: top 25 mega-caps)')
    parser.add_argument('--no-news', action='store_true', help='Disable news')
    args = parser.parse_args()

    runner = USProductionRunner(
        use_news=not args.no_news,
        use_fundamentals=True,
        ticker_list=args.tickers,
    )

    results = runner.run()

    # Pretty top-picks display
    actionable = [r for r in results if r['signal'] in ('STRONG_BUY', 'BUY', 'SELL', 'STRONG_SELL')]

    print('\n' + '=' * 70)
    print('🎯 ACTIONABLE SIGNALS — US MARKET')
    print('=' * 70 + '\n')

    if actionable:
        for r in actionable:
            sig = r["signal"]
            emoji = {"STRONG_BUY": "🟢", "BUY": "🔵", "SELL": "🔴", "STRONG_SELL": "⛔"}
            prefix = emoji.get(sig, "⚪")

            price = r.get('price', 0)
            fund = r.get('fundamentals', {})

            print(f'{prefix} {r["ticker"]:6s} | {sig:11s} | ${price:.2f}')
            print(f'     Trend: {r["trend"]:12s} | Score: {r["composite_score"]:.0f} | Position: {r["position_size"]*100:.0f}%')

            if fund:
                metrics = []
                pe = fund.get('pe_ratio')
                roe = fund.get('roe')
                grade = fund.get('grade', 'N/A')
                if pe:
                    metrics.append(f'P/E: {pe:.1f}')
                if roe:
                    metrics.append(f'ROE: {roe*100:.1f}%')
                metrics.append(f'Grade: {grade}')
                print(f'     {" | ".join(metrics)}')

                strengths = fund.get('strengths', [])
                weaknesses = fund.get('weaknesses', [])
                if strengths:
                    for s in strengths[:2]:
                        print(f'     ✅ {s}')
                if weaknesses:
                    for w in weaknesses[:2]:
                        print(f'     ⚠️ {w}')
            print()
    else:
        print('NO ACTIONABLE SIGNALS — all HOLD')
        print()

    # Summary bar
    signals = [r['signal'] for r in results]
    total = len(signals)
    print(f'📊 {total} tickers: '
          f'🟢{signals.count("STRONG_BUY")} '
          f'🔵{signals.count("BUY")} '
          f'⚪{signals.count("HOLD")} '
          f'🔴{signals.count("SELL")} '
          f'⛔{signals.count("STRONG_SELL")}')
