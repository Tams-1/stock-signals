"""
News Aggregator: Fetch, deduplicate, and store financial news for Brazilian stocks.
- NewsAPI integration for Brazilian market
- Deduplication by title and content hash
- Time-series storage with exact timestamps
- Support for multiple news sources
"""

import requests
import json
import sqlite3
import hashlib
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
import logging

logger = logging.getLogger(__name__)


class NewsAggregator:
    """Fetch and manage financial news for stocks."""
    
    def __init__(self, api_key: str = 'demo', db_path: str = 'stock_signals.db'):
        """
        Initialize News Aggregator.
        
        Args:
            api_key: NewsAPI key (get free key at https://newsapi.org/)
            db_path: Path to SQLite database for news storage
        """
        self.api_key = api_key
        self.db_path = db_path
        self.base_url = "https://newsapi.org/v2/everything"
        self._init_database()
        
    def _init_database(self):
        """Initialize SQLite database for news storage."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Table for news articles
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS news_articles (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ticker TEXT NOT NULL,
                    source TEXT NOT NULL,
                    title TEXT NOT NULL,
                    url TEXT UNIQUE NOT NULL,
                    description TEXT,
                    content TEXT,
                    polarity REAL,
                    sentiment TEXT,
                    published_at TEXT NOT NULL,
                    fetched_at TEXT NOT NULL,
                    content_hash TEXT UNIQUE,
                    UNIQUE(ticker, content_hash)
                )
            ''')
            
            # Table for sentiment velocity metrics
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS sentiment_velocity (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ticker TEXT NOT NULL,
                    window TEXT NOT NULL,
                    news_count INTEGER,
                    avg_sentiment REAL,
                    max_sentiment REAL,
                    min_sentiment REAL,
                    calculated_at TEXT NOT NULL,
                    UNIQUE(ticker, window, calculated_at)
                )
            ''')
            
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Database initialization error: {e}")
    
    def _hash_content(self, title: str, description: str) -> str:
        """Generate content hash for deduplication."""
        content_str = f"{title}:{description}".lower().strip()
        return hashlib.md5(content_str.encode()).hexdigest()
    
    def fetch_news(self, ticker: str, days: int = 7, language: str = 'pt') -> List[Dict]:
        """
        Fetch news for a ticker from NewsAPI.
        
        Args:
            ticker: Stock ticker (e.g., 'PETR4', 'VALE3')
            days: Number of days to look back (max 30 for NewsAPI free tier)
            language: Language code ('pt' for Portuguese, 'en' for English)
        
        Returns:
            List of news articles with metadata
        """
        if self.api_key == 'demo':
            logger.warning("Using demo API key - no actual news will be fetched")
            return []
        
        try:
            # Build search query for Brazilian stock
            search_query = f"{ticker.replace('4', '').replace('3', '').replace('5', '')} stock Brazil"
            from_date = (datetime.now() - timedelta(days=days)).isoformat()
            
            params = {
                'q': search_query,
                'sortBy': 'publishedAt',
                'language': language,
                'from': from_date,
                'apiKey': self.api_key,
                'pageSize': 100
            }
            
            response = requests.get(self.base_url, params=params, timeout=10)
            response.raise_for_status()
            
            articles = response.json().get('articles', [])
            logger.info(f"Fetched {len(articles)} articles for {ticker}")
            return articles
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching news for {ticker}: {e}")
            return []
    
    def deduplicate_and_store(self, ticker: str, articles: List[Dict]) -> Tuple[int, int]:
        """
        Store articles, deduplicating by title and content hash.
        
        Args:
            ticker: Stock ticker
            articles: List of articles from NewsAPI
        
        Returns:
            Tuple of (stored_count, duplicate_count)
        """
        stored = 0
        duplicates = 0
        
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            for article in articles:
                title = article.get('title', '')
                description = article.get('description', '') or ''
                content = article.get('content', '') or ''
                url = article.get('url', '')
                
                if not url or not title:
                    continue
                
                content_hash = self._hash_content(title, description)
                published_at = article.get('publishedAt', datetime.now().isoformat())
                source = article.get('source', {}).get('name', 'Unknown')
                
                try:
                    cursor.execute('''
                        INSERT INTO news_articles 
                        (ticker, source, title, url, description, content, 
                         published_at, fetched_at, content_hash)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        ticker, source, title, url, description, content,
                        published_at, datetime.now().isoformat(), content_hash
                    ))
                    stored += 1
                    
                except sqlite3.IntegrityError:
                    duplicates += 1
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"Error storing news for {ticker}: {e}")
        
        return stored, duplicates
    
    def get_recent_news(self, ticker: str, hours: int = 24, limit: int = 10) -> List[Dict]:
        """
        Retrieve recent news for a ticker.
        
        Args:
            ticker: Stock ticker
            hours: Hours to look back
            limit: Maximum articles to return
        
        Returns:
            List of recent news articles
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cutoff_time = (datetime.now() - timedelta(hours=hours)).isoformat()
            
            cursor.execute('''
                SELECT id, title, url, source, description, published_at, polarity, sentiment
                FROM news_articles
                WHERE ticker = ? AND published_at > ?
                ORDER BY published_at DESC
                LIMIT ?
            ''', (ticker, cutoff_time, limit))
            
            results = cursor.fetchall()
            conn.close()
            
            return [
                {
                    'id': r[0],
                    'title': r[1],
                    'url': r[2],
                    'source': r[3],
                    'description': r[4],
                    'published_at': r[5],
                    'polarity': r[6],
                    'sentiment': r[7]
                }
                for r in results
            ]
            
        except Exception as e:
            logger.error(f"Error retrieving news for {ticker}: {e}")
            return []
    
    def update_article_sentiment(self, article_id: int, polarity: float, sentiment: str):
        """
        Update article with sentiment score.
        
        Args:
            article_id: Article ID in database
            polarity: Sentiment polarity (-1.0 to 1.0)
            sentiment: Sentiment label ('bullish', 'bearish', 'neutral')
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                UPDATE news_articles
                SET polarity = ?, sentiment = ?
                WHERE id = ?
            ''', (polarity, sentiment, article_id))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"Error updating article sentiment: {e}")
    
    def get_news_for_analysis(self, ticker: str, hours: int = 24) -> List[Dict]:
        """
        Get all news for sentiment analysis.
        
        Args:
            ticker: Stock ticker
            hours: Hours to look back
        
        Returns:
            List of articles with full content for analysis
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cutoff_time = (datetime.now() - timedelta(hours=hours)).isoformat()
            
            cursor.execute('''
                SELECT id, title, description, content, published_at
                FROM news_articles
                WHERE ticker = ? AND published_at > ?
                ORDER BY published_at DESC
            ''', (ticker, cutoff_time))
            
            results = cursor.fetchall()
            conn.close()
            
            return [
                {
                    'id': r[0],
                    'title': r[1],
                    'description': r[2],
                    'content': r[3],
                    'published_at': r[4]
                }
                for r in results
            ]
            
        except Exception as e:
            logger.error(f"Error retrieving news for analysis: {e}")
            return []
    
    def calculate_sentiment_velocity(self, ticker: str) -> Dict[str, Dict]:
        """
        Calculate news count and average sentiment in various time windows.
        
        Args:
            ticker: Stock ticker
        
        Returns:
            Dictionary with velocity metrics for each window
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            windows = {
                '1h': 1,
                '4h': 4,
                '1d': 24,
                '7d': 24 * 7
            }
            
            velocity = {}
            now = datetime.now().isoformat()
            
            for window_name, hours in windows.items():
                cutoff_time = (datetime.now() - timedelta(hours=hours)).isoformat()
                
                cursor.execute('''
                    SELECT COUNT(*), AVG(polarity), MAX(polarity), MIN(polarity)
                    FROM news_articles
                    WHERE ticker = ? AND published_at > ? AND polarity IS NOT NULL
                ''', (ticker, cutoff_time))
                
                result = cursor.fetchone()
                count, avg_sentiment, max_sentiment, min_sentiment = result
                
                velocity[window_name] = {
                    'news_count': count or 0,
                    'avg_sentiment': round(avg_sentiment or 0, 3),
                    'max_sentiment': round(max_sentiment or 0, 3),
                    'min_sentiment': round(min_sentiment or 0, 3)
                }
                
                # Store in database
                try:
                    cursor.execute('''
                        INSERT OR REPLACE INTO sentiment_velocity
                        (ticker, window, news_count, avg_sentiment, max_sentiment, min_sentiment, calculated_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        ticker, window_name, count or 0, avg_sentiment or 0,
                        max_sentiment or 0, min_sentiment or 0, now
                    ))
                except:
                    pass
            
            conn.commit()
            conn.close()
            
            return velocity
            
        except Exception as e:
            logger.error(f"Error calculating sentiment velocity: {e}")
            return {}
    
    def get_top_stocks_by_sentiment(self, limit: int = 10, hours: int = 24) -> List[Tuple]:
        """
        Get stocks with highest sentiment activity.
        
        Args:
            limit: Number of stocks to return
            hours: Time window
        
        Returns:
            List of (ticker, avg_sentiment, news_count)
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cutoff_time = (datetime.now() - timedelta(hours=hours)).isoformat()
            
            cursor.execute('''
                SELECT ticker, AVG(polarity), COUNT(*) as count
                FROM news_articles
                WHERE published_at > ? AND polarity IS NOT NULL
                GROUP BY ticker
                ORDER BY ABS(AVG(polarity)) DESC, count DESC
                LIMIT ?
            ''', (cutoff_time, limit))
            
            results = cursor.fetchall()
            conn.close()
            
            return results
            
        except Exception as e:
            logger.error(f"Error retrieving top stocks: {e}")
            return []
    
    def cleanup_old_news(self, days: int = 60):
        """
        Clean up old news articles from database.
        
        Args:
            days: Delete articles older than this many days
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cutoff_date = (datetime.now() - timedelta(days=days)).isoformat()
            
            cursor.execute('''
                DELETE FROM news_articles
                WHERE published_at < ?
            ''', (cutoff_date,))
            
            deleted = cursor.rowcount
            conn.commit()
            conn.close()
            
            logger.info(f"Cleaned up {deleted} old news articles")
            
        except Exception as e:
            logger.error(f"Error cleaning up old news: {e}")
