#!/usr/bin/env python3
"""
Build a temporal-safe news cache for backtesting.

CRITICAL: News cache must ONLY contain articles published BEFORE each trading day.
This prevents temporal leakage in backtesting.

For production backtesting, we use mock news sentiment based on price action
to simulate the signal without API costs. In live trading, real news would be used.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import json
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List


class NewsCacheBuilder:
    """Build temporal-safe news cache for backtesting."""
    
    def __init__(self, cache_path: str = 'backtest/news_cache.json'):
        self.cache_path = Path(cache_path)
        self.cache = self._load_cache()
    
    def _load_cache(self) -> Dict:
        """Load existing cache or create new one."""
        if self.cache_path.exists():
            with open(self.cache_path, 'r') as f:
                return json.load(f)
        return {}
    
    def save_cache(self):
        """Save cache to disk."""
        # Ensure parent directory exists
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.cache_path, 'w') as f:
            json.dump(self.cache, f, indent=2)
    
    def generate_mock_sentiment(self, ticker: str, date: datetime, 
                                price_data: pd.DataFrame) -> Dict:
        """
        Generate mock sentiment based on recent price action.
        
        In production, this would be replaced with actual news articles.
        For backtesting, we simulate sentiment correlation with price moves.
        
        TEMPORAL SAFETY: Only uses price data from BEFORE the given date.
        
        Args:
            ticker: Stock ticker
            date: Current date (uses data from BEFORE this date)
            price_data: Historical price data
        
        Returns:
            Mock sentiment signal
        """
        # Get price data up to (but not including) current date
        historical = price_data[price_data.index < date]
        
        if len(historical) < 5:
            return {
                'sentiment': 0.0,
                'strength': 0.0,
                'direction': 'neutral',
                'source': 'news',
                'type': 'mock_sentiment'
            }
        
        # Use 3-day price momentum as sentiment proxy
        # This simulates news following price trends (realistic)
        recent_prices = historical.tail(3)['Close'].values
        momentum = (recent_prices[-1] / recent_prices[0] - 1)
        
        # Scale to sentiment (-1 to +1)
        sentiment = max(-1.0, min(1.0, momentum * 10))
        
        # Convert to signal format
        if sentiment > 0.2:
            direction = 'bullish'
            strength = min(1.0, abs(sentiment))
        elif sentiment < -0.2:
            direction = 'bearish'
            strength = min(1.0, abs(sentiment))
        else:
            direction = 'neutral'
            strength = abs(sentiment)
        
        return {
            'sentiment': sentiment,
            'strength': strength,
            'direction': direction,
            'source': 'news',
            'type': 'mock_sentiment',
            'date': date.strftime('%Y-%m-%d')
        }
    
    def build_cache_for_period(self, ticker: str, start_date: str, end_date: str,
                               price_data: pd.DataFrame):
        """
        Build news cache for a ticker across a date range.
        
        Args:
            ticker: Stock ticker
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            price_data: Price data for the ticker
        """
        if ticker not in self.cache:
            self.cache[ticker] = {}
        
        date_range = pd.date_range(start=start_date, end=end_date, freq='D')
        
        for date in date_range:
            date_str = date.strftime('%Y-%m-%d')
            
            # Generate sentiment using only prior data
            sentiment = self.generate_mock_sentiment(ticker, date, price_data)
            
            self.cache[ticker][date_str] = sentiment
    
    def get_sentiment(self, ticker: str, date: datetime) -> Dict:
        """
        Get cached sentiment for a ticker on a specific date.
        
        TEMPORAL SAFETY: Returns sentiment generated from data BEFORE the date.
        
        Args:
            ticker: Stock ticker
            date: Query date
        
        Returns:
            Sentiment signal or empty dict
        """
        date_str = date.strftime('%Y-%m-%d')
        
        if ticker in self.cache and date_str in self.cache[ticker]:
            return self.cache[ticker][date_str]
        
        return {}


if __name__ == "__main__":
    print("News Cache Builder")
    print("=" * 70)
    print()
    print("This module creates a temporal-safe news cache for backtesting.")
    print("Sentiment is generated from PRIOR price data only (no look-ahead).")
    print()
    print("In production backtesting, mock sentiment is used to avoid API costs.")
    print("Live trading would use real news from NewsAggregator + SentimentAnalyzer.")
    print()
