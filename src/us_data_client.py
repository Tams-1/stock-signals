"""
US Market Data Client — yfinance-first for US equities.

Replaces BrAPIClient for the US market. Uses yfinance for both
historical OHLCV and real-time/spot prices, with a local price cache.

No .SA suffixes, no BrAPI dependency. Works with plain tickers:
AAPL, MSFT, NVDA, SPY, etc.
"""

import json
import logging
import math
import os
from datetime import datetime, time, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo

import pandas as pd
import yfinance as yf
import requests

CACHE_FILE = Path(__file__).parent.parent / "price_cache.json"
DEFAULT_TTL_SECONDS = 60 * 60  # 60 minutes
US_TZ = ZoneInfo("America/New_York")
MARKET_OPEN = time(9, 30)
MARKET_CLOSE = time(16, 0)
FRESH_PRICE_SECONDS = 60 * 60  # 60 min tolerance during market hours

logger = logging.getLogger(__name__)


class USDataClient:
    """Client for US stock data via yfinance with local caching."""

    def __init__(self, timeout: int = 30, cache_ttl: int = DEFAULT_TTL_SECONDS):
        self.timeout = timeout
        self.cache_ttl = cache_ttl
        self._cache = self._load_cache()

    # -- Time helpers --

    @staticmethod
    def _now_utc() -> datetime:
        return datetime.now(timezone.utc)

    @staticmethod
    def _now_us() -> datetime:
        return datetime.now(US_TZ)

    def is_market_hours(self, current_time: Optional[datetime] = None) -> bool:
        current_time = current_time.astimezone(US_TZ) if current_time else self._now_us()
        if current_time.weekday() >= 5:
            return False
        return MARKET_OPEN <= current_time.time() <= MARKET_CLOSE

    @staticmethod
    def _is_price_reasonable(price: Optional[float]) -> bool:
        if price is None:
            return False
        try:
            price = float(price)
        except (TypeError, ValueError):
            return False
        return math.isfinite(price) and price > 0.0

    @staticmethod
    def _parse_timestamp(value: Any) -> Optional[datetime]:
        if value in (None, ""):
            return None
        if isinstance(value, datetime):
            return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
        if isinstance(value, (int, float)):
            try:
                return datetime.fromtimestamp(float(value), tz=timezone.utc)
            except (TypeError, ValueError, OSError):
                return None
        if isinstance(value, str):
            try:
                cleaned = value.replace("Z", "+00:00")
                parsed = datetime.fromisoformat(cleaned)
                return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
            except ValueError:
                return None
        return None

    def _is_quote_fresh(self, quote_time: Optional[datetime]) -> bool:
        if quote_time is None:
            return not self.is_market_hours()
        if not self.is_market_hours():
            return True
        age_seconds = (self._now_utc() - quote_time.astimezone(timezone.utc)).total_seconds()
        return age_seconds <= FRESH_PRICE_SECONDS

    # -- Cache --

    def _load_cache(self) -> Dict:
        if CACHE_FILE.exists():
            try:
                with open(CACHE_FILE, "r") as f:
                    return json.load(f)
            except (json.JSONDecodeError, OSError):
                pass
        return {}

    def _save_cache(self):
        try:
            with open(CACHE_FILE, "w") as f:
                json.dump(self._cache, f, indent=2)
        except OSError as e:
            print(f"⚠️ Could not write price cache: {e}")

    def _cache_get_entry(self, ticker: str) -> Optional[Dict[str, Any]]:
        ticker = ticker.upper()
        entry = self._cache.get(ticker)
        if entry is None:
            return None
        if not self._is_price_reasonable(entry.get("price")):
            return None
        cached_ts = float(entry.get("ts", 0) or 0)
        now = self._now_utc().timestamp()
        if now - cached_ts > self.cache_ttl:
            return None
        quote_time = self._parse_timestamp(entry.get("quote_ts")) or self._parse_timestamp(cached_ts)
        if not self._is_quote_fresh(quote_time):
            return None
        return dict(entry)

    def _cache_get(self, ticker: str) -> Optional[float]:
        entry = self._cache_get_entry(ticker)
        return float(entry["price"]) if entry else None

    def _cache_put(self, ticker: str, price: float, source: str = "yfinance",
                   quote_ts: Any = None):
        ticker = ticker.upper()
        now = self._now_utc()
        quote_time = self._parse_timestamp(quote_ts) or now
        self._cache[ticker] = {
            "price": price,
            "ts": now.timestamp(),
            "updated": now.isoformat(),
            "quote_ts": quote_time.isoformat(),
            "source": source,
        }

    def get_price_snapshot(self, ticker: str) -> Optional[Dict[str, Any]]:
        return self._cache_get_entry(ticker.upper())

    # -- Price fetching --

    def get_price(self, ticker: str) -> Optional[float]:
        """Get current price for a single ticker (cache-first, then yfinance)."""
        ticker = ticker.upper()
        cached = self._cache_get(ticker)
        if cached is not None:
            return cached

        try:
            stock = yf.Ticker(ticker)
            info = stock.info or {}
            price = info.get("regularMarketPrice") or info.get("currentPrice")
            quote_time = self._parse_timestamp(info.get("regularMarketTime"))

            if self._is_price_reasonable(price):
                self._cache_put(ticker, float(price), source="yfinance", quote_ts=quote_time)
                return float(price)

            # Fallback: latest close from history
            hist = stock.history(period="5d")
            if hist is not None and not hist.empty:
                close = float(hist["Close"].iloc[-1])
                self._cache_put(ticker, close, source="yfinance_close", quote_ts=hist.index[-1])
                return close

        except Exception as e:
            logger.warning("yfinance error for %s: %s", ticker, e)

        return None

    def get_prices(self, tickers: List[str]) -> Dict[str, float]:
        """Get prices for multiple tickers (cache-first, batch yfinance fallback)."""
        prices: Dict[str, float] = {}
        need_fetch: List[str] = []

        for t in tickers:
            clean = t.upper()
            cached = self._cache_get(clean)
            if cached is not None:
                prices[clean] = cached
            else:
                need_fetch.append(clean)

        if not need_fetch:
            return prices

        # Batch fetch via yfinance
        try:
            batch = yf.download(
                tickers=" ".join(need_fetch),
                period="5d",
                progress=False,
                group_by="ticker"
            )
            if batch is not None and not batch.empty:
                if isinstance(batch.columns, pd.MultiIndex):
                    for t in need_fetch:
                        if t in batch.columns.levels[1] if hasattr(batch.columns, 'levels') else False:
                            close = batch["Close"][t].dropna()
                            if not close.empty:
                                price = float(close.iloc[-1])
                                prices[t] = price
                                self._cache_put(t, price, source="yfinance_batch", quote_ts=close.index[-1])
                else:
                    # Single ticker result
                    close = batch["Close"].dropna()
                    if not close.empty:
                        price = float(close.iloc[-1])
                        prices[need_fetch[0]] = price
                        self._cache_put(need_fetch[0], price, source="yfinance_batch", quote_ts=close.index[-1])
        except Exception as e:
            logger.warning("yfinance batch error: %s", e)

        # Individual fallback for any still missing
        for t in need_fetch:
            if t not in prices:
                p = self.get_price(t)
                if p is not None:
                    prices[t] = p

        self._save_cache()
        return prices

    def get_historical(self, ticker: str, period: str = "6mo") -> Optional[pd.DataFrame]:
        """Get historical OHLCV data for a ticker."""
        try:
            data = yf.download(ticker, period=period, progress=False)
            if data is not None and len(data) > 0:
                if isinstance(data.columns, pd.MultiIndex):
                    data.columns = data.columns.get_level_values(0)
                return data
        except Exception as e:
            logger.warning("yfinance historical error for %s: %s", ticker, e)
        return None

    def get_ticker_info(self, ticker: str) -> Optional[Dict]:
        """Get detailed ticker info (fundamentals, ratios, etc.)."""
        try:
            stock = yf.Ticker(ticker.upper())
            return stock.info or {}
        except Exception as e:
            logger.warning("yfinance info error for %s: %s", ticker, e)
        return None

    def get_fundamentals(self, ticker: str) -> Dict:
        """
        Extract key fundamental metrics from yfinance info.

        Returns a dict with standardized fields matching what
        the FundamentalIntegrator expects.
        """
        info = self.get_ticker_info(ticker) or {}
        return {
            'pe_ratio': info.get('trailingPE') or info.get('forwardPE'),
            'pb_ratio': info.get('priceToBook'),
            'roe': info.get('returnOnEquity'),
            'roic': None,  # yfinance doesn't directly provide this
            'div_yield': info.get('dividendYield'),
            'debt_equity': info.get('debtToEquity'),
            'market_cap': info.get('marketCap'),
            'eps': info.get('trailingEps'),
            'revenue_growth': info.get('revenueGrowth'),
            'profit_margins': info.get('profitMargins'),
            'current_ratio': info.get('currentRatio'),
            'free_cashflow': info.get('freeCashflow'),
            'operating_margins': info.get('operatingMargins'),
            'sector': info.get('sector'),
            'industry': info.get('industry'),
            'short_ratio': info.get('shortRatio'),
            'beta': info.get('beta'),
            'fifty_two_week_high': info.get('fiftyTwoWeekHigh'),
            'fifty_two_week_low': info.get('fiftyTwoWeekLow'),
            'name': info.get('shortName') or info.get('longName'),
        }


def main():
    """Test the US data client."""
    client = USDataClient()

    print("Fetching AAPL...")
    price = client.get_price("AAPL")
    if price:
        print(f"AAPL: ${price:.2f}")
    else:
        print("AAPL: failed to fetch")

    print("\nFetching batch...")
    tickers = ["AAPL", "MSFT", "NVDA", "GOOGL", "AMZN"]
    prices = client.get_prices(tickers)
    for ticker, p in prices.items():
        print(f"{ticker}: ${p:.2f}")

    print("\nFundamentals for AAPL...")
    fund = client.get_fundamentals("AAPL")
    for k, v in fund.items():
        if v is not None:
            print(f"  {k}: {v}")


if __name__ == "__main__":
    main()