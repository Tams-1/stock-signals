#!/usr/bin/env python3
"""Generate visualization plots from fixed code backtest results."""

import json
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
import pandas as pd
from pathlib import Path
from datetime import datetime

# Load results
results_file = Path(__file__).parent.parent / 'brazilian_backtest_results.json'
with open(results_file, 'r') as f:
    results = json.load(f)

# Create output directory
output_dir = Path(__file__).parent.parent / 'Documents' / 'TARS projects'
output_dir.mkdir(parents=True, exist_ok=True)

# Extract data
tickers = [r['ticker'] for r in results]
returns = [r['total_return_pct'] for r in results]
win_rates = [r['win_rate_pct'] for r in results]
trades = [r['num_trades'] for r in results]
drawdowns = [r['max_drawdown_pct'] for r in results]

# Flatten trades for win rate calculation
all_trades = []
for r in results:
    all_trades.extend(r['trades'])

# Create color scheme
colors = ['green' if r > 0 else 'red' for r in returns]

# ===== PLOT 1: Stock Performance Ranking =====
print("Generating Plot 1: Stock Performance Ranking...")
fig, ax = plt.subplots(figsize=(14, 8))

sorted_indices = np.argsort(returns)
sorted_tickers = [tickers[i] for i in sorted_indices]
sorted_returns = [returns[i] for i in sorted_indices]
sorted_colors = [colors[i] for i in sorted_indices]

bars = ax.barh(sorted_tickers, sorted_returns, color=sorted_colors, alpha=0.7, edgecolor='black')

# Add value labels
for i, (ticker, ret) in enumerate(zip(sorted_tickers, sorted_returns)):
    ax.text(ret + 0.5, i, f'{ret:+.1f}%', va='center', fontweight='bold')

ax.axvline(x=0, color='black', linestyle='-', linewidth=0.8)
ax.set_xlabel('Return (%)', fontsize=12, fontweight='bold')
ax.set_title('Brazilian Market Backtest - Stock Performance Ranking\n(Fixed Code: Feb 2025 - Feb 2026)', 
             fontsize=14, fontweight='bold')
ax.grid(axis='x', alpha=0.3)

plt.tight_layout()
plt.savefig(output_dir / 'stock_performance_ranking_fixed.png', dpi=300, bbox_inches='tight')
print(f"✓ Saved: {output_dir / 'stock_performance_ranking_fixed.png'}")
plt.close()

# ===== PLOT 2: Win Rate by Stock =====
print("Generating Plot 2: Win Rate by Stock...")
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 6))

# Left: Win rate scatter
scatter = ax1.scatter(trades, win_rates, s=[abs(r)*20 for r in returns], 
                     c=returns, cmap='RdYlGn', alpha=0.6, edgecolors='black', linewidth=1)

for i, ticker in enumerate(tickers):
    if trades[i] > 0:
        ax1.annotate(ticker, (trades[i], win_rates[i]), 
                    xytext=(5, 5), textcoords='offset points', fontsize=9)

ax1.set_xlabel('Number of Trades', fontsize=12, fontweight='bold')
ax1.set_ylabel('Win Rate (%)', fontsize=12, fontweight='bold')
ax1.set_title('Win Rate vs Trade Frequency', fontsize=13, fontweight='bold')
ax1.grid(alpha=0.3)
ax1.axhline(y=50, color='red', linestyle='--', alpha=0.5, label='50% threshold')
ax1.axhline(y=72.7, color='blue', linestyle='--', alpha=0.5, label='Portfolio avg (72.7%)')
ax1.legend()

# Add colorbar
cbar = plt.colorbar(scatter, ax=ax1)
cbar.set_label('Return (%)', fontweight='bold')

# Right: Win rate distribution
win_rate_data = [r['win_rate_pct'] for r in results if r['num_trades'] > 0]
ax2.hist(win_rate_data, bins=8, color='skyblue', edgecolor='black', alpha=0.7)
ax2.axvline(x=np.mean(win_rate_data), color='red', linestyle='--', linewidth=2, label=f'Mean: {np.mean(win_rate_data):.1f}%')
ax2.set_xlabel('Win Rate (%)', fontsize=12, fontweight='bold')
ax2.set_ylabel('Number of Stocks', fontsize=12, fontweight='bold')
ax2.set_title('Win Rate Distribution', fontsize=13, fontweight='bold')
ax2.legend()
ax2.grid(alpha=0.3)

plt.tight_layout()
plt.savefig(output_dir / 'win_rate_by_stock_fixed.png', dpi=300, bbox_inches='tight')
print(f"✓ Saved: {output_dir / 'win_rate_by_stock_fixed.png'}")
plt.close()

# ===== PLOT 3: Signal Distribution =====
print("Generating Plot 3: Signal Distribution...")
fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(14, 10))

# Top left: Return distribution
ax1.hist(returns, bins=10, color='lightcoral', edgecolor='black', alpha=0.7)
ax1.axvline(x=np.mean(returns), color='darkred', linestyle='--', linewidth=2.5, 
            label=f'Mean: {np.mean(returns):.2f}%')
ax1.axvline(x=np.median(returns), color='blue', linestyle='--', linewidth=2.5,
            label=f'Median: {np.median(returns):.2f}%')
ax1.set_xlabel('Return (%)', fontsize=11, fontweight='bold')
ax1.set_ylabel('Frequency', fontsize=11, fontweight='bold')
ax1.set_title('Return Distribution', fontsize=12, fontweight='bold')
ax1.legend()
ax1.grid(alpha=0.3)

# Top right: Trades distribution
ax2.hist(trades, bins=8, color='lightgreen', edgecolor='black', alpha=0.7)
ax2.axvline(x=np.mean(trades), color='darkgreen', linestyle='--', linewidth=2.5,
            label=f'Mean: {np.mean(trades):.1f}')
ax2.set_xlabel('Number of Trades', fontsize=11, fontweight='bold')
ax2.set_ylabel('Frequency', fontsize=11, fontweight='bold')
ax2.set_title('Trade Frequency Distribution', fontsize=12, fontweight='bold')
ax2.legend()
ax2.grid(alpha=0.3)

# Bottom left: Drawdown distribution
ax3.hist(drawdowns, bins=8, color='lightyellow', edgecolor='black', alpha=0.7)
ax3.axvline(x=np.mean(drawdowns), color='orange', linestyle='--', linewidth=2.5,
            label=f'Mean: {np.mean(drawdowns):.1f}%')
ax3.set_xlabel('Max Drawdown (%)', fontsize=11, fontweight='bold')
ax3.set_ylabel('Frequency', fontsize=11, fontweight='bold')
ax3.set_title('Max Drawdown Distribution', fontsize=12, fontweight='bold')
ax3.legend()
ax3.grid(alpha=0.3)

# Bottom right: Summary statistics
ax4.axis('off')
summary_text = f"""
BACKTEST SUMMARY (Fixed Code)
{'='*40}
Period: Feb 2025 - Feb 2026
Stocks: {len(results)} IBOV stocks

KEY METRICS:
• Average Return: {np.mean(returns):+.2f}%
• Median Return: {np.median(returns):+.2f}%
• Total Trades: {sum(trades)}
• Overall Win Rate: {sum(1 for t in all_trades if t['pnl']>0)/len(all_trades)*100:.1f}%
• Avg Drawdown: {np.mean(drawdowns):.1f}%
• Max Drawdown: {max(drawdowns):.1f}%

TOP PERFORMER:
• {tickers[np.argmax(returns)]}: {max(returns):+.2f}%

IMPROVEMENT vs ORIGINAL:
• Return: +3.88% → {np.mean(returns):.2f}% (+{np.mean(returns)-3.88:.2f}%)
• Win Rate: 77.5% → {sum(1 for t in all_trades if t['pnl']>0)/len(all_trades)*100:.1f}%
"""
ax4.text(0.05, 0.95, summary_text, transform=ax4.transAxes, fontsize=10,
         verticalalignment='top', fontfamily='monospace',
         bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))

plt.tight_layout()
plt.savefig(output_dir / 'signal_distribution_fixed.png', dpi=300, bbox_inches='tight')
print(f"✓ Saved: {output_dir / 'signal_distribution_fixed.png'}")
plt.close()

# ===== PLOT 4: Drawdown Comparison =====
print("Generating Plot 4: Drawdown Comparison...")
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))

# Left: Drawdown by stock
sorted_indices = np.argsort(drawdowns)
sorted_tickers_dd = [tickers[i] for i in sorted_indices]
sorted_drawdowns = [drawdowns[i] for i in sorted_indices]

bars = ax1.barh(sorted_tickers_dd, sorted_drawdowns, color='lightcoral', alpha=0.7, edgecolor='black')
ax1.axvline(x=np.mean(drawdowns), color='darkred', linestyle='--', linewidth=2,
           label=f'Mean: {np.mean(drawdowns):.1f}%')
ax1.set_xlabel('Max Drawdown (%)', fontsize=12, fontweight='bold')
ax1.set_title('Maximum Drawdown by Stock', fontsize=13, fontweight='bold')
ax1.legend()
ax1.grid(axis='x', alpha=0.3)

# Right: Return vs Drawdown scatter
scatter = ax2.scatter(drawdowns, returns, s=[t*30 for t in trades],
                     c=returns, cmap='RdYlGn', alpha=0.6, edgecolors='black', linewidth=1)

for i, ticker in enumerate(tickers):
    ax2.annotate(ticker, (drawdowns[i], returns[i]),
                xytext=(5, 5), textcoords='offset points', fontsize=9)

ax2.axhline(y=0, color='black', linestyle='-', linewidth=0.8)
ax2.set_xlabel('Max Drawdown (%)', fontsize=12, fontweight='bold')
ax2.set_ylabel('Return (%)', fontsize=12, fontweight='bold')
ax2.set_title('Risk vs Return Profile', fontsize=13, fontweight='bold')
ax2.grid(alpha=0.3)

cbar = plt.colorbar(scatter, ax=ax2)
cbar.set_label('Return (%)', fontweight='bold')

plt.tight_layout()
plt.savefig(output_dir / 'drawdown_comparison_fixed.png', dpi=300, bbox_inches='tight')
print(f"✓ Saved: {output_dir / 'drawdown_comparison_fixed.png'}")
plt.close()

# ===== PLOT 5: Strategy vs IBOV Comparison =====
print("Generating Plot 5: Strategy Performance Summary...")
fig = plt.figure(figsize=(14, 8))
gs = fig.add_gridspec(2, 2, hspace=0.3, wspace=0.3)

# Main plot: Returns ranking
ax_main = fig.add_subplot(gs[0, :])
sorted_indices = np.argsort(returns)
sorted_tickers = [tickers[i] for i in sorted_indices]
sorted_returns = [returns[i] for i in sorted_indices]
sorted_colors = [colors[i] for i in sorted_indices]

bars = ax_main.barh(sorted_tickers, sorted_returns, color=sorted_colors, alpha=0.7, edgecolor='black')

# Add value labels
for i, (ticker, ret) in enumerate(zip(sorted_tickers, sorted_returns)):
    ax_main.text(ret + 0.5, i, f'{ret:+.1f}%', va='center', fontweight='bold', fontsize=9)

ax_main.axvline(x=np.mean(returns), color='blue', linestyle='--', linewidth=2.5, alpha=0.7,
               label=f'Portfolio Avg: {np.mean(returns):+.2f}%')
ax_main.axvline(x=0, color='black', linestyle='-', linewidth=0.8)
ax_main.set_xlabel('Return (%)', fontsize=12, fontweight='bold')
ax_main.set_title('Strategy Performance by Stock - Fixed Code\n(Feb 2025 - Feb 2026, 18 IBOV Stocks)', 
                  fontsize=14, fontweight='bold')
ax_main.grid(axis='x', alpha=0.3)
ax_main.legend(fontsize=11)

# Bottom left: Key metrics table
ax_bl = fig.add_subplot(gs[1, 0])
ax_bl.axis('off')

metrics_text = f"""
PORTFOLIO METRICS (Fixed Code)
{'='*35}
Total Stocks:        {len(results)}
Total Trades:        {sum(trades)}
Winning Trades:      {sum(1 for t in all_trades if t['pnl']>0)}
Losing Trades:       {sum(1 for t in all_trades if t['pnl']<0)}

Average Return:      {np.mean(returns):+.2f}%
Median Return:       {np.median(returns):+.2f}%
Win Rate:            {sum(1 for t in all_trades if t['pnl']>0)/len(all_trades)*100:.1f}%
Overall Drawdown:    {max(drawdowns):.1f}%
"""
ax_bl.text(0.05, 0.95, metrics_text, transform=ax_bl.transAxes, fontsize=10,
          verticalalignment='top', fontfamily='monospace',
          bbox=dict(boxstyle='round', facecolor='lightblue', alpha=0.5))

# Bottom right: Comparison with original
ax_br = fig.add_subplot(gs[1, 1])
ax_br.axis('off')

comparison_text = f"""
FIXED vs ORIGINAL CODE
{'='*35}
Return (Original):      +3.88%
Return (Fixed):         {np.mean(returns):+.2f}%
Improvement:            +{np.mean(returns)-3.88:.2f}%

Win Rate (Original):    77.5%
Win Rate (Fixed):       {sum(1 for t in all_trades if t['pnl']>0)/len(all_trades)*100:.1f}%
Change:                 {sum(1 for t in all_trades if t['pnl']>0)/len(all_trades)*100 - 77.5:.1f} pp

Key Changes:
✓ Look-ahead bias fixed
✓ Signal format standardized
✓ Error handling improved
✓ More selective trading
"""
ax_br.text(0.05, 0.95, comparison_text, transform=ax_br.transAxes, fontsize=10,
          verticalalignment='top', fontfamily='monospace',
          bbox=dict(boxstyle='round', facecolor='lightgreen', alpha=0.5))

plt.savefig(output_dir / 'strategy_performance_summary_fixed.png', dpi=300, bbox_inches='tight')
print(f"✓ Saved: {output_dir / 'strategy_performance_summary_fixed.png'}")
plt.close()

print(f"\n{'='*60}")
print(f"✅ ALL PLOTS GENERATED SUCCESSFULLY")
print(f"{'='*60}")
print(f"\nOutput directory: {output_dir}")
print(f"\nGenerated files:")
print(f"  1. stock_performance_ranking_fixed.png")
print(f"  2. win_rate_by_stock_fixed.png")
print(f"  3. signal_distribution_fixed.png")
print(f"  4. drawdown_comparison_fixed.png")
print(f"  5. strategy_performance_summary_fixed.png")
