#!/usr/bin/env python3
"""
US Market Production Runner — yfinance-first for US equities.

Replaces the Brazilian-market production_simple.py for the US market.
Key differences:
  - No BrAPI dependency (pure yfinance)
  - No .SA suffix handling
  - Market index: ^GSPC (S&P 500) instead of ^BVSP
  - Fundamentals from yfinance .info instead of Fundamentus
  - Liquidity thresholds in USD
  - S&P 500 / NASDAQ 100 ticker universe
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import argparse
from typing import Dict, List, Optional, Tuple
import json
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

from src.signals.trend_detector_v2 import TrendDetectorV2
from src.news.free_news_client import FreeNewsClient
from src.features.feature_engineering import get_feature_engineer
from src.fundamentals.us_integration import USFundamentalIntegrator
from src.indicators.signal_fusion import fuse_all_signals
from src.us_data_client import USDataClient
from src.alerts.alert_generator import generate_trading_alerts
from src.strategy.regime_detection import get_regime_detector, get_adaptive_params

# US Market index for regime detection
US_MARKET_INDEX = "^GSPC"  # S&P 500


# -- US-specific thresholds --
def _load_us_thresholds() -> Dict:
    """Load US market thresholds from config."""
    config_path = Path(__file__).parent / 'config' / 'us_thresholds.json'
    defaults = {
        'buy_confidence': 0.45, 'sell_confidence': 0.40,
        'min_score': 0.25, 'stop_loss': 0.08,
        'max_position_pct': 0.50, 'min_position_pct': 0.05,
        'default_position_pct': 0.15, 'kelly_fraction': 0.40,
        'max_portfolio_exposure': 0.75,
        'min_skip_turnover_usd': 10_000_000,
        'min_downgrade_turnover_usd': 50_000_000,
    }
    if config_path.exists():
        try:
            with open(config_path, 'r') as f:
                data = json.load(f)
            th = data.get('thresholds', {})
            ps = data.get('position_sizing', {})
            liq = data.get('liquidity', {})
            defaults.update({
                'buy_confidence': th.get('default', {}).get('buy_confidence', defaults['buy_confidence']),
                'sell_confidence': th.get('default', {}).get('sell_confidence', defaults['sell_confidence']),
                'min_score': th.get('default', {}).get('min_score', defaults['min_score']),
                'stop_loss': th.get('default', {}).get('stop_loss', defaults['stop_loss']),
                'max_position_pct': ps.get('max_position_pct', defaults['max_position_pct']),
                'min_position_pct': ps.get('min_position_pct', defaults['min_position_pct']),
                'default_position_pct': ps.get('default_position_pct', defaults['default_position_pct']),
                'kelly_fraction': ps.get('kelly_fraction', defaults['kelly_fraction']),
                'max_portfolio_exposure': ps.get('max_portfolio_exposure', defaults['max_portfolio_exposure']),
                'min_skip_turnover_usd': liq.get('min_skip_turnover_usd', defaults['min_skip_turnover_usd']),
                'min_downgrade_turnover_usd': liq.get('min_downgrade_turnover_usd', defaults['min_downgrade_turnover_usd']),
            })
        except Exception as e:
            print(f"⚠️ Error loading US thresholds: {e}")
    return defaults


_US_THRESHOLDS = _load_us_thresholds()

# Default US ticker universe (S&P 500 top liquid names)
SP500_TOP_TICKERS = [
    "AAPL", "MSFT", "NVDA", "GOOGL", "AMZN", "META", "BRK-B", "LLY", "AVGO", "TSLA",
    "JPM", "V", "XOM", "UNH", "MA", "PG", "COST", "JNJ", "HD", "MRK",
    "ABBV", "CVX", "CRM", "BAC", "WMT", "NFLX", "AMD", "KO", "PEP", "ADBE",
    "TMO", "DIS", "WFC", "CSCO", "MCD", "ABT", "ACN", "DHR", "VZ", "LIN",
    "CMCSA", "TXN", "NEE", "PM", "IBM", "QCOM", "INTU", "AMGN", "UBER", "GE",
    "GS", "CAT", "RTX", "SPGI", "LOW", "MS", "PFE", "BLK", "AXP", "C",
    "SYK", "SCHW", "BKNG", "DE", "UNP", "PLD", "AMAT", "GILD", "ADP", "TMUS",
    "MDT", "ISRG", "TJX", "MU", "LRCX", "ELV", "CI", "REGN", "VRTX", "HCA",
    "MMC", "CB", "PGR", "ICE", "CME", "ZTS", "EOG", "COP", "SLB", "NSC",
    "FISV", "KLAC", "ITW", "BDX", "APD", "TGT", "AON", "MCO", "SHW", "ECL",
]

# NASDAQ 100 additions (tech-heavy)
NASDAQ_100_ADDITIONS = [
    "MELI", "CRWD", "PANW", "SNPS", "CDNS", "ADSK", "WDAY", "DDOG", "TEAM",
    "ZS", "NET", "MDB", "TTD", "CPRT", "FAST", "PAYX", "CTAS", "BKR", "ODFL",
    "ROST", "MAR", "HLT", "LULU", "SBUX", "MNST", "KDP", "CHTR", "ANSS",
    "IDXX", "DXCM", "ILMN", "ALGN", "VRSK", "VRSN", "FOXA", "FOX", "NWS",
    "NWSA", "AEP", "PCG", "EXC", "XEL", "ED", "EIX", "WBD", "SIRI",
]

# Combined universe
US_TICKER_UNIVERSE = sorted(set(SP500_TOP_TICKERS + NASDAQ_100_ADDITIONS))


def load_us_tickers() -> List[str]:
    """Load US tickers from config file or use default universe."""
    config_path = Path(__file__).parent / 'data' / 'us_tickers.json'
    if config_path.exists():
        with open(config_path, 'r') as f:
            data = json.load(f)
        tickers = data.get('tickers', [])
        if tickers:
            return tickers
    return US_TICKER_UNIVERSE


class USProductionRunner:
    """
    End-to-end US market pipeline: indicators + TrendDetectorV2 + optional news +
    US fundamentals (yfinance .info), then signals and sizing.
    """

    # Class-level model cache
    _model_cache = {}
    MIN_SKIP_TURNOVER_USD = _US_THRESHOLDS.get('min_skip_turnover_usd', 10_000_000)
    MIN_DOWNGRADE_TURNOVER_USD = _US_THRESHOLDS.get('min_downgrade_turnover_usd', 50_000_000)

    def __init__(self, use_news: bool = True, use_fundamentals: bool = True,
                 n_workers: int = None, ticker_list: List[str] = None):
        self.trend_detector = TrendDetectorV2()
        self.use_news = use_news
        self.use_fundamentals = use_fundamentals

        from multiprocessing import cpu_count
        max_workers = min(cpu_count(), 8)
        self.n_workers = min(n_workers, max_workers) if n_workers else max_workers

        # US data client (yfinance-first)
        self.data_client = USDataClient()
        self._spot_prices: Dict[str, float] = {}
        self._price_snapshots: Dict[str, Dict] = {}

        if use_news:
            if 'news_client' not in self._model_cache:
                self._model_cache['news_client'] = FreeNewsClient()
            self.news_client = self._model_cache['news_client']

        if use_fundamentals:
            self.fundamental_integrator = USFundamentalIntegrator()

        # Market regime detection on S&P 500
        self.regime_detector = get_regime_detector()
        self.adaptive_params = get_adaptive_params()
        self.current_regime = 'sideways'
        self.regime_strength = 0.5
        self.regime_params = {}

        # Ticker universe
        self.tickers = ticker_list or load_us_tickers()

        print(f"✅ US System initialized (news={'ON' if use_news else 'OFF'}, "
              f"fundamentals={'ON' if use_fundamentals else 'OFF'}, "
              f"universe={len(self.tickers)} tickers, workers={self.n_workers})")
        print(f"   Thresholds: buy={_US_THRESHOLDS['buy_confidence']}, "
              f"sell={_US_THRESHOLDS['sell_confidence']}, "
              f"min_score={_US_THRESHOLDS['min_score']}")

    @staticmethod
    def _normalize_data(data: pd.DataFrame) -> pd.DataFrame:
        if isinstance(data.columns, pd.MultiIndex):
            data = data.copy()
            data.columns = data.columns.get_level_values(0)
        return data

    def _fetch_market_data(self, as_of_date=None) -> pd.DataFrame:
        """Fetch S&P 500 index data for market regime detection."""
        try:
            if as_of_date:
                end = as_of_date.strftime('%Y-%m-%d') if hasattr(as_of_date, 'strftime') else str(as_of_date)
                spx = yf.download(US_MARKET_INDEX, period='2y', progress=False, end=end)
            else:
                spx = yf.download(US_MARKET_INDEX, period='2y', progress=False)
            if spx is not None and len(spx) > 0:
                if isinstance(spx.columns, pd.MultiIndex):
                    spx.columns = spx.columns.get_level_values(0)
                return spx
        except Exception as e:
            if not as_of_date:
                print(f"\n⚠️ Could not fetch S&P 500 for regime detection: {e}")
        return None

    def detect_market_regime(self, as_of_date=None) -> Dict:
        """Detect US market regime from S&P 500 index."""
        spx = self._fetch_market_data(as_of_date=as_of_date)
        if spx is None or len(spx) < 50:
            if not as_of_date:
                print("   [REGIME] No S&P 500 data, using fallback: sideways/neutral")
            return {'regime': 'sideways', 'strength': 0.5, 'params': {}}

        regime_info = self.regime_detector.detect_regime(spx)
        params = self.adaptive_params.get_parameters(
            regime_info['regime'], regime_info['strength']
        )

        if not as_of_date:
            self.current_regime = regime_info['regime']
            self.regime_strength = regime_info['strength']
            self.regime_params = params

        return {
            'regime': regime_info['regime'],
            'strength': regime_info['strength'],
            'params': params,
            'details': regime_info.get('details', {}),
        }

    def _calculate_liquidity_profile(self, data: pd.DataFrame) -> Dict:
        """Calculate 20-day liquidity using avg traded value (price * volume) in USD."""
        data = self._normalize_data(data)
        if 'Close' not in data.columns or 'Volume' not in data.columns or len(data) < 20:
            return {'avg_volume_20d': 0.0, 'avg_turnover_20d': 0.0, 'status': 'skip'}

        closes = data['Close'].tail(20).astype(float)
        volumes = data['Volume'].tail(20).astype(float)
        avg_volume_20d = float(volumes.mean()) if not volumes.empty else 0.0
        avg_turnover_20d = float((closes * volumes).mean()) if not closes.empty else 0.0

        if np.isnan(avg_turnover_20d):
            avg_turnover_20d = 0.0
        if np.isnan(avg_volume_20d):
            avg_volume_20d = 0.0

        status = 'healthy'
        if avg_turnover_20d < self.MIN_SKIP_TURNOVER_USD:
            status = 'skip'
        elif avg_turnover_20d < self.MIN_DOWNGRADE_TURNOVER_USD:
            status = 'downgrade'

        return {
            'avg_volume_20d': avg_volume_20d,
            'avg_turnover_20d': avg_turnover_20d,
            'status': status,
        }

    @staticmethod
    def _downgrade_signal(signal: str) -> str:
        downgrade_map = {
            'STRONG_BUY': 'BUY', 'BUY': 'HOLD',
            'SELL': 'HOLD', 'STRONG_SELL': 'SELL',
        }
        return downgrade_map.get(signal, signal)

    def _apply_liquidity_adjustment(self, ticker: str, signal: str, conviction: float,
                                    position_size: float, liquidity_profile: Dict) -> Tuple[Optional[str], float, float]:
        avg_turnover = liquidity_profile.get('avg_turnover_20d', 0.0)
        status = liquidity_profile.get('status', 'healthy')

        if status == 'skip':
            print(f"     [LIQ] Skipping {ticker}: "
                  f"20d avg turnover ${avg_turnover:,.0f} < ${self.MIN_SKIP_TURNOVER_USD:,.0f}")
            return None, 0.0, 0.0

        if status == 'downgrade' and signal not in ['HOLD', 'NONE']:
            downgraded = self._downgrade_signal(signal)
            if downgraded != signal:
                print(f"     [LIQ] Downgrading {ticker}: "
                      f"20d avg turnover ${avg_turnover:,.0f} < ${self.MIN_DOWNGRADE_TURNOVER_USD:,.0f} "
                      f"({signal} -> {downgraded})")
                signal = downgraded
                if signal == 'HOLD':
                    conviction = 0.0
                    position_size = 0.0
                else:
                    conviction = np.sign(conviction) * min(abs(conviction), 0.65)
                    position_size *= 0.75

        return signal, conviction, position_size

    @staticmethod
    def _latest_close_from_data(data: pd.DataFrame) -> float:
        price_val = data['Close'].iloc[-1]
        return float(price_val.item()) if hasattr(price_val, 'item') else float(price_val)

    def _prefetch_spot_prices(self, tickers: List[str]) -> None:
        print(f"💰 Fetching spot prices ({len(tickers)} tickers)...")
        self._spot_prices = self.data_client.get_prices(tickers)
        self._price_snapshots = {}

        for ticker in tickers:
            snapshot = self.data_client.get_price_snapshot(ticker)
            if snapshot is not None:
                self._price_snapshots[ticker] = snapshot

        print(f"   ✅ Spot prices: {len(self._price_snapshots)}/{len(tickers)}")

    def _resolve_current_price(self, ticker: str, data: pd.DataFrame) -> Tuple[Optional[float], str, Optional[str], bool]:
        """Resolve current price from cache or yfinance."""
        if ticker in self._price_snapshots:
            snapshot = self._price_snapshots[ticker]
            return (float(snapshot['price']), str(snapshot.get('source', 'yfinance')),
                    snapshot.get('quote_ts'), snapshot.get('is_stale', False))

        snapshot = self.data_client.get_price_snapshot(ticker)
        if snapshot is not None:
            self._price_snapshots[ticker] = snapshot
            return (float(snapshot['price']), str(snapshot.get('source', 'yfinance')),
                    snapshot.get('quote_ts'), snapshot.get('is_stale', False))

        # Fallback to last close
        close = self._latest_close_from_data(data)
        return (close, 'close', None, True)

    def analyze_ticker(self, ticker: str) -> Optional[Dict]:
        """Analyze a single US stock ticker."""
        try:
            print(f"📊 {ticker}...", end=" ", flush=True)

            # Historical data
            data = self.data_client.get_historical(ticker, period="6mo")
            if data is None or len(data) < 50:
                print(f"⚠️ Insufficient data ({len(data) if data is not None else 0} days)")
                return None

            data = self._normalize_data(data)

            # Current price
            current_price, price_source, quote_ts, is_stale = self._resolve_current_price(ticker, data)

            # Liquidity check
            liquidity = self._calculate_liquidity_profile(data)
            if liquidity['status'] == 'skip':
                print(f"⏭️ Low liquidity (${liquidity['avg_turnover_20d']:,.0f})")
                return None

            # Trend detection
            trend_result = self.trend_detector.detect_trend(data)
            consensus = trend_result.get('consensus', 'unknown')
            confidence = trend_result.get('confidence', 0.0)

            if consensus in ['uptrend', 'bull_pullback']:
                trend = "uptrend"
            elif consensus in ['downtrend', 'bear_bounce']:
                trend = "downtrend"
            else:
                trend = "consolidation"

            print(f"[{trend} @ {confidence:.0%}]", end=" ", flush=True)

            # Features
            feature_engineer = get_feature_engineer()
            features = feature_engineer.generate_all_features(ticker, data)

            # Volume adjustment
            volume_features = features.get('volume', {})
            if volume_features.get('unusual_volume', False):
                confidence *= 1.05

            vol_regime = features.get('volatility', {}).get('regime', 'medium')
            if vol_regime == 'high':
                confidence *= 0.90

            # Technical score
            tech_score = confidence * 100

            # Fundamentals
            fund_score = None
            if self.use_fundamentals:
                try:
                    integrated = self.fundamental_integrator.integrate(
                        ticker, tech_score, trend.upper(), confidence
                    )
                    fund_score = {
                        'composite_score': integrated.fundamental_score,
                        'grade': integrated.fundamental_grade,
                        'value_score': integrated.value_score,
                        'quality_score': integrated.quality_score,
                        'growth_score': integrated.growth_score,
                        'pe_ratio': integrated.pe_ratio,
                        'pb_ratio': integrated.pb_ratio,
                        'roe': integrated.roe,
                        'div_yield': integrated.div_yield,
                        'is_value_pick': integrated.is_value_pick,
                        'is_quality_pick': integrated.is_quality_pick,
                        'is_avoid': integrated.is_avoid,
                        'strengths': integrated.strengths,
                        'weaknesses': integrated.weaknesses,
                    }
                except Exception as e:
                    print(f"[FUND ERR: {e}]", end=" ", flush=True)

            # Composite score (60/40 tech/fund for US since fundamentals are live)
            fund_comp = fund_score.get('composite_score', 50) if fund_score else 50
            tech_weight = 0.50
            fund_weight = 0.50
            composite = (tech_score * tech_weight) + (fund_comp * fund_weight)

            # US-calibrated signal thresholds (from composite score 0-100)
            if composite >= 70:
                signal = "STRONG_BUY"
            elif composite >= 55:
                signal = "BUY"
            elif composite >= 35:
                signal = "HOLD"
            elif composite >= 20:
                signal = "SELL"
            else:
                signal = "STRONG_SELL"

            # Position sizing (US-calibrated)
            position_size = _US_THRESHOLDS.get('default_position_pct', 0.15)
            if fund_score:
                if fund_score.get('is_quality_pick'):
                    position_size = min(position_size * 1.3, _US_THRESHOLDS.get('max_position_pct', 0.50))
                if fund_score.get('is_value_pick'):
                    position_size = min(position_size * 1.2, _US_THRESHOLDS.get('max_position_pct', 0.50))
                if fund_comp < 40:
                    position_size *= 0.5

            # Liquidity adjustment
            signal, confidence, position_size = self._apply_liquidity_adjustment(
                ticker, signal, confidence, position_size, liquidity
            )
            if signal is None:
                return None

            print(f"{signal}")

            return {
                'ticker': ticker,
                'price': current_price,
                'signal': signal,
                'trend': trend,
                'confidence': confidence,
                'composite_score': composite,
                'tech_score': tech_score,
                'fund_score': fund_comp,
                'position_size': position_size,
                'features': features,
                'fundamentals': fund_score,
                'liquidity': liquidity,
                'price_source': price_source,
                'is_stale': is_stale,
            }

        except Exception as e:
            print(f"❌ Error: {e}")
            return None

    def run(self) -> List[Dict]:
        """Run full US market analysis."""
        tickers = self.tickers

        print(f"\n{'='*70}")
        print(f"🇺🇸 US MARKET ANALYSIS - {datetime.now().strftime('%Y-%m-%d %H:%M')} ET")
        print(f"📊 Analyzing {len(tickers)} US stocks")
        print(f"{'='*70}\n")

        # Detect market regime
        regime_info = self.detect_market_regime()
        print(f"📈 Market Regime: {regime_info['regime'].upper()} "
              f"(strength: {regime_info['strength']:.0%})")
        if 'details' in regime_info:
            d = regime_info['details']
            print(f"   Price vs MA200: {d.get('price_vs_ma200', 0):+.1%} | "
                  f"6mo return: {d.get('returns_6m', 0):+.1%} | "
                  f"Vol ratio: {d.get('vol_ratio', 1):.2f}")
        print()

        # Prefetch spot prices
        self._prefetch_spot_prices(tickers)

        # Analyze tickers
        results = []
        for ticker in tickers:
            result = self.analyze_ticker(ticker)
            if result:
                results.append(result)

        # Sort by composite score
        results.sort(key=lambda x: x.get('composite_score', 0), reverse=True)

        # Summary
        print(f"\n{'='*70}")
        signals = [r['signal'] for r in results]
        print(f"📊 Summary: {signals.count('STRONG_BUY')} STRONG_BUY | "
              f"{signals.count('BUY')} BUY | {signals.count('HOLD')} HOLD | "
              f"{signals.count('SELL')} SELL | {signals.count('STRONG_SELL')} STRONG_SELL")
        print(f"{'='*70}\n")

        # Top picks
        print("🏆 TOP PICKS:")
        for r in results[:10]:
            if r['signal'] in ('STRONG_BUY', 'BUY'):
                fund = r.get('fundamentals', {})
                grade = fund.get('grade', 'N/A') if fund else 'N/A'
                print(f"  {r['ticker']:6s} | {r['signal']:11s} | "
                      f"Score: {r['composite_score']:.0f} | "
                      f"Grade: {grade} | "
                      f"${r['price']:.2f}")

        return results


def main():
    parser = argparse.ArgumentParser(description='US Market Stock Signals')
    parser.add_argument('--no-news', action='store_true', help='Disable news sentiment')
    parser.add_argument('--no-fundamentals', action='store_true', help='Disable fundamentals')
    parser.add_argument('--workers', type=int, default=None, help='Number of workers')
    parser.add_argument('--tickers', type=str, nargs='+', help='Specific tickers to analyze')
    parser.add_argument('--save', action='store_true', help='Save results to file')
    args = parser.parse_args()

    runner = USProductionRunner(
        use_news=not args.no_news,
        use_fundamentals=not args.no_fundamentals,
        n_workers=args.workers,
        ticker_list=args.tickers,
    )

    results = runner.run()

    if args.save and results:
        output_path = Path(__file__).parent / 'data' / 'us_results.json'
        with open(output_path, 'w') as f:
            json.dump(results, f, indent=2, default=str)
        print(f"\n💾 Saved {len(results)} results to {output_path}")

    return results


if __name__ == '__main__':
    main()