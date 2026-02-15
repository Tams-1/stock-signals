#!/usr/bin/env python3
"""
Final comparison: WITHOUT news vs WITH real news vs IBOV
Period 4: Feb 2025 - Feb 2026
"""

import yfinance as yf
from datetime import datetime

def calculate_ibov_return():
    """Calculate IBOV return for Period 4"""
    start_date = "2025-02-01"
    end_date = "2026-02-14"
    
    print(f"Fetching IBOV data from {start_date} to {end_date}...")
    ibov = yf.download("^BVSP", start=start_date, end=end_date, progress=False)
    
    if len(ibov) < 2:
        print("❌ Failed to fetch IBOV data")
        return None
    
    start_price = ibov['Close'].iloc[0]
    end_price = ibov['Close'].iloc[-1]
    
    ibov_return = ((end_price - start_price) / start_price) * 100
    
    print(f"\n📊 IBOV Performance:")
    print(f"  Start: {start_price:.2f}")
    print(f"  End: {end_price:.2f}")
    print(f"  Return: {ibov_return:+.2f}%")
    
    return ibov_return

def extract_results_from_log(log_path):
    """Extract WITHOUT and WITH news results from log"""
    with open(log_path, 'r') as f:
        lines = f.readlines()
    
    # Look for final summary lines
    without_news = None
    with_news = None
    
    for line in lines:
        if "WITHOUT news:" in line:
            # Extract percentage (format: "WITHOUT news: +XX.XX%")
            parts = line.split("WITHOUT news:")
            if len(parts) > 1:
                pct_str = parts[1].strip().replace('%', '').replace('+', '')
                without_news = float(pct_str)
        
        if "WITH REAL news:" in line:
            parts = line.split("WITH REAL news:")
            if len(parts) > 1:
                pct_str = parts[1].strip().replace('%', '').replace('+', '')
                with_news = float(pct_str)
    
    return without_news, with_news

def main():
    print("=" * 80)
    print("FINAL COMPARISON: WITHOUT news vs WITH real news vs IBOV")
    print("Period 4: Feb 2025 - Feb 2026")
    print("=" * 80)
    
    # Calculate IBOV
    ibov_return = calculate_ibov_return()
    
    # Extract results from log
    log_path = "real_news_results.log"
    without_news, with_news = extract_results_from_log(log_path)
    
    print(f"\n📊 FINAL RESULTS:")
    print(f"  1. WITHOUT news: {without_news:+.2f}%")
    print(f"  2. WITH REAL news: {with_news:+.2f}%")
    print(f"  3. IBOV: {ibov_return:+.2f}%")
    
    print(f"\n📈 COMPARISONS:")
    if with_news is not None and without_news is not None:
        news_impact = with_news - without_news
        print(f"  News impact: {news_impact:+.2f}% ({'+' if news_impact > 0 else ''}improvement)")
    
    if with_news is not None and ibov_return is not None:
        vs_ibov_with_news = with_news - ibov_return
        print(f"  WITH news vs IBOV: {vs_ibov_with_news:+.2f}%")
    
    if without_news is not None and ibov_return is not None:
        vs_ibov_without_news = without_news - ibov_return
        print(f"  WITHOUT news vs IBOV: {vs_ibov_without_news:+.2f}%")
    
    print("=" * 80)

if __name__ == "__main__":
    main()
