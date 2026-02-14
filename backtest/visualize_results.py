"""
Visualize backtest results: equity curves, returns, win rate, drawdown.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from datetime import datetime


def plot_backtest_results(results, save_path=None):
    """Create comprehensive backtest visualization."""
    
    if not results:
        print("No results to plot")
        return
    
    # Create figure with subplots
    fig = plt.figure(figsize=(16, 12))
    
    # 1. Equity curves for each stock
    ax1 = plt.subplot(3, 3, 1)
    for result in results:
        equity_log = result['equity_log']
        dates = [e['date'] for e in equity_log]
        equities = [e['equity'] for e in equity_log]
        ax1.plot(dates, equities, label=result['ticker'], linewidth=2)
    
    ax1.set_title('Equity Curves by Stock', fontsize=12, fontweight='bold')
    ax1.set_ylabel('Equity ($)', fontsize=10)
    ax1.legend(loc='best')
    ax1.grid(True, alpha=0.3)
    ax1.tick_params(axis='x', rotation=45)
    
    # 2. Total return comparison
    ax2 = plt.subplot(3, 3, 2)
    tickers = [r['ticker'] for r in results]
    returns = [r['total_return_pct'] for r in results]
    colors = ['green' if r > 0 else 'red' for r in returns]
    
    bars = ax2.bar(tickers, returns, color=colors, alpha=0.7, edgecolor='black')
    ax2.axhline(y=0, color='black', linestyle='-', linewidth=0.5)
    ax2.set_title('Total Return by Stock', fontsize=12, fontweight='bold')
    ax2.set_ylabel('Return (%)', fontsize=10)
    ax2.grid(True, alpha=0.3, axis='y')
    
    # Add value labels on bars
    for bar, ret in zip(bars, returns):
        height = bar.get_height()
        ax2.text(bar.get_x() + bar.get_width()/2., height,
                f'{ret:+.1f}%', ha='center', va='bottom' if ret > 0 else 'top', fontsize=9)
    
    # 3. Win rate comparison
    ax3 = plt.subplot(3, 3, 3)
    win_rates = [r['win_rate_pct'] for r in results]
    bars = ax3.bar(tickers, win_rates, color='steelblue', alpha=0.7, edgecolor='black')
    ax3.axhline(y=50, color='red', linestyle='--', linewidth=1, label='50% (breakeven)')
    ax3.set_title('Win Rate by Stock', fontsize=12, fontweight='bold')
    ax3.set_ylabel('Win Rate (%)', fontsize=10)
    ax3.set_ylim([0, 100])
    ax3.grid(True, alpha=0.3, axis='y')
    ax3.legend(loc='best')
    
    # Add value labels
    for bar, wr in zip(bars, win_rates):
        ax3.text(bar.get_x() + bar.get_width()/2., bar.get_height(),
                f'{wr:.0f}%', ha='center', va='bottom', fontsize=9)
    
    # 4. Number of trades
    ax4 = plt.subplot(3, 3, 4)
    trades = [r['num_trades'] for r in results]
    ax4.bar(tickers, trades, color='orange', alpha=0.7, edgecolor='black')
    ax4.set_title('Number of Trades by Stock', fontsize=12, fontweight='bold')
    ax4.set_ylabel('Number of Trades', fontsize=10)
    ax4.grid(True, alpha=0.3, axis='y')
    
    # 5. Max drawdown
    ax5 = plt.subplot(3, 3, 5)
    drawdowns = [r['max_drawdown_pct'] for r in results]
    ax5.bar(tickers, drawdowns, color='red', alpha=0.7, edgecolor='black')
    ax5.set_title('Maximum Drawdown by Stock', fontsize=12, fontweight='bold')
    ax5.set_ylabel('Max Drawdown (%)', fontsize=10)
    ax5.grid(True, alpha=0.3, axis='y')
    
    # 6. Winning vs Losing trades
    ax6 = plt.subplot(3, 3, 6)
    winning = [r['winning_trades'] for r in results]
    losing = [r['losing_trades'] for r in results]
    
    x = np.arange(len(tickers))
    width = 0.35
    
    ax6.bar(x - width/2, winning, width, label='Winning', color='green', alpha=0.7)
    ax6.bar(x + width/2, losing, width, label='Losing', color='red', alpha=0.7)
    ax6.set_title('Winning vs Losing Trades', fontsize=12, fontweight='bold')
    ax6.set_ylabel('Number of Trades', fontsize=10)
    ax6.set_xticks(x)
    ax6.set_xticklabels(tickers)
    ax6.legend()
    ax6.grid(True, alpha=0.3, axis='y')
    
    # 7. Distribution of trade returns
    ax7 = plt.subplot(3, 3, 7)
    all_trades = []
    for result in results:
        all_trades.extend([t['pnl_pct'] for t in result['trades']])
    
    if all_trades:
        ax7.hist(all_trades, bins=20, color='steelblue', alpha=0.7, edgecolor='black')
        ax7.axvline(x=0, color='red', linestyle='--', linewidth=2, label='Breakeven')
        ax7.axvline(x=np.mean(all_trades), color='green', linestyle='-', linewidth=2, label=f'Mean: {np.mean(all_trades):.1f}%')
        ax7.set_title('Distribution of Trade Returns', fontsize=12, fontweight='bold')
        ax7.set_xlabel('Return (%)', fontsize=10)
        ax7.set_ylabel('Frequency', fontsize=10)
        ax7.legend()
        ax7.grid(True, alpha=0.3, axis='y')
    
    # 8. Return vs Risk scatter
    ax8 = plt.subplot(3, 3, 8)
    returns = [r['total_return_pct'] for r in results]
    risks = [r['max_drawdown_pct'] for r in results]
    
    for i, ticker in enumerate(tickers):
        ax8.scatter(risks[i], returns[i], s=200, alpha=0.6)
        ax8.annotate(ticker, (risks[i], returns[i]), fontsize=10, ha='center', va='center')
    
    ax8.axhline(y=0, color='black', linestyle='-', linewidth=0.5)
    ax8.set_title('Return vs Risk (Drawdown)', fontsize=12, fontweight='bold')
    ax8.set_xlabel('Max Drawdown (%)', fontsize=10)
    ax8.set_ylabel('Total Return (%)', fontsize=10)
    ax8.grid(True, alpha=0.3)
    
    # 9. Summary statistics table
    ax9 = plt.subplot(3, 3, 9)
    ax9.axis('off')
    
    summary_data = []
    for result in results:
        summary_data.append([
            result['ticker'],
            f"{result['total_return_pct']:+.1f}%",
            f"{result['win_rate_pct']:.0f}%",
            f"{result['num_trades']}",
            f"{result['max_drawdown_pct']:.1f}%"
        ])
    
    table = ax9.table(cellText=summary_data,
                     colLabels=['Stock', 'Return', 'Win %', 'Trades', 'Max DD'],
                     cellLoc='center',
                     loc='center',
                     bbox=[0, 0, 1, 1])
    table.auto_set_font_size(False)
    table.set_fontsize(9)
    table.scale(1, 2)
    
    # Color header
    for i in range(5):
        table[(0, i)].set_facecolor('#40466e')
        table[(0, i)].set_text_props(weight='bold', color='white')
    
    # Color rows
    for i in range(1, len(summary_data) + 1):
        for j in range(5):
            if j == 1:  # Return column
                return_val = float(summary_data[i-1][1].rstrip('%'))
                color = '#90EE90' if return_val > 0 else '#FFB6C6'
            else:
                color = '#f0f0f0'
            table[(i, j)].set_facecolor(color)
    
    ax9.set_title('Summary Statistics', fontsize=12, fontweight='bold', pad=20)
    
    # Overall title
    fig.suptitle('Stock Signal Backtest Results', fontsize=16, fontweight='bold', y=0.995)
    
    plt.tight_layout()
    
    if save_path:
        plt.savefig(save_path, dpi=150, bbox_inches='tight')
        print(f"Plot saved: {save_path}")
    
    plt.show()
    
    return fig


if __name__ == '__main__':
    from trading_simulator import TradingSimulator
    from datetime import datetime, timedelta
    
    # Run backtest
    tickers = ['AAPL', 'MSFT', 'NVDA']
    end_date = datetime.now()
    start_date = end_date - timedelta(days=180)
    
    print("Running backtest...")
    simulator = TradingSimulator(initial_capital=10000, position_size=0.5)
    results = simulator.run_backtest(tickers, start_date, end_date, threshold=0.5)
    simulator.generate_report(results)
    
    # Visualize
    print("\nGenerating visualizations...")
    plot_path = Path(__file__).parent / 'backtest_results.png'
    plot_backtest_results(results, save_path=str(plot_path))
