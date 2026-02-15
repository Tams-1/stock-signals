"""Unit tests for News Aggregator module."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
import sqlite3
from datetime import datetime, timedelta
import tempfile
import os

from src.news.news_aggregator import NewsAggregator


class TestNewsAggregator:
    """Test news aggregation functionality."""
    
    @pytest.fixture
    def temp_db(self):
        """Create temporary database for testing."""
        fd, path = tempfile.mkstemp(suffix='.db')
        os.close(fd)
        yield path
        if os.path.exists(path):
            os.unlink(path)
    
    @pytest.fixture
    def aggregator(self, temp_db):
        """Create NewsAggregator instance with temp database."""
        return NewsAggregator(api_key='demo', db_path=temp_db)
    
    def test_aggregator_initialization(self, aggregator):
        """Test that aggregator initializes correctly."""
        assert aggregator.api_key == 'demo'
        assert aggregator.base_url == "https://newsapi.org/v2/everything"
        assert aggregator.db_path is not None
    
    def test_database_initialization(self, temp_db):
        """Test that database tables are created correctly."""
        agg = NewsAggregator(api_key='demo', db_path=temp_db)
        
        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()
        
        # Check if tables exist
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]
        
        assert 'news_articles' in tables
        assert 'sentiment_velocity' in tables
        conn.close()
    
    def test_content_hash_generation(self, aggregator):
        """Test content hashing for deduplication."""
        title1 = "Stock rises 5%"
        desc1 = "Company reported strong earnings"
        
        title2 = "Stock rises 5%"
        desc2 = "Company reported strong earnings"
        
        hash1 = aggregator._hash_content(title1, desc1)
        hash2 = aggregator._hash_content(title2, desc2)
        
        # Same content should produce same hash
        assert hash1 == hash2
        
        # Different content should produce different hash
        hash3 = aggregator._hash_content("Different title", "Different description")
        assert hash1 != hash3
    
    def test_content_hash_case_insensitive(self, aggregator):
        """Test that content hashing is case-insensitive."""
        hash1 = aggregator._hash_content("Stock Rises", "Company earnings")
        hash2 = aggregator._hash_content("stock rises", "company earnings")
        
        assert hash1 == hash2
    
    def test_store_and_retrieve_news(self, aggregator):
        """Test storing and retrieving news articles."""
        articles = [
            {
                'title': 'PETR4 Rises 3%',
                'description': 'Petrobras reports strong quarterly results',
                'content': 'Full content here',
                'url': 'https://example.com/news1',
                'source': {'name': 'Reuters'},
                'publishedAt': datetime.now().isoformat()
            },
            {
                'title': 'VALE3 Drops 2%',
                'description': 'Vale faces supply chain challenges',
                'content': 'More content',
                'url': 'https://example.com/news2',
                'source': {'name': 'Bloomberg'},
                'publishedAt': (datetime.now() - timedelta(hours=1)).isoformat()
            }
        ]
        
        stored, duplicates = aggregator.deduplicate_and_store('PETR4', articles)
        
        # Should store both articles
        assert stored == 2
        assert duplicates == 0
        
        # Try to store again - should detect duplicates
        stored2, duplicates2 = aggregator.deduplicate_and_store('PETR4', articles)
        assert stored2 == 0
        assert duplicates2 == 2
    
    def test_get_recent_news(self, aggregator):
        """Test retrieving recent news articles."""
        # Store some articles
        articles = []
        for i in range(5):
            articles.append({
                'title': f'News {i}',
                'description': f'Description {i}',
                'content': f'Content {i}',
                'url': f'https://example.com/news{i}',
                'source': {'name': 'TestSource'},
                'publishedAt': (datetime.now() - timedelta(hours=i)).isoformat()
            })
        
        aggregator.deduplicate_and_store('PETR4', articles)
        
        # Retrieve recent news
        recent = aggregator.get_recent_news('PETR4', hours=24, limit=3)
        
        assert len(recent) == 3
        assert recent[0]['title'] == 'News 0'  # Most recent
    
    def test_update_article_sentiment(self, aggregator):
        """Test updating article sentiment score."""
        articles = [{
            'title': 'Good news',
            'description': 'Positive development',
            'content': '',
            'url': 'https://example.com/news',
            'source': {'name': 'Source'},
            'publishedAt': datetime.now().isoformat()
        }]
        
        aggregator.deduplicate_and_store('PETR4', articles)
        
        # Get article ID
        recent = aggregator.get_recent_news('PETR4', hours=24, limit=1)
        article_id = recent[0]['id']
        
        # Update sentiment
        aggregator.update_article_sentiment(article_id, 0.75, 'bullish')
        
        # Verify update
        updated = aggregator.get_recent_news('PETR4', hours=24, limit=1)
        assert updated[0]['polarity'] == 0.75
        assert updated[0]['sentiment'] == 'bullish'
    
    def test_calculate_sentiment_velocity(self, aggregator):
        """Test sentiment velocity calculation."""
        # Store articles across time windows
        for hours_ago in [0.5, 2, 6, 24, 48]:
            aggregator.deduplicate_and_store('PETR4', [{
                'title': 'News',
                'description': 'Positive news',
                'content': '',
                'url': f'https://example.com/news_{hours_ago}',
                'source': {'name': 'Source'},
                'publishedAt': (datetime.now() - timedelta(hours=hours_ago)).isoformat()
            }])
            
            # Set sentiment
            recent = aggregator.get_recent_news('PETR4', hours=72)
            if recent:
                aggregator.update_article_sentiment(recent[0]['id'], 0.8, 'bullish')
        
        velocity = aggregator.calculate_sentiment_velocity('PETR4')
        
        assert '1h' in velocity
        assert '4h' in velocity
        assert '1d' in velocity
        assert '7d' in velocity
        
        assert velocity['1h']['news_count'] >= 0
        assert -1.0 <= velocity['1h']['avg_sentiment'] <= 1.0
    
    def test_fetch_news_with_demo_key(self, aggregator):
        """Test that demo key returns no news."""
        news = aggregator.fetch_news('PETR4', days=7)
        
        assert news == []
    
    def test_get_news_for_analysis(self, aggregator):
        """Test retrieving news ready for sentiment analysis."""
        articles = [{
            'title': 'Important news',
            'description': 'This is important',
            'content': 'Full article content',
            'url': 'https://example.com/news',
            'source': {'name': 'Source'},
            'publishedAt': datetime.now().isoformat()
        }]
        
        aggregator.deduplicate_and_store('PETR4', articles)
        
        news = aggregator.get_news_for_analysis('PETR4', hours=24)
        
        assert len(news) == 1
        assert news[0]['title'] == 'Important news'
        assert news[0]['content'] == 'Full article content'
    
    def test_get_top_stocks_by_sentiment(self, aggregator):
        """Test getting top stocks by sentiment activity."""
        # Add news for multiple stocks
        for ticker in ['PETR4', 'VALE3', 'BBDC4']:
            for i in range(3):
                aggregator.deduplicate_and_store(ticker, [{
                    'title': f'News {ticker}',
                    'description': 'News description',
                    'content': '',
                    'url': f'https://example.com/{ticker}_{i}',
                    'source': {'name': 'Source'},
                    'publishedAt': datetime.now().isoformat()
                }])
                
                # Set sentiment
                recent = aggregator.get_recent_news(ticker, hours=24)
                if recent:
                    aggregator.update_article_sentiment(recent[0]['id'], 0.5, 'neutral')
        
        top_stocks = aggregator.get_top_stocks_by_sentiment(limit=3, hours=24)
        
        assert len(top_stocks) <= 3
        assert len(top_stocks) > 0
    
    def test_cleanup_old_news(self, aggregator):
        """Test cleanup of old news articles."""
        # Add old article
        old_date = (datetime.now() - timedelta(days=90)).isoformat()
        
        conn = sqlite3.connect(aggregator.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO news_articles 
            (ticker, source, title, url, published_at, fetched_at, content_hash)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', ('OLD', 'Source', 'Old news', 'https://old.com', old_date, old_date, 'hash123'))
        
        conn.commit()
        conn.close()
        
        # Verify old article exists
        old_news = aggregator.get_recent_news('OLD', hours=365*24)
        initial_count = len(old_news)
        
        # Clean up
        aggregator.cleanup_old_news(days=60)
        
        # Verify cleanup
        old_news_after = aggregator.get_recent_news('OLD', hours=365*24)
        assert len(old_news_after) < initial_count


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
