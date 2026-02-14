"""
Run all tests and backtest with visualization.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

import subprocess
from datetime import datetime, timedelta

print("="*70)
print("STOCK SIGNAL DETECTOR - COMPREHENSIVE TEST SUITE")
print("="*70)

# 1. Run unit tests
print("\n1. Running unit tests...")
print("-"*70)

result = subprocess.run([sys.executable, '-m', 'pytest', 'tests/test_signals.py', '-v'],
                       cwd=Path(__file__).parent)

if result.returncode == 0:
    print("\n✅ Unit tests PASSED")
else:
    print("\n❌ Unit tests FAILED")

# 2. Run backtest
print("\n2. Running backtests and generating visualizations...")
print("-"*70)

from backtest.trading_simulator import TradingSimulator
from backtest.visualize_results import plot_backtest_results

# Test on multiple stocks
tickers = ['AAPL', 'MSFT', 'NVDA', 'TSLA', 'GOOGL']

end_date = datetime.now()
start_date = end_date - timedelta(days=180)  # 6 months

print(f"\nBacktesting {len(tickers)} stocks from {start_date.date()} to {end_date.date()}...")
print(f"Initial capital: $10,000 | Position size: 50% | Signal threshold: 0.5\n")

simulator = TradingSimulator(initial_capital=10000, position_size=0.5)
results = simulator.run_backtest(tickers, start_date, end_date, threshold=0.5)

# Generate report
simulator.generate_report(results)

# Visualize
print("\n3. Generating visualization...")
print("-"*70)

plot_path = Path(__file__).parent / 'backtest' / 'backtest_results.png'
try:
    plot_backtest_results(results, save_path=str(plot_path))
    print(f"\n✅ Visualization saved: {plot_path}")
except Exception as e:
    print(f"\n❌ Visualization failed: {e}")

# 3. Summary
print("\n" + "="*70)
print("TEST SUITE COMPLETE")
print("="*70)
print("\nResults:")
if results:
    print(f"  ✅ Backtest completed on {len(results)} stocks")
    total_return = sum(r['total_return_pct'] for r in results) / len(results)
    print(f"  📊 Average return: {total_return:+.1f}%")
    print(f"  📈 Visualization: {plot_path}")
else:
    print("  ❌ Backtest failed")
