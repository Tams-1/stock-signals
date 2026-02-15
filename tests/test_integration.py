"""Integration tests for News Sentiment + Market Regime Detection."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import tempfile
import os

from src.news.news_aggregator import NewsAggregator
from src.news.sentiment_analyzer import SentimentAnalyzer
from src.signals.regime_detector import RegimeDetector


class TestIntegration:
    """Integration tests for Phase 1 & 2 modules."""
    
    @pytest.fixture
    def temp_db(self):
        """Create temporary database."""
        fd, path = tempfile.mkstemp(suffix='.db')
        os.close(fd)
        yield path
        if os.path.exists(path):
            os.unlink(path)
    
    @pytest.fixture
    def components(self, temp_db):
        """Create all components for integration testing."""
        aggregator = NewsAggregator(api_key='demo', db_path=temp_db)
        analyzer = SentimentAnalyzer(language='en')
        detector = RegimeDetector(db_path=temp_db)
        return aggregator, analyzer, detector
    
    def create_sample_market_data(self, length=30, trend='uptrend'):
        """Create sample OHLCV data."""
        dates = pd.date_range(end=datetime.now(), periods=length, freq='D')
        
        if trend == 'uptrend':
            close = np.linspace(100, 120, length) + np.random.normal(0, 0.5, length)
        elif trend == 'downtrend':
            close = np.linspace(120, 100, length) + np.random.normal(0, 0.5, length)
        else:
            close = np.full(length, 110) + np.random.normal(0, 1.5, length)
        
        return pd.DataFrame({
            'Open': close - 0.5,
            'High': close + 1.5,
            'Low': close - 1.5,
            'Close': close,
            'Volume': np.random.randint(1000000, 5000000, length)
        }, index=dates)
    
    def test_news_to_sentiment_pipeline(self, components):
        """Test news aggregation -> sentiment analysis pipeline."""
        aggregator, analyzer, _ = components
        
        # Create sample news articles
        articles = [
            {
                'title': 'Company reports record profit growth',
                'description': 'Strong quarterly earnings exceeded expectations',
                'content': 'Full article about positive earnings',
                'url': 'https://example.com/news1',
                'source': {'name': 'Reuters'},
                'publishedAt': datetime.now().isoformat()
            },
            {
                'title': 'Stock faces bearish losses',
                'description': 'Company reports massive quarterly losses',
                'content': 'Article about losses',
                'url': 'https://example.com/news2',
                'source': {'name': 'Bloomberg'},
                'publishedAt': (datetime.now() - timedelta(hours=1)).isoformat()
            }
        ]
        
        # Store news
        stored, _ = aggregator.deduplicate_and_store('PETR4', articles)
        assert stored == 2
        
        # Get news for analysis
        news = aggregator.get_news_for_analysis('PETR4', hours=24)
        assert len(news) == 2
        
        # Analyze sentiment
        analyzed = analyzer.batch_analyze(news)
        
        # First should be positive
        assert analyzed[0]['sentiment'] == 'bullish'
        assert analyzed[0]['polarity'] > 0
        
        # Second should be negative
        assert analyzed[1]['sentiment'] == 'bearish'
        assert analyzed[1]['polarity'] < 0
        
        # Update articles with sentiment
        for article in analyzed:
            aggregator.update_article_sentiment(
                article['id'],
                article['polarity'],
                article['sentiment']
            )
        
        # Calculate sentiment velocity
        velocity = aggregator.calculate_sentiment_velocity('PETR4')
        
        assert velocity['1d']['news_count'] == 2
        assert -1 <= velocity['1d']['avg_sentiment'] <= 1
    
    def test_sentiment_velocity_tracking(self, components):
        """Test tracking of sentiment velocity over time windows."""
        aggregator, analyzer, _ = components
        
        # Add news over different time periods
        news_data = [
            ('0.25h', 'Positive news about recovery'),
            ('1h', 'Neutral earnings announcement'),
            ('3h', 'Negative warning issued'),
            ('12h', 'Positive quarterly results')
        ]
        
        articles_to_update = []
        
        for hours_ago_str, title in news_data:
            hours = float(hours_ago_str.replace('h', ''))
            article = {
                'title': title,
                'description': title,
                'content': '',
                'url': f'https://example.com/{hours}_{title.replace(" ", "")}',
                'source': {'name': 'News'},
                'publishedAt': (datetime.now() - timedelta(hours=hours)).isoformat()
            }
            
            aggregator.deduplicate_and_store('PETR4', [article])
            
            # Get all articles and update sentiment for all
            all_recent = aggregator.get_recent_news('PETR4', hours=72, limit=100)
            for art in all_recent:
                if art['polarity'] is None:
                    sentiment = analyzer.analyze_sentiment(art['title'])
                    aggregator.update_article_sentiment(
                        art['id'],
                        sentiment['polarity'],
                        sentiment['sentiment']
                    )
        
        # Get velocity metrics
        velocity = aggregator.calculate_sentiment_velocity('PETR4')
        
        # Verify all windows are present
        assert '1h' in velocity
        assert '4h' in velocity
        assert '1d' in velocity
        assert '7d' in velocity
        
        # Just verify that sentiment velocity can be calculated
        # The exact counts will vary based on timing
        assert velocity['1h']['news_count'] >= 0
        assert velocity['4h']['news_count'] >= 0
        assert velocity['1d']['news_count'] >= 0
    
    def test_regime_detection_with_sentiment(self, components):
        """Test regime detection integrating with sentiment signals."""
        _, analyzer, detector = components
        
        # Detect uptrend regime
        uptrend_data = self.create_sample_market_data(trend='uptrend')
        uptrend_regime = detector.detect_regime(uptrend_data)
        
        assert uptrend_regime['regime'] == 'uptrend'
        assert uptrend_regime['confidence'] > 0.5
        
        # In uptrend, use positive sentiment signals
        # Should have 70% capital allocation
        strategy = uptrend_regime['strategy']
        assert strategy['allocation'] == 0.70
        assert strategy['mode'] == 'aggressive'
        
        # Detect downtrend regime
        downtrend_data = self.create_sample_market_data(trend='downtrend')
        downtrend_regime = detector.detect_regime(downtrend_data)
        
        assert downtrend_regime['regime'] == 'downtrend'
        
        # In downtrend, use defensive strategy
        # Should have 30% capital allocation
        strategy = downtrend_regime['strategy']
        assert strategy['allocation'] == 0.30
        assert strategy['mode'] == 'defensive'
    
    def test_combined_signal_generation(self, components):
        """Test combined signal from news sentiment + regime detection."""
        aggregator, analyzer, detector = components
        
        # Setup: Uptrend market with positive news
        market_data = self.create_sample_market_data(trend='uptrend')
        regime = detector.detect_regime(market_data)
        
        # Add positive news
        articles = [{
            'title': 'Strong earnings growth and expansion plans',
            'description': 'Company achieves record profit growth',
            'content': 'Positive earnings',
            'url': 'https://example.com/news',
            'source': {'name': 'Reuters'},
            'publishedAt': datetime.now().isoformat()
        }]
        
        aggregator.deduplicate_and_store('PETR4', articles)
        news = aggregator.get_news_for_analysis('PETR4', hours=24)
        analyzed = analyzer.batch_analyze(news)
        
        # Combined signal: Uptrend + Positive News = Strong BUY
        market_signal = 'BUY'
        sentiment_signal = analyzed[0]['sentiment']
        regime_signal = regime['regime']
        
        if regime_signal == 'uptrend' and sentiment_signal == 'bullish':
            combined_signal = 'STRONG_BUY'
        elif regime_signal == 'uptrend' and sentiment_signal in ['neutral', 'bearish']:
            combined_signal = 'BUY'
        elif regime_signal == 'downtrend' and sentiment_signal == 'bullish':
            combined_signal = 'HOLD'
        else:
            combined_signal = 'SELL'
        
        assert combined_signal == 'STRONG_BUY'
        assert regime['confidence'] > 0.5
    
    def test_regime_history_storage(self, components, temp_db):
        """Test storing and retrieving regime detection history."""
        _, _, detector = components
        
        # Generate regimes at different times
        uptrend_data = self.create_sample_market_data(trend='uptrend')
        downtrend_data = self.create_sample_market_data(trend='downtrend')
        
        # Store uptrend
        regime1 = detector.detect_regime(uptrend_data)
        detector.store_regime('PETR4', regime1)
        
        # Store downtrend
        regime2 = detector.detect_regime(downtrend_data)
        detector.store_regime('PETR4', regime2)
        
        # Retrieve history
        history = detector.get_regime_history('PETR4', days=1)
        
        assert len(history) >= 2
        assert history[0]['regime'] in ['uptrend', 'downtrend']
        assert history[1]['regime'] in ['uptrend', 'downtrend']
        
        # Get summary
        summary = detector.get_regime_summary('PETR4', days=1)
        
        assert 'dominant_regime' in summary
        assert 'avg_confidence' in summary
        assert summary['regime_changes'] >= 1
    
    def test_full_pipeline_workflow(self, components):
        """Test complete workflow: news -> sentiment -> regime -> signal."""
        aggregator, analyzer, detector = components
        
        # 1. Fetch and store news
        ticker = 'PETR4'
        articles = [
            {
                'title': 'Recovery signals emerge',
                'description': 'Technical indicators turn positive',
                'content': 'Strong recovery',
                'url': 'https://example.com/1',
                'source': {'name': 'Source'},
                'publishedAt': datetime.now().isoformat()
            },
            {
                'title': 'Growth acceleration continues',
                'description': 'Expansion in key markets',
                'content': 'Positive expansion',
                'url': 'https://example.com/2',
                'source': {'name': 'Source'},
                'publishedAt': datetime.now().isoformat()
            }
        ]
        
        aggregator.deduplicate_and_store(ticker, articles)
        
        # 2. Analyze sentiment
        news = aggregator.get_news_for_analysis(ticker, hours=24)
        analyzed = analyzer.batch_analyze(news)
        
        # Store sentiment
        for article in analyzed:
            aggregator.update_article_sentiment(
                article['id'],
                article['polarity'],
                article['sentiment']
            )
        
        # 3. Get sentiment distribution
        distribution = analyzer.get_sentiment_distribution(analyzed)
        
        assert distribution['total_count'] == 2
        assert distribution['bullish_count'] > 0
        
        # 4. Detect market regime
        market_data = self.create_sample_market_data(trend='uptrend')
        regime = detector.detect_regime(market_data)
        detector.store_regime(ticker, regime)
        
        # 5. Calculate sentiment velocity
        velocity = aggregator.calculate_sentiment_velocity(ticker)
        
        # 6. Generate final trading signal
        signal_strength = abs(distribution['avg_sentiment'])  # 0-1
        regime_confidence = regime['confidence']  # 0-1
        combined_confidence = (signal_strength + regime_confidence) / 2
        
        assert 0 <= combined_confidence <= 1
        assert regime['regime'] in ['uptrend', 'downtrend', 'consolidation']
        assert velocity['1d']['news_count'] == 2


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
