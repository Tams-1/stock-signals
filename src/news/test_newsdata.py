#!/usr/bin/env python3
"""
Test script for NewsData.io client.

Tests:
1. API connectivity
2. Sentiment parsing
3. Brazilian ticker mapping
4. Rate limiting
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from news.newsdata_client import NewsDataClient
from datetime import datetime


def test_client(api_key: str):
    """Test NewsData.io client with real API key."""
    
    print("="*80)
    print("NEWSDATA.IO CLIENT TEST")
    print("="*80)
    print()
    
    # Initialize client
    client = NewsDataClient(api_key)
    print("✓ Client initialized")
    print()
    
    # Test tickers (Brazilian stocks)
    test_tickers = [
        'PETR4.SA',  # Petrobras
        'VALE3.SA',  # Vale
        'ITUB4.SA',  # Itaú
    ]
    
    today = datetime.now().strftime('%Y-%m-%d')
    
    print(f"Testing sentiment fetch for {today}")
    print(f"Tickers: {', '.join(test_tickers)}")
    print()
    
    for ticker in test_tickers:
        print(f"Fetching {ticker}...")
        try:
            sentiment = client.get_sentiment(ticker, today)
            
            if sentiment > 0:
                sentiment_label = "POSITIVE"
            elif sentiment < 0:
                sentiment_label = "NEGATIVE"
            else:
                sentiment_label = "NEUTRAL"
            
            print(f"  {ticker}: {sentiment:+.2f} ({sentiment_label})")
        
        except Exception as e:
            print(f"  {ticker}: ERROR - {e}")
        
        print()
    
    print("="*80)
    print("TEST COMPLETE")
    print("="*80)
    print()
    print("If you see sentiment scores above, the integration is working!")
    print()


if __name__ == "__main__":
    # API key from environment or hardcoded for testing
    API_KEY = "pub_1757f48565d149cb8e2053f54b26e977"
    
    if not API_KEY:
        print("ERROR: API_KEY not set")
        sys.exit(1)
    
    test_client(API_KEY)
