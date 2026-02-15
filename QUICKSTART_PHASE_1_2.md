# Quick Start Guide: Phase 1 & 2

## Installation

```bash
# Install required dependencies
pip install textblob pandas numpy scipy

# Optional: Portuguese language support
python -m spacy download pt_core_news_sm
```

## 5-Minute Setup

### 1. News Sentiment Analysis

```python
from src.news.news_aggregator import NewsAggregator
from src.news.sentiment_analyzer import SentimentAnalyzer

# Initialize
aggregator = NewsAggregator(api_key='YOUR_NEWSAPI_KEY')
analyzer = SentimentAnalyzer(language='en')

# Fetch news
articles = aggregator.fetch_news('PETR4', days=7)

# Store with deduplication
stored, duplicates = aggregator.deduplicate_and_store('PETR4', articles)
print(f"Stored {stored} new articles, {duplicates} duplicates")

# Analyze sentiment
news = aggregator.get_news_for_analysis('PETR4', hours=24)
results = analyzer.batch_analyze(news)

# Update database
for article in results:
    aggregator.update_article_sentiment(
        article['id'],
        article['polarity'],
        article['sentiment']
    )

# Get sentiment distribution
distribution = analyzer.get_sentiment_distribution(results)
print(f"Bullish: {distribution['bullish_pct']}%")
print(f"Bearish: {distribution['bearish_pct']}%")
print(f"Avg Sentiment: {distribution['avg_sentiment']}")
```

### 2. Market Regime Detection

```python
from src.signals.regime_detector import RegimeDetector
import pandas as pd

# Initialize
detector = RegimeDetector()

# Get market data (you provide this)
df = pd.read_csv('petr4_daily.csv', index_col='Date', parse_dates=True)

# Detect regime
result = detector.detect_regime(df)
print(f"Regime: {result['regime']}")
print(f"Confidence: {result['confidence']:.2%}")

# Get strategy allocation
strategy = result['strategy']
print(f"Capital Allocation: {strategy['allocation']:.0%}")
print(f"Mode: {strategy['mode']}")

# Store for history
detector.store_regime('PETR4', result)

# Get regime summary
summary = detector.get_regime_summary('PETR4', days=7)
print(f"Dominant regime: {summary['dominant_regime']}")
print(f"Regime changes in 7d: {summary['regime_changes']}")
```

### 3. Combined Signal

```python
# 1. Get sentiment
sentiment_dist = analyzer.get_sentiment_distribution(results)

# 2. Get regime
regime = detector.detect_regime(df)

# 3. Generate signal
if regime['regime'] == 'uptrend' and sentiment_dist['bullish_pct'] > 60:
    signal = '🟢 STRONG BUY'
elif regime['regime'] == 'downtrend' and sentiment_dist['bearish_pct'] > 60:
    signal = '🔴 STRONG SELL'
elif regime['regime'] == 'uptrend':
    signal = '🟡 BUY'
elif regime['regime'] == 'downtrend':
    signal = '🟠 AVOID LONGS'
else:
    signal = '⚪ HOLD / NEUTRAL'

print(f"Signal: {signal}")
print(f"Confidence: {regime['confidence']:.0%}")
```

## Common Tasks

### Get Sentiment Velocity

```python
velocity = aggregator.calculate_sentiment_velocity('PETR4')

print(f"News in last 1h: {velocity['1h']['news_count']}")
print(f"News in last 4h: {velocity['4h']['news_count']}")
print(f"1d avg sentiment: {velocity['1d']['avg_sentiment']}")
```

### Find Top Stocks by Sentiment Activity

```python
top_stocks = aggregator.get_top_stocks_by_sentiment(limit=10)

for ticker, avg_sentiment, count in top_stocks:
    print(f"{ticker}: {avg_sentiment:.2f} ({count} articles)")
```

### Analyze Single Article

```python
article = {
    'title': 'Company Reports Strong Earnings',
    'description': 'Q4 results exceed expectations',
    'content': 'Full article text here...'
}

result = analyzer.analyze_article(
    article['title'],
    article['description'],
    article['content']
)

print(f"Polarity: {result['polarity']:.2f}")
print(f"Sentiment: {result['sentiment']}")
```

### Bulk Analyze Articles

```python
# Analyze multiple articles at once
results = analyzer.batch_analyze(articles)

# Get distribution
distribution = analyzer.get_sentiment_distribution(results)
print(f"Total articles: {distribution['total_count']}")
print(f"Bullish: {distribution['bullish_count']}")
print(f"Bearish: {distribution['bearish_count']}")
print(f"Avg sentiment: {distribution['avg_sentiment']}")
```

### Get Regime History

```python
# Last 60 days
history = detector.get_regime_history('PETR4', days=60)

for entry in history[-5:]:  # Last 5 entries
    print(f"{entry['detected_at']}: {entry['regime']} ({entry['confidence']:.2%})")
```

## Testing

```bash
# Run all tests
pytest tests/ -v

# Run specific test
pytest tests/test_sentiment_analyzer.py -v

# Run with coverage
pytest tests/ --cov=src
```

## API Reference Quick Links

### SentimentAnalyzer

| Method | Purpose |
|--------|---------|
| `analyze_sentiment(text)` | Analyze single text (returns polarity -1 to 1) |
| `analyze_article(title, desc, content)` | Weighted analysis with title/body weighting |
| `batch_analyze(articles)` | Analyze multiple articles efficiently |
| `get_sentiment_distribution(articles)` | Get bullish/bearish percentages |

### NewsAggregator

| Method | Purpose |
|--------|---------|
| `fetch_news(ticker, days)` | Fetch news from NewsAPI |
| `deduplicate_and_store(ticker, articles)` | Store with deduplication |
| `get_recent_news(ticker, hours, limit)` | Retrieve recent articles |
| `calculate_sentiment_velocity(ticker)` | Get sentiment metrics by time window |
| `get_top_stocks_by_sentiment(limit)` | Find most active stocks |

### RegimeDetector

| Method | Purpose |
|--------|---------|
| `detect_regime(df)` | Detect current market regime |
| `store_regime(ticker, result)` | Store regime in database |
| `get_regime_history(ticker, days)` | Retrieve regime history |
| `get_regime_summary(ticker, days)` | Get dominant regime stats |

## Next Steps

1. **Get NewsAPI Key:** https://newsapi.org/
2. **Load Historical Data:** Populate OHLCV DataFrame
3. **Run Tests:** Verify everything works
4. **Backtest:** Use historical data to validate
5. **Deploy:** Integrate into live system

## Troubleshooting

**Q: NewsAPI returns no results**  
A: Check if you're using the 'demo' key. Get a real key at https://newsapi.org/

**Q: Module not found errors**  
A: Make sure you're in the stock-signals directory and have installed dependencies

**Q: Sentiment seems off**  
A: Check if the text includes financial keywords. Add custom keywords if needed in the FINANCIAL_KEYWORDS dict.

**Q: Regime detection always returns consolidation**  
A: Need at least 20-30 days of data. More data = better signals.

## Support

See `PHASE_1_2_IMPLEMENTATION.md` for detailed documentation.
