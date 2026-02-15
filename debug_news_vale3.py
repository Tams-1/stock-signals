#!/usr/bin/env python3
"""
DEBUG: Show exactly how news component works on VALE3
- Fetch articles
- Score each article sentiment  
- Show final position sizing impact
"""

import sys
import os
sys.path.insert(0, '/home/ulluboz/.openclaw/workspace/stock-signals')

import requests
import json
from datetime import datetime, timedelta

print(f"\n{'='*70}")
print(f"🔍 NEWS COMPONENT DEBUG: VALE3")
print(f"{'='*70}\n")

# Use newsdata.io (Google News RSS is blocked with 503)
API_KEY = "pub_1757f48565d149cb8e2053f54b26e977"
ticker = "VALE3"

print(f"📰 [1] FETCHING ARTICLES")
print(f"   Source: newsdata.io API")
print(f"   Ticker: {ticker}")
print(f"   Country: Brazil (br)")
print(f"   Language: Portuguese (pt)")
print(f"   Period: Last 3 days\n")

articles_found = []

for days_ago in range(3):
    date = (datetime.now() - timedelta(days=days_ago)).strftime("%Y-%m-%d")
    
    # newsdata.io API endpoint with ticker (no category filter - too restrictive)
    url = f"https://newsdata.io/api/1/news?q={ticker}&country=br&language=pt&apikey={API_KEY}"
    
    try:
        print(f"   📅 {date}...", end=" ", flush=True)
        response = requests.get(url, timeout=5)
        
        if response.status_code == 200:
            data = response.json()
            articles = data.get('results', [])
            articles_found.extend(articles)
            print(f"✅ Found {len(articles)} articles")
        else:
            print(f"⚠️  Status {response.status_code}")
    except Exception as e:
        print(f"❌ Error: {e}")

print(f"\n   TOTAL: {len(articles_found)} articles\n")

if not articles_found:
    print(f"❌ No articles found. Showing how sentiment analysis would work:\n")
    print(f"{'='*70}")
    print(f"📊 [2] SENTIMENT ANALYSIS (SIMULATED)")
    print(f"{'='*70}\n")
    
    # Show mock articles with sentiment
    mock_articles = [
        {"title": "Vale3 sobe 2,5% com reforma tributária", "sentiment": 0.75, "type": "positive"},
        {"title": "Preço do minério de ferro cai 1,8%", "sentiment": -0.65, "type": "negative"},
        {"title": "Vale3 mantém dividendos estáveis em 2026", "sentiment": 0.45, "type": "positive"},
    ]
    
    for i, art in enumerate(mock_articles, 1):
        emoji = "😊" if art['sentiment'] > 0.1 else "😞" if art['sentiment'] < -0.1 else "😐"
        print(f"[{i}] {emoji} {art['title']}")
        print(f"    Sentiment Score: {art['sentiment']:+.2f} ({art['type']})\n")
    
    print(f"{'='*70}")
    print(f"💰 [3] POSITION SIZING IMPACT")
    print(f"{'='*70}\n")
    
    # Show how sentiment affects position
    base_confidence = 0.55  # Assume uptrend @ 55% confidence
    base_position = 0.40  # 40% position (0.50-0.60 confidence band)
    
    print(f"SCENARIO: VALE3 shows UPTREND @ {base_confidence:.0%} confidence")
    print(f"Base position size: {base_position:.0%}\n")
    
    print(f"Option A: If average sentiment is +0.60 (POSITIVE news)")
    news_boost = min(0.60 * 0.20, 0.20)  # Up to 20% boost
    final_pos_a = min(1.0, base_position + news_boost)
    print(f"  News boost: +{news_boost:.0%}")
    print(f"  Final position: {final_pos_a:.0%} ✅ (MORE aggressive)\n")
    
    print(f"Option B: If average sentiment is -0.50 (NEGATIVE news)")
    news_penalty = max(-0.50 * 0.15, -0.10)  # Up to 10% penalty
    final_pos_b = max(0.20, base_position + news_penalty)
    print(f"  News penalty: {news_penalty:.0%}")
    print(f"  Final position: {final_pos_b:.0%} (LESS aggressive)\n")
    
    print(f"Option C: If average sentiment is 0.0 (NEUTRAL news)")
    print(f"  News impact: No change")
    print(f"  Final position: {base_position:.0%} (UNCHANGED)\n")

else:
    print(f"{'='*70}")
    print(f"📊 [2] SENTIMENT ANALYSIS")
    print(f"{'='*70}\n")
    
    sentiments = []
    
    for i, article in enumerate(articles_found[:5], 1):
        title = article.get('title', 'No title')[:70]
        source = article.get('source_id', 'unknown')
        date = article.get('pubDate', 'N/A')[:10]
        
        # Simulate FinBERT sentiment (in real version, FinBERT would analyze title + content)
        text = f"{title} {article.get('description', '')}"
        
        # Simple mock sentiment (real: FinBERT)
        if any(word in text.lower() for word in ['sobe', 'ganha', 'lucro', 'forte']):
            sentiment = 0.65
        elif any(word in text.lower() for word in ['cai', 'perde', 'queda', 'fraco']):
            sentiment = -0.60
        else:
            sentiment = 0.0
        
        sentiments.append(sentiment)
        
        emoji = "😊" if sentiment > 0.1 else "😞" if sentiment < -0.1 else "😐"
        print(f"[{i}] {emoji} {title}...")
        print(f"    Date: {date} | Source: {source}")
        print(f"    Sentiment: {sentiment:+.2f}\n")
    
    if len(articles_found) > 5:
        print(f"   ... and {len(articles_found) - 5} more articles\n")
    
    avg_sentiment = sum(sentiments) / len(sentiments) if sentiments else 0.0
    
    print(f"{'='*70}")
    print(f"💰 [3] POSITION SIZING IMPACT")
    print(f"{'='*70}\n")
    
    print(f"Average sentiment from {len(sentiments)} articles: {avg_sentiment:+.2f}\n")
    
    # Show impact
    base_position = 0.40
    base_confidence = 0.55
    
    print(f"IF VALE3 shows UPTREND @ {base_confidence:.0%} confidence:")
    print(f"  Base position size: {base_position:.0%}\n")
    
    if avg_sentiment > 0.1:
        boost = min(avg_sentiment * 0.20, 0.20)
        final = min(1.0, base_position + boost)
        print(f"  News sentiment: POSITIVE ({avg_sentiment:+.2f})")
        print(f"  Position boost: +{boost:.0%}")
        print(f"  → FINAL POSITION: {final:.0%} ✅ (MORE aggressive due to positive news)\n")
    elif avg_sentiment < -0.1:
        penalty = max(avg_sentiment * 0.10, -0.10)
        final = max(0.20, base_position + penalty)
        print(f"  News sentiment: NEGATIVE ({avg_sentiment:+.2f})")
        print(f"  Position penalty: {penalty:.0%}")
        print(f"  → FINAL POSITION: {final:.0%} (LESS aggressive due to negative news)\n")
    else:
        print(f"  News sentiment: NEUTRAL ({avg_sentiment:+.2f})")
        print(f"  Position impact: None")
        print(f"  → FINAL POSITION: {base_position:.0%} (UNCHANGED)\n")

print(f"{'='*70}")
print(f"✅ This is how the news component affects BUY/SELL decisions:")
print(f"   1. Articles are fetched from news sources")
print(f"   2. Each article is scored by FinBERT (-1.0 to +1.0)")
print(f"   3. Average sentiment is calculated")
print(f"   4. Positive sentiment boosts position size (+10-20%)")
print(f"   5. Negative sentiment reduces position size (-10%)")
print(f"{'='*70}\n")
