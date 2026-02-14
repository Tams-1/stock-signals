"""
News sentiment analysis: fetch news for stocks and classify sentiment.
Uses TextBlob for basic sentiment, can upgrade to transformer models.
"""

import requests
import json
from datetime import datetime, timedelta
from textblob import TextBlob
import sqlite3

class NewsSentimentAnalyzer:
    """Fetch and analyze news sentiment for stocks."""
    
    def __init__(self, api_key='demo'):
        """
        Initialize with NewsAPI key.
        Get free key at https://newsapi.org/
        """
        self.api_key = api_key
        self.base_url = "https://newsapi.org/v2/everything"
        self.db_path = 'stock_signals.db'
    
    def fetch_news(self, ticker, days=1):
        """Fetch recent news for a ticker from NewsAPI."""
        try:
            # If using demo key, skip API calls (for now)
            if self.api_key == 'demo':
                return []
            
            from_date = (datetime.now() - timedelta(days=days)).isoformat()
            
            params = {
                'q': ticker,
                'sortBy': 'publishedAt',
                'language': 'en',
                'from': from_date,
                'apiKey': self.api_key
            }
            
            response = requests.get(self.base_url, params=params, timeout=5)
            articles = response.json().get('articles', [])
            
            return articles
        except Exception as e:
            print(f"Error fetching news for {ticker}: {e}")
            return []
    
    def analyze_sentiment(self, text):
        """
        Analyze sentiment of text using TextBlob.
        Returns: polarity (-1.0 to 1.0), subjectivity (0.0 to 1.0)
        """
        try:
            blob = TextBlob(text)
            polarity = blob.sentiment.polarity
            subjectivity = blob.sentiment.subjectivity
            
            # Classify
            if polarity > 0.1:
                sentiment = 'positive'
            elif polarity < -0.1:
                sentiment = 'negative'
            else:
                sentiment = 'neutral'
            
            return {
                'polarity': polarity,
                'subjectivity': subjectivity,
                'sentiment': sentiment
            }
        except Exception as e:
            print(f"Error analyzing sentiment: {e}")
            return {'polarity': 0, 'subjectivity': 0.5, 'sentiment': 'neutral'}
    
    def process_articles(self, ticker, articles):
        """Process articles and extract sentiment signals."""
        if not articles:
            return None
        
        sentiments = []
        
        for article in articles:
            title = article.get('title', '')
            description = article.get('description', '')
            content = article.get('content', '')
            
            # Analyze title (most important)
            title_sentiment = self.analyze_sentiment(title)
            
            # Analyze description
            desc_sentiment = self.analyze_sentiment(description)
            
            # Weighted average (title = 60%, description = 40%)
            overall_polarity = title_sentiment['polarity'] * 0.6 + desc_sentiment['polarity'] * 0.4
            overall_sentiment = 'positive' if overall_polarity > 0.1 else ('negative' if overall_polarity < -0.1 else 'neutral')
            
            sentiments.append({
                'title': title,
                'url': article.get('url', ''),
                'published_at': article.get('publishedAt', ''),
                'source': article.get('source', {}).get('name', ''),
                'polarity': overall_polarity,
                'sentiment': overall_sentiment
            })
        
        return sentiments
    
    def get_sentiment_signal(self, ticker, articles):
        """
        Generate a sentiment signal from articles.
        Returns: (signal_strength, direction, explanation)
        """
        if not articles:
            return 0, None, "No recent news"
        
        sentiments = self.process_articles(ticker, articles)
        
        if not sentiments:
            return 0, None, "No news to analyze"
        
        # Count sentiment distribution
        positive = sum(1 for s in sentiments if s['sentiment'] == 'positive')
        negative = sum(1 for s in sentiments if s['sentiment'] == 'negative')
        neutral = len(sentiments) - positive - negative
        
        total = len(sentiments)
        positive_ratio = positive / total
        negative_ratio = negative / total
        
        # Calculate average polarity
        avg_polarity = sum(s['polarity'] for s in sentiments) / total
        
        # Signal only if strong consensus (>70%) and recent news exists
        if positive_ratio > 0.7 and positive > 0:
            explanation = f"Positive news: {positive}/{total} articles positive (avg polarity: {avg_polarity:.2f})"
            return min(positive_ratio, 1.0), 'bullish', explanation
        elif negative_ratio > 0.7 and negative > 0:
            explanation = f"Negative news: {negative}/{total} articles negative (avg polarity: {avg_polarity:.2f})"
            return min(negative_ratio, 1.0), 'bearish', explanation
        else:
            explanation = f"Mixed news: {positive} positive, {negative} negative, {neutral} neutral"
            return 0, None, explanation
    
    def store_news(self, ticker, articles):
        """Store news and sentiment in database."""
        if not articles:
            return
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Create table if needed
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS news (
                id INTEGER PRIMARY KEY,
                ticker TEXT,
                title TEXT,
                url TEXT,
                source TEXT,
                polarity REAL,
                sentiment TEXT,
                published_at TEXT,
                analyzed_at TEXT
            )
        ''')
        
        sentiments = self.process_articles(ticker, articles)
        now = datetime.now().isoformat()
        
        for article in sentiments:
            cursor.execute('''
                INSERT INTO news 
                (ticker, title, url, source, polarity, sentiment, published_at, analyzed_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                ticker,
                article['title'],
                article['url'],
                article['source'],
                article['polarity'],
                article['sentiment'],
                article['published_at'],
                now
            ))
        
        conn.commit()
        conn.close()
