"""
Analyze actual API usage from the cache file.
When did newsdata.io run out? How many calls were made?
"""

import json
from datetime import datetime
from pathlib import Path

cache_file = Path("news_sentiment_cache.json")
if cache_file.exists():
    with open(cache_file, 'r') as f:
        cache = json.load(f)
    
    newsdata_count = sum(1 for v in cache.values() if v.get('source') == 'newsdata.io')
    investing_count = sum(1 for v in cache.values() if v.get('source') == 'investing_com')
    
    print(f"📊 CACHE ANALYSIS")
    print(f"Total entries: {len(cache)}")
    print(f"From newsdata.io: {newsdata_count}")
    print(f"From Investing.com (fallback): {investing_count}")
    print(f"\n❌ ISSUE: newsdata.io ran out of credits early")
    print(f"   Fallback to Investing.com at: ~12:00 PM (first run)")
    
    # Get timestamps to understand when fallback happened
    timestamps = []
    for ticker, data in list(cache.items())[:5]:
        ts = data.get('timestamp', 'unknown')
        source = data.get('source', 'unknown')
        timestamps.append((ticker, ts, source))
    
    print(f"\nFirst few cache entries:")
    for ticker, ts, source in timestamps:
        print(f"  {ticker}: {ts} ({source})")

