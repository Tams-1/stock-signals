# Stock Signal Detector

Real-time detection of important market signals in S&P500 stocks using SOTA value investing and technical analysis frameworks.

## Overview

This system monitors the top 100 most liquid S&P500 stocks for statistically significant signals that indicate important market moves or regime changes. Signals are based on established economic theory and market microstructure, not arbitrary thresholds.

## Architecture

```
stock-signals/
├── src/
│   ├── data/
│   │   └── sp500_liquidity.py      # Fetch top 100 liquid stocks
│   ├── signals/
│   │   ├── information_flow.py     # Volume, volatility, bid-ask spreads
│   │   ├── momentum_reversal.py    # Order imbalance, mean reversion, momentum
│   │   ├── fundamental_shifts.py   # (Coming) Earnings, guidance surprises
│   │   ├── valuation_breaks.py     # (Coming) P/E, PEG, dividend anomalies
│   │   └── correlation_breaks.py   # (Coming) Stock vs sector/index decoupling
│   ├── analysis/
│   │   └── explain.py              # (Coming) Generate explanations
│   └── monitor.py                  # Real-time monitoring loop
├── backtest/
│   └── backtest.py                 # Historical backtesting framework
├── configs/
│   └── top_100_tickers.txt         # S&P500 liquid stocks
└── README.md
```

## Signal Types

### 1. Information Flow Signals
Detect changes in information availability and uncertainty:
- **Volume Anomaly**: Extreme volume at price extremes (z-score > 2.0) suggests information discovery
- **Volatility Regime Shift**: Sudden increase in volatility (F-test, p < 0.05) indicates new information
- **Bid-Ask Spread Expansion**: Range expansion (proxy for spread widening) signals uncertainty

### 2. Momentum & Reversal Signals
Detect directional persistence and mean reversion:
- **Order Imbalance**: Buy/sell pressure persistence (binomial test for significance)
- **Mean Reversion Extreme**: Price moves > 2σ from mean (statistical extremes)
- **Momentum Continuation**: Price + volume both trending in same direction

### 3. Fundamental Signals (Coming)
- Earnings surprise magnitude
- Guidance vs expectations delta
- Free cash flow vs buybacks signals

### 4. Valuation Signals (Coming)
- P/E vs peer divergence (repricing event)
- PEG ratio anomalies
- Dividend yield changes

### 5. Correlation Signals (Coming)
- Stock decouples from sector
- Stock decouples from index
- Sector/index correlation breaks

## Installation

```bash
pip install yfinance pandas scipy sqlite3
```

## Usage

### Real-time Monitoring

```python
from src.monitor import StockSignalMonitor

# Load stock list
with open('configs/top_100_tickers.txt') as f:
    tickers = [line.strip() for line in f if line.strip()]

# Run monitor
monitor = StockSignalMonitor(lookback_days=30)
signals = monitor.run_monitor(tickers)

# Get summary
summary = monitor.get_signals_summary()
print(summary)
```

### Backtesting

```python
from backtest.backtest import SignalBacktest

backtest = SignalBacktest(test_days=5)
results = backtest.run_backtest(['AAPL', 'MSFT', 'NVDA'], test_months=3)
```

## Data Storage

All data and signals are stored in a local SQLite database (`stock_signals.db`):

- **ohlcv**: Historical price/volume data (ticker, date, OHLCV)
- **signals**: Detected signals (ticker, date, signal_type, strength, direction, explanation)

Keeps N days of data for context in decision-making (configurable).

## Signal Quality Metrics

Each signal includes:
- **Strength** (0-1.0): Magnitude of the statistical deviation
- **Direction** (bullish/bearish): Expected impact direction
- **Explanation**: Specific reason signal was triggered
- **Timestamp**: When signal was detected

## Backtest Results

Backtesting validates signal quality by measuring:
1. **Signal frequency**: How often do signals occur?
2. **Accuracy**: What % of signals precede positive moves?
3. **Average move**: How large are typical moves after signals?
4. **Risk/reward**: Best performing signal combinations

## Real-time Production Daemon

Run the signal monitor every minute on all 100 stocks:

```bash
# Single scan (test)
python src/daemon.py

# Continuous monitoring (production)
from src.daemon import run_continuous_monitor

tickers = [line.strip() for line in open('configs/top_100_tickers.txt')]
run_continuous_monitor(tickers, interval_seconds=60, fetch_news=True)
```

**What it does**:
- Fetches latest daily data for all stocks
- Detects technical signals (information flow, momentum, reversal)
- Fetches recent news and analyzes sentiment
- Correlates technical signals with news sentiment
- Assesses overall confidence (0-1.0)
- Stores alerts in SQLite DB
- Can send Telegram notifications

**Alert Confidence Calculation**:
- Base: average strength of technical signals
- Boost: +30% if news sentiment agrees with signal direction
- Threshold: only alert on confidence > 0.4

## News Sentiment Analysis

Uses TextBlob for quick sentiment classification:
- **Polarity**: -1.0 (very negative) to +1.0 (very positive)
- **Sentiment**: positive/negative/neutral
- **Weighted**: title 60%, description 40%

Can upgrade to transformer models (DistilBERT, FinBERT) for better accuracy on financial text.

## Next Steps

1. **Setup NewsAPI** (free tier): Get API key at https://newsapi.org/
2. **Deploy daemon**: Use cron/systemd to run every minute
3. **Telegram integration**: Link alerts to OpenClaw messaging
4. **Add fundamental signals**: Earnings, guidance, cash flow
5. **Add valuation signals**: P/E relative value, PEG, dividend yields
6. **Add correlation signals**: Stock/sector/index decoupling
7. **Dashboard**: Real-time visualization of signals and performance
8. **Optimize**: Backtest signal combinations, tune confidence thresholds

## References

- Market Microstructure (O'Hara, 1995)
- Behavioral Finance (Kahneman & Tversky)
- Value Investing (Graham, Dodd, Buffett)
- Technical Analysis (Pring, Murphy)

## License

MIT
