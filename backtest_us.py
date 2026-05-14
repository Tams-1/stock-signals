#!/usr/bin/env python3
"""
US Market Backtest: Active Strategy vs S&P 500 (SPY)

Compares the stock signals system against a passive buy & hold of SPY.
Uses price-based sentiment proxy (no look-ahead bias).

Periods:
  1Y: Recent bull/sideways
  2Y: Full cycle
  COVID: Mar-May 2020 stress test

Usage:
  python3 backtest_us.py --period 1y
  python3 backtest_us.py --period 2y
  python3 backtest_us.py --period covid
  python3 backtest_us.py --period all
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import argparse
import warnings
warnings.filterwarnings('ignore')

from src.signals.trend_detector_v2 import TrendDetectorV2

# Major US stocks — diverse sectors
TEST_TICKERS = [
    "AAPL", "MSFT", "GOOGL", "AMZN",    # Tech mega
    "JPM", "BAC", "V",                   # Financials
    "JNJ", "UNH", "PFE",                 # Healthcare
    "XOM", "CVX",                        # Energy
    "PG", "KO", "WMT",                   # Consumer defensive
    "HD", "MCD", "NKE",                  # Consumer cyclical
    "CAT", "GE", "BA",                   # Industrials
]

BENCHMARK = "SPY"  # S&P 500 ETF

# Period configs
PERIODS = {
    "1y": {"start": None, "end": datetime.now(), "label": "1 Year"},
    "2y": {"start": None, "end": datetime.now(), "label": "2 Years"},
    "covid": {"start": datetime(2020, 1, 2), "end": datetime(2020, 6, 1), "label": "COVID Crash"},
    "2023": {"start": datetime(2023, 1, 2), "end": datetime(2023, 12, 29), "label": "2023 Rally"},
    "bear22": {"start": datetime(2022, 1, 3), "end": datetime(2022, 12, 30), "label": "2022 Bear Market"},
}


def calculate_price_sentiment(data: pd.DataFrame, lookback: int = 10) -> float:
    """
    Calculate sentiment proxy from price action (no look-ahead bias).
    Replaces news sentiment in backtest mode.
    """
    if len(data) < lookback:
        return 0.0
    if isinstance(data.columns, pd.MultiIndex):
        data = data.copy()
        data.columns = data.columns.get_level_values(0)

    recent = data.tail(lookback)
    returns = recent['Close'].pct_change().dropna()
    if len(returns) == 0:
        return 0.0

    momentum = np.clip(returns.mean() * 50, -1, 1)

    volume_factor = 0
    if 'Volume' in data.columns and data['Volume'].notna().sum() > lookback:
        vol_ratio = recent['Volume'].mean() / data['Volume'].tail(lookback * 3).mean()
        volume_factor = np.clip(vol_ratio - 1, 0, 2) if vol_ratio > 0 else 0

    vol_dampener = max(0.5, 1 - returns.std() * 25) if len(returns) > 2 else 1.0

    return np.clip(momentum * (1 + volume_factor * 0.3) * vol_dampener, -1, 1)


class PassiveBenchmark:
    """Buy & hold SPY for the entire period."""

    def __init__(self, initial_capital: float = 10000):
        self.initial_capital = initial_capital
        self.history = []

    def run(self, spy_data: pd.DataFrame) -> dict:
        spy = spy_data.copy()
        if isinstance(spy.columns, pd.MultiIndex):
            spy.columns = spy.columns.get_level_values(0)

        first_price = float(spy['Close'].iloc[0])
        shares = self.initial_capital / first_price
        last_price = float(spy['Close'].iloc[-1])
        final_value = shares * last_price
        ret = (final_value / self.initial_capital - 1) * 100

        # Daily series
        spy['value'] = spy['Close'] * shares
        daily_returns = spy['Close'].pct_change().dropna()
        sharpe = np.sqrt(252) * daily_returns.mean() / daily_returns.std() if daily_returns.std() > 0 else 0
        dd = (spy['value'] / spy['value'].cummax() - 1).min() * 100

        return {
            "strategy": "SPY (Buy & Hold)",
            "initial": self.initial_capital,
            "final": round(final_value, 2),
            "return_pct": round(ret, 2),
            "sharpe": round(sharpe, 2),
            "max_drawdown_pct": round(dd, 2),
            "trades": 1,
            "win_rate": 100.0 if ret > 0 else 0.0,
            "history": spy[['Close', 'value']].copy(),
        }


class USActiveStrategy:
    """Active US stock signals strategy."""

    def __init__(self, tickers: list, initial_capital: float = 10000):
        self.tickers = tickers
        self.initial_capital = initial_capital
        self.per_stock = initial_capital / len(tickers)

        self.trend_detector = TrendDetectorV2()

        self.cash = initial_capital
        self.positions = {}  # ticker -> {'shares': x, 'cost_basis': y}
        self.trades = []
        self.history = []
        self.price_cache = {}

    def _get_historical(self, ticker: str, end_date) -> pd.DataFrame:
        """Fetch yfinance data up to a specific date."""
        cache_key = (ticker, str(end_date.date()))
        if cache_key in self.price_cache:
            return self.price_cache[cache_key]

        start = end_date - timedelta(days=400)
        data = yf.download(
            ticker, start=start.strftime('%Y-%m-%d'),
            end=end_date.strftime('%Y-%m-%d'), progress=False
        )
        if data is not None and len(data) > 0:
            if isinstance(data.columns, pd.MultiIndex):
                data.columns = data.columns.get_level_values(0)
            self.price_cache[cache_key] = data
            return data
        return None

    def analyze_stock(self, ticker: str, current_date) -> dict:
        """Analyze a stock at a point in time using only technical analysis.

        No fundamentals — they'd introduce look-ahead bias in backtest mode
        since yfinance returns CURRENT data even for historical dates.
        """
        data = self._get_historical(ticker, current_date)
        if data is None or len(data) < 60:
            return {'signal': 'HOLD', 'score': 50, 'conviction': 0}

        # Trend
        trend_result = self.trend_detector.detect_trend(data)
        consensus = trend_result.get('consensus', 'unknown')
        confidence = trend_result.get('confidence', 0.0)

        trend = 'uptrend' if consensus in ('uptrend', 'bull_pullback') else \
                'downtrend' if consensus in ('downtrend', 'bear_bounce') else 'consolidation'

        # Price sentiment (replaces news — no look-ahead, uses only past prices)
        sentiment = calculate_price_sentiment(data)
        confidence *= (1 + sentiment * 0.15)

        tech_score = confidence * 100

        # Only technical analysis in backtest (fundamentals would introduce look-ahead bias)
        # Use a slightly lower composite threshold since we're tech-only
        composite = tech_score

        # Signal
        if composite >= 60:
            signal = 'STRONG_BUY'
        elif composite >= 45:
            signal = 'BUY'
        elif composite >= 25:
            signal = 'HOLD'
        elif composite >= 15:
            signal = 'SELL'
        else:
            signal = 'STRONG_SELL'

        return {'signal': signal, 'score': composite, 'conviction': confidence,
                'trend': trend, 'price': float(data['Close'].iloc[-1])}

    def _get_price(self, date, price_data: dict, ticker: str) -> float:
        """Get price for a ticker on a date, handling yfinance MultiIndex."""
        try:
            df = price_data[ticker]
            if date not in df.index:
                # Use nearest available date
                dates = df.index[df.index <= date]
                if len(dates) == 0:
                    return 0.0
                date = dates[-1]
            px = df.loc[date, 'Close']
            if isinstance(px, pd.Series):
                return float(px.iloc[0]) if not px.empty else 0.0
            return float(px)
        except (KeyError, TypeError, ValueError):
            return 0.0

    def execute_trades(self, date, analyses: dict, price_data: dict):
        """Execute trades based on analysis results for a rebalance date.

        Cash logic:
          - cash starts at initial_capital and decreases on buys, increases on sells
          - portfolio_value = cash + sum(position_values)
        """
        # First, sell any positions that have SELL signals
        for ticker, pos in list(self.positions.items()):
            if ticker not in analyses:
                continue
            signal = analyses[ticker]['signal']
            price = self._get_price(date, price_data, ticker)
            if price <= 0:
                continue

            if signal in ('SELL', 'STRONG_SELL'):
                trade_value = pos['shares'] * price
                pnl = (price - pos['cost_basis']) / pos['cost_basis'] * 100
                self.cash += trade_value
                del self.positions[ticker]
                self.trades.append({
                    'date': date, 'ticker': ticker, 'action': 'SELL',
                    'price': price, 'shares': pos['shares'],
                    'value': trade_value, 'pnl_pct': round(pnl, 2),
                    'signal': signal
                })

        # Calculate how much each BUY signal should get
        buy_signals = [t for t in self.tickers if t in analyses
                       and analyses[t]['signal'] in ('STRONG_BUY', 'BUY')
                       and t not in self.positions]

        if buy_signals and self.cash > 0:
            # Split cash among new buys (20% per strong buy, 12% per buy)
            weights = {}
            total_w = 0
            for t in buy_signals:
                w = 0.20 if analyses[t]['signal'] == 'STRONG_BUY' else 0.12
                weights[t] = w
                total_w += w

            for t in buy_signals:
                price = self._get_price(date, price_data, t)
                if price <= 0:
                    continue

                alloc = self.cash * (weights[t] / total_w)
                shares = alloc / price
                self.positions[t] = {'shares': shares, 'cost_basis': price}
                self.cash -= alloc
                self.trades.append({
                    'date': date, 'ticker': t, 'action': 'BUY',
                    'price': price, 'shares': shares,
                    'value': alloc, 'signal': analyses[t]['signal']
                })

    def run(self, start_date, end_date, price_data: dict) -> dict:
        """Run active strategy over period with monthly rebalance."""
        print(f"\n🤖 Active Strategy: {len(self.tickers)} tickers")
        print(f"   Initial capital: ${self.initial_capital:,.0f}")
        print(f"   Rebalancing: Monthly")
        print(f"   Period: {start_date.date()} to {end_date.date()}")

        # Generate rebalance dates (monthly)
        rebalance_dates = pd.date_range(start=start_date, end=end_date, freq='MS')
        if len(rebalance_dates) == 0:
            rebalance_dates = [start_date]

        progress_step = max(1, len(rebalance_dates) // 10)

        for i, rdate in enumerate(rebalance_dates):
            if i % progress_step == 0:
                print(f"   Progress: {i}/{len(rebalance_dates)} months...", end="\r")

            analyses = {}
            for ticker in self.tickers:
                try:
                    analyses[ticker] = self.analyze_stock(ticker, rdate)
                except Exception:
                    pass

            self.execute_trades(rdate, analyses, price_data)

            # Track portfolio value (cash + positions)
            total_value = self.cash
            for ticker, pos in self.positions.items():
                price = self._get_price(rdate, price_data, ticker)
                if price > 0:
                    total_value += pos['shares'] * price

            self.history.append({'date': rdate, 'value': total_value})

        print(f"   Progress: {len(rebalance_dates)}/{len(rebalance_dates)} months... ✅")

        # Results
        final_value = self.history[-1]['value'] if self.history else self.initial_capital
        ret = (final_value / self.initial_capital - 1) * 100

        # Performance metrics
        series = pd.DataFrame(self.history).set_index('date')
        daily_ret = series['value'].pct_change().dropna()
        sharpe = np.sqrt(12) * daily_ret.mean() / daily_ret.std() if daily_ret.std() > 0 else 0
        dd = (series['value'] / series['value'].cummax() - 1).min() * 100

        # Win rate
        buys = [t for t in self.trades if t['action'] == 'SELL']
        wins = [t for t in buys if t.get('pnl_pct', 0) > 0]
        win_rate = len(wins) / len(buys) * 100 if buys else 0

        return {
            "strategy": "Stock Signals (Active)",
            "initial": self.initial_capital,
            "final": round(final_value, 2),
            "return_pct": round(ret, 2),
            "sharpe": round(sharpe, 2),
            "max_drawdown_pct": round(dd, 2),
            "trades": len(self.trades),
            "buys": len([t for t in self.trades if t['action'] == 'BUY']),
            "sells": len([t for t in self.trades if t['action'] == 'SELL']),
            "win_rate": round(win_rate, 1),
            "pos_ratio": f"{len(wins)}/{len(buys)}" if buys else "N/A",
        }


def fetch_period_data(tickers: list, start: datetime, end: datetime) -> dict:
    """Fetch price data for all tickers + SPY over a period."""
    all_tickers = list(set(tickers + [BENCHMARK]))
    print(f"📥 Fetching data for {len(all_tickers)} tickers ({start.date()} to {end.date()})...")

    data = {}
    for t in all_tickers:
        df = yf.download(t, start=start.strftime('%Y-%m-%d'),
                         end=end.strftime('%Y-%m-%d'), progress=False)
        if df is not None and len(df) > 0:
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            data[t] = df

    print(f"   ✅ {len(data)}/{len(all_tickers)} loaded")
    return data


def run_backtest(period_key: str):
    """Run full backtest for a period."""
    cfg = PERIODS[period_key]
    label = cfg['label']

    end = cfg['end']
    if period_key == "1y":
        start = end - timedelta(days=365)
    elif period_key == "2y":
        start = end - timedelta(days=730)
    else:
        start = cfg['start']

    print(f"\n{'='*70}")
    print(f"📊 US BACKTEST: {label}")
    print(f"{'='*70}")
    print(f"Active: Stock Signals | Passive: {BENCHMARK}")

    # Fetch data
    price_data = fetch_period_data(TEST_TICKERS, start, end)

    if BENCHMARK not in price_data:
        print(f"❌ Failed to fetch {BENCHMARK} data")
        return None

    # Passive strategy
    passive = PassiveBenchmark()
    passive_result = passive.run(price_data[BENCHMARK])

    # Active strategy
    active = USActiveStrategy(TEST_TICKERS)
    active_result = active.run(start, end, price_data)

    # Comparison
    print(f"\n{'='*70}")
    print(f"📊 RESULTS: {label}")
    print(f"{'='*70}")

    results = [active_result, passive_result]
    print(f"\n{'Metric':25s} {'Active':>15s} {'SPY (Passive)':>15s}")
    print(f"{'-'*25} {'-'*15} {'-'*15}")
    print(f"{'Initial Capital':25s} {'$'+str(results[0]['initial']):>15s} {'$'+str(results[1]['initial']):>15s}")
    print(f"{'Final Value':25s} {'$'+str(results[0]['final']):>15s} {'$'+str(results[1]['final']):>15s}")
    print(f"{'Return':25s} {str(results[0]['return_pct'])+'%':>15s} {str(results[1]['return_pct'])+'%':>15s}")
    print(f"{'Sharpe Ratio':25s} {str(results[0]['sharpe']):>15s} {str(results[1]['sharpe']):>15s}")
    print(f"{'Max Drawdown':25s} {str(results[0]['max_drawdown_pct'])+'%':>15s} {str(results[1]['max_drawdown_pct'])+'%':>15s}")
    print(f"{'Total Trades':25s} {str(results[0]['trades']):>15s} {'1':>15s}")
    print(f"{'Win Rate':25s} {str(results[0]['win_rate'])+'%':>15s} {'100%' if results[1]['return_pct'] > 0 else '0%':>15s}")

    # Alpha
    alpha = results[0]['return_pct'] - results[1]['return_pct']
    print(f"\n{'📈 ALPHA (Active - Passive)':25s} {'+' if alpha > 0 else ''}{alpha:.2f}%")
    print(f"{'📊 VERDICT':25s} {'✅ OUTPERFORMS' if alpha > 0 else '❌ UNDERPERFORMS'}")

    return {
        'period': label,
        'active': active_result,
        'passive': passive_result,
        'alpha_pct': round(alpha, 2),
    }


def run_all():
    """Run backtests for all periods."""
    results = {}
    for key in PERIODS:
        r = run_backtest(key)
        if r:
            results[key] = r

    print(f"\n\n{'='*70}")
    print(f"🏆 BACKTEST SUMMARY — ALL PERIODS")
    print(f"{'='*70}")
    print(f"\n{'Period':15s} {'Active':>10s} {'SPY':>10s} {'Alpha':>10s} {'Sharpe(A)':>10s} {'Sharpe(P)':>10s} {'DD(A)':>8s} {'DD(P)':>8s}")
    print(f"{'-'*15} {'-'*10} {'-'*10} {'-'*10} {'-'*10} {'-'*10} {'-'*8} {'-'*8}")
    for key, r in results.items():
        a = r['active']
        p = r['passive']
        alpha = r['alpha_pct']
        print(f"{PERIODS[key]['label']:15s} {str(a['return_pct'])+'%':>10s} {str(p['return_pct'])+'%':>10s} "
              f"{('+' if alpha > 0 else '')+str(alpha)+'%':>10s} {str(a['sharpe']):>10s} {str(p['sharpe']):>10s} "
              f"{str(a['max_drawdown_pct'])+'%':>8s} {str(p['max_drawdown_pct'])+'%':>8s}")
    print()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='US Market Backtest')
    parser.add_argument('--period', choices=list(PERIODS.keys()) + ['all'], default='all',
                       help='Backtest period')
    args = parser.parse_args()

    if args.period == 'all':
        run_all()
    else:
        run_backtest(args.period)