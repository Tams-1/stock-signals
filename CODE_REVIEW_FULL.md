# Comprehensive Code Review - Stock Signals System

**Date:** 2026-02-17  
**Reviewer:** Code Review Subagent  
**Scope:** All Python files in /home/ulluboz/.openclaw/workspace/stock-signals

---

## Executive Summary

The stock-signals codebase is a sophisticated trading signal generation system with dual-timeframe trend detection, news sentiment analysis, and risk-adjusted position sizing. While the architecture is well-designed with good separation of concerns, there are **critical issues** that must be addressed before production deployment, including potential data leakage, incorrect Kelly Criterion implementation, and missing error handling in several key areas.

**Overall Assessment:**
- Architecture: ⭐⭐⭐⭐ (4/5) - Well-structured with clear module separation
- Code Quality: ⭐⭐⭐ (3/5) - Good in places, but inconsistent error handling
- Testing: ⭐⭐⭐⭐ (4/5) - Comprehensive test coverage
- Production Readiness: ⭐⭐ (2/5) - Critical issues must be fixed

---

## Critical Issues (Must Fix Before Production)

### 1. **DATA LEAKAGE in Backtest - Look-Ahead Bias** ⚠️⚠️⚠️

**Location:** `production_simple.py` - `analyze_ticker()` method

**Issue:** The `analyze_ticker()` method downloads fresh data when `data=None`, which means in backtest mode it uses data up to "today" instead of the historical date being simulated. This creates look-ahead bias where the strategy "knows" future prices.

**Current Code:**
```python
def analyze_ticker(self, ticker: str, data: pd.DataFrame = None) -> Dict:
    try:
        # Download data if not provided (production mode)
        if data is None:
            data = self.get_data(ticker)  # <-- Downloads up to TODAY
        ...
```

**Fix:** The backtest code in `fixed_backtest.py` correctly passes historical data, but the production code should have a clear separation between "live" and "backtest" modes with explicit date bounds.

**Recommended Fix:**
```python
def analyze_ticker(self, ticker: str, data: pd.DataFrame = None, 
                   end_date: datetime = None) -> Dict:
    """
    Analyze single ticker
    
    Args:
        ticker: Stock ticker symbol
        data: Optional pre-loaded DataFrame (for backtesting)
        end_date: Optional end date for data download (for backtesting)
    """
    try:
        if data is None:
            if end_date is not None:
                # Backtest mode: download only up to end_date
                data = self.get_data(ticker, end_date=end_date)
            else:
                # Live mode: download up to today
                data = self.get_data(ticker)
        ...
```

---

### 2. **INCORRECT Kelly Criterion Implementation** ⚠️⚠️⚠️

**Location:** `production_simple.py` - `calculate_kelly_position()` method

**Issue:** The Kelly Criterion formula is mathematically incorrect. The current implementation uses a simplified heuristic that doesn't follow the actual Kelly formula: `K% = (bp - q) / b` where `b` is odds, `p` is win probability, `q` is loss probability.

**Current Code:**
```python
def calculate_kelly_position(self, data: pd.DataFrame, confidence: float) -> float:
    """
    Calculate Kelly Criterion position size based on volatility and confidence.
    Simplified version for stability.
    """
    try:
        # Calculate annualized volatility
        close_prices = data['Close'].squeeze()
        returns = close_prices.pct_change().dropna()
        
        # ... error handling ...
        
        volatility = float(np.std(returns_values) * np.sqrt(252))
        avg_daily_return = float(np.abs(np.mean(returns_values)))
        
        if volatility == 0 or avg_daily_return == 0 or np.isnan(volatility):
            return 0.20  # Default to 20% if can't calculate
        
        # Simplified Kelly: position scales with confidence and inverse volatility
        # Higher confidence = larger position
        # Higher volatility = smaller position
        base_position = confidence * 0.5  # Max 50% at full confidence
        vol_adjustment = min(1.0, 0.20 / max(0.05, volatility))
        
        position = base_position * vol_adjustment + 0.10  # Minimum 10%
        
        # Bound between 10% and 60%
        return max(0.10, min(0.60, position))
    
    except Exception as e:
        return 0.20
```

**Problems:**
1. The formula `confidence * 0.5 * vol_adjustment + 0.10` is NOT the Kelly Criterion
2. Kelly requires win probability, loss probability, and win/loss ratio - none of which are calculated
3. The "simplified Kelly" comment is misleading - this is just heuristic position sizing

**Recommended Fix:**
Rename the method to reflect what it actually does, or implement proper Kelly Criterion:

```python
def calculate_position_size(self, data: pd.DataFrame, confidence: float) -> float:
    """
    Calculate position size based on volatility and confidence.
    Uses volatility-adjusted confidence scaling (NOT Kelly Criterion).
    
    Args:
        data: Price data for volatility calculation
        confidence: Signal confidence (0-1)
    
    Returns:
        Position size (0.10 to 0.60)
    """
    try:
        returns = data['Close'].pct_change().dropna()
        volatility = returns.std() * np.sqrt(252)
        
        if pd.isna(volatility) or volatility == 0:
            return 0.20
        
        # Volatility-adjusted position sizing
        base_position = confidence * 0.5
        vol_adjustment = min(1.0, 0.20 / max(0.05, volatility))
        
        position = base_position * vol_adjustment + 0.10
        
        return max(0.10, min(0.60, position))
    
    except Exception:
        return 0.20


def calculate_kelly_position(self, data: pd.DataFrame, confidence: float) -> float:
    """
    Calculate position size using TRUE Kelly Criterion.
    
    Kelly Formula: f* = (bp - q) / b
    where: b = average win / average loss (odds)
           p = win probability
           q = 1 - p (loss probability)
    
    Uses historical returns to estimate win rate and payoff ratio.
    """
    try:
        returns = data['Close'].pct_change().dropna()
        
        if len(returns) < 30:
            return 0.20
        
        # Calculate win rate and payoff ratio
        positive_returns = returns[returns > 0]
        negative_returns = returns[returns < 0]
        
        if len(positive_returns) == 0 or len(negative_returns) == 0:
            return 0.20
        
        p = len(positive_returns) / len(returns)  # Win probability
        q = 1 - p  # Loss probability
        
        avg_win = positive_returns.mean()
        avg_loss = abs(negative_returns.mean())
        
        b = avg_win / avg_loss if avg_loss > 0 else 1.0  # Odds
        
        # Kelly formula
        kelly = (b * p - q) / b
        
        # Apply confidence weighting and bounds
        position = kelly * confidence
        
        # Half-Kelly for safety
        position = position * 0.5
        
        return max(0.10, min(0.60, position))
    
    except Exception:
        return 0.20
```

---

### 3. **Missing Error Handling in News Client** ⚠️⚠️

**Location:** `src/news/free_news_client.py` - `_fetch_newsdata_io()` method

**Issue:** The method has a hardcoded API key fallback and doesn't properly handle API rate limit errors (HTTP 429). When the API returns a 429 status, the code doesn't implement exponential backoff or proper retry logic.

**Current Code:**
```python
def _fetch_newsdata_io(self, ticker: str, date: str) -> List[Dict]:
    # ...
    # Get API key from environment variable (SECURITY FIX #13)
    import os
    api_key = os.environ.get('NEWSDATA_API_KEY', 'pub_1757f48565d149cb8e2053f54b26e977')
    
    if api_key == 'pub_1757f48565d149cb8e2053f54b26e977':
        logger.warning("⚠️ Using default API key - set NEWSDATA_API_KEY environment variable for production!")
    # ...
    try:
        response = self.session.get(url, timeout=10)
        response.raise_for_status()
        # ...
    except Exception as e:
        logger.error(f"Failed to fetch newsdata.io: {e}")
        return []
```

**Problems:**
1. Hardcoded API key is a security risk (even with warning)
2. No specific handling for HTTP 429 (rate limit) errors
3. No exponential backoff for transient failures
4. Generic exception handling loses error context

**Recommended Fix:**
```python
def _fetch_newsdata_io(self, ticker: str, date: str) -> List[Dict]:
    """
    Fetch news from newsdata.io API with proper error handling.
    
    Implements:
    - Environment-based API key (no hardcoded fallback)
    - Rate limit handling with exponential backoff
    - Specific error handling for different HTTP status codes
    """
    self._rate_limit()
    
    ticker_search = ticker.replace('.SA', '')
    
    # SECURITY: Only use environment variable, no fallback
    api_key = os.environ.get('NEWSDATA_API_KEY')
    if not api_key:
        logger.error("NEWSDATA_API_KEY environment variable not set")
        return []
    
    url = f"https://newsdata.io/api/1/news?q={ticker_search}&country=br&language=pt&apikey={api_key}"
    
    # Check budget before making request
    from src.news.api_budget_tracker import get_budget_tracker
    budget_tracker = get_budget_tracker()
    
    if not budget_tracker.can_make_request():
        logger.warning(f"API budget exhausted - cannot fetch news for {ticker_search}")
        return []
    
    # Implement retry with exponential backoff
    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = self.session.get(url, timeout=10)
            
            # Handle specific status codes
            if response.status_code == 429:
                retry_after = int(response.headers.get('Retry-After', 60))
                logger.warning(f"Rate limited (429). Retry after {retry_after}s")
                if attempt < max_retries - 1:
                    time.sleep(retry_after)
                    continue
                return []
            
            elif response.status_code == 401:
                logger.error("API key invalid (401)")
                return []
            
            elif response.status_code == 403:
                logger.error("API key quota exceeded (403)")
                return []
            
            response.raise_for_status()
            
            # Record successful call
            budget_tracker.record_call(credits_used=1, ticker=ticker_search)
            
            data = response.json()
            articles = data.get('results', [])
            
            return self._format_articles(articles)
            
        except requests.exceptions.Timeout:
            logger.warning(f"Request timeout (attempt {attempt + 1}/{max_retries})")
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)  # Exponential backoff
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Request failed: {e}")
            return []
            
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            return []
    
    return []
```

---

## Major Issues (Should Fix)

### 4. **Inconsistent Confidence Thresholds Across Files** ⚠️

**Locations:**
- `production_simple.py`: `MIN_CONFIDENCE = 0.50`
- `comprehensive_backtest.py`: `confidence >= 0.5`
- `run_backtest.py`: `confidence >= 0.6`
- `backtest_1year.py`: `confidence >= 0.6`

**Issue:** Different confidence thresholds are used across the codebase, making it difficult to reproduce results and understand the actual strategy behavior. The backtest results may not reflect production behavior.

**Recommended Fix:**
Create a centralized configuration file:

```python
# config/strategy_config.py
from dataclasses import dataclass

@dataclass
class StrategyConfig:
    """Centralized strategy configuration."""
    MIN_CONFIDENCE: float = 0.50
    MAX_POSITION_SIZE: float = 0.60
    MIN_POSITION_SIZE: float = 0.10
    KELLY_FRACTION: float = 0.5  # Half-Kelly for safety
    
    # Trend detection
    MACRO_PERIOD: int = 50
    MICRO_PERIOD: int = 20
    
    # News settings
    NEWS_CACHE_TTL_HOURS: int = 6
    MIN_NEWS_SENTIMENT: float = 0.1

# Global config instance
CONFIG = StrategyConfig()
```

---

### 5. **Hardcoded API Key in Source Code** ⚠️

**Location:** `src/news/free_news_client.py` line ~180

**Issue:** A default API key is hardcoded in the source code. While there's a warning when it's used, this is a security risk as the key could be committed to version control.

**Current Code:**
```python
api_key = os.environ.get('NEWSDATA_API_KEY', 'pub_1757f48565d149cb8e2053f54b26e977')

if api_key == 'pub_1757f48565d149cb8e2053f54b26e977':
    logger.warning("⚠️ Using default API key...")
```

**Recommended Fix:**
Remove the default value entirely:
```python
api_key = os.environ.get('NEWSDATA_API_KEY')
if not api_key:
    logger.error("NEWSDATA_API_KEY not set. News fetching disabled.")
    return []
```

---

### 6. **Missing Input Validation in Feature Engineering** ⚠️

**Location:** `src/features/feature_engineering.py`

**Issue:** Multiple methods don't validate input data before processing, which can lead to unexpected errors or NaN propagation.

**Examples:**
```python
def add_volume_features(self, data: pd.DataFrame) -> Dict:
    # No validation that data is not empty
    # No validation that Volume column exists before accessing
    volume = data['Volume']  # Will raise KeyError if missing
    ...

def add_volatility_regime(self, data: pd.DataFrame) -> Dict:
    # No validation of data length
    returns = data['Close'].pct_change().dropna()
    volatility = returns.std() * np.sqrt(252)  # Will be NaN for short data
    ...
```

**Recommended Fix:**
Add input validation decorators or explicit checks:
```python
def _validate_data(func):
    """Decorator to validate input data."""
    def wrapper(self, data, *args, **kwargs):
        if data is None or not isinstance(data, pd.DataFrame):
            raise ValueError("data must be a non-empty DataFrame")
        if len(data) < 20:
            raise ValueError(f"data must have at least 20 rows, got {len(data)}")
        return func(self, data, *args, **kwargs)
    return wrapper

class FeatureEngineer:
    @_validate_data
    def add_volume_features(self, data: pd.DataFrame) -> Dict:
        if 'Volume' not in data.columns:
            return {'volume_momentum': 1.0, 'unusual_volume': False, 'volume_trend': 'neutral'}
        ...
```

---

## Minor Issues (Nice to Have)

### 7. **Inconsistent Type Handling for Price Values**

**Location:** Multiple files (`fixed_backtest.py`, `comprehensive_backtest.py`, etc.)

**Issue:** Code repeatedly handles the yfinance MultiIndex column issue and scalar/Series price values with verbose try-except blocks.

**Current Pattern (repeated 10+ times):**
```python
price_val = data['Close'].iloc[-1]
# Handle both scalar and Series
if hasattr(price_val, 'item'):
    current_price = float(price_val.item())
elif hasattr(price_val, 'iloc'):
    current_price = float(price_val.iloc[0])
else:
    current_price = float(price_val)
```

**Recommended Fix:**
Create a utility function:
```python
# src/utils/price_utils.py
def extract_price(price_val) -> float:
    """Extract scalar price from various yfinance return types."""
    if price_val is None or (isinstance(price_val, float) and np.isnan(price_val)):
        raise ValueError("Price value is None or NaN")
    if hasattr(price_val, 'item'):
        return float(price_val.item())
    if hasattr(price_val, 'iloc'):
        return float(price_val.iloc[0])
    return float(price_val)

def normalize_columns(data: pd.DataFrame) -> pd.DataFrame:
    """Handle yfinance MultiIndex column issue."""
    if isinstance(data.columns, pd.MultiIndex):
        data.columns = data.columns.get_level_values(0)
    return data
```

---

### 8. **Missing Documentation for Complex Logic**

**Location:** `src/signals/trend_detector_v2.py` - `_get_consensus()` method

**Issue:** The consensus logic between macro and micro timeframes is complex (200+ lines of nested if-elif-else) but lacks inline comments explaining the reasoning behind each case.

**Recommendation:** Add comments explaining the logic:
```python
def _get_consensus(self, macro, macro_conf, micro, micro_conf):
    """
    Combine macro regime and micro state into consensus view.
    
    Logic:
    - Both agree → strong signal with weighted confidence
    - Macro uptrend + micro downtrend → likely pullback, not reversal
    - Macro downtrend + micro uptrend → likely bounce, be skeptical
    - Either consolidation → reduced confidence
    """
    # ... existing code with added comments for each case
```

---

### 9. **Test Files Have Production Code**

**Location:** `tests/test_production_hardening.py` (lines 800+)

**Issue:** The test file contains extensive production-like code for portfolio analysis that appears to be actual analysis code, not tests. This code runs portfolio backtests and saves results to files.

**Recommendation:** Move this code to a separate analysis script in a `scripts/` or `analysis/` directory, or convert it to proper unit tests with assertions.

---

### 10. **Unused Imports and Variables**

**Locations:** Multiple files

**Issues Found:**
- `production_simple.py`: `Pool` and `cpu_count` imported but `n_workers` not actually used for parallel processing
- `comprehensive_backtest.py`: `json` imported but not used
- `monitor_market_v3.py`: `timedelta` imported but not used

**Recommendation:** Run `flake8` or `pylint` to identify and remove unused imports.

---

## Recommended Fixes Priority Order

### Phase 1: Critical (Before Production)
1. **Fix data leakage** in `analyze_ticker()` - Add explicit date bounds parameter
2. **Fix or rename Kelly Criterion** - Either implement proper Kelly or rename to "volatility-adjusted position sizing"
3. **Remove hardcoded API key** - Require environment variable
4. **Add input validation** to feature engineering methods

### Phase 2: Major (Within 1 Week)
5. **Standardize confidence thresholds** - Create centralized config
6. **Add proper error handling** for news API rate limits (429 errors)
7. **Create utility functions** for price extraction to reduce code duplication
8. **Add comprehensive docstrings** to complex logic

### Phase 3: Minor (Within 1 Month)
9. **Clean up unused imports**
10. **Move analysis code out of test files**
11. **Add type hints** to all public methods
12. **Set up linting** (flake8, black) in CI/CD

---

## Code Examples for Key Fixes

### Fix 1: Data Leakage Prevention

```python
# In production_simple.py

class SimpleProductionRunner:
    def __init__(self, use_news: bool = True, n_workers: int = None, 
                 backtest_mode: bool = False):
        self.backtest_mode = backtest_mode
        # ... rest of init
    
    def analyze_ticker(self, ticker: str, data: pd.DataFrame = None,
                       as_of_date: datetime = None) -> Dict:
        """
        Analyze single ticker.
        
        Args:
            ticker: Stock ticker symbol
            data: Optional pre-loaded DataFrame (for backtesting)
            as_of_date: Date to analyze as-of (for backtesting, uses historical data only)
        """
        try:
            if data is None:
                if self.backtest_mode and as_of_date is not None:
                    # Backtest: only get data up to as_of_date
                    data = self.get_data(ticker, end_date=as_of_date)
                else:
                    # Live mode: get latest data
                    data = self.get_data(ticker)
            
            if data is None or len(data) < 50:
                return None
            
            # ... rest of analysis
```

### Fix 2: Proper Kelly Criterion

```python
def calculate_kelly_position(self, data: pd.DataFrame, confidence: float) -> float:
    """
    Calculate position size using TRUE Kelly Criterion with confidence adjustment.
    
    Kelly Formula: f* = (bp - q) / b
    where: b = average win / average loss (odds)
           p = win probability
           q = 1 - p (loss probability)
    
    Uses Half-Kelly for safety: position = 0.5 * kelly * confidence
    """
    try:
        returns = data['Close'].pct_change().dropna()
        
        if len(returns) < 30:
            return 0.20
        
        # Separate positive and negative returns
        positive = returns[returns > 0]
        negative = returns[returns < 0]
        
        if len(positive) == 0 or len(negative) == 0:
            return 0.20
        
        # Calculate Kelly parameters
        p = len(positive) / len(returns)  # Win probability
        q = 1 - p
        
        avg_win = positive.mean()
        avg_loss = abs(negative.mean())
        
        if avg_loss == 0:
            return 0.20
        
        b = avg_win / avg_loss  # Odds
        
        # Kelly formula
        kelly = (b * p - q) / b
        
        # Apply confidence weighting and Half-Kelly for safety
        position = kelly * confidence * 0.5
        
        # Bounds
        return max(0.10, min(0.60, position))
    
    except Exception:
        return 0.20
```

---

## Summary

This codebase represents a well-architected trading signal system with good test coverage and thoughtful design. However, **the critical issues around data leakage and incorrect Kelly Criterion implementation must be fixed before any production deployment**. These issues could lead to:

1. **Overstated backtest performance** due to look-ahead bias
2. **Incorrect position sizing** that doesn't actually optimize growth
3. **Security vulnerabilities** from exposed API keys

The recommended fixes are provided above with complete code examples. Addressing these issues will significantly improve the reliability and accuracy of the trading system.
