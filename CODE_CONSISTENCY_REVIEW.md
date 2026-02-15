# Code Consistency Review - stock-signals Project
**Date:** 2026-02-14  
**Scope:** All files in src/, backtest/, and tests/ directories

---

## EXECUTIVE SUMMARY

**Overall Code Health: 7/10**

The stock-signals project demonstrates a mature multi-factor signal detection system with robust trend analysis and production-ready backtesting infrastructure. However, there are several consistency issues across the codebase that could affect reliability and maintainability.

### Key Findings:
- ✅ **Strengths:** Multi-method trend detection, comprehensive error handling, realistic cost modeling
- ⚠️ **Issues:** Inconsistent signal return structures, parameter divergence, incomplete data validation
- 🔧 **Recommendations:** Standardize return types, consolidate duplicate code, improve unit test coverage

---

## PART 1: SIGNAL DETECTION LOGIC CONSISTENCY

### 1.1 Information Flow Detector (`information_flow.py`)

**File:** `/home/ulluboz/.openclaw/workspace/stock-signals/src/signals/information_flow.py`

#### Return Structure:
- `detect_volume_anomaly()`: Returns `(signal_strength: float, explanation: str)`
- `detect_volatility_regime_shift()`: Returns `(signal_strength: float, explanation: str)`
- `detect_bid_ask_expansion()`: Returns `(signal_strength: float, explanation: str)`
- `run_all()`: Returns `List[(signal_type: str, strength: float, explanation: str)]`

**Issues:**
- ❌ **Missing direction field**: Unlike momentum signals, information flow signals don't include direction (bullish/bearish)
- ⚠️ **Inconsistent tuple length**: `run_all()` returns 3-tuples while momentum returns 4-tuples
- ✅ Good: All strength values normalized to [0, 1.0]
- ✅ Good: Consistent z-score and statistical methodology

#### Parameters:
- `lookback_period = 20` (consistent across all methods)

---

### 1.2 Momentum Reversal Detector (`momentum_reversal.py`)

**File:** `/home/ulluboz/.openclaw/workspace/stock-signals/src/signals/momentum_reversal.py`

#### Return Structure:
- `detect_order_imbalance()`: Returns `(strength: float, direction: str|None, explanation: str)` → 3-tuple
- `detect_mean_reversion_extreme()`: Returns `(strength: float, direction: str|None, explanation: str)` → 3-tuple
- `detect_momentum_continuation()`: Returns `(strength: float, direction: str|None, explanation: str)` → 3-tuple
- `run_all()`: Returns `List[(type: str, strength: float, direction: str|None, explanation: str)]` → **4-tuples**

**Issues:**
- ⚠️ **Inconsistency in run_all()**: Returns 4-tuples but individual methods return 3-tuples
- ✅ Direction field included ('bullish', 'bearish', None)
- ✅ Good: Binomial test for statistical significance in order imbalance

#### Parameters:
- `lookback_period = 20` (consistent with information flow)

---

### 1.3 Trend Detection (`trend_detection.py`)

**File:** `/home/ulluboz/.openclaw/workspace/stock-signals/src/signals/trend_detection.py`

#### Inconsistencies Found:
1. **Return type mismatch in ADX method:**
   ```python
   # detect_trend_via_adx() returns: (direction: str, adx_value: float) - 2-tuple
   # But other methods return: (direction: str, strength: float) - 2-tuple
   # This is confusing because 'strength' vs 'adx_value' are different scales
   ```

2. **Direction string inconsistency:**
   - Some methods: `'uptrend'`, `'downtrend'`, `'consolidation'`
   - ADX method: `'strong_up'`, `'strong_down'`, `'weak'`
   - Price structure: `'uptrend'`, `'downtrend'`, `'consolidation'`
   - ⚠️ **Inconsistent terminology** makes consensus logic fragile

3. **Confidence/Strength measurement:**
   - slope: R-squared value (strength = |r_value|)
   - price_structure: Manual ratio-based (0-1.0)
   - adx: ADX value (0-100) with hard threshold at 25
   - ⚠️ **Non-uniform scales** complicate composite scoring

#### Parameters:
- Most use 20-day lookback
- ADX uses hard-coded 14-period for DI calculation
- ⚠️ **Parameter inconsistency**: 20 vs 14 day lookback not documented

---

### 1.4 Robust Trend Detection (`robust_trend_detection.py`)

**File:** `/home/ulluboz/.openclaw/workspace/stock-signals/src/signals/robust_trend_detection.py`

**Status:** Parallel implementation with different methodology
- Uses Theil-Sen, LOWESS, Huber regression instead of simple linear regression
- More resistant to outliers and gap moves
- ✅ Good: Documented outlier-resistant approach

**Issue:**
- ⚠️ **Code duplication**: `trend_detection.py` and `robust_trend_detection.py` both implement similar functionality
- No clear guidance on which to use in production

---

### 1.5 Ensemble Signal Generator (`ensemble_signal_generator.py`)

**File:** `/home/ulluboz/.openclaw/workspace/stock-signals/src/signals/ensemble_signal_generator.py`

**Status:** Advanced multi-method approach
- Combines 6 trend detection methods for consensus
- ✅ Good: Kalman filter, RANSAC, HP filter implementations
- ✅ Good: Confidence scoring system

**Issues:**
- ⚠️ **Method not in use**: No evidence of this being called in main backtest
- ⚠️ **Incomplete implementation**: Some methods have try-except blocks without proper fallback
- 🔧 **Recommendation**: Either integrate fully or deprecate

---

## PART 2: DATA HANDLING AND EDGE CASES

### 2.1 Data Validation

**Issue:** Inconsistent data validation across signal detectors

```python
# information_flow.py - Good practice:
if len(data) < self.lookback_period:
    return 0, "Insufficient data"

# momentum_reversal.py - Same pattern
if len(data) < self.lookback_period:
    return 0, None, "Insufficient data"

# trading_simulator.py - Weak validation:
if len(data) < 40:
    print("Insufficient data")
    return None  # Returns None instead of structured response
```

**Recommendations:**
- ✅ Standardize minimum data validation
- 🔧 Create `DataValidator` class to enforce consistent checks

### 2.2 NaN/Inf Handling

**Observations:**
- `trend_detection.py`: Checks for `== 0` (good for division by zero)
- `momentum_reversal.py`: No explicit NaN checks
- ⚠️ **Risk**: Potential for NaN propagation in statistical calculations

**Example from information_flow.py:**
```python
if std_volume <= 1e-8:  # Good: Handles near-zero std
    return 0, "No volume variation"
```

**Recommendations:**
- Add explicit NaN/Inf checks after all statistical operations
- Use pandas `dropna()` before calculations

### 2.3 Type Conversion Issues

**Found in information_flow.py:**
```python
avg_volume = float(history['Volume'].mean()) if hasattr(...) else float(...)
std_volume = float(history['Volume'].std()) if hasattr(...) else float(...)
```

⚠️ **Issue**: Defensive programming suggests underlying type issues  
🔧 **Recommendation**: Ensure DataFrames are always float64 before calculations

---

## PART 3: ERROR HANDLING AND LOGGING

### 3.1 Logging

**Current State:**
- ✅ Some modules import logging: `logger = logging.getLogger(__name__)`
- ❌ But logging is rarely used in practice
- Most errors are silently caught: `except: pass`

**Issues in production_simulator_robust.py:**
```python
try:
    info_sigs = self.info_detector.run_all(data)
    # ...
except Exception as e:
    pass  # Silent failure
```

🔧 **Recommendation:**
- Use logging instead of silent pass statements
- Add log levels: DEBUG (signal details), INFO (trades), WARNING (anomalies), ERROR (failures)

### 3.2 Exception Handling

**Pattern Observed:**
```python
try:
    trends['theil_sen'] = self._theil_sen_trend(price)
except:
    trends['theil_sen'] = 0.0  # Return neutral signal
```

✅ **Good**: Fallback to neutral (0.0) instead of failing
⚠️ **Issue**: Broad `except:` catches everything including KeyboardInterrupt
🔧 **Recommendation**: Use specific exception types

---

## PART 4: NAMING CONVENTIONS AND CODE STYLE

### 4.1 Naming Consistency

**Good patterns:**
- Signal detector classes: `InformationFlowDetector`, `MomentumReversalDetector` (consistent)
- Methods: `detect_*`, `run_*`, `get_*` (clear intent)
- Class variables: `lookback_period` (snake_case)

**Issues:**
- Method params in trend_detection: Sometimes `data`, sometimes `df`
- Signal types: `'order_imbalance'` vs `'momentum_continuation'` (inconsistent naming style)

### 4.2 Code Style (PEP 8)

✅ Generally follows PEP 8:
- 4-space indentation
- Docstrings for all public methods
- Type hints in ensemble_signal_generator but missing elsewhere

🔧 **Recommendation**: Add type hints to all signal detector methods

**Example fix:**
```python
# Current:
def detect_volume_anomaly(self, data):

# Improved:
def detect_volume_anomaly(self, data: pd.DataFrame) -> Tuple[float, str]:
```

---

## PART 5: STATISTICAL METHOD IMPLEMENTATIONS

### 5.1 Volume Z-Score Calculation

**information_flow.py:**
```python
volume_zscore = (float(recent['Volume']) - avg_volume) / std_volume
```

✅ Correct calculation  
✅ Handles std=0 case  
⚠️ Minor: Uses float() conversion which is redundant for numpy/pandas

### 5.2 Volatility Regime Detection

**issue:** Uses F-test but doesn't account for autocorrelation
```python
f_stat = (curr_returns ** 2) / (prev_returns ** 2)
p_value = 1 - stats.f.cdf(f_stat, len(history) - 1, len(prev_history) - 1)
```

✅ Proper F-test for variance  
⚠️ Returns have autocorrelation that violates F-test assumptions

### 5.3 Mean Reversion Z-Score

**momentum_reversal.py:**
```python
zscore = cum_returns / std_return if std_return > 0 else 0
```

⚠️ **Issue**: Dividing cumulative return by daily volatility is dimensionally incorrect
- Should normalize by sqrt(holding_period)

### 5.4 Order Imbalance Binomial Test

**Good:** Uses proper statistical test
```python
p_value = stats.binom_test(int(up_volume), int(total_volume), 0.5, alternative='two-sided')
```

✅ Correct hypothesis test
✅ Proper type conversion

---

## PART 6: PARAMETER CONSISTENCY

### Parameter Variance Summary

| Parameter | Information Flow | Momentum | Trend | Robust Trend |
|-----------|------------------|----------|-------|--------------|
| lookback_period | 20 | 20 | 20 | 20 |
| volatility lookback | 20 | 20 | 20 | 20 |
| ADX period | N/A | N/A | 14 (hard-coded) | 14 |
| RSI period | N/A | N/A | N/A | varies |
| Signal threshold | N/A | 0.5 (default) | N/A | 0.6 |

**Issues:**
- ⚠️ Hard-coded periods (14 for ADX) vs configurable (20 for lookback)
- 🔧 Create configuration object for all periods

### Recommended Standardization:
```python
class SignalConfig:
    lookback_period = 20
    atr_period = 14
    adx_period = 14
    mean_reversion_threshold = 2.0  # Z-score
    volume_anomaly_threshold = 2.0  # Z-score
    momentum_threshold = 0.02  # 2% price move
```

---

## PART 7: DATA HANDLING CONSISTENCY

### 7.1 Closing Position Logic

**trading_simulator.py:**
```python
if shares > 0:
    final_price = float(closes[-1])
    proceeds = shares * final_price
    cash += proceeds
```

✅ Handles open positions at end of backtest

**production_simulator_robust.py:**
Similar logic, but uses `data.iloc[-1]['Close']`

⚠️ **Inconsistency**: Some use numpy array indices, others use DataFrame iloc
🔧 **Recommendation**: Standardize to DataFrame access

### 7.2 Trade Statistics

**Issue:** Different calculators compute win_rate differently

In `trading_simulator.py`:
```python
win_rate = winning / len(trades) * 100 if trades else 0
```

In production simulators: Similar but sometimes uses `total_pnl` division

✅ Generally correct  
🔧 **Recommendation**: Create `TradeStats` class

---

## PART 8: BACKTEST FRAMEWORK ISSUES

### 8.1 Look-Ahead Bias

**trading_simulator.py:**
```python
window = data.iloc[max(0, i-window_size):i].copy()
signals = self.detect_signals(window)  # Uses current day's data
```

❌ **Critical Issue**: Uses current day's data to generate signals
- Should use only data through day i-1

**production_simulator_robust.py:**
✅ **Correct**: Uses prior day's data, trades execute next day

### 8.2 Slippage and Cost Modeling

**production_simulator_robust.py:**
```python
def apply_costs(self, price, is_entry=True):
    if is_entry:
        cost_pct = (self.spread_pct / 2 + self.slippage_pct + self.commission_pct) / 100
        return price * (1 + cost_pct)
```

✅ **Realistic**: Includes spread, slippage, and commission
✅ **Asymmetric**: Entry costs differ from exit costs

**Defaults:** commission=0.1%, spread=0.05%, slippage=0.1%

**Recommendation for Brazilian market:**
- Commission: 0.1% (standard)
- Spread: 0.2% (typical for IBOV stocks)
- Slippage: 0.1% (retail execution)

### 8.3 Position Sizing

**trading_simulator.py:**
```python
position_size = 0.5  # 50% of capital per trade
```

⚠️ **Risk**: 50% position size can lead to margin requirements
🔧 **Better**: 25-30% for retail trading

---

## PART 9: INCONSISTENCIES SUMMARY TABLE

| Issue | Severity | Files | Recommendation |
|-------|----------|-------|-----------------|
| Signal return structure mismatch | HIGH | information_flow.py, momentum_reversal.py | Standardize to 4-tuple with direction |
| Trend direction terminology | MEDIUM | trend_detection.py | Use enum instead of strings |
| Look-ahead bias | CRITICAL | trading_simulator.py | Use production_simulator_robust instead |
| Duplicate trend detection | MEDIUM | trend_detection.py, robust_trend_detection.py | Consolidate or deprecate |
| Silent exception handling | MEDIUM | All signal detectors | Add proper logging |
| Type hints missing | LOW | Most files | Add throughout codebase |
| Inconsistent data access | LOW | Backtest files | Standardize to DataFrame.iloc |
| Hard-coded parameters | MEDIUM | trend_detection.py | Create config object |

---

## PART 10: RECOMMENDATIONS FOR IMPROVEMENT

### Priority 1 (Critical):
1. **Fix look-ahead bias** - Use production_simulator_robust as template for all backtests
2. **Standardize signal returns** - Create SignalResult dataclass
3. **Consolidate trend detection** - Choose between trend_detection.py and robust_trend_detection.py

### Priority 2 (Important):
4. **Add comprehensive logging** - Replace silent exception handling with proper logging
5. **Create configuration system** - Centralize all parameters in SignalConfig class
6. **Add type hints** - Use Python 3.9+ typing throughout

### Priority 3 (Nice to have):
7. **Increase test coverage** - Current tests cover only basic functionality
8. **Add integration tests** - Test full signal flow with sample data
9. **Create style guide** - Document naming conventions and code patterns

---

## POSITIVE FINDINGS

✅ **Strengths that should be maintained:**

1. **Robust error handling pattern** - Try-except with fallback to neutral signals is sound
2. **Realistic cost modeling** - Production simulator includes spread, slippage, commission
3. **Statistical rigor** - Use of z-scores, F-tests, binomial tests for significance
4. **Multi-method approach** - Ensemble methods reduce false positives
5. **Documentation** - Good docstrings explaining the theory
6. **Modular design** - Easy to test and extend individual detectors

---

## CONCLUSION

The stock-signals codebase is **production-ready for research** but needs **standardization for production deployment**. 

**Key Metrics:**
- Code quality: 7/10 (Good structure, needs polish)
- Test coverage: 4/10 (Basic tests only)
- Documentation: 8/10 (Excellent docstrings)
- Consistency: 6/10 (Multiple implementations, parameter divergence)

**Next Steps:**
1. Choose production-grade simulator (use robust version)
2. Run Brazilian market backtest with standardized parameters
3. Compare results to IBOV baseline
4. Address critical consistency issues before production deployment

---

**Report Generated:** 2026-02-14  
**Reviewer:** Automated Code Analysis System
