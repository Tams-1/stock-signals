#!/usr/bin/env python3
"""
Test BrAPI batch fetching with smaller batches and delays
"""

import sys
sys.path.insert(0, '/home/ulluboz/.openclaw/workspace/stock-signals')

from src.data.brapi_client import BrAPIClient
import json
from pathlib import Path
import time

# Load tickers
with open('/home/ulluboz/.openclaw/workspace/stock-signals/data/validated_tickers.json') as f:
    data = json.load(f)
tickers = data['all_tickers']

print(f"Testing BrAPI with {len(tickers)} tickers...")

client = BrAPIClient(api_key="1PinDyFUxXXBdvkdGN9Bi2")

# Fetch in smaller batches with delays
all_quotes = {}
batch_size = 5  # Smaller batches
delay = 0.5  # Delay between batches

for i in range(0, len(tickers), batch_size):
    batch = tickers[i:i+batch_size]
    
    # Retry logic
    for attempt in range(3):
        try:
            quotes = client.get_quotes(batch, use_cache=False)
            all_quotes.update(quotes)
            print(f"Batch {i//batch_size + 1}: {len(quotes)}/{len(batch)} quotes ✓")
            break
        except Exception as e:
            if attempt < 2:
                print(f"Batch {i//batch_size + 1}: Retry {attempt+1}...")
                time.sleep(1)
            else:
                print(f"Batch {i//batch_size + 1}: Failed - {e}")
    
    time.sleep(delay)

print(f"\nTotal: {len(all_quotes)} quotes fetched")

# Save quotes
with open('/home/ulluboz/.openclaw/workspace/stock-signals/data/quotes_cache.json', 'w') as f:
    json.dump(all_quotes, f, indent=2)
print("Saved to data/quotes_cache.json")
