"""
Phase 6: Comprehensive Backtesting Report & Visualization

Generates detailed analysis, comparison tables, and visualizations for:
1. Multi-period backtest results
2. Walk-forward validation results
3. Comparison to baselines (v1, IBOV, CDI)
4. Regime-specific analysis
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import json
from datetime import datetime
from typing import Dict, List, Tuple


class Phase6Reporter:
    """Generate comprehensive Phase 6 reports and visualizations."""
    
    def __init__(self, backtest_results=None, wf_results=None):
        """
        Initialize reporter with backtest and walk-forward results.
        
        Args:
            backtest_results: Dict with multi-period backtest results
            wf_results: Dict with walk-forward validation results
        """
        self.backtest_results = backtest_results or {}
        self.wf_results = wf_results or {}
        
        # Baseline values
        self.v1_baseline = 3.68  # Original v1 return (Feb 2025-Feb 2026)
        self.cdi_annual = 11.0   # CDI typical annual rate
    
    def generate_comparison_table(self):
        """Generate comparison table: v1 vs v2 vs IBOV vs CDI."""
        
        rows = []
        
        # Period 4 (critical test: Feb 2025-Feb 2026)
        p4_key = 'period_4'
        if p4_key in self.backtest_results:
            p4 = self.backtest_results[p4_key]
            summary = p4.get('summary', {})
            
            rows.append({
                'Strategy': 'v1 (mean-reversion only)',
                'Period': 'Feb 2025 - Feb 2026',
                'Return %': f"{self.v1_baseline:+.2f}%",
                'Win Rate %': "N/A",
                'Notes': "Original baseline"
            })
            
            rows.append({
                'Strategy': 'v2 Full (all phases)',
                'Period': 'Feb 2025 - Feb 2026',
                'Return %': f"{summary.get('avg_return_pct', 0):+.2f}%",
                'Win Rate %': f"{summary.get('avg_win_rate', 0):.1f}%",
                'Notes': f"Beats v1: {'✓' if summary.get('avg_return_pct', 0) > self.v1_baseline else '✗'}"
            })
            
            if 'ibov_return_pct' in summary:
                rows.append({
                    'Strategy': 'IBOV (buy-and-hold)',
                    'Period': 'Feb 2025 - Feb 2026',
                    'Return %': f"{summary.get('ibov_return_pct', 0):+.2f}%",
                    'Win Rate %': "N/A",
                    'Notes': "Market baseline"
                })
            
            if 'cdi_return_pct' in summary:
                rows.append({
                    'Strategy': 'CDI (risk-free)',
                    'Period': 'Feb 2025 - Feb 2026',
                    'Return %': f"{summary.get('cdi_return_pct', 0):+.2f}%",
                    'Win Rate %': "N/A",
                    'Notes': "~11% annual"
                })
        
        return pd.DataFrame(rows)
    
    def generate_regime_analysis(self):
        """Analyze performance by regime."""
        
        regime_data = {
            'mixed': [],
            'uptrend': []
        }
        
        for period_key, result in self.backtest_results.items():
            regime = result.get('regime', 'unknown')
            summary = result.get('summary', {})
            
            if regime in regime_data:
                regime_data[regime].append({
                    'period': result['name'],
                    'return': summary.get('avg_return_pct', 0),
                    'win_rate': summary.get('avg_win_rate', 0)
                })
        
        analysis = []
        
        for regime, periods in regime_data.items():
            if periods:
                avg_return = np.mean([p['return'] for p in periods])
                avg_win = np.mean([p['win_rate'] for p in periods])
                
                analysis.append({
                    'Regime': regime.capitalize(),
                    'Periods': len(periods),
                    'Avg Return %': f"{avg_return:+.2f}%",
                    'Avg Win Rate %': f"{avg_win:.1f}%",
                    'Examples': ', '.join([p['period'].split(' - ')[0][:3] + "'24-'26" for p in periods])
                })
        
        return pd.DataFrame(analysis)
    
    def plot_performance_comparison(self, filename='phase6_performance.png'):
        """Plot performance across periods."""
        
        fig, axes = plt.subplots(2, 2, figsize=(14, 10))
        fig.suptitle('Phase 6: Multi-Period Performance Analysis', fontsize=16, fontweight='bold')
        
        # Plot 1: Return by period
        ax = axes[0, 0]
        periods = sorted(self.backtest_results.keys())
        returns = [self.backtest_results[p].get('summary', {}).get('avg_return_pct', 0) for p in periods]
        period_names = [self.backtest_results[p]['name'].split(' - ')[0] for p in periods]
        
        colors = ['green' if r > 0 else 'red' for r in returns]
        ax.bar(period_names, returns, color=colors, alpha=0.7, edgecolor='black')
        ax.axhline(y=0, color='black', linestyle='-', linewidth=0.5)
        ax.set_title('Strategy Return by Period')
        ax.set_ylabel('Return %')
        ax.grid(axis='y', alpha=0.3)
        
        # Add value labels
        for i, v in enumerate(returns):
            ax.text(i, v + 0.5, f'{v:+.1f}%', ha='center', fontsize=9)
        
        # Plot 2: Win rate by period
        ax = axes[0, 1]
        win_rates = [self.backtest_results[p].get('summary', {}).get('avg_win_rate', 0) for p in periods]
        ax.bar(period_names, win_rates, color='steelblue', alpha=0.7, edgecolor='black')
        ax.axhline(y=50, color='orange', linestyle='--', linewidth=2, label='50% baseline')
        ax.set_title('Average Win Rate by Period')
        ax.set_ylabel('Win Rate %')
        ax.set_ylim(0, 100)
        ax.grid(axis='y', alpha=0.3)
        ax.legend()
        
        # Plot 3: Comparison to baselines
        ax = axes[1, 0]
        if 'period_4' in self.backtest_results:
            p4 = self.backtest_results['period_4']
            summary = p4.get('summary', {})
            
            values = [
                self.v1_baseline,
                summary.get('avg_return_pct', 0),
                summary.get('ibov_return_pct', 0),
                summary.get('cdi_return_pct', 0)
            ]
            labels = ['v1\n(Mean-Rev)', 'v2\n(Full)', 'IBOV\n(Buy-Hold)', 'CDI\n(Risk-Free)']
            
            colors_comp = ['lightcoral', 'lightgreen', 'lightyellow', 'lightblue']
            ax.bar(labels, values, color=colors_comp, edgecolor='black', alpha=0.8)
            ax.axhline(y=0, color='black', linestyle='-', linewidth=0.5)
            ax.set_title('Period 4: Comparison to Baselines (Feb 2025-Feb 2026)')
            ax.set_ylabel('Return %')
            ax.grid(axis='y', alpha=0.3)
            
            # Add value labels
            for i, v in enumerate(values):
                ax.text(i, v + 0.5, f'{v:+.1f}%', ha='center', fontsize=10, fontweight='bold')
        
        # Plot 4: Success metrics summary
        ax = axes[1, 1]
        ax.axis('off')
        
        metrics_text = "CRITICAL SUCCESS METRICS\n\n"
        
        # Check success metrics
        p4 = self.backtest_results.get('period_4', {})
        s4 = p4.get('summary', {})
        
        metric1 = s4.get('avg_return_pct', 0) > self.v1_baseline
        metrics_text += f"✓ v2 beats v1 (>3.68%): {'PASS' if metric1 else 'FAIL'}\n"
        metrics_text += f"  v2: {s4.get('avg_return_pct', 0):+.2f}% vs v1: {self.v1_baseline:+.2f}%\n\n"
        
        beats_ibov = sum(1 for r in self.backtest_results.values() 
                        if r.get('summary', {}).get('beats_ibov', False))
        metric2 = beats_ibov >= 2
        metrics_text += f"✓ v2 beats IBOV (≥2 periods): {'PASS' if metric2 else 'FAIL'}\n"
        metrics_text += f"  {beats_ibov}/4 periods\n\n"
        
        beats_cdi = sum(1 for r in self.backtest_results.values() 
                       if r.get('summary', {}).get('beats_cdi', False))
        metric3 = beats_cdi >= 2
        metrics_text += f"✓ v2 beats CDI (≥2 periods): {'PASS' if metric3 else 'FAIL'}\n"
        metrics_text += f"  {beats_cdi}/4 periods\n\n"
        
        recommendation = "READY" if (metric1 and metric2 and metric3) else "NEEDS WORK"
        metrics_text += f"\nRECOMMENDATION: {recommendation} ✓" if (metric1 and metric2 and metric3) else f"\nRECOMMENDATION: {recommendation} ⚠️"
        
        ax.text(0.1, 0.5, metrics_text, fontsize=11, family='monospace',
               verticalalignment='center', bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))
        
        plt.tight_layout()
        
        output_path = Path(__file__).parent / filename
        plt.savefig(output_path, dpi=150, bbox_inches='tight')
        print(f"✓ Performance chart saved to {output_path}")
        plt.close()
        
        return output_path
    
    def plot_walk_forward_results(self, filename='phase6_wf_results.png'):
        """Plot walk-forward validation results."""
        
        if not self.wf_results:
            print("No walk-forward results available")
            return None
        
        fig, axes = plt.subplots(1, 2, figsize=(14, 5))
        fig.suptitle('Phase 6: Walk-Forward Out-of-Sample Validation', fontsize=16, fontweight='bold')
        
        # Collect data
        tickers = []
        in_sample_returns = []
        out_sample_returns = []
        overfit_gaps = []
        
        for ticker, windows in self.wf_results.items():
            if not windows:
                continue
            
            avg_in = np.mean([w['in_sample_return'] for w in windows])
            avg_out = np.mean([w['out_sample_return'] for w in windows])
            gap = avg_in - avg_out
            
            tickers.append(ticker)
            in_sample_returns.append(avg_in)
            out_sample_returns.append(avg_out)
            overfit_gaps.append(gap)
        
        if tickers:
            # Plot 1: In-Sample vs Out-of-Sample
            x = np.arange(len(tickers))
            width = 0.35
            
            ax = axes[0]
            ax.bar(x - width/2, in_sample_returns, width, label='In-Sample', color='steelblue', alpha=0.8)
            ax.bar(x + width/2, out_sample_returns, width, label='Out-of-Sample', color='orange', alpha=0.8)
            
            ax.set_ylabel('Return %')
            ax.set_title('In-Sample vs Out-of-Sample Returns')
            ax.set_xticks(x)
            ax.set_xticklabels(tickers)
            ax.legend()
            ax.grid(axis='y', alpha=0.3)
            ax.axhline(y=0, color='black', linestyle='-', linewidth=0.5)
            
            # Plot 2: Overfit gaps
            ax = axes[1]
            colors = ['red' if gap > 10 else 'orange' if gap > 5 else 'green' for gap in overfit_gaps]
            ax.bar(tickers, overfit_gaps, color=colors, alpha=0.7, edgecolor='black')
            ax.set_ylabel('Gap (percentage points)')
            ax.set_title('Overfitting Gap (In-Sample - Out-of-Sample)')
            ax.axhline(y=0, color='black', linestyle='-', linewidth=1)
            ax.axhline(y=5, color='orange', linestyle='--', linewidth=1, alpha=0.5, label='Warning threshold')
            ax.grid(axis='y', alpha=0.3)
            ax.legend()
        
        plt.tight_layout()
        
        output_path = Path(__file__).parent / filename
        plt.savefig(output_path, dpi=150, bbox_inches='tight')
        print(f"✓ Walk-forward chart saved to {output_path}")
        plt.close()
        
        return output_path
    
    def generate_final_report(self, filename='PHASE_6_BACKTEST_RESULTS.md'):
        """Generate comprehensive final report."""
        
        report = []
        report.append("# PHASE 6: BACKTESTING & VALIDATION\n")
        report.append("## Comprehensive Multi-Period & Walk-Forward Analysis\n\n")
        
        report.append(f"**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S GMT-3')}\n\n")
        report.append("---\n\n")
        
        # Executive Summary
        report.append("## Executive Summary\n\n")
        
        p4 = self.backtest_results.get('period_4', {})
        s4 = p4.get('summary', {})
        
        report.append(f"The Phase 1-5 integrated strategy (v2) has been rigorously tested across **4 market periods** ")
        report.append(f"spanning from January 2024 to February 2026. \n\n")
        
        report.append(f"**Key Finding**: v2 achieved **{s4.get('avg_return_pct', 0):+.2f}%** return in the critical test period ")
        report.append(f"(Feb 2025-Feb 2026) vs. **{self.v1_baseline:+.2f}%** for the original v1 baseline.\n\n")
        
        beats_ibov_count = sum(1 for r in self.backtest_results.values() 
                              if r.get('summary', {}).get('beats_ibov', False))
        beats_cdi_count = sum(1 for r in self.backtest_results.values() 
                             if r.get('summary', {}).get('beats_cdi', False))
        
        report.append(f"- **Beats IBOV**: {beats_ibov_count}/4 periods\n")
        report.append(f"- **Beats CDI**: {beats_cdi_count}/4 periods\n")
        report.append(f"- **Win Rate**: {s4.get('avg_win_rate', 0):.1f}%\n\n")
        
        # Comparison Table
        report.append("## Strategy Comparison (Critical Test Period: Feb 2025-Feb 2026)\n\n")
        
        comparison_table = self.generate_comparison_table()
        if not comparison_table.empty:
            report.append(comparison_table.to_markdown(index=False))
        
        report.append("\n\n---\n\n")
        
        # Detailed Period Analysis
        report.append("## Detailed Period Results\n\n")
        
        for period_key in sorted(self.backtest_results.keys()):
            result = self.backtest_results[period_key]
            summary = result.get('summary', {})
            
            report.append(f"### {result['name']}\n\n")
            report.append(f"**Regime**: {result['regime'].capitalize()} | ")
            report.append(f"**Period**: {result['start_date']} to {result['end_date']}\n\n")
            
            report.append("#### Performance Metrics\n\n")
            report.append(f"| Metric | Value |\n")
            report.append(f"|--------|-------|\n")
            report.append(f"| Average Return | {summary.get('avg_return_pct', 0):+.2f}% |\n")
            report.append(f"| Win Rate | {summary.get('avg_win_rate', 0):.1f}% |\n")
            report.append(f"| Avg Sharpe | {summary.get('avg_sharpe', 0):.2f} |\n")
            report.append(f"| Stocks Tested | {summary.get('num_stocks_tested', 0)}/{summary.get('total_stocks', 0)} |\n")
            
            report.append("\n#### Baseline Comparisons\n\n")
            
            if 'ibov_return_pct' in summary:
                report.append(f"| Comparison | Strategy | Baseline | Beats | Advantage |\n")
                report.append(f"|---|---|---|---|---|\n")
                
                ibov_ret = summary.get('ibov_return_pct', 0)
                strat_ret = summary.get('avg_return_pct', 0)
                report.append(f"| vs IBOV | {strat_ret:+.2f}% | {ibov_ret:+.2f}% | " +
                            f"{'✓' if strat_ret > ibov_ret else '✗'} | " +
                            f"{(strat_ret - ibov_ret):+.2f}pp |\n")
                
                if 'cdi_return_pct' in summary:
                    cdi_ret = summary.get('cdi_return_pct', 0)
                    report.append(f"| vs CDI | {strat_ret:+.2f}% | {cdi_ret:+.2f}% | " +
                                f"{'✓' if strat_ret > cdi_ret else '✗'} | " +
                                f"{(strat_ret - cdi_ret):+.2f}pp |\n")
            
            report.append("\n")
        
        report.append("---\n\n")
        
        # Regime Analysis
        report.append("## Regime-Specific Analysis\n\n")
        
        regime_analysis = self.generate_regime_analysis()
        if not regime_analysis.empty:
            report.append(regime_analysis.to_markdown(index=False))
        
        report.append("\n\n")
        report.append("**Interpretation**:\n")
        report.append("- Uptrend periods show strong performance (momentum mode)\n")
        report.append("- Mixed periods show variable performance (regime detection)\n")
        report.append("- Regime-adaptive strategy captures both uptrends and consolidations\n\n")
        
        report.append("---\n\n")
        
        # Success Metrics
        report.append("## Critical Success Metrics\n\n")
        
        metric1 = s4.get('avg_return_pct', 0) > self.v1_baseline
        metric2 = beats_ibov_count >= 2
        metric3 = beats_cdi_count >= 2
        
        report.append("| Criterion | Target | Result | Status |\n")
        report.append("|-----------|--------|--------|--------|\n")
        report.append(f"| v2 beats v1 (Feb'25-Feb'26) | >3.68% | {s4.get('avg_return_pct', 0):+.2f}% | " +
                     f"{'✅ PASS' if metric1 else '❌ FAIL'} |\n")
        report.append(f"| v2 beats IBOV (≥2 periods) | 2+ | {beats_ibov_count} | " +
                     f"{'✅ PASS' if metric2 else '❌ FAIL'} |\n")
        report.append(f"| v2 beats CDI (≥2 periods) | 2+ | {beats_cdi_count} | " +
                     f"{'✅ PASS' if metric3 else '❌ FAIL'} |\n")
        
        report.append("\n\n")
        
        # Conclusion
        report.append("## Conclusions & Recommendations\n\n")
        
        if metric1 and metric2 and metric3:
            report.append("### ✅ READY FOR PHASE 7 (Extended Validation)\n\n")
            report.append("All critical success metrics have been met:\n")
            report.append("- v2 beats original v1 baseline\n")
            report.append("- v2 beats IBOV in multiple periods\n")
            report.append("- v2 beats risk-free rate (CDI) in multiple periods\n\n")
            report.append("**Next Steps**:\n")
            report.append("1. Run extended live paper trading (8+ weeks)\n")
            report.append("2. Validate walk-forward out-of-sample returns\n")
            report.append("3. Optimize position sizing and risk management\n")
            report.append("4. Proceed to Phase 8: Live Deployment\n")
        else:
            report.append("### ⚠️ NEEDS REFINEMENT\n\n")
            report.append("Some success metrics not met:\n")
            if not metric1:
                report.append(f"- v2 return ({s4.get('avg_return_pct', 0):+.2f}%) below v1 baseline ({self.v1_baseline:+.2f}%)\n")
            if not metric2:
                report.append(f"- Beats IBOV in only {beats_ibov_count}/4 periods\n")
            if not metric3:
                report.append(f"- Beats CDI in only {beats_cdi_count}/4 periods\n")
            report.append("\n**Recommendations**:\n")
            report.append("1. Review regime detection accuracy\n")
            report.append("2. Optimize signal thresholds and weighting\n")
            report.append("3. Enhance conviction scoring\n")
            report.append("4. Consider multi-timeframe confirmation\n")
        
        report.append("\n\n---\n\n")
        
        # Technical Details
        report.append("## Technical Specifications\n\n")
        report.append("### Backtest Configuration\n")
        report.append("- **Capital**: $50,000 initial\n")
        report.append("- **Position Size**: 5% per trade\n")
        report.append("- **Trading Costs**:\n")
        report.append("  - 0.1% slippage (entry & exit)\n")
        report.append("  - $5 fixed commission (round-trip)\n")
        report.append("- **Stocks**: Top 18 IBOV by volume\n")
        report.append("- **Modules**: Phase 1-5 fully integrated\n\n")
        
        report.append("### Strategy Components\n")
        report.append("- **Phase 1-2**: News sentiment + information flow\n")
        report.append("- **Phase 3**: Conviction scoring\n")
        report.append("- **Phase 4**: Momentum detection\n")
        report.append("- **Phase 5**: Regime-adaptive routing\n")
        report.append("- **Execution**: Paper trading simulation\n\n")
        
        report.append("### Walk-Forward Validation\n")
        report.append("- **Window Size**: 3-month training + 1-month test\n")
        report.append("- **Optimization**: Signal thresholds (0.3-0.7)\n")
        report.append("- **Metrics**: In-sample vs out-of-sample returns\n")
        report.append("- **Purpose**: Validate no curve-fitting\n\n")
        
        report.append("---\n\n")
        
        # Save report
        output_path = Path(__file__).parent.parent / filename
        with open(output_path, 'w') as f:
            f.write('\n'.join(report))
        
        print(f"✓ Final report saved to {output_path}")
        return output_path
    
    def export_all(self):
        """Generate all reports and visualizations."""
        
        print("\n" + "=" * 80)
        print("PHASE 6: GENERATING COMPREHENSIVE REPORTS & VISUALIZATIONS")
        print("=" * 80)
        
        # Generate reports
        print("\n📄 Generating final report...")
        self.generate_final_report()
        
        # Generate charts
        print("📊 Generating performance comparison chart...")
        self.plot_performance_comparison()
        
        if self.wf_results:
            print("📊 Generating walk-forward validation chart...")
            self.plot_walk_forward_results()
        
        print("\n✓ All Phase 6 reports and visualizations generated!")


def main():
    """Main entry point."""
    
    # Try to load existing backtest results
    backtest_results_path = Path(__file__).parent / 'backtest_results.json'
    backtest_results = {}
    
    if backtest_results_path.exists():
        with open(backtest_results_path) as f:
            backtest_results = json.load(f)
        print(f"✓ Loaded backtest results from {backtest_results_path}")
    else:
        print("⚠️ No backtest results found. Using placeholder data...")
    
    # Create reporter
    reporter = Phase6Reporter(backtest_results=backtest_results)
    
    # Generate all outputs
    reporter.export_all()
    
    # Print summary
    print("\n" + "=" * 80)
    print("PHASE 6 SUMMARY")
    print("=" * 80)
    
    if backtest_results:
        print("\nComparison Table:")
        print(reporter.generate_comparison_table().to_string(index=False))
        
        print("\n\nRegime Analysis:")
        print(reporter.generate_regime_analysis().to_string(index=False))


if __name__ == '__main__':
    main()
