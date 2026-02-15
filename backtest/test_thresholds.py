#!/usr/bin/env python3
"""
Test multiple thresholds to find optimal configuration

Current: 0.25 → +14.42% (17 trades)
Target: Beat buy&hold (+46.30%) and IBOV (+40.79%)
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import subprocess
import json

# Thresholds to test
THRESHOLDS = [0.15, 0.20, 0.25, 0.30]

print("="*70)
print("🧪 THRESHOLD OPTIMIZATION TEST")
print("="*70)
print(f"\nTesting thresholds: {THRESHOLDS}")
print("Period: Aug 2025 - Feb 2026 (6 months)")
print("Baseline: Buy & Hold +46.30%, IBOV +40.79%")
print(f"Current (0.25): +14.42% (17 trades)\n")

results = []

for threshold in THRESHOLDS:
    print(f"\n{'='*70}")
    print(f"🔍 Testing threshold: {threshold}")
    print(f"{'='*70}\n")
    
    # Modify realtime_backtest.py threshold
    with open('realtime_backtest.py', 'r') as f:
        content = f.read()
    
    # Replace threshold in two places (uptrend and downtrend checks)
    modified = content.replace(
        'if trend == "uptrend" and confidence > 0.25:',
        f'if trend == "uptrend" and confidence > {threshold}:'
    ).replace(
        'elif trend == "downtrend" and confidence > 0.25:',
        f'elif trend == "downtrend" and confidence > {threshold}:'
    )
    
    with open('realtime_backtest.py', 'w') as f:
        f.write(modified)
    
    # Run backtest
    try:
        result = subprocess.run(
            ['python3', 'realtime_backtest.py'],
            capture_output=True,
            text=True,
            timeout=300
        )
        
        # Load results
        with open('realtime_backtest_results.json', 'r') as f:
            data = json.load(f)
        
        results.append({
            'threshold': threshold,
            'return': data['total_return_pct'],
            'trades': data['total_trades'],
            'vs_ibov': data['vs_ibov']
        })
        
        print(f"✅ Threshold {threshold}:")
        print(f"   Return: {data['total_return_pct']:+.2f}%")
        print(f"   Trades: {data['total_trades']}")
        print(f"   vs IBOV: {data['vs_ibov']:+.2f}%")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        results.append({
            'threshold': threshold,
            'return': None,
            'trades': None,
            'vs_ibov': None,
            'error': str(e)
        })

print(f"\n{'='*70}")
print("📊 RESULTS SUMMARY")
print(f"{'='*70}\n")

print(f"{'Threshold':<12} {'Return':<12} {'Trades':<10} {'vs IBOV':<12} {'vs B&H':<12}")
print("-" * 70)

buy_hold = 46.30

for r in results:
    if r['return'] is not None:
        vs_bh = r['return'] - buy_hold
        print(f"{r['threshold']:<12.2f} {r['return']:+11.2f}% {r['trades']:<10} {r['vs_ibov']:+11.2f}% {vs_bh:+11.2f}%")
    else:
        print(f"{r['threshold']:<12.2f} {'ERROR':<12} {'-':<10} {'-':<12} {'-':<12}")

# Find best
valid_results = [r for r in results if r['return'] is not None]
if valid_results:
    best = max(valid_results, key=lambda x: x['return'])
    
    print(f"\n{'='*70}")
    print("🏆 BEST CONFIGURATION")
    print(f"{'='*70}\n")
    print(f"Threshold: {best['threshold']}")
    print(f"Return: {best['return']:+.2f}%")
    print(f"Trades: {best['trades']}")
    print(f"vs IBOV: {best['vs_ibov']:+.2f}%")
    print(f"vs Buy & Hold: {best['return'] - buy_hold:+.2f}%")
    
    if best['return'] > buy_hold:
        print("\n✅ BEATS BUY & HOLD!")
    if best['vs_ibov'] > 0:
        print("✅ BEATS IBOV!")

# Restore original threshold
with open('realtime_backtest.py', 'r') as f:
    content = f.read()

# Restore to 0.25
for threshold in THRESHOLDS:
    content = content.replace(
        f'if trend == "uptrend" and confidence > {threshold}:',
        'if trend == "uptrend" and confidence > 0.25:'
    ).replace(
        f'elif trend == "downtrend" and confidence > {threshold}:',
        'elif trend == "downtrend" and confidence > 0.25:'
    )

with open('realtime_backtest.py', 'w') as f:
    f.write(content)

print(f"\n{'='*70}")
print("✅ Original threshold (0.25) restored")
print(f"{'='*70}\n")

# Save results
with open('threshold_optimization_results.json', 'w') as f:
    json.dump(results, f, indent=2)

print("💾 Results saved to threshold_optimization_results.json")
