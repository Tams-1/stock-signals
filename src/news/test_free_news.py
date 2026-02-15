#!/usr/bin/env python3
"""
Test script for free news client.

Tests:
1. Google News RSS (recent news)
2. FinBERT sentiment analysis
3. Historical vs real-time switching
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from news.free_news_client import get_client
from datetime import datetime, timedelta


def test_free_client():
    """Test free news client with real and historical data."""
    
    print("="*80)
    print("FREE NEWS CLIENT TEST")
    print("="*80)
    print()
    
    # Initialize client
    client = get_client()
    print("✓ Client initialized (FinBERT may download on first run)")
    print()
    
    # Test tickers
    test_tickers = [
        'PETR4.SA',  # Petrobras
        'VALE3.SA',  # Vale
    ]
    
    # Test dates: recent (7 days ago) and historical (6 months ago)
    today = datetime.now()
    recent_date = (today - timedelta(days=7)).strftime('%Y-%m-%d')
    historical_date = (today - timedelta(days=180)).strftime('%Y-%m-%d')
    
    print("="*80)
    print("TEST 1: RECENT NEWS (Google News RSS)")
    print("="*80)
    print(f"Date: {recent_date} (7 days ago)")
    print()
    
    for ticker in test_tickers:
        print(f"Fetching {ticker}...")
        try:
            sentiment = client.get_sentiment(ticker, recent_date)
            
            if sentiment > 0.2:
                label = "POSITIVE (bullish)"
            elif sentiment < -0.2:
                label = "NEGATIVE (bearish)"
            else:
                label = "NEUTRAL"
            
            print(f"  {ticker}: {sentiment:+.2f} ({label})")
        
        except Exception as e:
            print(f"  {ticker}: ERROR - {e}")
        
        print()
    
    print("="*80)
    print("TEST 2: HISTORICAL NEWS (Investing.com Scraping)")
    print("="*80)
    print(f"Date: {historical_date} (6 months ago)")
    print()
    
    for ticker in test_tickers:
        print(f"Fetching {ticker}...")
        try:
            sentiment = client.get_sentiment(ticker, historical_date)
            
            if sentiment > 0.2:
                label = "POSITIVE (bullish)"
            elif sentiment < -0.2:
                label = "NEGATIVE (bearish)"
            else:
                label = "NEUTRAL"
            
            print(f"  {ticker}: {sentiment:+.2f} ({label})")
        
        except Exception as e:
            print(f"  {ticker}: ERROR - {e}")
        
        print()
    
    print("="*80)
    print("TEST COMPLETE")
    print("="*80)
    print()
    print("✅ If you see sentiment scores above, the integration is working!")
    print()
    print("Notes:")
    print("- Recent news: Google News RSS (free, real-time)")
    print("- Historical news: Investing.com scraping (free, may be limited)")
    print("- Sentiment: FinBERT (local, no API costs)")
    print()


if __name__ == "__main__":
    test_free_client()
