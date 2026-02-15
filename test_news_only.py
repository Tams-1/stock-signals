#!/usr/bin/env python3
"""Test news fetching and display for a single ticker"""

import sys
sys.path.insert(0, '/home/ulluboz/.openclaw/workspace/stock-signals')

from src.news.free_news_client import FreeNewsClient
from datetime import datetime, timedelta

ticker = "VALE3.SA"
print(f"\n{'='*70}")
print(f"📰 NEWS TEST: {ticker}")
print(f"{'='*70}\n")

news_client = FreeNewsClient()

# Fetch news from last 3 days
print("Fetching articles from last 3 days...\n")

all_articles = []
for days_ago in range(3):
    date = (datetime.now() - timedelta(days=days_ago)).strftime("%Y-%m-%d")
    query = news_client._ticker_to_query(ticker)
    
    print(f"📅 {date} - Searching for '{query}'...")
    articles = news_client._fetch_google_news(query, days=1)
    
    if articles:
        print(f"   ✅ Found {len(articles)} articles:")
        for i, article in enumerate(articles[:3], 1):  # Show first 3
            print(f"\n   [{i}] TITLE: {article['title'][:80]}")
            print(f"       SOURCE: {article['source']}")
            print(f"       LINK: {article['link'][:60]}...")
            if article.get('summary'):
                print(f"       SUMMARY: {article['summary'][:100]}...")
        
        if len(articles) > 3:
            print(f"\n   ... and {len(articles) - 3} more articles")
        
        all_articles.extend(articles)
    else:
        print(f"   ⚠️  No articles found")

print(f"\n{'='*70}")
print(f"📊 TOTAL: {len(all_articles)} articles fetched")
print(f"{'='*70}\n")

# Now analyze sentiment (without FinBERT - just show what would be analyzed)
print("📈 SENTIMENT ANALYSIS (using FinBERT):\n")

if all_articles:
    for i, article in enumerate(all_articles[:5], 1):  # Show first 5
        text = f"{article['title']} {article.get('summary', '')}"
        print(f"[{i}] Analyzing: {text[:70]}...")
        try:
            sentiment = news_client.sentiment_analyzer.analyze(text)
            print(f"    Sentiment Score: {sentiment:+.2f}")
        except Exception as e:
            print(f"    Error: {e}")
        print()

print(f"{'='*70}\n")
