# Stock Signals v2 - Implementation Roadmap
**Objective:** Build a hybrid market signal + news sentiment system that adapts to market regimes and beats IBOV/CDI returns.

**Status:** ⏳ IN PROGRESS (Started 2026-02-14 21:26)

---

## PHASE 1: News Sentiment Integration (Primary Signal)

### 1.1 News Data Pipeline
- [ ] **Fetch news from multiple sources**: NewsAPI + Twitter/X + MarketWatch (pt-BR)
- [ ] **Filter for Brazilian stocks + market**: Only relevant news (not global fluff)
- [ ] **Timestamp parsing**: Exact time of news publication (minute-level precision)
- [ ] **Deduplication**: Remove duplicate stories across sources
- [ ] **Status**: NOT STARTED

### 1.2 Sentiment Analysis Engine
- [ ] **Implement Portuguese NLP**: Use spaCy + translations for financial PT-BR terms
- [ ] **Sentiment scoring**: -1.0 (very bearish) to +1.0 (very bullish)
- [ ] **Financial domain tuning**: "Lucro" (profit) = +0.8, "Prejuízo" (loss) = -0.9
- [ ] **Title + Body weighting**: Title 60%, body 40% of sentiment
- [ ] **Sentiment history per stock**: Store last 10 news items with sentiment scores
- [ ] **Status**: NOT STARTED

### 1.3 News-Signal Correlation
- [ ] **Calculate news velocity**: How many stories in last 1h/4h/1d?
- [ ] **Sentiment clustering**: Group sentiment by topic (earnings, regulatory, macro, sector)
- [ ] **News-price lag analysis**: Does news sentiment precede price moves? By how much?
- [ ] **Confidence scoring**: High velocity + high sentiment agreement = high confidence
- [ ] **Status**: NOT STARTED

---

## PHASE 2: Market Regime Detection

### 2.1 Regime Classification Algorithm
- [ ] **Implement 4-method ensemble** (same as trend detector):
  - Slope analysis (20-day linear regression)
  - Moving average cross (5d/20d MA)
  - ADX (Average Directional Index)
  - Price structure (higher lows/lower highs)
- [ ] **Consensus logic**: 
  - Uptrend: 2+ methods agree on up + average slope > +0.1%/day
  - Downtrend: 2+ methods agree on down + average slope < -0.1%/day
  - Consolidation: Otherwise (range-bound, choppy)
- [ ] **Regime confidence**: 0-1.0 (how sure are we?)
- [ ] **Regime history**: Store last 60 days of regime classifications
- [ ] **Status**: NOT STARTED

### 2.2 Regime-Specific Strategy Selection
- [ ] **Uptrend mode**: 
  - Follow momentum (don't fight it)
  - Use order imbalance + momentum continuation signals
  - Ignore mean-reversion (too risky in trends)
  - Position sizing: 70% capital (aggressive)
- [ ] **Downtrend mode**:
  - Avoid longs or go short (if allowed)
  - Use volatility + trend continuation
  - Mean-reversion only for extreme oversolds (>3σ)
  - Position sizing: 30% capital (defensive)
- [ ] **Consolidation mode**:
  - Use mean-reversion (current strategy)
  - Watch for breakouts (entry points)
  - Position sizing: 50% capital (balanced)
- [ ] **Regime transitions**: How to handle regime changes mid-position?
- [ ] **Status**: NOT STARTED

---

## PHASE 3: Multi-Signal Conviction Scoring

### 3.1 Signal Aggregation Framework
- [ ] **Define signal types** (with weights TBD):
  - Technical: volume anomaly, volatility shift, order imbalance, mean-reversion, momentum
  - News: positive sentiment, negative sentiment, high velocity
  - Regime: uptrend confirmation, downtrend confirmation, consolidation confirmation
- [ ] **Combine signals**: 
  - If technical bullish + news bullish + regime bullish = very high conviction (0.8+)
  - If technical bullish but news bearish = medium conviction (0.4-0.6)
  - If signals disagree = low confidence (reject trade)
- [ ] **Conviction formula**: Weighted agreement across signal types
- [ ] **Status**: NOT STARTED

### 3.2 Position Sizing by Conviction
- [ ] **Dynamic sizing**: 
  - Conviction 0.8+: 70% of capital per position
  - Conviction 0.6-0.8: 50%
  - Conviction 0.4-0.6: 25%
  - Conviction <0.4: Skip trade (no signal)
- [ ] **Portfolio-level limits**:
  - Max 3 concurrent positions
  - Max 100% gross exposure (no leverage)
  - Min 15% cash reserve
- [ ] **Status**: NOT STARTED

---

## PHASE 4: Momentum Module (Bull Market Handling)

### 4.1 Momentum Detection
- [ ] **Price momentum**: 5-bar MA vs 20-bar MA, slope of close > +0.05%/bar
- [ ] **Volume momentum**: Recent volume > 1.2x average
- [ ] **Persistence check**: Momentum sustained for 3+ consecutive days?
- [ ] **Momentum strength**: 0-1.0 scale (how strong is it?)
- [ ] **Status**: NOT STARTED

### 4.2 Momentum Following Strategy
- [ ] **Entry conditions**: 
  - Regime = uptrend + momentum detected + news sentiment positive
  - Order: Breakout above 20-day high
- [ ] **Exit conditions**:
  - Momentum breaks (MA cross reverses)
  - Price closes below 20-day MA
  - Regime changes to consolidation/downtrend
- [ ] **Stop loss**: -3% from entry (protect against regime change)
- [ ] **Take profit**: +5% from entry (lock in gains, let winners run with trailing stop)
- [ ] **Status**: NOT STARTED

---

## PHASE 5: Real-Time Execution Framework

### 5.1 Live Monitoring System
- [ ] **Data pipeline**:
  - 1-minute price updates (yfinance)
  - News sentiment updates (hourly from NewsAPI)
  - Regime recalculation (hourly)
- [ ] **Signal generation**: Run on each update, not just daily close
- [ ] **Alert system**: 
  - High-conviction signals trigger Telegram alert
  - Show conviction score, regime, news summary
  - Allow manual confirmation before trade execution
- [ ] **Status**: NOT STARTED

### 5.2 Paper Trading Simulation
- [ ] **Live paper trader**: Track hypothetical entries/exits with realistic costs
- [ ] **Daily reporting**: P&L, win rate, signal quality vs backtest
- [ ] **Drawdown tracking**: Max drawdown, current drawdown
- [ ] **Regime tracking**: Show current regime + confidence
- [ ] **Status**: NOT STARTED

---

## PHASE 6: Backtesting & Validation

### 6.1 Historical Backtests (Multiple Periods)
- [ ] **Test Period 1**: Jan 2024 - Jun 2024 (choppy + bull mix) — *Should beat original*
- [ ] **Test Period 2**: Jul 2024 - Dec 2024 (likely continuation) — *Should beat original*
- [ ] **Test Period 3**: Jan 2025 - Feb 2025 (trending) — *Should beat original (use momentum)*
- [ ] **Test Period 4**: Feb 2025 - Feb 2026 (bull market) — *Should beat +3.68% baseline*
- [ ] **Metric per period**: Return, win rate, max drawdown, Sharpe ratio
- [ ] **Status**: NOT STARTED

### 6.2 Out-of-Sample Validation
- [ ] **Walk-forward validation**: 
  - Train on 3 months, test on 1 month (rolling window)
  - Verify edge is real, not curve-fit
- [ ] **Regime-specific validation**:
  - Backtest uptrend mode on uptrend periods only
  - Backtest consolidation mode on choppy periods only
  - Verify each regime strategy beats buy-and-hold in that regime
- [ ] **Status**: NOT STARTED

### 6.3 Comparison to Baselines
- [ ] **IBOV buy-and-hold**: How much does strategy beat it?
- [ ] **CDI (risk-free)**: Does strategy beat 10-12% baseline?
- [ ] **Mean-reversion only**: Current system performance (baseline)
- [ ] **Momentum only**: Uptrend-only strategy
- [ ] **Sentiment only**: News-based strategy (no technicals)
- [ ] **Status**: NOT STARTED

---

## PHASE 7: Code Implementation

### 7.1 New Modules
- [ ] `src/news/sentiment_analyzer.py` — News fetching + Portuguese NLP + sentiment scoring
- [ ] `src/news/news_aggregator.py` — History storage, deduplication, correlation analysis
- [ ] `src/signals/regime_detector.py` — Market regime classification (uptrend/downtrend/consolidation)
- [ ] `src/signals/momentum_detector.py` — Momentum detection + following strategy
- [ ] `src/signals/conviction_scorer.py` — Multi-signal aggregation + conviction calculation
- [ ] `src/execution/live_monitor.py` — Real-time monitoring, alerts, paper trading
- [ ] `backtest/regime_aware_backtest.py` — Backtest that accounts for regimes
- [ ] `backtest/multi_period_validator.py` — Test across Jan2024-Feb2026 periods
- [ ] **Status**: NOT STARTED

### 7.2 Integration Points
- [ ] Modify `trading_simulator.py` to accept conviction scores for dynamic position sizing
- [ ] Modify `monitor.py` to pull news + calculate sentiment
- [ ] Add regime detection to signal generation pipeline
- [ ] Add momentum module to signal detection
- [ ] **Status**: NOT STARTED

### 7.3 Unit Tests
- [ ] Test sentiment analyzer (accuracy on known bullish/bearish news)
- [ ] Test regime detector (correctly classifies uptrend/downtrend/consolidation)
- [ ] Test momentum detector (finds real momentum moves)
- [ ] Test conviction scorer (high agreement → high conviction)
- [ ] Test position sizing (conviction 0.8 → 70% allocation)
- [ ] **Status**: NOT STARTED

---

## PHASE 8: Final Integration & Deployment

### 8.1 End-to-End System Test
- [ ] **Live paper trade for 2 weeks**: 
  - Real-time news + signals
  - Verify alerts work
  - Verify paper trading matches expected behavior
  - Compare paper results to backtest
- [ ] **Debugging**: Fix any issues found in live environment
- [ ] **Status**: NOT STARTED

### 8.2 Documentation & Deployment
- [ ] **STRATEGY_DOCUMENTATION.md**: How strategy works, when it wins/loses
- [ ] **DEPLOYMENT_GUIDE.md**: How to run live monitor, interpret alerts
- [ ] **Push to GitHub**: All code, documentation, test results
- [ ] **Status**: NOT STARTED

### 8.3 Live Deployment (Optional, After Validation)
- [ ] **Start with 2-5% of capital** (as before)
- [ ] **Monitor daily**: Compare live results to paper trading
- [ ] **Scale gradually**: Only increase if live matches backtest
- [ ] **Status**: NOT STARTED

---

## SUCCESS CRITERIA

The new system succeeds when:
1. ✅ **Beats IBOV + CDI**: Average annual return > 15% (over 2024-2026 data)
2. ✅ **Adapts to regimes**: Uptrend mode outperforms consolidation mode in up markets, etc.
3. ✅ **High conviction trades work**: Conviction 0.8+ trades win >75% of time
4. ✅ **Low conviction → skip**: Conviction <0.4 trades are skipped, reducing noise
5. ✅ **News matters**: Adding sentiment data improves returns vs tech-only baseline
6. ✅ **Out-of-sample holds**: Walk-forward validation shows edge is real, not curve-fit
7. ✅ **Live paper matches backtest**: No surprises when going live

---

## Timeline Estimate
- Phase 1-2 (News + Regime): 2-3 hours
- Phase 3-4 (Conviction + Momentum): 2-3 hours
- Phase 5 (Real-time execution): 2 hours
- Phase 6 (Backtesting): 3-4 hours (data fetching, running multiple tests)
- Phase 7 (Code): 1-2 hours (integration)
- Phase 8 (Final): 2 hours (testing, docs)
- **Total: 12-17 hours of work**

---

## Notes
- This is a major redesign. The current system (mean-reversion only) will be replaced by a hybrid regime-aware system.
- News sentiment is now a PRIMARY signal, not auxiliary.
- Momentum module allows strategy to profit in bull markets (Feb2025-Feb2026 scenario).
- Walk-forward validation ensures we're not over-fitting.
- This should beat IBOV/CDI or we abandon and try something else.

**Last Updated:** 2026-02-14 21:26  
**Progress:** 0% (Planning phase)
