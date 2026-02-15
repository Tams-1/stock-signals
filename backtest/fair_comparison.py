#!/usr/bin/env python3
"""
Fair apples-to-apples comparison with SAME data window (rolling 50-day).

Tests:
1. Simple threshold (0.35) + rolling window → +12.73% baseline
2. Conviction scoring + rolling window → ?% (fair comparison)
3. Conviction scoring + cumulative window → +48.19% (current)

This isolates the impact of conviction scoring vs data window advantage.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import json
import numpy as np
from typing import List, Dict

from production_simulator_full import ProductionSimulatorFull
from src.data.fetch_data import fetch_ticker_data


class FairComparisonSimulator(ProductionSimulatorFull):
    """
    Modified simulator that uses ROLLING window like the baseline.
    This ensures fair comparison (same data availability).
    """
    
    def simulate_ticker(self, ticker: str, start_date: str, end_date: str,
                       min_conviction: float = 0.40, use_rolling_window: bool = True) -> Dict:
        """
        Simulate with option for rolling vs cumulative window.
        
        Args:
            use_rolling_window: If True, use rolling 50-day (fair comparison)
                               If False, use cumulative (current implementation)
        """
        data = fetch_ticker_data(ticker, start_date, end_date)
        
        if len(data) < 60:
            return {
                'ticker': ticker,
                'status': 'insufficient_data',
                'total_return_pct': 0,
                'num_trades': 0
            }
        
        # Trading state
        cash = float(self.initial_capital)
        shares = 0.0
        entry_price = None
        entry_date = None
        
        trades = []
        
        window_size = 50
        dates = data.index
        closes = data['Close'].values
        opens = data['Open'].values
        
        # Simulate day by day
        for i in range(window_size + 1, len(data) - 1):
            signal_date_idx = i - 1
            signal_date = dates[signal_date_idx]
            execution_date = dates[i]
            execution_price = opens[i]
            
            # KEY DIFFERENCE: Rolling vs cumulative window
            if use_rolling_window:
                # ROLLING: Same as baseline (fair comparison)
                window = data.iloc[max(0, i - window_size - 1):i].copy()
            else:
                # CUMULATIVE: Current implementation
                window = data.iloc[:signal_date_idx + 1].copy()
            
            if len(window) < window_size:
                continue
            
            # Detect signals
            signals = self.detect_signals(window, signal_date, ticker)
            
            # Calculate conviction
            conviction, direction = self.calculate_conviction(signals)
            
            # Get regime
            regime = signals['regime'][0]['regime'] if signals.get('regime') else 'unknown'
            
            # Tie-breaker logic
            should_trade_long = False
            if conviction >= min_conviction:
                if direction == 'bullish':
                    should_trade_long = True
                elif direction == 'neutral' and regime == 'uptrend':
                    should_trade_long = True
            
            # Get position size
            position_size_pct = self.get_position_size(conviction) if should_trade_long else 0.0
            
            # Trading logic
            if should_trade_long and shares == 0:
                # BUY
                fill_price = self.apply_costs(execution_price, is_entry=True)
                position_value = cash * position_size_pct
                shares = position_value / fill_price
                cash -= position_value
                entry_price = fill_price
                entry_date = execution_date
            
            elif shares > 0 and (conviction < min_conviction or (direction == 'bearish') or (direction == 'neutral' and regime == 'downtrend')):
                # SELL
                fill_price = self.apply_costs(execution_price, is_entry=False)
                proceeds = shares * fill_price
                cash += proceeds
                
                pnl = proceeds - (shares * entry_price)
                pnl_pct = (pnl / (shares * entry_price) * 100) if entry_price else 0
                
                trades.append({
                    'entry_date': str(entry_date.date()),
                    'exit_date': str(execution_date.date()),
                    'entry_price': float(entry_price),
                    'exit_price': float(fill_price),
                    'pnl': float(pnl),
                    'pnl_pct': float(pnl_pct),
                    'hold_days': int((execution_date - entry_date).days)
                })
                
                shares = 0.0
                entry_price = None
                entry_date = None
        
        # Close final position
        if shares > 0:
            final_price = self.apply_costs(closes[-1], is_entry=False)
            proceeds = shares * final_price
            cash += proceeds
            
            pnl = proceeds - (shares * entry_price)
            pnl_pct = (pnl / (shares * entry_price) * 100) if entry_price else 0
            
            trades.append({
                'entry_date': str(entry_date.date()),
                'exit_date': str(dates[-1].date()),
                'entry_price': float(entry_price),
                'exit_price': float(final_price),
                'pnl': float(pnl),
                'pnl_pct': float(pnl_pct),
                'hold_days': int((dates[-1] - entry_date).days)
            })
        
        # Calculate metrics
        final_equity = cash + (shares * closes[-1])
        total_return = (final_equity - self.initial_capital) / self.initial_capital * 100
        
        win_rate = (sum(1 for t in trades if t['pnl'] > 0) / len(trades) * 100) if trades else 0
        
        return {
            'ticker': ticker,
            'total_return_pct': float(total_return),
            'num_trades': len(trades),
            'win_rate_pct': float(win_rate),
            'trades': trades,
            'status': 'success'
        }


def main():
    """Run fair comparison."""
    print("="*80)
    print("FAIR APPLES-TO-APPLES COMPARISON")
    print("="*80)
    print()
    print("Comparing 3 approaches on Period 4 (Feb 2025 - Feb 2026):")
    print()
    print("1. Simple threshold (0.35) + rolling 50-day")
    print("   Baseline: +12.73% (from previous validation)")
    print()
    print("2. Conviction scoring + rolling 50-day (FAIR COMPARISON)")
    print("   Tests: conviction scoring impact with same data window")
    print()
    print("3. Conviction scoring + cumulative (CURRENT)")
    print("   Current: +48.19% (gives TrendDetectorV2 full history)")
    print()
    
    tickers = [
        "PETR4.SA", "VALE3.SA", "ITUB4.SA", "BBDC4.SA", "BBAS3.SA",
        "ABEV3.SA", "B3SA3.SA", "SUZB3.SA", "RENT3.SA", "WEGE3.SA",
        "MGLU3.SA", "PCAR3.SA", "LREN3.SA", "RAIZ4.SA", "GGBR4.SA",
        "ASAI3.SA", "JBSS3.SA", "RDOR3.SA"
    ]
    
    sim = FairComparisonSimulator(initial_capital=10000, use_news_sentiment=False)
    
    # Test 2: Conviction scoring + rolling window (FAIR)
    print("="*80)
    print("TEST 2: Conviction Scoring + Rolling 50-Day (Fair Comparison)")
    print("="*80)
    print()
    
    results_rolling = []
    for ticker in tickers:
        result = sim.simulate_ticker(ticker, "2025-02-01", "2026-02-28",
                                    min_conviction=0.40, use_rolling_window=True)
        if result['status'] == 'success':
            results_rolling.append(result)
            print(f"  {ticker}: {result['total_return_pct']:+.1f}% | Trades: {result['num_trades']}")
    
    returns_rolling = [r['total_return_pct'] for r in results_rolling]
    avg_rolling = np.mean(returns_rolling) if returns_rolling else 0
    
    print()
    print(f"Portfolio (rolling window): {avg_rolling:+.2f}%")
    
    # Test 3: Conviction scoring + cumulative (CURRENT)
    print()
    print("="*80)
    print("TEST 3: Conviction Scoring + Cumulative (Current Implementation)")
    print("="*80)
    print()
    
    results_cumulative = []
    for ticker in tickers:
        result = sim.simulate_ticker(ticker, "2025-02-01", "2026-02-28",
                                    min_conviction=0.40, use_rolling_window=False)
        if result['status'] == 'success':
            results_cumulative.append(result)
            print(f"  {ticker}: {result['total_return_pct']:+.1f}% | Trades: {result['num_trades']}")
    
    returns_cumulative = [r['total_return_pct'] for r in results_cumulative]
    avg_cumulative = np.mean(returns_cumulative) if returns_cumulative else 0
    
    print()
    print(f"Portfolio (cumulative): {avg_cumulative:+.2f}%")
    
    # Summary
    print()
    print("="*80)
    print("COMPARISON SUMMARY")
    print("="*80)
    print()
    print(f"1. Simple threshold + rolling:     {12.73:+.2f}% (baseline)")
    print(f"2. Conviction + rolling:           {avg_rolling:+.2f}% (fair comparison)")
    print(f"3. Conviction + cumulative:        {avg_cumulative:+.2f}% (current)")
    print()
    print(f"Impact of conviction scoring:      {avg_rolling - 12.73:+.2f}%")
    print(f"Impact of cumulative window:       {avg_cumulative - avg_rolling:+.2f}%")
    print(f"Total improvement:                 {avg_cumulative - 12.73:+.2f}%")
    print()
    
    # Save results
    output = {
        'baseline_simple_rolling': 12.73,
        'conviction_rolling': avg_rolling,
        'conviction_cumulative': avg_cumulative,
        'conviction_impact': avg_rolling - 12.73,
        'window_impact': avg_cumulative - avg_rolling,
        'total_impact': avg_cumulative - 12.73,
        'results_rolling': results_rolling,
        'results_cumulative': results_cumulative
    }
    
    output_file = Path(__file__).parent / "fair_comparison_results.json"
    with open(output_file, 'w') as f:
        json.dump(output, f, indent=2)
    
    print(f"✓ Results saved to {output_file}")


if __name__ == "__main__":
    main()
