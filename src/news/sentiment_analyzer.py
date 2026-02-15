"""
Sentiment Analyzer: Financial sentiment scoring with Portuguese language support.
- spaCy-based text processing
- Financial keyword mapping for Portuguese
- Title/body weighting (60%/40%)
- Polarity scoring (-1.0 to +1.0)
- Bullish/Bearish classification
"""

import re
import logging
from typing import Dict, Tuple, Optional
from textblob import TextBlob
try:
    import spacy
    SPACY_AVAILABLE = True
except ImportError:
    SPACY_AVAILABLE = False

logger = logging.getLogger(__name__)


class SentimentAnalyzer:
    """Analyze financial sentiment in Portuguese and English news."""
    
    # Financial keywords mapping: keyword -> (sentiment_score, language)
    # Format: {'keyword': {'pt': score, 'en': score}}
    FINANCIAL_KEYWORDS = {
        # Positive indicators
        'lucro': {'pt': 0.85, 'en': 0.85},  # profit
        'profit': {'pt': 0.85, 'en': 0.85},  # profit
        'ganho': {'pt': 0.80, 'en': 0.80},  # gain
        'gain': {'pt': 0.80, 'en': 0.80},  # gain
        'alta': {'pt': 0.75, 'en': 0.75},   # high/rise
        'subida': {'pt': 0.75, 'en': 0.75}, # rise
        'crescimento': {'pt': 0.80, 'en': 0.80},  # growth
        'growth': {'pt': 0.80, 'en': 0.80},  # growth
        'expansão': {'pt': 0.80, 'en': 0.80},  # expansion
        'recuperação': {'pt': 0.70, 'en': 0.70},  # recovery
        'recovery': {'pt': 0.70, 'en': 0.70},  # recovery
        'otimismo': {'pt': 0.75, 'en': 0.75},  # optimism
        'fortalecimento': {'pt': 0.75, 'en': 0.75},  # strengthening
        'melhoria': {'pt': 0.70, 'en': 0.70},  # improvement
        'sucesso': {'pt': 0.80, 'en': 0.80},  # success
        'success': {'pt': 0.80, 'en': 0.80},  # success
        'aumento': {'pt': 0.75, 'en': 0.75},  # increase
        'increase': {'pt': 0.75, 'en': 0.75},  # increase
        'divulgação': {'pt': 0.70, 'en': 0.70},  # disclosure (often positive)
        'recordes': {'pt': 0.85, 'en': 0.85},  # records
        'record': {'pt': 0.85, 'en': 0.85},  # record
        'melhor': {'pt': 0.70, 'en': 0.70},  # better
        'better': {'pt': 0.70, 'en': 0.70},  # better
        'positivo': {'pt': 0.75, 'en': 0.75},  # positive
        'positive': {'pt': 0.75, 'en': 0.75},  # positive
        'good': {'pt': 0.70, 'en': 0.70},  # good
        'bullish': {'pt': 0.80, 'en': 0.80},  # bullish
        'upgrade': {'pt': 0.80, 'en': 0.80},  # upgrade
        'overweight': {'pt': 0.75, 'en': 0.75},  # overweight
        'strong': {'pt': 0.30, 'en': 0.30},  # intensifier (used with results, earnings)
        
        # Negative indicators
        'prejuízo': {'pt': -0.90, 'en': -0.90},  # loss
        'loss': {'pt': -0.90, 'en': -0.90},  # loss
        'losses': {'pt': -0.85, 'en': -0.85},  # losses
        'queda': {'pt': -0.80, 'en': -0.80},  # fall
        'diminuição': {'pt': -0.75, 'en': -0.75},  # decrease
        'redução': {'pt': -0.75, 'en': -0.75},  # reduction
        'perdas': {'pt': -0.85, 'en': -0.85},  # losses
        'risco': {'pt': -0.65, 'en': -0.65},  # risk
        'bankruptcy': {'pt': -0.95, 'en': -0.95},  # bankruptcy
        'bankrupt': {'pt': -0.95, 'en': -0.95},  # bankrupt
        'crise': {'pt': -0.85, 'en': -0.85},  # crisis
        'colapso': {'pt': -0.90, 'en': -0.90},  # collapse
        'falha': {'pt': -0.75, 'en': -0.75},  # failure
        'pior': {'pt': -0.70, 'en': -0.70},  # worse
        'problema': {'pt': -0.70, 'en': -0.70},  # problem
        'preocupação': {'pt': -0.65, 'en': -0.65},  # concern
        'pessimismo': {'pt': -0.80, 'en': -0.80},  # pessimism
        'fraqueza': {'pt': -0.75, 'en': -0.75},  # weakness
        'enfraquecimento': {'pt': -0.75, 'en': -0.75},  # weakening
        'negativo': {'pt': -0.75, 'en': -0.75},  # negative
        'bearish': {'pt': -0.80, 'en': -0.80},  # bearish
        'downgrade': {'pt': -0.80, 'en': -0.80},  # downgrade
        'underweight': {'pt': -0.75, 'en': -0.75},  # underweight
        'desempenho fraco': {'pt': -0.75, 'en': -0.75},  # poor performance
        'demissão': {'pt': -0.70, 'en': -0.70},  # layoff
        'investigação': {'pt': -0.65, 'en': -0.65},  # investigation
        'multa': {'pt': -0.70, 'en': -0.70},  # fine
        'fraude': {'pt': -0.90, 'en': -0.90},  # fraud
        'massive': {'pt': -0.30, 'en': -0.30},  # intensifier for negative (used with losses, etc.)
    }
    
    def __init__(self, language: str = 'en', use_spacy: bool = True):
        """
        Initialize Sentiment Analyzer.
        
        Args:
            language: 'en' for English, 'pt' for Portuguese
            use_spacy: Use spaCy for NLP processing if available
        """
        self.language = language
        self.nlp = None
        
        if use_spacy and SPACY_AVAILABLE:
            try:
                # Try to load Portuguese model
                if language == 'pt':
                    self.nlp = spacy.load('pt_core_news_sm')
                else:
                    self.nlp = spacy.load('en_core_web_sm')
                logger.info(f"Loaded spaCy model for language: {language}")
            except OSError:
                logger.warning(f"spaCy model not found for {language}. Install with: python -m spacy download pt_core_news_sm")
    
    def analyze_sentiment(self, text: str, title_weight: float = 0.6, 
                         body_weight: float = 0.4) -> Dict:
        """
        Analyze sentiment of text.
        
        Args:
            text: Text to analyze
            title_weight: Weight for title analysis (if title present)
            body_weight: Weight for body analysis (if body present)
        
        Returns:
            Dictionary with polarity, sentiment, and explanation
        """
        if not text or not isinstance(text, str):
            return self._neutral_result()
        
        try:
            # Clean text
            text = text.strip()
            if not text:
                return self._neutral_result()
            
            # Use TextBlob as base
            blob = TextBlob(text)
            polarity = blob.sentiment.polarity
            
            # Enhance with financial keywords
            keyword_score = self._extract_keyword_sentiment(text)
            
            # Combine scores with weighting
            # If keyword score is strong, weight it more heavily
            # Keywords: 70%, TextBlob: 30% (keywords are more reliable for financial sentiment)
            if abs(keyword_score) > 0.3:
                combined_polarity = (keyword_score * 0.7) + (polarity * 0.3)
            else:
                combined_polarity = (polarity * 0.6) + (keyword_score * 0.4)
            
            # Clamp to [-1, 1]
            combined_polarity = max(-1.0, min(1.0, combined_polarity))
            
            # Classify
            sentiment = self._classify_sentiment(combined_polarity)
            
            return {
                'polarity': round(combined_polarity, 3),
                'sentiment': sentiment,
                'textblob_polarity': round(polarity, 3),
                'keyword_score': round(keyword_score, 3),
                'explanation': self._explain_sentiment(combined_polarity, keyword_score, polarity)
            }
            
        except Exception as e:
            logger.error(f"Error analyzing sentiment: {e}")
            return self._neutral_result()
    
    def analyze_article(self, title: str, description: str, content: str = '') -> Dict:
        """
        Analyze full article with title/description weighting.
        
        Args:
            title: Article title (60% weight)
            description: Article description (25% weight)
            content: Full content (15% weight)
        
        Returns:
            Dictionary with weighted sentiment score
        """
        try:
            # Analyze each component
            title_result = self.analyze_sentiment(title)
            desc_result = self.analyze_sentiment(description)
            content_result = self.analyze_sentiment(content)
            
            # Weighted combination
            weights = [0.60, 0.25, 0.15]
            title_pol = title_result['polarity']
            desc_pol = desc_result['polarity']
            content_pol = content_result['polarity']
            
            weighted_polarity = (
                title_pol * weights[0] +
                desc_pol * weights[1] +
                content_pol * weights[2]
            )
            
            # Classify
            sentiment = self._classify_sentiment(weighted_polarity)
            
            return {
                'polarity': round(weighted_polarity, 3),
                'sentiment': sentiment,
                'title_polarity': title_pol,
                'description_polarity': desc_pol,
                'content_polarity': content_pol,
                'explanation': f"Title: {title_result['sentiment']} ({title_pol}), "
                               f"Description: {desc_result['sentiment']} ({desc_pol})"
            }
            
        except Exception as e:
            logger.error(f"Error analyzing article: {e}")
            return self._neutral_result()
    
    def _extract_keyword_sentiment(self, text: str) -> float:
        """
        Extract sentiment from financial keywords in text.
        
        Args:
            text: Text to analyze
        
        Returns:
            Sentiment score (-1.0 to 1.0)
        """
        if not text:
            return 0.0
        
        text_lower = text.lower()
        scores = []
        matches = []
        
        for keyword, scores_dict in self.FINANCIAL_KEYWORDS.items():
            if keyword in text_lower:
                score = scores_dict.get(self.language, scores_dict.get('en', 0))
                scores.append(score)
                matches.append((keyword, score))
        
        if not scores:
            return 0.0
        
        # Average of keyword scores
        avg_score = sum(scores) / len(scores)
        
        # Boost by frequency (more keywords = stronger signal)
        frequency_boost = min(len(matches) * 0.05, 0.2)
        
        result = avg_score + frequency_boost if avg_score > 0 else avg_score - frequency_boost
        
        return max(-1.0, min(1.0, result))
    
    def _classify_sentiment(self, polarity: float) -> str:
        """Classify sentiment from polarity score."""
        if polarity > 0.2:
            return 'bullish'
        elif polarity < -0.2:
            return 'bearish'
        else:
            return 'neutral'
    
    def _neutral_result(self) -> Dict:
        """Return neutral sentiment result."""
        return {
            'polarity': 0.0,
            'sentiment': 'neutral',
            'textblob_polarity': 0.0,
            'keyword_score': 0.0,
            'explanation': 'No sentiment detected'
        }
    
    def _explain_sentiment(self, combined: float, keywords: float, textblob: float) -> str:
        """Generate explanation for sentiment score."""
        sources = []
        
        if abs(keywords) > abs(textblob) * 1.5:
            sources.append(f"financial keywords ({keywords:.2f})")
        else:
            sources.append(f"text analysis ({textblob:.2f})")
        
        return f"Combined score {combined:.2f} from {', '.join(sources)}"
    
    def batch_analyze(self, articles: list) -> list:
        """
        Analyze sentiment for multiple articles.
        
        Args:
            articles: List of article dicts with 'title', 'description', 'content'
        
        Returns:
            List of article dicts with added sentiment data
        """
        results = []
        
        for article in articles:
            try:
                sentiment_data = self.analyze_article(
                    article.get('title', ''),
                    article.get('description', ''),
                    article.get('content', '')
                )
                
                article['polarity'] = sentiment_data['polarity']
                article['sentiment'] = sentiment_data['sentiment']
                article['sentiment_details'] = sentiment_data
                results.append(article)
                
            except Exception as e:
                logger.error(f"Error analyzing article: {e}")
                article['polarity'] = 0.0
                article['sentiment'] = 'neutral'
                article['sentiment_details'] = self._neutral_result()
                results.append(article)
        
        return results
    
    def get_sentiment_distribution(self, articles: list) -> Dict:
        """
        Calculate sentiment distribution for a batch of articles.
        
        Args:
            articles: List of articles (must have 'polarity' field)
        
        Returns:
            Dictionary with distribution stats
        """
        polarities = [a.get('polarity', 0) for a in articles]
        
        if not polarities:
            return {
                'total_count': 0,
                'bullish_count': 0,
                'bearish_count': 0,
                'neutral_count': 0,
                'avg_sentiment': 0.0,
                'sentiment_strength': 0.0
            }
        
        bullish = sum(1 for p in polarities if p > 0.2)
        bearish = sum(1 for p in polarities if p < -0.2)
        neutral = len(polarities) - bullish - bearish
        
        avg_sentiment = sum(polarities) / len(polarities)
        sentiment_strength = abs(avg_sentiment)
        
        return {
            'total_count': len(articles),
            'bullish_count': bullish,
            'bearish_count': bearish,
            'neutral_count': neutral,
            'bullish_pct': round(bullish / len(articles) * 100, 1),
            'bearish_pct': round(bearish / len(articles) * 100, 1),
            'avg_sentiment': round(avg_sentiment, 3),
            'sentiment_strength': round(sentiment_strength, 3)
        }
