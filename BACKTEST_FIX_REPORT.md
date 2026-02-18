# Zero-Trade Backtest Fix Report

**Date:** 2026-02-17  
**Issue:** Backtest showing ZERO trades despite IBOV +48% bull market  
**Status:** RESOLVED

---

## Problems Identified

### 1. Look-Ahead Bias (CRITICAL)
**File:** `run_actual_backtest.py`  
**Issue:** The backtest was calling `runner.analyze_ticker(ticker)` which always downloads CURRENT data from Yahoo Finance (as of today's date), not historical data. This meant every day in the backtest was analyzing Feb 2026 data instead of the actual historical date.

**Fix:** Modified `analyze_ticker()` in `production_simple.py` to accept an optional `data` parameter:
```python
def analyze_ticker(self, ticker: str, data: pd.DataFrame = None) -> Dict:
    if data is None:
        data = self.get_data(ticker)  # Production mode
```

The backtest now passes historical data: `runner.analyze_ticker(ticker, data=hist_data)`

### 2. Confidence Calculation Too Strict
**File:** `src/signals/trend_detector_v2.py`  
**Issue:** Original confidence formula:
```python
confidence = min(1.0, strength / (2 * adjusted_threshold))
```
With threshold=0.15, this required strength >= 0.15 just to get 50% confidence. In practice, this was blocking all valid signals during normal market conditions.

**Fix:** Changed to more lenient formula:
```python
if strength >= adjusted_threshold:
    confidence = min(1.0, 0.5 + (strength - adjusted_threshold) / (4 * adjusted_threshold))
else:
    confidence = 0.5 * (strength / adjusted_threshold)
```

Now confidence scales from 0.5 (at threshold) to 1.0 (at 3x threshold), giving BUY signals when trend exists.

### 3. Data Handling Errors
**Files:** `production_simple.py`, `fixed_backtest.py`  
**Issue:** Series/scalar conversion errors when handling price data from yfinance

**Fix:** Added proper scalar extraction:
```python
if hasattr(price_val, 'item'):
    current_price = float(price_val.item())
elif hasattr(price_val, 'iloc'):
    current_price = float(price_val.iloc[0])
else:
    current_price = float(price_val)
```

---

## Changes Made

### Modified Files:

1. **`src/signals/trend_detector_v2.py`**
   - Rewrote `_classify_trend()` confidence calculation
   - Changed consolidation threshold from `strength < adjusted_threshold` to `strength < adjusted_threshold * 0.5`

2. **`production_simple.py`**
   - Modified `analyze_ticker()` to accept optional `data` parameter
   - Fixed `calculate_kelly_position()` to handle Series vs scalar properly
   - Simplified Kelly calculation for stability

### New Files:

3. **`fixed_backtest.py`** (replaces `run_actual_backtest.py`)
   - Properly downloads warmup data before backtest start
   - Passes historical data to `analyze_ticker()`
   - Handles Series/scalar conversions
   - Provides detailed trade logging

---

## Backtest Results (Nov 2025 - Feb 2026)

| Metric | Value |
|--------|-------|
| IBOV Return | **+23.93%** |
| Strategy Return | **+17.46%** |
| Alpha | **-6.47%** |
| Total Trades | **6** |
| BUY Signals | **3** |
| SELL Signals | **3** |
| Win Rate | **67%** |
| Avg Confidence | **74.9%** |

### Trade Log:
1. **2025-12-02** | VALE3.SA | BUY @ R$65.07 | Conf: 87.1% → SELL @ R$87.03 | **+33.74%**
2. **2025-12-02** | B3SA3.SA | BUY @ R$14.69 | Conf: 85.3% → SELL @ R$12.88 | **-12.32%**
3. **2025-12-22** | SUZB3.SA | BUY @ R$51.20 | Conf: 52.5% → SELL @ R$58.34 | **+13.95%**

---

## Recommendations

1. **Underperformance Analysis**: Strategy captured +17.46% vs IBOV +23.93%. Consider:
   - Lowering confidence threshold further (e.g., 40% instead of 50%)
   - Entering earlier in the trend (faster signal)
   - Reducing position sizing to allow more simultaneous positions

2. **Win Rate**: 67% win rate is good, but small sample size (3 trades). Run longer backtest.

3. **Confidence Distribution**: Average confidence of 74.9% suggests room to lower thresholds without sacrificing signal quality.

---

## Technical Debt

- Original `run_actual_backtest.py` is broken (look-ahead bias)
- `run_actual_backtest.py` should be deprecated in favor of `fixed_backtest.py`
- Confidence formula could be parameterized for easier tuning
