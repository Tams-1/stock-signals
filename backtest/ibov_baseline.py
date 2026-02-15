#!/usr/bin/env python3
"""
IBOV Index Baseline Analysis (Feb 2025 - Feb 2026)
Fetches IBOV data for comparison against signal strategy
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np
import pandas as pd
import yfinance as yf
from datetime import datetime
import json
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def fetch_ibov_data(start_date, end_date):
    """Fetch IBOV index data"""
    logger.info(f"Fetching IBOV data from {start_date.date()} to {end_date.date()}...")
    
    try:
        data = yf.download('^BVSP', start=start_date, end=end_date, progress=False)
        
        if isinstance(data.columns, pd.MultiIndex):
            data.columns = data.columns.droplevel(-1)
        
        return data
    except Exception as e:
        logger.error(f"Failed to fetch IBOV: {e}")
        return None


def calculate_ibov_returns(data):
    """Calculate IBOV returns and statistics"""
    if data is None or len(data) < 2:
        return None
    
    closes = data['Close'].values.astype(float)
    dates = data.index.tolist()
    
    # Buy and hold from start to end
    buy_price = closes[0]
    sell_price = closes[-1]
    total_return_pct = (sell_price - buy_price) / buy_price * 100
    
    # Monthly returns
    df = data.copy()
    df['Month'] = df.index.to_period('M')
    monthly_returns = []
    
    for month in df['Month'].unique():
        month_data = df[df['Month'] == month]
        if len(month_data) > 1:
            month_start = month_data.iloc[0]['Close']
            month_end = month_data.iloc[-1]['Close']
            month_return = (month_end - month_start) / month_start * 100
            monthly_returns.append({
                'month': str(month),
                'return_pct': month_return,
                'start_price': month_start,
                'end_price': month_end
            })
    
    # Volatility and drawdown
    daily_returns = np.diff(closes) / closes[:-1]
    volatility = np.std(daily_returns) * np.sqrt(252) * 100  # Annualized
    
    # Max drawdown
    peak = closes[0]
    max_dd = 0
    for price in closes:
        if price > peak:
            peak = price
        dd = (peak - price) / peak
        max_dd = max(max_dd, dd)
    
    max_dd_pct = max_dd * 100
    
    # Equity curve
    equity_log = [{'date': dates[0], 'price': closes[0], 'return_pct': 0.0}]
    for i in range(1, len(closes)):
        ret = (closes[i] - closes[0]) / closes[0] * 100
        equity_log.append({'date': dates[i], 'price': closes[i], 'return_pct': ret})
    
    result = {
        'index': '^BVSP',
        'start_date': str(dates[0].date()),
        'end_date': str(dates[-1].date()),
        'start_price': float(closes[0]),
        'end_price': float(closes[-1]),
        'total_return_pct': total_return_pct,
        'annualized_volatility_pct': volatility,
        'max_drawdown_pct': max_dd_pct,
        'sharpe_ratio': (total_return_pct / 12) / (volatility / np.sqrt(12)) if volatility > 0 else 0,
        'monthly_returns': monthly_returns,
        'equity_log': equity_log
    }
    
    return result


def main():
    start_date = datetime(2025, 2, 1)
    end_date = datetime(2026, 2, 14)
    
    # Fetch IBOV data
    ibov_data = fetch_ibov_data(start_date, end_date)
    
    if ibov_data is None or len(ibov_data) < 2:
        logger.error("Failed to get IBOV data")
        return None
    
    # Calculate metrics
    ibov_metrics = calculate_ibov_returns(ibov_data)
    
    # Save results
    results_file = Path(__file__).parent.parent / 'ibov_baseline_results.json'
    
    # Convert dates to strings
    ibov_metrics['equity_log'] = [
        {**log, 'date': log['date'].isoformat() if hasattr(log['date'], 'isoformat') else str(log['date'])}
        for log in ibov_metrics['equity_log']
    ]
    
    with open(results_file, 'w') as f:
        json.dump(ibov_metrics, f, indent=2, default=str)
    
    logger.info(f"\nIBOV Results saved to {results_file}")
    
    # Print summary
    logger.info(f"\n{'='*70}")
    logger.info(f"IBOV INDEX BASELINE")
    logger.info(f"{'='*70}")
    logger.info(f"Period: {ibov_metrics['start_date']} to {ibov_metrics['end_date']}")
    logger.info(f"Total Return: {ibov_metrics['total_return_pct']:+.2f}%")
    logger.info(f"Annual Volatility: {ibov_metrics['annualized_volatility_pct']:.2f}%")
    logger.info(f"Max Drawdown: {ibov_metrics['max_drawdown_pct']:.2f}%")
    logger.info(f"Sharpe Ratio: {ibov_metrics['sharpe_ratio']:.3f}")
    logger.info(f"{'='*70}\n")
    
    return ibov_metrics


if __name__ == '__main__':
    ibov_results = main()
