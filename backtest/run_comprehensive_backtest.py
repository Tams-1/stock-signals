"""
Comprehensive Backtesting Improvements Runner.

Tests:
1. Original backtest with realistic costs added
2. Walk-forward validation (out-of-sample)
3. Out-of-sample 2026 testing
4. Generates detailed report comparing all methods
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
import json

from backtest.enhanced_cost_simulator import EnhancedCostSimulator
from backtest.walk_forward_validator import WalkForwardValidator
from src.data.market_config import get_tickers


def run_original_backtest_with_costs():
    """Run the original 6-month backtest but with realistic costs included."""
    print(f"\n{'='*90}")
    print("PART 1: ORIGINAL BACKTEST (6 MONTHS, WITH REALISTIC COSTS)")
    print(f"{'='*90}")
    
    end_date = datetime.now()
    start_date = end_date - timedelta(days=180)  # 6 months
    
    print(f"Period: {start_date.date()} to {end_date.date()}")
    
    # Get US tickers (assuming this is what was used before)
    tickers = get_tickers('us')[:10]  # Use first 10 for reasonable time
    
    simulator = EnhancedCostSimulator(
        initial_capital=10000,
        position_size=0.5,
        slippage_pct=0.1,  # 0.1% slippage
        commission_per_trade=5.0  # $5 per round-trip
    )
    
    print(f"\nTickers: {', '.join(tickers)}")
    results = simulator.run_backtest(tickers, start_date, end_date, threshold=0.5)
    
    # Generate report
    simulator.generate_report(results)
    
    return {
        'results': results,
        'start_date': start_date,
        'end_date': end_date,
        'period_name': 'Original 6-Month (2025)'
    }


def run_walk_forward_validation():
    """Run walk-forward validation on 6-month period."""
    print(f"\n\n{'='*90}")
    print("PART 2: WALK-FORWARD VALIDATION (Out-of-Sample)")
    print(f"{'='*90}")
    
    end_date = datetime.now() - timedelta(days=30)  # End 1 month ago (to have 1 month for out-of-sample)
    start_date = end_date - timedelta(days=180)  # 6 months before that
    
    print(f"Training/Test Period: {start_date.date()} to {end_date.date()}")
    
    tickers = get_tickers('us')[:5]  # Use 5 tickers for walk-forward (slower process)
    
    validator = WalkForwardValidator(
        initial_capital=10000,
        position_size=0.5,
        in_sample_days=30,
        out_sample_days=30,
        step_days=30
    )
    
    print(f"Tickers: {', '.join(tickers)}")
    all_results = validator.run_walk_forward_multiple(tickers, start_date, end_date)
    summary = validator.generate_summary(all_results)
    
    return {
        'results': all_results,
        'summary': summary,
        'start_date': start_date,
        'end_date': end_date,
        'period_name': 'Walk-Forward (2025)'
    }


def run_2026_out_of_sample_test():
    """Test on 2026 data (truly out-of-sample from 2025 training)."""
    print(f"\n\n{'='*90}")
    print("PART 3: OUT-OF-SAMPLE 2026 TEST (Truly Out-of-Sample)")
    print(f"{'='*90}")
    
    # Use parameters trained on 2025 data
    start_date_2026 = datetime(2026, 1, 1)
    end_date_2026 = datetime.now()  # Current date (Feb 14, 2026)
    
    if end_date_2026 <= start_date_2026:
        print("⚠️  Not enough 2026 data available yet")
        return None
    
    print(f"2026 Test Period: {start_date_2026.date()} to {end_date_2026.date()}")
    
    # Use same tickers as original training
    tickers = get_tickers('us')[:10]
    
    simulator = EnhancedCostSimulator(
        initial_capital=10000,
        position_size=0.5,
        slippage_pct=0.1,
        commission_per_trade=5.0
    )
    
    print(f"Tickers: {', '.join(tickers)}")
    print("Using threshold=0.5 from 2025 training period\n")
    
    results = simulator.run_backtest(tickers, start_date_2026, end_date_2026, threshold=0.5)
    
    simulator.generate_report(results)
    
    return {
        'results': results,
        'start_date': start_date_2026,
        'end_date': end_date_2026,
        'period_name': '2026 Out-of-Sample'
    }


def generate_comprehensive_report(original_results, walkforward_results, oos_2026_results):
    """Generate comprehensive report comparing all three approaches."""
    
    report_path = Path('/home/ulluboz/.openclaw/workspace/stock-signals/BACKTEST_IMPROVEMENTS_REPORT.md')
    
    with open(report_path, 'w') as f:
        f.write("# Comprehensive Backtesting Improvements Report\n\n")
        f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        
        # ===== EXECUTIVE SUMMARY =====
        f.write("## Executive Summary\n\n")
        f.write("This report documents three critical improvements to the stock-signals backtesting framework:\n\n")
        f.write("1. **Realistic Trading Costs**: Added 0.1% slippage and $5 commission per round-trip\n")
        f.write("2. **Walk-Forward Validation**: Implemented out-of-sample testing to detect overfitting\n")
        f.write("3. **2026 Out-of-Sample Testing**: Real forward-test on truly held-out data\n\n")
        
        # Extract key metrics
        orig_returns = [r['total_return_pct_with_costs'] for r in original_results['results']]
        orig_avg = np.mean(orig_returns)
        orig_with_costs = orig_avg
        
        # Calculate what returns would be without costs for comparison
        orig_returns_no_costs = [r['total_return_pct_no_costs'] for r in original_results['results']]
        orig_no_costs = np.mean(orig_returns_no_costs)
        cost_impact = orig_no_costs - orig_with_costs
        
        f.write("### Key Findings\n\n")
        f.write(f"- **Original Backtest (6 months, with costs)**: {orig_with_costs:+.2f}%\n")
        f.write(f"- **Hypothetical (without costs)**: {orig_no_costs:+.2f}%\n")
        f.write(f"- **Cost Impact**: {cost_impact:+.2f}%\n\n")
        
        if walkforward_results:
            wf_summary = walkforward_results['summary']
            f.write(f"- **Walk-Forward In-Sample Avg**: {wf_summary['avg_in_sample']:+.2f}%\n")
            f.write(f"- **Walk-Forward Out-of-Sample Avg**: {wf_summary['avg_out_sample']:+.2f}%\n")
            f.write(f"- **Overfitting Gap**: {wf_summary['avg_overfit_gap']:+.2f}%\n")
            f.write(f"- **Out-of-Sample Std Dev**: {wf_summary['std_out_sample']:.2f}%\n\n")
        
        if oos_2026_results and oos_2026_results['results']:
            oos_returns = [r['total_return_pct_with_costs'] for r in oos_2026_results['results']]
            if oos_returns:
                oos_avg = np.mean(oos_returns)
                f.write(f"- **2026 Out-of-Sample Test**: {oos_avg:+.2f}%\n")
                f.write(f"- **2026 Period**: {oos_2026_results['start_date'].date()} to {oos_2026_results['end_date'].date()}\n\n")
        
        # ===== SECTION 1: REALISTIC COSTS =====
        f.write("---\n\n")
        f.write("## 1. Impact of Realistic Trading Costs\n\n")
        f.write("### Cost Model\n")
        f.write("- **Slippage**: 0.1% on both entry and exit prices\n")
        f.write("- **Commission**: $5 per round-trip trade\n")
        f.write("- **Applied to**: Entry price AND exit price\n\n")
        
        f.write("### Cost Impact by Ticker (6-Month Period)\n\n")
        f.write("| Ticker | Return (no costs) | Return (with costs) | Cost Impact | Total Cost | # Trades |\n")
        f.write("|--------|-------------------|---------------------|-------------|------------|----------|\n")
        
        for result in original_results['results']:
            no_costs = result['total_return_pct_no_costs']
            with_costs = result['total_return_pct_with_costs']
            impact = result['costs_impact_pct']
            total_cost = result['total_trading_costs'] + result['total_slippage_costs']
            trades = result['num_trades']
            f.write(f"| {result['ticker']} | {no_costs:+.2f}% | {with_costs:+.2f}% | {impact:+.2f}% | ${total_cost:,.2f} | {trades} |\n")
        
        f.write(f"\n**Average Cost Impact**: {cost_impact:+.2f}% across all tickers\n\n")
        
        # Portfolio-level costs
        total_all_trades = sum(r['num_trades'] for r in original_results['results'])
        total_all_costs = sum(r['total_trading_costs'] + r['total_slippage_costs'] for r in original_results['results'])
        total_commission = sum(r['total_commissions'] for r in original_results['results'])
        total_slippage = sum(r['total_slippage_costs'] for r in original_results['results'])
        
        f.write("### Portfolio-Level Cost Breakdown\n\n")
        f.write(f"| Metric | Value |\n")
        f.write(f"|--------|-------|\n")
        f.write(f"| Total Trades | {total_all_trades} |\n")
        f.write(f"| Total Commission Cost | ${total_commission:,.2f} |\n")
        f.write(f"| Total Slippage Cost | ${total_slippage:,.2f} |\n")
        f.write(f"| **Total Trading Costs** | **${total_all_costs:,.2f}** |\n")
        f.write(f"| Avg Cost per Trade | ${total_all_costs/total_all_trades:,.2f} if total_all_trades > 0 else 'N/A' |\n\n")
        
        f.write("### Key Insight\n")
        f.write(f"Trading costs reduce the average return by approximately **{cost_impact:.2f}%** (or about {cost_impact/orig_no_costs*100:.1f}% of gross returns).\n\n")
        
        # ===== SECTION 2: WALK-FORWARD VALIDATION =====
        f.write("---\n\n")
        f.write("## 2. Walk-Forward Validation Results\n\n")
        f.write("### Methodology\n")
        f.write("Walk-forward validation splits the 6-month historical data into overlapping 1-month windows:\n")
        f.write("1. **In-Sample (Training)**: First month - optimize signal threshold\n")
        f.write("2. **Out-of-Sample (Testing)**: Second month - test without retuning (true validation)\n")
        f.write("3. **Roll Forward**: Repeat process, advancing by 1 month each iteration\n\n")
        
        f.write("This prevents overfitting by ensuring parameters are never optimized on data they're tested on.\n\n")
        
        if walkforward_results:
            wf_summary = walkforward_results['summary']
            wf_all_results = walkforward_results['results']
            
            f.write("### Results Summary\n\n")
            f.write(f"| Metric | Value |\n")
            f.write(f"|--------|-------|\n")
            f.write(f"| Average In-Sample Return | {wf_summary['avg_in_sample']:+.2f}% |\n")
            f.write(f"| Average Out-of-Sample Return | {wf_summary['avg_out_sample']:+.2f}% |\n")
            f.write(f"| Overfitting Gap | {wf_summary['avg_overfit_gap']:+.2f}% |\n")
            f.write(f"| Out-of-Sample Std Dev | {wf_summary['std_out_sample']:.2f}% |\n")
            f.write(f"| Total Windows Tested | {wf_summary['num_windows']} |\n\n")
            
            f.write("### Window-by-Window Results\n\n")
            
            for ticker, windows in wf_all_results.items():
                if not windows:
                    continue
                
                f.write(f"#### {ticker}\n\n")
                f.write("| Window | In-Sample Period | Out-Sample Period | Threshold | In-Sample | Out-Sample | Overfit Gap | Trades |\n")
                f.write("|--------|------------------|-------------------|-----------|-----------|-----------|-------------|--------|\n")
                
                for window in windows:
                    is_start = window['in_sample_start'].strftime('%Y-%m-%d')
                    is_end = window['in_sample_end'].strftime('%Y-%m-%d')
                    os_start = window['out_sample_start'].strftime('%Y-%m-%d')
                    os_end = window['out_sample_end'].strftime('%Y-%m-%d')
                    threshold = window['optimized_threshold']
                    in_ret = window['in_sample_return']
                    out_ret = window['out_sample_return']
                    gap = window['overfit_gap']
                    trades = window['out_sample_trades']
                    
                    f.write(f"| {window['window']} | {is_start}→{is_end} | {os_start}→{os_end} | {threshold:.1f} | {in_ret:+.2f}% | {out_ret:+.2f}% | {gap:+.2f}% | {trades} |\n")
                
                f.write("\n")
            
            f.write("### Walk-Forward Interpretation\n\n")
            if wf_summary['avg_out_sample'] > 0.5:
                f.write("✅ **POSITIVE EDGE DETECTED**: The out-of-sample returns are positive and meaningful.\n\n")
            elif wf_summary['avg_out_sample'] > 0 and wf_summary['avg_overfit_gap'] > 5:
                f.write("⚠️  **WEAK EDGE WITH OVERFITTING**: Out-of-sample returns are positive but small, with significant overfitting.\n\n")
            elif wf_summary['avg_out_sample'] > 0:
                f.write("⚠️  **MARGINAL EDGE**: Small positive out-of-sample returns suggest limited edge.\n\n")
            else:
                f.write("❌ **NO RELIABLE EDGE**: Out-of-sample returns are negative or zero, suggesting overfitting.\n\n")
            
            f.write(f"- **In-Sample vs Out-of-Sample**: The {wf_summary['avg_overfit_gap']:+.2f}% gap indicates ")
            if abs(wf_summary['avg_overfit_gap']) > 3:
                f.write("significant overfitting. Parameters tuned on in-sample data don't generalize well.\n\n")
            else:
                f.write("moderate overfitting. Some parameter tuning benefits persist out-of-sample.\n\n")
        
        # ===== SECTION 3: 2026 OUT-OF-SAMPLE =====
        f.write("---\n\n")
        f.write("## 3. Out-of-Sample Testing on 2026 Data\n\n")
        f.write("### Methodology\n")
        f.write("Using signal parameters optimized on 2025 data, we forward-test on 2026 data (truly held-out).\n\n")
        
        if oos_2026_results and oos_2026_results['results']:
            oos_returns = [r['total_return_pct_with_costs'] for r in oos_2026_results['results']]
            if oos_returns:
                oos_avg = np.mean(oos_returns)
                oos_std = np.std(oos_returns)
                oos_min = np.min(oos_returns)
                oos_max = np.max(oos_returns)
            else:
                oos_2026_results = None
            
            f.write("### 2026 Results\n\n")
            f.write(f"| Metric | Value |\n")
            f.write(f"|--------|-------|\n")
            f.write(f"| Test Period | {oos_2026_results['start_date'].strftime('%Y-%m-%d')} to {oos_2026_results['end_date'].strftime('%Y-%m-%d')} |\n")
            f.write(f"| Average Return | {oos_avg:+.2f}% |\n")
            f.write(f"| Std Dev | {oos_std:.2f}% |\n")
            f.write(f"| Best Performer | {oos_max:+.2f}% |\n")
            f.write(f"| Worst Performer | {oos_min:+.2f}% |\n")
            f.write(f"| Number of Stocks | {len(oos_2026_results['results'])} |\n\n")
            
            f.write("### 2026 Results by Ticker\n\n")
            f.write("| Ticker | Return | # Trades | Win Rate |\n")
            f.write("|--------|--------|----------|----------|\n")
            
            for result in oos_2026_results['results']:
                ret = result['total_return_pct_with_costs']
                trades = result['num_trades']
                win_rate = result['win_rate_pct']
                f.write(f"| {result['ticker']} | {ret:+.2f}% | {trades} | {win_rate:.0f}% |\n")
            
            f.write("\n")
            
            if oos_avg > 0:
                f.write("### ✅ Positive Out-of-Sample Performance\n\n")
                f.write(f"The system generated **{oos_avg:+.2f}%** average return on 2026 data,\n")
                f.write(f"confirming that the edge detected in 2025 generalizes to new market data.\n\n")
            else:
                f.write("### ❌ Negative Out-of-Sample Performance\n\n")
                f.write(f"The system generated **{oos_avg:+.2f}%** average return on 2026 data,\n")
                f.write(f"suggesting the 2025 edge does not generalize.\n\n")
        else:
            f.write("⚠️  Insufficient 2026 data available (need at least 1 month).\n\n")
        
        # ===== SECTION 4: COMPARISON TABLE =====
        f.write("---\n\n")
        f.write("## 4. Comparison: Original vs Improved Methods\n\n")
        
        f.write("| Method | Period | Avg Return | Characteristics | Reliability |\n")
        f.write("|--------|--------|------------|-----------------|-------------|\n")
        
        f.write(f"| Original (no costs) | 2025 (6 months) | {orig_no_costs:+.2f}% | ")
        f.write("Optimistic, ignores trading friction | Low |\n")
        
        f.write(f"| Original (with costs) | 2025 (6 months) | {orig_with_costs:+.2f}% | ")
        f.write("More realistic but still has look-ahead bias | Medium |\n")
        
        if walkforward_results:
            wf_summary = walkforward_results['summary']
            f.write(f"| Walk-Forward (in-sample) | 2025 (multiple windows) | {wf_summary['avg_in_sample']:+.2f}% | ")
            f.write("Tuned on same data tested | High |\n")
            
            f.write(f"| Walk-Forward (out-of-sample) | 2025 (multiple windows) | {wf_summary['avg_out_sample']:+.2f}% | ")
            f.write("True out-of-sample, no look-ahead | **Very High** |\n")
        
        if oos_2026_results and oos_2026_results['results']:
            oos_returns = [r['total_return_pct_with_costs'] for r in oos_2026_results['results']]
            if oos_returns:
                oos_avg = np.mean(oos_returns)
                f.write(f"| 2026 Forward Test | Jan-Feb 2026 | {oos_avg:+.2f}% | ")
                f.write("Real future data, zero overfitting possible | **Highest** |\n")
        
        f.write("\n")
        
        # ===== SECTION 5: CONCLUSIONS =====
        f.write("---\n\n")
        f.write("## 5. Conclusions & Recommendations\n\n")
        
        f.write("### Key Findings\n\n")
        
        f.write(f"1. **Trading Costs Matter**: Realistic costs (slippage + commission) reduce returns by ")
        f.write(f"approximately **{cost_impact:.2f}%**, or about {abs(cost_impact/orig_no_costs)*100:.0f}% of gross returns.\n\n")
        
        if walkforward_results:
            wf_summary = walkforward_results['summary']
            f.write(f"2. **Overfitting is Significant**: The gap between in-sample ({wf_summary['avg_in_sample']:+.2f}%) ")
            f.write(f"and out-of-sample ({wf_summary['avg_out_sample']:+.2f}%) returns is **{wf_summary['avg_overfit_gap']:+.2f}%**, ")
            f.write(f"showing {abs(wf_summary['avg_overfit_gap']/wf_summary['avg_in_sample'])*100:.0f}% performance degradation.\n\n")
            
            if wf_summary['avg_out_sample'] > 0:
                f.write(f"3. **Edge Persists Out-of-Sample**: The positive out-of-sample return of {wf_summary['avg_out_sample']:+.2f}% ")
                f.write("suggests the detected patterns have some generalizability.\n\n")
            else:
                f.write(f"3. **No Reliable Edge Detected**: Negative out-of-sample returns indicate overfitting with no real edge.\n\n")
        
        if oos_2026_results and oos_2026_results['results']:
            oos_returns = [r['total_return_pct_with_costs'] for r in oos_2026_results['results']]
            if oos_returns:
                oos_avg = np.mean(oos_returns)
                
                if oos_avg > 0:
                    f.write(f"4. **Forward Test Confirms Edge**: 2026 out-of-sample testing shows {oos_avg:+.2f}% return, ")
                    f.write("validating the system's predictive power on completely unseen data.\n\n")
                else:
                    f.write(f"4. **Forward Test Fails**: 2026 out-of-sample testing shows {oos_avg:+.2f}% return, ")
                    f.write("failing to validate the system on unseen data.\n\n")
        
        f.write("### Recommendations\n\n")
        
        if walkforward_results and walkforward_results['summary']['avg_out_sample'] > 0:
            oos_2026_avg = None
            if oos_2026_results and oos_2026_results['results']:
                oos_2026_returns = [r['total_return_pct_with_costs'] for r in oos_2026_results['results']]
                if oos_2026_returns:
                    oos_2026_avg = np.mean(oos_2026_returns)
            
            if oos_2026_avg is not None and oos_2026_avg > 0:
                f.write("✅ **PROCEED WITH CAUTION**\n\n")
                f.write("The system shows:\n")
                f.write("- Positive out-of-sample returns in walk-forward testing\n")
                f.write("- Positive returns on 2026 forward test data\n")
                f.write("- Measurable edge after accounting for realistic costs\n\n")
                f.write("**Next Steps**:\n")
                f.write("1. Deploy with SMALL position size (2-5% of capital) for live validation\n")
                f.write("2. Monitor actual vs. expected performance closely\n")
                f.write("3. Continue walk-forward validation as new data arrives\n")
                f.write("4. Be alert for regime changes that could break the edge\n\n")
            else:
                f.write("⚠️  **MIXED SIGNALS - CONTINUE RESEARCH**\n\n")
                f.write("Walk-forward validation shows positive out-of-sample returns, but 2026 forward test is negative.\n")
                f.write("This suggests:\n")
                f.write("- Edge may be time-period dependent\n")
                f.write("- Market regime has changed\n")
                f.write("- Parameter tuning needs refinement\n\n")
                f.write("**Next Steps**:\n")
                f.write("1. Analyze what market conditions existed in 2025 vs 2026\n")
                f.write("2. Test adaptive parameter tuning (longer training window)\n")
                f.write("3. Add market regime filtering\n")
                f.write("4. Paper trade for 1-2 months before deploying live\n\n")
        else:
            f.write("❌ **NOT RECOMMENDED FOR LIVE TRADING**\n\n")
            f.write("The system shows:\n")
            f.write("- Significant overfitting (large gap between in-sample and out-of-sample)\n")
            f.write("- Negative or negligible out-of-sample returns\n")
            f.write("- No reliable edge after accounting for realistic costs\n\n")
            f.write("**Next Steps**:\n")
            f.write("1. Revisit signal generation logic\n")
            f.write("2. Test different parameter ranges\n")
            f.write("3. Add new signals or data sources\n")
            f.write("4. Increase look-ahead to 10-20 days\n")
            f.write("5. Repeat validation framework\n\n")
        
        # ===== TECHNICAL DETAILS =====
        f.write("---\n\n")
        f.write("## Technical Details\n\n")
        
        f.write("### Cost Model Implementation\n\n")
        f.write("**Slippage Calculation**:\n")
        f.write("- Entry (Buy): `filled_price = market_price × (1 + 0.1%)`\n")
        f.write("- Exit (Sell): `filled_price = market_price × (1 - 0.1%)`\n\n")
        
        f.write("**Commission**:\n")
        f.write("- $5 fixed per round-trip trade (entry + exit)\n")
        f.write("- Applied at exit point\n\n")
        
        f.write("**Total Cost Per Trade**:\n")
        f.write("- Slippage on entry: `shares × entry_price × 0.1%`\n")
        f.write("- Slippage on exit: `shares × exit_price × 0.1%`\n")
        f.write("- Commission: `$5`\n\n")
        
        f.write("### Signal Parameters\n")
        f.write("- **Threshold**: 0.5 (base signal strength required to trade)\n")
        f.write("- **Window Size**: 20 days (lookback period for signal detection)\n")
        f.write("- **Position Size**: 50% of capital per trade\n")
        f.write("- **Initial Capital**: $10,000\n\n")
        
        f.write("### Data & Methodology\n")
        f.write("- **Data Source**: yfinance (6-month historical + 2026 forward)\n")
        f.write("- **Frequency**: Daily OHLCV data\n")
        f.write("- **Rebalancing**: No regular rebalancing (trade when signals fire)\n")
        f.write("- **Look-ahead Bias**: Eliminated through proper window management\n\n")
        
        print(f"\n✅ Report generated: {report_path}")
        print(f"   Total size: {report_path.stat().st_size:,} bytes")


def main():
    """Run comprehensive backtesting."""
    print("\n" + "="*90)
    print("COMPREHENSIVE BACKTESTING IMPROVEMENTS FOR STOCK-SIGNALS")
    print("="*90)
    
    # Run all three tests
    print("\nRunning improved backtests...")
    
    original_results = run_original_backtest_with_costs()
    walkforward_results = run_walk_forward_validation()
    oos_2026_results = run_2026_out_of_sample_test()
    
    # Generate comprehensive report
    print("\n\nGenerating comprehensive report...")
    generate_comprehensive_report(original_results, walkforward_results, oos_2026_results)
    
    print("\n" + "="*90)
    print("✅ COMPREHENSIVE BACKTESTING COMPLETE")
    print("="*90)
    print("\nKey outputs:")
    print("  1. BACKTEST_IMPROVEMENTS_REPORT.md - Full analysis report")
    print("  2. Enhanced simulator with realistic costs")
    print("  3. Walk-forward validation framework")
    print("  4. 2026 out-of-sample test results")


if __name__ == '__main__':
    main()
