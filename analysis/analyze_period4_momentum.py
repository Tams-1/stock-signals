#!/usr/bin/env python3
"""
Analyze Period 4 (Feb 2025 - Feb 2026) to identify momentum signal failures.

This script:
1. Loads actual market data from Period 4
2. Analyzes where strong momentum existed but signals missed it
3. Measures signal strength distribution vs actual price moves
4. Identifies specific improvement opportunities
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
import json

from src.data.fetch_data import fetch_ticker_data
from src.signals.momentum_reversal import MomentumReversalDetector
from src.signals.robust_trend_detection import RobustTrendDetector


# Period 4 definition
START_DATE = "2025-02-01"
END_DATE = "2026-02-28"

# Top IBOV stocks
TICKERS = [
    "PETR4.SA", "VALE3.SA", "ITUB4.SA", "BBDC4.SA", "BBAS3.SA",
    "ABEV3.SA", "B3SA3.SA", "SUZB3.SA", "RENT3.SA", "WEGE3.SA",
    "MGLU3.SA", "PCAR3.SA", "LREN3.SA", "RAIZ4.SA", "GGBR4.SA",
    "ASAI3.SA", "JBSS3.SA", "RDOR3.SA"
]


def analyze_momentum_opportunities(ticker, data):
    """
    Find periods where strong momentum existed but signals didn't capture it.
    
    Returns dict with:
    - missed_moves: List of strong price moves (>5%) that weren't signaled
    - signal_accuracy: How often momentum signals matched actual moves
    - optimal_threshold: What threshold would have captured more moves
    """
    detector = MomentumReversalDetector()
    trend_detector = RobustTrendDetector()
    
    results = {
        'ticker': ticker,
        'missed_moves': [],
        'false_signals': [],
        'signal_stats': {},
        'recommendations': []
    }
    
    # Calculate actual price momentum (5-day, 10-day, 20-day)
    data = data.copy()
    data['returns_5d'] = data['Close'].pct_change(5)
    data['returns_10d'] = data['Close'].pct_change(10)
    data['returns_20d'] = data['Close'].pct_change(20)
    data['volume_spike'] = data['Volume'] / data['Volume'].rolling(20).mean()
    
    # Get momentum signals at each point
    signal_log = []
    
    for i in range(50, len(data) - 10):  # Leave room for forward-looking validation
        window = data.iloc[:i+1]
        
        try:
            # Get momentum signal
            signals = detector.run_all(window)
            
            # Get trend context
            trend_ctx = trend_detector.get_robust_trend(window)
            
            # Calculate actual forward return (next 10 days)
            future_return = (data.iloc[i+10]['Close'] / data.iloc[i]['Close']) - 1
            
            # Log signal vs outcome
            signal_strength = max([s[1] for s in signals]) if signals else 0
            signal_direction = signals[0][2] if signals and signals[0][2] else 'none'
            
            signal_log.append({
                'date': data.iloc[i].name,
                'close': data.iloc[i]['Close'],
                'signal_strength': signal_strength,
                'signal_direction': signal_direction,
                'trend_consensus': trend_ctx['consensus'],
                'future_10d_return': future_return,
                'volume_spike': data.iloc[i]['volume_spike']
            })
            
        except Exception as e:
            continue
    
    # Convert to DataFrame for analysis
    signals_df = pd.DataFrame(signal_log)
    
    if len(signals_df) == 0:
        return results
    
    # Find missed moves: strong future returns but weak/no signal
    missed_threshold = 0.05  # 5% move
    signal_threshold = 0.5   # Current threshold
    
    missed_moves = signals_df[
        (abs(signals_df['future_10d_return']) > missed_threshold) & 
        (signals_df['signal_strength'] < signal_threshold)
    ]
    
    results['missed_moves'] = [
        {
            'date': str(row['date'].date()) if hasattr(row['date'], 'date') else str(row['date']),
            'close': float(row['close']),
            'actual_return': float(row['future_10d_return']),
            'signal_strength': float(row['signal_strength']),
            'trend': str(row['trend_consensus']),
            'volume_spike': float(row['volume_spike'])
        }
        for _, row in missed_moves.iterrows()
    ]
    
    # Find false signals: strong signal but small/opposite move
    false_signals = signals_df[
        (signals_df['signal_strength'] >= signal_threshold) & 
        (abs(signals_df['future_10d_return']) < 0.02)  # <2% move
    ]
    
    results['false_signals'] = [
        {
            'date': str(row['date'].date()) if hasattr(row['date'], 'date') else str(row['date']),
            'close': float(row['close']),
            'signal_strength': float(row['signal_strength']),
            'actual_return': float(row['future_10d_return']),
            'trend': str(row['trend_consensus'])
        }
        for _, row in false_signals.head(10).iterrows()
    ]
    
    # Calculate optimal threshold (balance precision vs recall)
    thresholds = np.arange(0.3, 0.8, 0.05)
    best_f1 = 0
    best_threshold = 0.5
    
    for thresh in thresholds:
        # True positives: signal + actual move
        tp = len(signals_df[
            (signals_df['signal_strength'] >= thresh) & 
            (abs(signals_df['future_10d_return']) > 0.03)
        ])
        
        # False positives: signal but no move
        fp = len(signals_df[
            (signals_df['signal_strength'] >= thresh) & 
            (abs(signals_df['future_10d_return']) < 0.02)
        ])
        
        # False negatives: no signal but actual move
        fn = len(signals_df[
            (signals_df['signal_strength'] < thresh) & 
            (abs(signals_df['future_10d_return']) > 0.03)
        ])
        
        if tp + fp > 0 and tp + fn > 0:
            precision = tp / (tp + fp)
            recall = tp / (tp + fn)
            if precision + recall > 0:
                f1 = 2 * (precision * recall) / (precision + recall)
                if f1 > best_f1:
                    best_f1 = f1
                    best_threshold = thresh
    
    results['signal_stats'] = {
        'total_signals': int(len(signals_df[signals_df['signal_strength'] >= signal_threshold])),
        'missed_moves_count': int(len(missed_moves)),
        'false_signals_count': int(len(false_signals)),
        'optimal_threshold': float(best_threshold),
        'optimal_f1_score': float(best_f1),
        'avg_signal_strength': float(signals_df['signal_strength'].mean()),
        'signal_strength_std': float(signals_df['signal_strength'].std())
    }
    
    # Generate recommendations
    if len(missed_moves) > 5:
        results['recommendations'].append(
            f"Lower threshold from 0.5 to {best_threshold:.2f} (missed {len(missed_moves)} strong moves)"
        )
    
    if missed_moves['volume_spike'].mean() > 1.5:
        results['recommendations'].append(
            f"Add volume confirmation (missed moves had {missed_moves['volume_spike'].mean():.1f}x avg volume)"
        )
    
    if len(false_signals) > 10:
        results['recommendations'].append(
            f"Improve signal filtering ({len(false_signals)} false positives with current threshold)"
        )
    
    return results


def main():
    """Run analysis on all tickers."""
    print("=" * 80)
    print("PERIOD 4 MOMENTUM ANALYSIS")
    print(f"Period: {START_DATE} to {END_DATE}")
    print("=" * 80)
    print()
    
    all_results = {}
    
    for ticker in TICKERS:
        print(f"Analyzing {ticker}...", flush=True)
        
        try:
            data = fetch_ticker_data(ticker, START_DATE, END_DATE)
            
            if len(data) < 60:
                print(f"  ⚠️  Insufficient data ({len(data)} days)")
                continue
            
            results = analyze_momentum_opportunities(ticker, data)
            all_results[ticker] = results
            
            print(f"  ✓ Missed moves: {results['signal_stats'].get('missed_moves_count', 0)}")
            print(f"  ✓ False signals: {results['signal_stats'].get('false_signals_count', 0)}")
            print(f"  ✓ Optimal threshold: {results['signal_stats'].get('optimal_threshold', 0.5):.2f}")
            
            if results['recommendations']:
                print("  Recommendations:")
                for rec in results['recommendations']:
                    print(f"    - {rec}")
            print()
            
        except Exception as e:
            print(f"  ✗ Error: {str(e)}")
            continue
    
    # Save results
    output_file = Path(__file__).parent / "period4_momentum_analysis.json"
    with open(output_file, 'w') as f:
        json.dump(all_results, f, indent=2)
    
    print(f"\n✓ Analysis saved to {output_file}")
    
    # Summary statistics
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    
    total_missed = sum(r['signal_stats'].get('missed_moves_count', 0) for r in all_results.values())
    total_false = sum(r['signal_stats'].get('false_signals_count', 0) for r in all_results.values())
    avg_optimal_thresh = np.mean([r['signal_stats'].get('optimal_threshold', 0.5) for r in all_results.values()])
    
    print(f"Total missed moves across all stocks: {total_missed}")
    print(f"Total false signals: {total_false}")
    print(f"Average optimal threshold: {avg_optimal_thresh:.2f} (current: 0.50)")
    print()
    
    # Most common recommendations
    all_recs = []
    for r in all_results.values():
        all_recs.extend(r['recommendations'])
    
    if all_recs:
        print("Most common recommendations:")
        from collections import Counter
        rec_counts = Counter([rec.split('(')[0].strip() for rec in all_recs])
        for rec, count in rec_counts.most_common(3):
            print(f"  {count}/{len(all_results)} stocks: {rec}")
    
    print("\n✓ Analysis complete. Next: implement top improvements.")


if __name__ == "__main__":
    main()
