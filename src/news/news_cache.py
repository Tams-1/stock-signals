#!/usr/bin/env python3
"""
News cache management - reduces API calls by caching sentiment scores.

Strategy:
- Cache news sentiment for up to 6 hours
- Only fetch fresh news for top movers (high-confidence signals)
- Reuse cached sentiment for consolidating stocks
- Budget: ~150 credits/day (50 headroom from 200 limit)
"""

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Optional, List

logger = logging.getLogger(__name__)


class NewsCache:
    """Manage news sentiment cache with TTL."""
    
    def __init__(self, cache_file: str = "news_sentiment_cache.json", ttl_hours: int = 6):
        self.cache_file = Path(cache_file)
        self.ttl = timedelta(hours=ttl_hours)
        self.cache = self._load_cache()
    
    def _load_cache(self) -> Dict:
        """Load cache from disk."""
        if self.cache_file.exists():
            try:
                with open(self.cache_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Failed to load cache: {e}")
                return {}
        return {}
    
    def _save_cache(self):
        """Save cache to disk."""
        try:
            with open(self.cache_file, 'w') as f:
                json.dump(self.cache, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save cache: {e}")
    
    def is_fresh(self, ticker: str) -> bool:
        """Check if cached sentiment is still fresh (within TTL)."""
        if ticker not in self.cache:
            return False
        
        try:
            cached_time = datetime.fromisoformat(self.cache[ticker]['timestamp'])
            age = datetime.now() - cached_time
            is_fresh = age < self.ttl
            
            if not is_fresh:
                logger.debug(f"{ticker} cache expired (age: {age})")
            
            return is_fresh
        except Exception as e:
            logger.warning(f"Error checking cache for {ticker}: {e}")
            return False
    
    def get(self, ticker: str) -> Optional[float]:
        """Get cached sentiment if fresh, otherwise None."""
        if self.is_fresh(ticker):
            sentiment = self.cache[ticker].get('sentiment', 0.0)
            logger.debug(f"Cache HIT: {ticker} (sentiment: {sentiment:+.2f})")
            return sentiment
        return None
    
    def set(self, ticker: str, sentiment: float, source: str = "newsdata_io"):
        """Cache sentiment score with timestamp."""
        self.cache[ticker] = {
            'sentiment': sentiment,
            'timestamp': datetime.now().isoformat(),
            'source': source
        }
        self._save_cache()
        logger.info(f"Cached {ticker}: {sentiment:+.2f} from {source}")
    
    def get_cache_age(self, ticker: str) -> Optional[timedelta]:
        """Get age of cached item."""
        if ticker not in self.cache:
            return None
        
        try:
            cached_time = datetime.fromisoformat(self.cache[ticker]['timestamp'])
            return datetime.now() - cached_time
        except:
            return None
    
    def prune_expired(self):
        """Remove expired entries from cache."""
        expired = [k for k in self.cache if not self.is_fresh(k)]
        for ticker in expired:
            del self.cache[ticker]
        
        if expired:
            self._save_cache()
            logger.info(f"Pruned {len(expired)} expired cache entries")
    
    def stats(self) -> Dict:
        """Get cache statistics."""
        self.prune_expired()
        
        fresh = sum(1 for k in self.cache if self.is_fresh(k))
        expired = len(self.cache) - fresh
        
        return {
            'total_entries': len(self.cache),
            'fresh': fresh,
            'expired': expired,
            'cache_file': str(self.cache_file)
        }
