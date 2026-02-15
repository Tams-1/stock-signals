#!/usr/bin/env python3
"""
NewsData.io API client for real-time stock market news sentiment.

Features:
- Fetches market news for Brazilian stocks (IBOV tickers)
- Built-in sentiment analysis (positive/negative/neutral)
- Rate limiting and caching
- Fallback to neutral sentiment on errors

API Docs: https://newsdata.io/blog/market-news-endpoint/
"""

import requests
import logging
import time
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from functools import lru_cache


logger = logging.getLogger(__name__)


class NewsDataClient:
    """Client for NewsData.io Market News API."""
    
    BASE_URL = "https://newsdata.io/api/1/market"
    
    # Sentiment mapping
    SENTIMENT_MAP = {
        'positive': 1.0,
        'neutral': 0.0,
        'negative': -1.0
    }
    
    def __init__(self, api_key: str, cache_ttl: int = 3600):
        """
        Initialize NewsData.io client.
        
        Args:
            api_key: NewsData.io API key
            cache_ttl: Cache time-to-live in seconds (default: 1 hour)
        """
        self.api_key = api_key
        self.cache_ttl = cache_ttl
        self.session = requests.Session()
        self.last_request_time = 0
        self.min_request_interval = 1.0  # Minimum 1 second between requests
        
        logger.info("NewsDataClient initialized")
    
    def _rate_limit(self):
        """Enforce rate limiting between API requests."""
        elapsed = time.time() - self.last_request_time
        if elapsed < self.min_request_interval:
            time.sleep(self.min_request_interval - elapsed)
        self.last_request_time = time.time()
    
    def _ticker_to_query(self, ticker: str) -> str:
        """
        Convert Brazilian ticker to company name for query.
        
        Examples:
            PETR4.SA -> Petrobras
            VALE3.SA -> Vale
            ITUB4.SA -> Itaú
        
        Args:
            ticker: Stock ticker (e.g., PETR4.SA)
        
        Returns:
            Company name or ticker for query
        """
        # Map of common Brazilian stocks to company names
        ticker_map = {
            'PETR4.SA': 'Petrobras',
            'PETR3.SA': 'Petrobras',
            'VALE3.SA': 'Vale',
            'ITUB4.SA': 'Itaú',
            'BBDC4.SA': 'Bradesco',
            'BBAS3.SA': 'Banco do Brasil',
            'ABEV3.SA': 'Ambev',
            'B3SA3.SA': 'B3',
            'SUZB3.SA': 'Suzano',
            'RENT3.SA': 'Localiza',
            'WEGE3.SA': 'WEG',
            'MGLU3.SA': 'Magazine Luiza',
            'PCAR3.SA': 'Pão de Açúcar',
            'LREN3.SA': 'Lojas Renner',
            'RAIZ4.SA': 'Raízen',
            'GGBR4.SA': 'Gerdau',
            'ASAI3.SA': 'Assaí',
            'JBSS3.SA': 'JBS',
            'RDOR3.SA': 'Rede D\'Or',
        }
        
        return ticker_map.get(ticker, ticker.replace('.SA', ''))
    
    def _fetch_news(self, query: str) -> Dict:
        """
        Fetch news from NewsData.io API.
        
        Args:
            query: Search query (company name or ticker)
        
        Returns:
            API response dict
        
        Raises:
            requests.RequestException: On API errors
        """
        self._rate_limit()
        
        params = {
            'apikey': self.api_key,
            'q': query,
            'language': 'pt',  # Brazilian Portuguese
            'country': 'br'  # Brazil
        }
        
        logger.debug(f"Fetching news for '{query}'")
        
        response = self.session.get(self.BASE_URL, params=params, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        
        if data.get('status') != 'success':
            logger.warning(f"API returned non-success status: {data.get('status')}")
        
        return data
    
    def _parse_sentiment(self, articles: List[Dict]) -> float:
        """
        Parse sentiment from articles.
        
        Args:
            articles: List of article dicts from API
        
        Returns:
            Aggregated sentiment score (-1 to +1)
        """
        if not articles:
            logger.debug("No articles found, returning neutral sentiment")
            return 0.0
        
        sentiments = []
        for article in articles:
            raw_sentiment = article.get('sentiment', 'neutral')
            if raw_sentiment:
                sentiment_score = self.SENTIMENT_MAP.get(raw_sentiment.lower(), 0.0)
                sentiments.append(sentiment_score)
        
        if not sentiments:
            return 0.0
        
        # Average sentiment
        avg_sentiment = sum(sentiments) / len(sentiments)
        
        logger.debug(f"Parsed {len(sentiments)} articles: avg_sentiment={avg_sentiment:.2f}")
        
        return avg_sentiment
    
    @lru_cache(maxsize=128)
    def get_sentiment(self, ticker: str, date: str) -> float:
        """
        Get sentiment score for a ticker on a given date.
        
        This method is cached to avoid redundant API calls.
        
        Note: Free tier fetches last 48h of news (no timeframe parameter).
        
        Args:
            ticker: Stock ticker (e.g., PETR4.SA)
            date: Date string (YYYY-MM-DD)
        
        Returns:
            Sentiment score (-1.0 to +1.0)
            - Positive: bullish sentiment
            - Negative: bearish sentiment
            - Zero: neutral or no news
        """
        query = self._ticker_to_query(ticker)
        
        try:
            data = self._fetch_news(query)
            
            articles = data.get('results', [])
            total_results = data.get('totalResults', 0)
            
            if total_results == 0:
                logger.info(f"No news found for {ticker} ('{query}') on {date}")
                return 0.0
            
            sentiment = self._parse_sentiment(articles)
            
            logger.info(f"{ticker} ('{query}') on {date}: {total_results} articles, sentiment={sentiment:.2f}")
            
            return sentiment
        
        except requests.RequestException as e:
            logger.error(f"Failed to fetch news for {ticker}: {e}")
            return 0.0  # Fallback to neutral on errors
        
        except Exception as e:
            logger.error(f"Unexpected error for {ticker}: {e}")
            return 0.0
    
    def get_sentiment_batch(self, tickers: List[str], date: str) -> Dict[str, float]:
        """
        Get sentiment scores for multiple tickers.
        
        Args:
            tickers: List of stock tickers
            date: Date string (YYYY-MM-DD)
        
        Returns:
            Dict mapping ticker to sentiment score
        """
        results = {}
        
        for ticker in tickers:
            results[ticker] = self.get_sentiment(ticker, date)
            time.sleep(0.1)  # Small delay between tickers
        
        return results
    
    def clear_cache(self):
        """Clear the sentiment cache."""
        self.get_sentiment.cache_clear()
        logger.info("Sentiment cache cleared")


# Singleton instance (will be initialized with API key later)
_client: Optional[NewsDataClient] = None


def initialize_client(api_key: str):
    """Initialize the global NewsDataClient instance."""
    global _client
    _client = NewsDataClient(api_key)
    logger.info("Global NewsDataClient initialized")


def get_client() -> NewsDataClient:
    """Get the global NewsDataClient instance."""
    if _client is None:
        raise RuntimeError("NewsDataClient not initialized. Call initialize_client() first.")
    return _client
