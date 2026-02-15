"""
Filtered News Client - Only fetches news directly related to specific stocks
Uses Google News RSS with ticker-specific queries
"""

import feedparser
import requests
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import time
from transformers import AutoTokenizer, AutoModelForSequenceClassification
import torch
import hashlib


class FilteredNewsClient:
    """
    Fetches news with strict filtering:
    1. Only news mentioning the specific ticker/company
    2. From Brazilian financial sources (InfoMoney, Valor, EstadãoE3, etc.)
    3. Published in the last N hours
    """
    
    # Ticker to company name mapping (for better news search)
    TICKER_TO_COMPANY = {
        "PETR4.SA": "Petrobras",
        "VALE3.SA": "Vale",
        "ITUB4.SA": "Itaú",
        "ITUB3.SA": "Itaú", 
        "BBDC4.SA": "Bradesco",
        "BBAS3.SA": "Banco do Brasil",
        "ABEV3.SA": "Ambev",
        "B3SA3.SA": "B3",
        "SUZB3.SA": "Suzano",
        "RENT3.SA": "Localiza",
        "WEGE3.SA": "Weg",
        "MGLU3.SA": "Magazine Luiza",
        "PCAR3.SA": "Pão de Açúcar",
        "LREN3.SA": "Lojas Renner",
        "RAIZ4.SA": "Raízen",
        "GGBR4.SA": "Gerdau",
        "ASAI3.SA": "Assaí",
        "JBSS3.SA": "JBS",
        "RDOR3.SA": "Rede D'Or",
        "KLBN11.SA": "Klabin",
        "MTRE3.SA": "Mitre",
        "ITSA4.SA": "Itaúsa",
    }
    
    # Brazilian financial news sources
    SOURCES = [
        "infomoney.com.br",
        "valor.com.br",
        "estadao.com.br/economia",
        "g1.globo.com/economia",
        "exame.com",
        "moneytimes.com.br",
    ]
    
    def __init__(self, cache_minutes: int = 10):
        """
        Initialize filtered news client
        
        Args:
            cache_minutes: Cache duration for news (to avoid rate limits)
        """
        self.cache_minutes = cache_minutes
        self.cache = {}  # ticker -> (timestamp, news_list)
        
        # Load FinBERT model for sentiment analysis
        try:
            print("📰 Loading FinBERT model for sentiment analysis...")
            self.tokenizer = AutoTokenizer.from_pretrained("ProsusAI/finbert")
            self.model = AutoModelForSequenceClassification.from_pretrained("ProsusAI/finbert")
            self.model.eval()
            print("✅ FinBERT loaded")
        except Exception as e:
            print(f"⚠️ FinBERT load failed: {e}")
            print("📰 News sentiment will return 0.0 (neutral)")
            self.tokenizer = None
            self.model = None
    
    def _get_cache_key(self, ticker: str) -> str:
        """Generate cache key"""
        return ticker
    
    def _is_cache_valid(self, ticker: str) -> bool:
        """Check if cache is still valid"""
        cache_key = self._get_cache_key(ticker)
        
        if cache_key not in self.cache:
            return False
        
        timestamp, _ = self.cache[cache_key]
        age_minutes = (datetime.now() - timestamp).total_seconds() / 60
        
        return age_minutes < self.cache_minutes
    
    def _get_from_cache(self, ticker: str) -> Optional[List[Dict]]:
        """Get news from cache"""
        cache_key = self._get_cache_key(ticker)
        
        if cache_key in self.cache:
            _, news_list = self.cache[cache_key]
            return news_list
        
        return None
    
    def _save_to_cache(self, ticker: str, news_list: List[Dict]):
        """Save news to cache"""
        cache_key = self._get_cache_key(ticker)
        self.cache[cache_key] = (datetime.now(), news_list)
    
    def fetch_news(
        self,
        ticker: str,
        hours_back: int = 24,
        max_results: int = 10,
    ) -> List[Dict]:
        """
        Fetch news for a specific ticker with strict filtering
        
        Args:
            ticker: Stock ticker (e.g., "VALE3.SA")
            hours_back: How many hours back to search (default 24)
            max_results: Maximum number of results (default 10)
            
        Returns:
            List of news articles with title, link, published, summary
        """
        # Check cache
        if self._is_cache_valid(ticker):
            return self._get_from_cache(ticker)
        
        company_name = self.TICKER_TO_COMPANY.get(ticker, ticker.replace(".SA", ""))
        
        # Build Google News query
        # Search for company name + economia/bolsa keywords
        query = f'{company_name} (ações OR bolsa OR resultado OR lucro OR dividendo)'
        
        # Restrict to Brazilian news sources
        source_filter = " OR ".join([f"site:{source}" for source in self.SOURCES])
        full_query = f'{query} ({source_filter})'
        
        # Google News RSS URL
        rss_url = f"https://news.google.com/rss/search?q={requests.utils.quote(full_query)}&hl=pt-BR&gl=BR&ceid=BR:pt-419"
        
        try:
            # Fetch RSS feed
            feed = feedparser.parse(rss_url)
            
            articles = []
            cutoff_time = datetime.now() - timedelta(hours=hours_back)
            
            for entry in feed.entries[:max_results * 2]:  # Fetch extra to account for filtering
                # Parse published time
                try:
                    published = datetime(*entry.published_parsed[:6])
                except:
                    published = datetime.now()
                
                # Filter by time
                if published < cutoff_time:
                    continue
                
                # Extract info
                title = entry.get('title', '')
                link = entry.get('link', '')
                summary = entry.get('summary', title)
                
                # Strict relevance filter: title or summary must mention company
                company_lower = company_name.lower()
                title_lower = title.lower()
                summary_lower = summary.lower()
                
                # Check if company is actually mentioned (not just related keywords)
                if company_lower not in title_lower and company_lower not in summary_lower:
                    continue
                
                articles.append({
                    'title': title,
                    'link': link,
                    'published': published.isoformat(),
                    'summary': summary,
                    'ticker': ticker,
                    'company': company_name,
                })
                
                if len(articles) >= max_results:
                    break
            
            # Save to cache
            self._save_to_cache(ticker, articles)
            
            return articles
            
        except Exception as e:
            print(f"⚠️ Error fetching news for {ticker}: {e}")
            return []
    
    def analyze_sentiment(self, text: str) -> float:
        """
        Analyze sentiment of text using FinBERT
        
        Args:
            text: Text to analyze
            
        Returns:
            Sentiment score from -1.0 (very negative) to +1.0 (very positive)
        """
        # Check if model loaded successfully
        if self.model is None or self.tokenizer is None:
            return 0.0
        
        try:
            # Truncate to avoid token limits
            text = text[:512]
            
            # Tokenize
            inputs = self.tokenizer(text, return_tensors="pt", truncation=True, max_length=512)
            
            # Get predictions
            with torch.no_grad():
                outputs = self.model(**inputs)
                predictions = torch.nn.functional.softmax(outputs.logits, dim=-1)
            
            # FinBERT outputs: [negative, neutral, positive]
            negative, neutral, positive = predictions[0].tolist()
            
            # Convert to -1 to +1 scale
            sentiment = positive - negative
            
            return sentiment
        except Exception as e:
            print(f"⚠️ Sentiment analysis error: {e}")
            return 0.0
    
    def get_ticker_sentiment(
        self,
        ticker: str,
        hours_back: int = 24,
    ) -> Dict:
        """
        Get aggregated sentiment for a ticker
        
        Args:
            ticker: Stock ticker
            hours_back: How many hours back to search
            
        Returns:
            Dict with sentiment score, article count, and summary
        """
        articles = self.fetch_news(ticker, hours_back=hours_back)
        
        if not articles:
            return {
                'ticker': ticker,
                'sentiment': 0.0,
                'article_count': 0,
                'summary': 'No recent news',
            }
        
        # Analyze sentiment of each article
        sentiments = []
        for article in articles:
            text = f"{article['title']} {article['summary']}"
            sentiment = self.analyze_sentiment(text)
            sentiments.append(sentiment)
        
        # Average sentiment
        avg_sentiment = sum(sentiments) / len(sentiments)
        
        # Summary of articles
        summary_text = f"{len(articles)} articles in last {hours_back}h"
        if avg_sentiment > 0.3:
            summary_text += " (mostly positive)"
        elif avg_sentiment < -0.3:
            summary_text += " (mostly negative)"
        else:
            summary_text += " (neutral)"
        
        return {
            'ticker': ticker,
            'sentiment': avg_sentiment,
            'article_count': len(articles),
            'summary': summary_text,
            'articles': articles[:3],  # Top 3 articles
        }


# Example usage
if __name__ == "__main__":
    client = FilteredNewsClient(cache_minutes=10)
    
    # Test with VALE3
    print("\n📰 Testing with VALE3.SA...")
    result = client.get_ticker_sentiment("VALE3.SA", hours_back=48)
    
    print(f"\n📊 Sentiment Analysis:")
    print(f"   Ticker: {result['ticker']}")
    print(f"   Sentiment: {result['sentiment']:+.2f}")
    print(f"   Articles: {result['article_count']}")
    print(f"   Summary: {result['summary']}")
    
    if result['articles']:
        print(f"\n📰 Top Articles:")
        for i, article in enumerate(result['articles'], 1):
            print(f"   {i}. {article['title']}")
            print(f"      {article['link']}")
            print()
