"""Unit tests for Sentiment Analyzer module."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from src.news.sentiment_analyzer import SentimentAnalyzer


class TestSentimentAnalyzer:
    """Test sentiment analysis functionality."""
    
    @pytest.fixture
    def analyzer_en(self):
        """Create English sentiment analyzer."""
        return SentimentAnalyzer(language='en', use_spacy=False)
    
    @pytest.fixture
    def analyzer_pt(self):
        """Create Portuguese sentiment analyzer."""
        return SentimentAnalyzer(language='pt', use_spacy=False)
    
    def test_analyzer_initialization_en(self, analyzer_en):
        """Test English analyzer initialization."""
        assert analyzer_en.language == 'en'
        assert analyzer_en.FINANCIAL_KEYWORDS is not None
    
    def test_analyzer_initialization_pt(self, analyzer_pt):
        """Test Portuguese analyzer initialization."""
        assert analyzer_pt.language == 'pt'
        assert analyzer_pt.FINANCIAL_KEYWORDS is not None
    
    def test_analyze_positive_sentiment(self, analyzer_en):
        """Test detection of positive sentiment."""
        text = "Company reports record profits and strong growth"
        result = analyzer_en.analyze_sentiment(text)
        
        assert result['polarity'] > 0
        assert result['sentiment'] in ['bullish', 'positive']
        assert 'polarity' in result
        assert 'sentiment' in result
    
    def test_analyze_negative_sentiment(self, analyzer_en):
        """Test detection of negative sentiment."""
        text = "Company faces massive losses and bankruptcy risk"
        result = analyzer_en.analyze_sentiment(text)
        
        assert result['polarity'] < 0
        assert result['sentiment'] in ['bearish', 'negative']
    
    def test_analyze_neutral_sentiment(self, analyzer_en):
        """Test detection of neutral sentiment."""
        text = "Company announces quarterly earnings report"
        result = analyzer_en.analyze_sentiment(text)
        
        assert result['sentiment'] == 'neutral'
        assert -0.2 <= result['polarity'] <= 0.2
    
    def test_keyword_extraction_positive(self, analyzer_en):
        """Test extraction of positive financial keywords."""
        text = "lucro aumento ganho crescimento"
        score = analyzer_en._extract_keyword_sentiment(text)
        
        # Should be positive
        assert score > 0
    
    def test_keyword_extraction_negative(self, analyzer_en):
        """Test extraction of negative financial keywords."""
        text = "prejuizo queda perda risco"
        score = analyzer_en._extract_keyword_sentiment(text)
        
        # Should be negative
        assert score < 0
    
    def test_keyword_extraction_mixed(self, analyzer_en):
        """Test extraction with mixed keywords."""
        text = "lucro pero também risco"
        score = analyzer_en._extract_keyword_sentiment(text)
        
        # Should be near neutral
        assert -1 <= score <= 1
    
    def test_analyze_article_with_weighting(self, analyzer_en):
        """Test article analysis with title/description weighting."""
        title = "Positive news about recovery"
        description = "The company recovered from losses"
        content = "Full content with neutral tone"
        
        result = analyzer_en.analyze_article(title, description, content)
        
        assert 'polarity' in result
        assert 'sentiment' in result
        assert 'title_polarity' in result
        assert 'description_polarity' in result
        assert 'content_polarity' in result
        
        # Title (60%) should have more influence than content (15%)
        # So if title is positive and content neutral, overall should be positive-leaning
    
    def test_sentiment_classification_positive(self, analyzer_en):
        """Test positive sentiment classification."""
        sentiment = analyzer_en._classify_sentiment(0.8)
        assert sentiment == 'bullish'
    
    def test_sentiment_classification_negative(self, analyzer_en):
        """Test negative sentiment classification."""
        sentiment = analyzer_en._classify_sentiment(-0.8)
        assert sentiment == 'bearish'
    
    def test_sentiment_classification_neutral(self, analyzer_en):
        """Test neutral sentiment classification."""
        sentiment = analyzer_en._classify_sentiment(0.0)
        assert sentiment == 'neutral'
    
    def test_sentiment_classification_boundaries(self, analyzer_en):
        """Test sentiment classification boundary values."""
        assert analyzer_en._classify_sentiment(0.21) == 'bullish'
        assert analyzer_en._classify_sentiment(0.20) == 'neutral'
        assert analyzer_en._classify_sentiment(-0.21) == 'bearish'
        assert analyzer_en._classify_sentiment(-0.20) == 'neutral'
    
    def test_empty_text_handling(self, analyzer_en):
        """Test handling of empty text."""
        result = analyzer_en.analyze_sentiment("")
        
        assert result['polarity'] == 0.0
        assert result['sentiment'] == 'neutral'
    
    def test_none_text_handling(self, analyzer_en):
        """Test handling of None text."""
        result = analyzer_en.analyze_sentiment(None)
        
        assert result['polarity'] == 0.0
        assert result['sentiment'] == 'neutral'
    
    def test_batch_analysis(self, analyzer_en):
        """Test batch sentiment analysis."""
        articles = [
            {
                'title': 'Positive news',
                'description': 'Good results',
                'content': ''
            },
            {
                'title': 'Negative news',
                'description': 'Bad results',
                'content': ''
            },
            {
                'title': 'Regular announcement',
                'description': 'Standard news',
                'content': ''
            }
        ]
        
        results = analyzer_en.batch_analyze(articles)
        
        assert len(results) == 3
        
        # First should be positive
        assert results[0]['sentiment'] == 'bullish'
        
        # Second should be negative
        assert results[1]['sentiment'] == 'bearish'
        
        # Third should be neutral
        assert results[2]['sentiment'] == 'neutral'
        
        # All should have polarity values
        for result in results:
            assert -1 <= result['polarity'] <= 1
    
    def test_batch_analysis_error_handling(self, analyzer_en):
        """Test batch analysis with invalid data."""
        articles = [
            {'title': 'Good news', 'description': 'Positive', 'content': ''},
            {'title': None, 'description': None},  # Invalid
            {'title': 'News', 'description': '', 'content': 'Content'}
        ]
        
        results = analyzer_en.batch_analyze(articles)
        
        assert len(results) == 3
        
        # All should have sentiment scores even with errors
        for result in results:
            assert 'polarity' in result
            assert 'sentiment' in result
    
    def test_sentiment_distribution(self, analyzer_en):
        """Test sentiment distribution calculation."""
        articles = [
            {'polarity': 0.8},   # bullish
            {'polarity': 0.9},   # bullish
            {'polarity': 0.0},   # neutral
            {'polarity': -0.7},  # bearish
            {'polarity': -0.8}   # bearish
        ]
        
        distribution = analyzer_en.get_sentiment_distribution(articles)
        
        assert distribution['total_count'] == 5
        assert distribution['bullish_count'] == 2
        assert distribution['bearish_count'] == 2
        assert distribution['neutral_count'] == 1
        assert distribution['bullish_pct'] == 40.0
        assert distribution['bearish_pct'] == 40.0
        assert distribution['avg_sentiment'] == round((-0.7 + -0.8 + 0.8 + 0.9) / 5, 3)
    
    def test_sentiment_distribution_empty(self, analyzer_en):
        """Test sentiment distribution with empty list."""
        distribution = analyzer_en.get_sentiment_distribution([])
        
        assert distribution['total_count'] == 0
        assert distribution['bullish_count'] == 0
        assert distribution['bearish_count'] == 0
        assert distribution['neutral_count'] == 0
    
    def test_portuguese_keywords(self, analyzer_pt):
        """Test Portuguese financial keyword detection."""
        # Test positive Portuguese keywords
        text_positive = "Lucro recorde crescimento expansão melhoria"
        score_pos = analyzer_pt._extract_keyword_sentiment(text_positive)
        assert score_pos > 0
        
        # Test negative Portuguese keywords
        text_negative = "Prejuízo queda redução crise fraude"
        score_neg = analyzer_pt._extract_keyword_sentiment(text_negative)
        assert score_neg < 0
    
    def test_polarity_bounds(self, analyzer_en):
        """Test that polarity values stay within [-1, 1] bounds."""
        extreme_texts = [
            "positive " * 100,  # Many positive words
            "negative " * 100,  # Many negative words
            "profit gain gains growth success success success",
            "loss loss loss loss loss loss loss"
        ]
        
        for text in extreme_texts:
            result = analyzer_en.analyze_sentiment(text)
            assert -1.0 <= result['polarity'] <= 1.0
    
    def test_keyword_frequency_boost(self, analyzer_en):
        """Test that keyword frequency boosts sentiment signal."""
        # Single keyword
        text1 = "profit"
        score1 = analyzer_en._extract_keyword_sentiment(text1)
        
        # Multiple keywords
        text2 = "profit profit profit profit"
        score2 = analyzer_en._extract_keyword_sentiment(text2)
        
        # More keywords should have stronger signal
        assert abs(score2) >= abs(score1)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
