# Stock-Signals

**Production-grade trading signal system for Brazilian equities (IBOV + SMLL)**

A multi-indicator, value-investing fusion stack that combines **TrendDetectorV2** (dual-timeframe technicals), **Graham / Lynch / Greenblatt** fundamentals (via `src/fundamentals/`), and optional **news sentiment** (newsdata.io + FinBERT). **Day-to-day production monitoring** runs on the **top 50 most liquid** names through `scripts/quick_market_monitor.py` (fundamentals on, news off for API stability); the full validated universe remains available for deeper batch runs and Sheets export.

---

## Features

### Real-time price data (BrAPI)
- **BrAPI** (brapi.dev) for near real-time Brazilian quotes
- **Batch-friendly** — large quote batches complete quickly compared to naive per-ticker scraping
- **`production_simple` path** — BrAPI spot prices plus **yfinance** daily history for indicators
- **`production_brapi` / `run_production`** — BrAPI client in `src/data/brapi_client.py` (candles + quotes per that client’s API usage)

### Multi-Indicator Technical Analysis
- **12 technical indicators** across 4 categories:
  - Momentum: RSI, MACD, Stochastic, Williams %R
  - Volatility: ATR, Bollinger Bands, Keltner, SuperTrend
  - Volume: OBV, VWAP, MFI, Volume Momentum
  - Trend: Moving Averages (MA50/MA200), ADX, DI+/DI-
- **Signal Fusion**: Weighted ensemble combining all indicators
- **Two-timeframe trend detection** (`TrendDetectorV2`): ~50-day macro regime + ~20-day micro trend (reduces false downtrends in bull pullbacks)

### Value Investing Integration
- **Graham's Defensive Investor criteria** (7-point checklist)
- **Lynch's GARP** (PEG ratio analysis)
- **Greenblatt's Magic Formula** (Earnings Yield + ROC)
- **Composite scoring**: 50% technical + 50% fundamental
- **20+ fundamental metrics**: P/E, P/B, ROE, ROIC, margins, debt, dividends
- Daily fundamental updates from fundamentus.com.br

### News Sentiment Analysis
- **Translation pipeline**: Portuguese → English (Google Translate)
- **FinBERT sentiment analysis**: State-of-the-art financial NLP
- **Multi-source**: newsdata.io API + Google News RSS fallback
- **Smart caching**: 4h trading hours, 12h overnight
- **Two-pass processing**: Technical screening → News enhancement for top candidates (disabled in the scheduled quick monitor to respect news API limits)

### Position Sizing
- **Kelly Criterion** for optimal sizing
- **Volatility-adjusted** for risk management
- **Fundamental quality adjustments**:
  - Quality picks: +20% position boost
  - Value picks: Moderate positions (contrarian)
  - Poor fundamentals: -50% reduction
  - Avoid flag: Signal blocked

### Google Sheets Integration
- **Automatic sync** - Daily signals exported to Google Sheets
- **52 columns** - All technical + fundamental metrics
- **Historical logging** - Append-only for backtesting
- **Shared access** - Multi-user collaboration

---

## Operations (production monitoring)

| Item | Current setup |
|------|----------------|
| **Entry point** | `python scripts/quick_market_monitor.py` |
| **Universe** | Top **50** liquid tickers from `data/top_50_tickers.json` (IBOV-oriented list; `.SA` suffix applied for Yahoo Finance) |
| **Runner** | `SimpleProductionRunner` in `production_simple.py` — **BrAPI** spot prices (`src/brapi_client.py`, cache `price_cache.json`) + **yfinance** historical OHLCV |
| **Fundamentals** | On (cached files under `data/fundamentals/`) |
| **News / FinBERT** | **Off** in this path (`use_news=False`) to avoid news API rate limits |
| **Alerts** | `src/alerts/alert_generator.py` formats output (e.g. Telegram-style text) |
| **Typical schedule** | **3× on trading days** — **09:00, 14:00, 16:00** America/São Paulo (configure in your scheduler / OpenClaw cron) |

Full-universe or BrAPI-first batch jobs use other runners (see **Architecture**).

---

## Architecture

```
stock-signals/
├── production_simple.py          # SimpleProductionRunner: yfinance history + BrAPI (src.brapi_client)
├── production_brapi.py           # BrAPIProductionRunner: BrAPI-heavy path (src.data.brapi_client)
├── production_enhanced.py        # Extended / experimental production variants
├── run_production.py             # Cached-quotes production runner (src.data.brapi_client)
├── monitor_live.py               # Two-pass live monitor (legacy / alternate ops)
├── monitor_brapi.py, monitor_simple.py, monitor_market_v3.py
│
├── scripts/
│   ├── quick_market_monitor.py   # Scheduled top-50 monitor (calls production_simple)
│   ├── update_fundamentals.py    # Daily fundamentus scraper
│   ├── sheets_sync.py            # Google Sheets sync
│   └── update_ticker_list.py     # Ticker list maintenance
│
├── src/
│   ├── brapi_client.py           # BrAPI client + price_cache.json (used by production_simple)
│   ├── data/
│   │   └── brapi_client.py       # BrAPI client + historical helpers (used by production_brapi, run_production)
│   ├── signals/
│   │   └── trend_detector_v2.py  # Dual-timeframe (50d + 20d) trend detection
│   ├── fundamentals/
│   │   ├── fundamentus_scraper.py
│   │   ├── scorer.py             # Graham / Lynch / Greenblatt
│   │   └── integration.py        # Technical + fundamental blend
│   ├── news/
│   │   └── free_news_client.py   # RSS + newsdata.io + FinBERT
│   ├── indicators/               # Momentum, volatility, volume, trend, signal_fusion
│   ├── alerts/
│   │   └── alert_generator.py
│   └── config.py
│
├── data/
│   ├── top_50_tickers.json       # Liquid subset for quick_market_monitor
│   ├── validated_tickers.json    # Full IBOV + SMLL universe (see total_tickers in file)
│   ├── quotes_cache.json         # Cached quotes (BrAPI batch flows)
│   ├── full_results.json         # Latest full run results (when written)
│   └── fundamentals/
│       ├── fundamentals_cache.json
│       └── fundamental_scores.json
│
└── config/
    └── thresholds.json           # Regime / confidence thresholds
```

---

## Data flow

### A. Scheduled quick monitor (`scripts/quick_market_monitor.py`)

1. Load `data/top_50_tickers.json` → normalize to `*.SA`.
2. `SimpleProductionRunner`: parallel workers fetch history (yfinance), batch **spot** prices (BrAPI via `src/brapi_client.py`).
3. **TrendDetectorV2** + indicator fusion → technical scores.
4. **FundamentalIntegrator** reads cached fundamentus data → composite signal.
5. **No news** in this path.
6. `generate_trading_alerts(results)` → printable / sendable alert text.

### B. Full universe / alternate runners

- **`production_brapi.py`** — `BrAPIProductionRunner`: tickers from `validated_tickers.json`, BrAPI via `src.data.brapi_client`, optional news + fundamentals.
- **`run_production.py`** — uses cached `data/quotes_cache.json` + same integrator stack.
- **`production_simple.py`** — can also be called with a custom ticker list (default loader uses `validated_tickers.json`).

Shared stages: technical fusion → fundamental integration → (optional) news enrichment → signals → position sizing → optional Sheets (`scripts/sheets_sync.py`).

---

## Processing flow (conceptual)

```
┌─────────────────────────────────────────────────────────┐
│  Load tickers (top 50 OR full list from JSON)           │
└─────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────┐
│  Prices: BrAPI spot (+ yfinance or BrAPI history)       │
└─────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────┐
│  Technical stack (indicators + TrendDetectorV2 + fusion)│
└─────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────┐
│  Fundamentals: cached Graham / Lynch / Greenblatt blend │
└─────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────┐
│  News + FinBERT (optional; skipped in quick monitor)   │
└─────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────┐
│  Signals, Kelly-style sizing, alerts / Sheets           │
└─────────────────────────────────────────────────────────┘
```

---

## Signal Types

| Signal | Composite Score | Condition |
|--------|-----------------|-----------|
| STRONG_BUY | ≥ 75 | Quality fundamentals + strong technicals |
| BUY | ≥ 60 | Acceptable fundamentals |
| HOLD | 40-60 | Mixed or weak signals |
| SELL | < 40 | Poor fundamentals + weak technicals |
| STRONG_SELL | < 25 | Very poor overall |
| **AVOID** | Any | Fundamentals < 40 + Technicals < 35 (signal blocked) |

---

## Fundamental Scoring

### Graham's Defensive Investor (7-point checklist)
1. P/E ratio ≤ 15
2. P/B ratio ≤ 1.5
3. P/E × P/B ≤ 22.5 (Graham's formula)
4. Current ratio ≥ 2
5. Debt/Equity ≤ 1
6. Positive earnings
7. Dividend yield ≥ 2% (bonus)

### Lynch's GARP (PEG Analysis)
- PEG = P/E ÷ Growth Rate
- PEG < 0.5: Excellent (100 points)
- PEG < 1.0: Good (80 points)
- PEG < 1.5: Fair (60 points)
- PEG < 2.0: Poor (40 points)
- PEG ≥ 2.0: Very Poor (20 points)

### Greenblatt's Magic Formula
- Earnings Yield = EBIT / Enterprise Value
- Return on Capital (ROCIC proxy)
- Combined ranking: Lower is better

### Raw Metrics Passed to Results
All 20+ fundamental metrics are available in results:
- **Valuation**: P/E, P/B, P/FCF, EV/EBITDA
- **Profitability**: ROE, ROIC, Net Margin, EBIT Margin
- **Financial Health**: Debt/Equity, Current Ratio, Asset Turnover
- **Dividends**: Div Yield, Payout Ratio
- **Growth**: Revenue Growth, Earnings Growth

---

## Position Sizing Logic

### Kelly Criterion
```python
# Win probability
p = winning_days / total_days

# Loss probability
q = 1 - p

# Win/Loss ratio
b = avg_win / avg_loss

# Kelly fraction
kelly = (b × p - q) / b

# Half-Kelly for safety
position = kelly × 0.5 × confidence
```

### Fundamental Adjustments

| Condition | Adjustment | Reason |
|-----------|------------|--------|
| Quality pick (ROE > 20, ROIC > 15) | +20% | Compounders deserve larger position |
| Value pick (P/E < 10, P/B < 1) | 15-50% | Contrarian opportunity |
| Poor fundamentals (< 40) | -50% | Risk reduction |
| Avoid flag | 0. Blocked | No position |

---

## Quick Start

### Installation

```bash
git clone https://github.com/arnonbruno/stock-signals.git
cd stock-signals
pip install -r requirements.txt
```

### Set environment variables

```bash
# BrAPI (recommended for production; improves limits vs anonymous usage)
export BRAPI_API_KEY="your_brapi_key"

# News pipeline (only if you enable news — e.g. use_news=True)
export NEWSDATA_API_KEY="your_newsdata_io_key"

# Google Sheets sync (if using scripts/sheets_sync.py)
export GOOGLE_CREDENTIALS_PATH="/path/to/credentials.json"
```

Set keys in the environment or in a repo-root `.env` file (loaded by `python-dotenv` where supported).

### Run the quick monitor (production default)

From the repo root:

```bash
python scripts/quick_market_monitor.py
```

Uses `data/top_50_tickers.json`, fundamentals on, news off. Wire this to cron or OpenClaw on **Mon–Fri** at **09:00, 14:00, 16:00** `America/Sao_Paulo` (or your chosen slots).

### Run full-universe analysis

```python
from run_production import ProductionRunner

runner = ProductionRunner()
results = runner.run()

# Uses tickers from data/validated_tickers.json (see total_tickers in that file).
# Includes technical + fundamental scores, signals, and position sizing.
```

### Run with BrAPI-first runner

```python
from production_brapi import BrAPIProductionRunner

runner = BrAPIProductionRunner(
    use_news=True,
    use_fundamentals=True
)
results = runner.run()

# Writes consolidated outputs (e.g. data/full_results.json, quotes cache) when configured in that runner.
```

### Sync to Google Sheets

```python
from scripts.sheets_sync import SheetsSync

sync = SheetsSync(sheet_id="your_sheet_id")
sync.append_results(results)

# 52 columns per stock:
# - Ticker, Price, Date
# - Signal, Composite Score
# - Tech Score, Fund Score
# - All 20+ fundamental metrics
# - Position size, Risk level
```

### Generate Trading Alerts

```python
from src.alerts.alert_generator import generate_trading_alerts

alert = generate_trading_alerts(results, top_n=5)
print(alert)
```

---

## Configuration

### Thresholds (`config/thresholds.json`)

Regime-specific `buy_confidence`, `sell_confidence`, `min_score`, and `stop_loss` values live in this file (updated by the threshold optimizer). Open the JSON for the exact current numbers; do not rely on stale copies in docs.

### Ticker lists

| File | Purpose |
|------|---------|
| `data/top_50_tickers.json` | **Top 50** liquid names for `scripts/quick_market_monitor.py` |
| `data/validated_tickers.json` | Full **IBOV + SMLL** universe; `total_tickers` and `all_tickers` are authoritative (count changes when B3 composition is refreshed) |

Lists are verified against B3 index composition when regenerated; delisted names are removed during cleanup.

### BrAPI Config (data/brapi_config.yaml)

```yaml
api_key: "your_brapi_key"
base_url: "https://brapi.dev/api"
batch_size: 5
retry_attempts: 3
retry_delay: 0.5
```

---

## Daily jobs

### Update fundamentals (e.g. 06:00 Mon–Fri)

```bash
python scripts/update_fundamentals.py --force
```

- Scrapes fundamentus.com.br for the tickers your script configuration covers (typically the full validated universe).
- Refreshes `data/fundamentals/fundamentals_cache.json` and related score files.

### Quick market monitor (09:00, 14:00, 16:00 Mon–Fri — typical)

```bash
python scripts/quick_market_monitor.py
```

- Top 50 liquid tickers, fundamentals on, news off.

### Sync to Google Sheets (after a full production run)

```bash
python scripts/sheets_sync.py
```

- Appends rows to your configured sheet (52 columns per stock when using the standard schema).

### Example scheduler entries

```python
# OpenClaw-style examples — adjust paths and timezone to your host.
cron.add(
    name="Update Fundamentals Daily",
    schedule="0 6 * * 1-5",
    command="cd /path/to/stock-signals && python scripts/update_fundamentals.py --force"
)

cron.add(
    name="Quick Market Monitor",
    schedule="0 9,14,16 * * 1-5",
    command="cd /path/to/stock-signals && python scripts/quick_market_monitor.py"
)

cron.add(
    name="Sync to Google Sheets",
    schedule="30 10 * * 1-5",
    command="cd /path/to/stock-signals && python scripts/sheets_sync.py"
)
```

---

## Output Example

```
🚨 TOP TRADING OPPORTUNITIES
Generated: 10:15:00

1️⃣  PRIO3 - STRONG_BUY 🟢
    Price: R$55.02
    └─ Drivers:
       • Trend: UPTREND (95% confidence)
       • Fundamentals: Grade B
         P/E: 4.8 | P/B: 3.87
         ROE: 38.7% | Div: 0%
         ✅ Low P/E (4.8), High ROE (38.7%)
       • Position: 15% (HIGH conviction)
    └─ Levels:
       Entry: R$55.02 | Stop: R$49.52
       Targets: R$66.02 (2:1) | R$77.02 (3:1)

2️⃣  CURY3 - STRONG_BUY 🟢
    Price: R$41.67
    └─ Drivers:
       • Trend: UPTREND (75% confidence)
       • Fundamentals: Grade A
         P/E: 14.7 | P/B: 9.27
         ROE: 62.9% | Div: 9.4%
         ✅ High ROE (62.9%), Excellent ROIC (35.7%)
       • Position: 15% (MEDIUM conviction)

3️⃣  TGMA3 - STRONG_BUY 🟢
    Price: R$40.48
    └─ Drivers:
       • Trend: UPTREND (80% confidence)
       • Fundamentals: Grade A
         P/E: 9.7 | P/B: 2.71
         ROE: 28.0% | Div: 10.9%
         ✅ Low P/E (9.7), High ROE (28.0%)
       • Position: 15% (MEDIUM conviction)

======================================================================
📊 Summary: 17 STRONG_BUY | 43 BUY | 65 HOLD | 8 SELL | 6 STRONG_SELL
======================================================================
```

---

## Google Sheets Columns (52 total)

| Category | Columns |
|----------|---------|
| **Basic** | Date, Ticker, Price, Signal, Composite Score |
| **Technical** | Tech Score, Trend, Confidence, MA50, MA200 |
| **Fundamental Scores** | Fund Score, Graham Score, Lynch Score, Greenblatt Score |
| **Valuation** | P/E, P/B, P/S, P/FCF, EV/EBITDA, PEG |
| **Profitability** | ROE, ROIC, Net Margin, EBIT Margin, Gross Margin |
| **Financial Health** | Debt/Equity, Current Ratio, Asset Turnover |
| **Dividends** | Div Yield, Payout Ratio |
| **Growth** | Revenue Growth, Earnings Growth, Book Value Growth |
| **Position** | Position Size, Risk Level, Entry, Stop, Target |

---

## News Sources

1. **newsdata.io API** (primary)
   - 200 credits/day free tier
   - Market endpoint for financial news
   - Fallback when exhausted

2. **Google News RSS** (free fallback)
   - No API limits
   - Used when newsdata.io budget exhausted

### Translation Pipeline

Brazilian news is in Portuguese, but FinBERT is trained on English:

```python
from deep_translator import GoogleTranslator

# Translate headline before sentiment analysis
translator = GoogleTranslator(source='pt', target='en')
translated = translator.translate("Petrobras lucro recorde")
# Result: "Petrobras profit record"
```

---

## Performance (order-of-magnitude)

| Metric | Typical notes |
|--------|---------------|
| Quick monitor (50 tickers) | Faster than a full-universe pass; dominated by yfinance history + BrAPI batch |
| Full universe (`validated_tickers.json`) | Depends on worker count and runner; often tens of seconds to a few minutes |
| News enabled | Extra latency + newsdata.io quota; FinBERT can use ~500MB+ RAM |
| Parallel workers | `SimpleProductionRunner` caps at 8; quick monitor often uses 4 |
| Google Sheets sync | Roughly seconds per hundred rows depending on API |

---

## Data sources

| Data type | Source | Notes |
|-----------|--------|--------|
| Spot quotes (`production_simple`) | BrAPI via `src/brapi_client.py` | Cached in `price_cache.json` (repo root) |
| History (`production_simple`) | yfinance | Daily OHLCV for indicators |
| Quotes / history (other runners) | BrAPI (`src/data/brapi_client.py`) | See that module for endpoints and cache layout |
| Fundamentals | Fundamentus (scraped) | Daily job recommended pre-market |
| News sentiment | newsdata.io + Google News RSS + FinBERT | Optional |

---

## Logs and monitoring

- Latest batch results (when written): `data/full_results.json`
- BrAPI quote cache (batch runners): `data/quotes_cache.json`
- BrAPI spot cache (`production_simple`): `price_cache.json` (repository root)
- API budget tracker: `api_budget.json`
- News sentiment cache: `news_sentiment_cache.json`
- Fundamental cache: `data/fundamentals/fundamentals_cache.json`
- Internal review notes: `REVIEW.md`

---

## Further documentation

- Threshold tuning: [docs/threshold_optimization.md](docs/threshold_optimization.md)

---

## Branches

`master` is the integration branch for production. Use short-lived feature branches for changes; merge via pull request when collaborating.

---

## License

MIT License - See LICENSE file for details.

---

## Contributing

1. Fork the repository
2. Create a feature branch
3. Run tests: `python -m pytest tests/`
4. Submit a pull request

---

## Support

- Issues: https://github.com/arnonbruno/stock-signals/issues
- Repository: https://github.com/arnonbruno/stock-signals
- Google Sheet: https://docs.google.com/spreadsheets/d/1OGwb43E3_CCxcmuzxHuxTWR_PS6QwD7HkKIdn06sx1E/edit
