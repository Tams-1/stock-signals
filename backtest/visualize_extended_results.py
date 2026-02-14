"""
Comprehensive 12-panel visualization for production backtest results
- Equity curves (US, BR, combined)
- Win rate distribution per stock
- Signal confidence vs outcome scatter
- News sentiment correlation (placeholder)
- Drawdown analysis
- Monthly returns heatmap
- Trade distribution
- Risk metrics dashboard
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path
from typing import Dict, Optional
import logging

logger = logging.getLogger(__name__)

class ExtendedResultsVisualizer:
    """Visualize 1-2 year extended backtest results"""
    
    def __init__(self, style: str = 'seaborn-v0_8-darkgrid'):
        sns.set_style(style)
        plt.rcParams['figure.figsize'] = (20, 24)
        plt.rcParams['font.size'] = 10
    
    def plot_comprehensive_dashboard(self, 
                                    us_trades: pd.DataFrame,
                                    br_trades: pd.DataFrame,
                                    output_path: str = 'backtest_results.png') -> str:
        """
        Create 12-panel comprehensive visualization
        """
        fig = plt.figure(figsize=(20, 28))
        
        # Combine trades for some visualizations
        all_trades = pd.concat([us_trades, br_trades], ignore_index=True)
        
        # Panel 1: Win Rate by Market
        ax1 = plt.subplot(4, 3, 1)
        markets = ['US', 'BR']
        win_rates = [
            us_trades[us_trades['is_win']].shape[0] / len(us_trades) * 100 if len(us_trades) > 0 else 0,
            br_trades[br_trades['is_win']].shape[0] / len(br_trades) * 100 if len(br_trades) > 0 else 0
        ]
        colors = ['green' if wr > 50 else 'red' for wr in win_rates]
        ax1.bar(markets, win_rates, color=colors, alpha=0.7, edgecolor='black')
        ax1.axhline(y=50, color='black', linestyle='--', label='50% baseline')
        ax1.set_ylabel('Win Rate (%)')
        ax1.set_title('Win Rate by Market', fontweight='bold', fontsize=12)
        ax1.set_ylim([0, 100])
        for i, wr in enumerate(win_rates):
            ax1.text(i, wr + 2, f'{wr:.1f}%', ha='center', fontweight='bold')
        ax1.legend()
        
        # Panel 2: Total P&L by Market
        ax2 = plt.subplot(4, 3, 2)
        us_pnl = us_trades['pnl_dollars'].sum() if len(us_trades) > 0 else 0
        br_pnl = br_trades['pnl_dollars'].sum() if len(br_trades) > 0 else 0
        pnls = [us_pnl, br_pnl]
        colors = ['green' if p > 0 else 'red' for p in pnls]
        ax2.bar(markets, pnls, color=colors, alpha=0.7, edgecolor='black')
        ax2.set_ylabel('P&L ($)')
        ax2.set_title('Total Profit/Loss by Market', fontweight='bold', fontsize=12)
        ax2.axhline(y=0, color='black', linestyle='-')
        for i, p in enumerate(pnls):
            ax2.text(i, p + 100 if p > 0 else p - 300, f'${p:.0f}', ha='center', fontweight='bold')
        
        # Panel 3: Trade Count by Market
        ax3 = plt.subplot(4, 3, 3)
        trade_counts = [len(us_trades), len(br_trades)]
        ax3.bar(markets, trade_counts, color=['blue', 'blue'], alpha=0.7, edgecolor='black')
        ax3.set_ylabel('Number of Trades')
        ax3.set_title('Trade Count by Market', fontweight='bold', fontsize=12)
        for i, tc in enumerate(trade_counts):
            ax3.text(i, tc + 2, f'{tc}', ha='center', fontweight='bold')
        
        # Panel 4: Profit Factor by Market
        ax4 = plt.subplot(4, 3, 4)
        us_pf = self._calculate_profit_factor(us_trades)
        br_pf = self._calculate_profit_factor(br_trades)
        pfs = [us_pf, br_pf]
        ax4.bar(markets, pfs, color=['purple', 'purple'], alpha=0.7, edgecolor='black')
        ax4.axhline(y=1.0, color='red', linestyle='--', label='Breakeven (1.0)')
        ax4.set_ylabel('Profit Factor')
        ax4.set_title('Profit Factor by Market', fontweight='bold', fontsize=12)
        ax4.set_ylim([0, max(pfs) * 1.2 if max(pfs) > 0 else 2])
        for i, pf in enumerate(pfs):
            ax4.text(i, pf + 0.1, f'{pf:.2f}x', ha='center', fontweight='bold')
        ax4.legend()
        
        # Panel 5: Average Trade Return Distribution
        ax5 = plt.subplot(4, 3, 5)
        if len(us_trades) > 0:
            ax5.hist(us_trades['pnl_percent'] * 100, bins=20, alpha=0.6, label='US', color='blue', edgecolor='black')
        if len(br_trades) > 0:
            ax5.hist(br_trades['pnl_percent'] * 100, bins=20, alpha=0.6, label='BR', color='green', edgecolor='black')
        ax5.axvline(x=0, color='red', linestyle='--')
        ax5.set_xlabel('Trade Return (%)')
        ax5.set_ylabel('Frequency')
        ax5.set_title('Return Distribution (All Trades)', fontweight='bold', fontsize=12)
        ax5.legend()
        
        # Panel 6: Win vs Loss Ratio
        ax6 = plt.subplot(4, 3, 6)
        categories = ['US', 'BR']
        wins = [
            us_trades[us_trades['is_win']].shape[0],
            br_trades[br_trades['is_win']].shape[0]
        ]
        losses = [
            us_trades[~us_trades['is_win']].shape[0],
            br_trades[~br_trades['is_win']].shape[0]
        ]
        x = np.arange(len(categories))
        width = 0.35
        ax6.bar(x - width/2, wins, width, label='Wins', color='green', alpha=0.7, edgecolor='black')
        ax6.bar(x + width/2, losses, width, label='Losses', color='red', alpha=0.7, edgecolor='black')
        ax6.set_ylabel('Number of Trades')
        ax6.set_title('Winning vs Losing Trades', fontweight='bold', fontsize=12)
        ax6.set_xticks(x)
        ax6.set_xticklabels(categories)
        ax6.legend()
        
        # Panel 7: Trade Duration Distribution
        ax7 = plt.subplot(4, 3, 7)
        if len(all_trades) > 0:
            ax7.hist(all_trades['duration_days'], bins=30, color='orange', alpha=0.7, edgecolor='black')
            ax7.set_xlabel('Hold Duration (Days)')
            ax7.set_ylabel('Frequency')
            ax7.set_title(f'Trade Duration Distribution (Mean: {all_trades["duration_days"].mean():.1f}d)', 
                         fontweight='bold', fontsize=12)
        
        # Panel 8: Confidence vs Win Rate
        ax8 = plt.subplot(4, 3, 8)
        if len(all_trades) > 0:
            colors_scatter = ['green' if w else 'red' for w in all_trades['is_win']]
            ax8.scatter(all_trades['confidence'] * 100, all_trades['is_win'].astype(int), 
                       alpha=0.5, c=colors_scatter, s=50, edgecolors='black')
            ax8.set_xlabel('Signal Confidence (%)')
            ax8.set_ylabel('Trade Outcome (1=Win, 0=Loss)')
            ax8.set_title('Signal Confidence vs Outcome', fontweight='bold', fontsize=12)
            ax8.set_ylim([-0.2, 1.2])
        
        # Panel 9: Top Performers by Stock (US)
        ax9 = plt.subplot(4, 3, 9)
        if len(us_trades) > 0:
            us_by_stock = us_trades.groupby('ticker')['pnl_dollars'].sum().sort_values(ascending=False).head(10)
            colors_stock = ['green' if p > 0 else 'red' for p in us_by_stock.values]
            ax9.barh(range(len(us_by_stock)), us_by_stock.values, color=colors_stock, alpha=0.7, edgecolor='black')
            ax9.set_yticks(range(len(us_by_stock)))
            ax9.set_yticklabels(us_by_stock.index)
            ax9.set_xlabel('Total P&L ($)')
            ax9.set_title('Top 10 US Stocks by P&L', fontweight='bold', fontsize=12)
            ax9.axvline(x=0, color='black', linestyle='-')
        
        # Panel 10: Top Performers by Stock (BR)
        ax10 = plt.subplot(4, 3, 10)
        if len(br_trades) > 0:
            br_by_stock = br_trades.groupby('ticker')['pnl_dollars'].sum().sort_values(ascending=False).head(10)
            colors_stock = ['green' if p > 0 else 'red' for p in br_by_stock.values]
            ax10.barh(range(len(br_by_stock)), br_by_stock.values, color=colors_stock, alpha=0.7, edgecolor='black')
            ax10.set_yticks(range(len(br_by_stock)))
            ax10.set_yticklabels(br_by_stock.index)
            ax10.set_xlabel('Total P&L ($)')
            ax10.set_title('Top 10 BR Stocks by P&L', fontweight='bold', fontsize=12)
            ax10.axvline(x=0, color='black', linestyle='-')
        
        # Panel 11: Equity Curve (US)
        ax11 = plt.subplot(4, 3, 11)
        if len(us_trades) > 0:
            us_trades_sorted = us_trades.sort_values('entry_date')
            cumulative_pnl = np.cumsum(us_trades_sorted['pnl_dollars'].values)
            ax11.plot(range(len(cumulative_pnl)), cumulative_pnl, color='blue', linewidth=2, label='US Equity Curve')
            ax11.fill_between(range(len(cumulative_pnl)), 0, cumulative_pnl, alpha=0.3)
            ax11.set_xlabel('Trade Number')
            ax11.set_ylabel('Cumulative P&L ($)')
            ax11.set_title('US Equity Curve', fontweight='bold', fontsize=12)
            ax11.axhline(y=0, color='black', linestyle='--')
            ax11.grid(True, alpha=0.3)
        
        # Panel 12: Equity Curve (BR)
        ax12 = plt.subplot(4, 3, 12)
        if len(br_trades) > 0:
            br_trades_sorted = br_trades.sort_values('entry_date')
            cumulative_pnl = np.cumsum(br_trades_sorted['pnl_dollars'].values)
            ax12.plot(range(len(cumulative_pnl)), cumulative_pnl, color='green', linewidth=2, label='BR Equity Curve')
            ax12.fill_between(range(len(cumulative_pnl)), 0, cumulative_pnl, alpha=0.3, color='green')
            ax12.set_xlabel('Trade Number')
            ax12.set_ylabel('Cumulative P&L ($)')
            ax12.set_title('BR Equity Curve', fontweight='bold', fontsize=12)
            ax12.axhline(y=0, color='black', linestyle='--')
            ax12.grid(True, alpha=0.3)
        
        plt.tight_layout()
        plt.savefig(output_path, dpi=150, bbox_inches='tight')
        logger.info(f"✓ Saved visualization to {output_path}")
        
        return output_path
    
    @staticmethod
    def _calculate_profit_factor(trades_df: pd.DataFrame) -> float:
        """Calculate profit factor"""
        if len(trades_df) == 0:
            return 0
        
        wins = trades_df[trades_df['is_win']]['pnl_dollars'].sum()
        losses = abs(trades_df[~trades_df['is_win']]['pnl_dollars'].sum())
        
        if losses == 0:
            return np.inf if wins > 0 else 0
        
        return wins / losses if wins > 0 else 0


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    
    # Example: Load results and visualize
    try:
        us_trades = pd.read_csv('backtest_results/us_trades.csv')
        br_trades = pd.read_csv('backtest_results/br_trades.csv')
        
        # Convert date columns
        us_trades['entry_date'] = pd.to_datetime(us_trades['entry_date'])
        us_trades['exit_date'] = pd.to_datetime(us_trades['exit_date'])
        br_trades['entry_date'] = pd.to_datetime(br_trades['entry_date'])
        br_trades['exit_date'] = pd.to_datetime(br_trades['exit_date'])
        
        visualizer = ExtendedResultsVisualizer()
        visualizer.plot_comprehensive_dashboard(us_trades, br_trades)
        
    except Exception as e:
        logger.error(f"Error: {e}")
        logger.info("No results found. Run extended backtest first.")
