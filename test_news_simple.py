#!/usr/bin/env python3
"""Simple news fetch test - NO FinBERT loading"""

import feedparser
from urllib.parse import quote_plus
from datetime import datetime, timedelta

ticker = "VALE3"
print(f"\n{'='*70}")
print(f"📰 NEWS TEST: {ticker}")
print(f"{'='*70}\n")

# Fetch from Google News RSS directly
for days_ago in range(3):
    date = (datetime.now() - timedelta(days=days_ago)).strftime("%Y-%m-%d")
    
    # URL encode query
    encoded_query = quote_plus(ticker)
    url = f"https://news.google.com/rss/search?q={encoded_query}+when:{days_ago+1}d&hl=pt-BR&gl=BR&ceid=BR:pt-419"
    
    print(f"📅 {date} - Fetching from Google News...")
    print(f"   URL: {url}\n")
    
    try:
        feed = feedparser.parse(url)
        
        if feed.entries:
            print(f"   ✅ Found {len(feed.entries)} articles:\n")
            
            for i, entry in enumerate(feed.entries[:5], 1):
                title = entry.get('title', 'No title')
                link = entry.get('link', 'No link')
                published = entry.get('published', 'No date')
                summary = entry.get('summary', '')[:150]
                
                print(f"   [{i}] TITLE: {title}")
                print(f"       DATE: {published}")
                print(f"       LINK: {link[:70]}...")
                if summary:
                    print(f"       SUMMARY: {summary}...")
                print()
            
            if len(feed.entries) > 5:
                print(f"   ... and {len(feed.entries) - 5} more articles\n")
        else:
            print(f"   ⚠️ No articles found\n")
    
    except Exception as e:
        print(f"   ❌ Error fetching news: {e}\n")

print(f"{'='*70}\n")
print("📊 This is what the app fetches for news sentiment analysis.")
print("   Each article title + summary is sent to FinBERT for sentiment scoring.")
print(f"{'='*70}\n")
