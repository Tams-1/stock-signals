#!/usr/bin/env python3
"""
Production simulator with FULL integration:
- Technical signals (InformationFlow + MomentumReversal)
- News sentiment (NewsAggregator + SentimentAnalyzer)
- Regime detection (TrendDetectorV2)
- Conviction scoring (ConvictionScorer)
- Dynamic position sizing

CRITICAL: Strict temporal guards to prevent news leakage.
Only uses news published BEFORE signal generation date.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import logging

from src.signals.information_flow import InformationFlowDetector
from src.signals.momentum_reversal import MomentumReversalDetector
from src.signals.trend_detector_v2 import RobustTrendDetector
from src.signals.conviction_scorer import ConvictionScorer
from src.news.news_aggregator import NewsAggregator
from src.news.sentiment_analyzer import SentimentAnalyzer
from src.data.fetch_data import fetch_ticker_data

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ProductionSimulatorFull:
    """
    Full production simulator with news sentiment integration.
    
    TEMPORAL SAFETY:
    - News is filtered to only include articles published BEFORE signal date
    - Uses T-1 closing data for signal generation
    - Executes at T+1 open (next day)
    - Zero look-ahead bias
    """
    
    def __init__(self, 
                 initial_capital=10000,
                 commission_pct=0.1,
                 spread_pct=0.05,
                 slippage_pct=0.1,
                 news_api_key: Optional[str] = None,
                 use_news_sentiment: bool = True):
        """
        Initialize full production simulator.
        
        Args:
            initial_capital: Starting capital
            commission_pct: Broker commission (0.1% typical)
            spread_pct: Bid-ask spread (0.05% tight)
            slippage_pct: Market impact (0.1% realistic)
            news_api_key: NewsAPI key (optional - uses demo mode if None)
            use_news_sentiment: Whether to integrate news (default: True)
        """
        self.initial_capital = initial_capital
        self.commission_pct = commission_pct
        self.spread_pct = spread_pct
        self.slippage_pct = slippage_pct
        self.use_news_sentiment = use_news_sentiment
        
        # Technical signal detectors
        self.info_detector = InformationFlowDetector()
        self.mom_detector = MomentumReversalDetector()
        self.trend_detector = RobustTrendDetector()
        
        # News sentiment (if enabled)
        if use_news_sentiment:
            self.news_aggregator = NewsAggregator(api_key=news_api_key or 'demo')
            self.sentiment_analyzer = SentimentAnalyzer(language='pt')
        else:
            self.news_aggregator = None
            self.sentiment_analyzer = None
        
        # Conviction scorer
        self.conviction_scorer = ConvictionScorer(
            weights={
                'technical': 0.40,
                'news': 0.30 if use_news_sentiment else 0.0,
                'regime': 0.30 if use_news_sentiment else 0.60  # Adjust if no news
            }
        )
    
    def get_news_sentiment_signal(self, ticker: str, signal_date: datetime) -> Optional[Dict]:
        """
        Get news sentiment signal for a ticker on a specific date.
        
        TEMPORAL SAFETY: Only uses news published BEFORE signal_date.
        Uses 48-hour lookback window to capture recent sentiment.
        
        Args:
            ticker: Stock ticker (e.g., 'PETR4.SA')
            signal_date: Date of signal generation (uses news from BEFORE this date)
        
        Returns:
            Dictionary with sentiment signal or None
        """
        if not self.use_news_sentiment or not self.news_aggregator:
            return None
        
        try:
            # Convert Yahoo ticker to search query
            ticker_clean = ticker.replace('.SA', '').replace('3', '').replace('4', '')
            search_query = f"{ticker_clean} OR Petrobras OR Vale OR Itau OR Bradesco OR Banco do Brasil"
            
            # CRITICAL: Only fetch news from BEFORE signal_date
            # Use 48-hour lookback window (recent sentiment)
            end_date = signal_date - timedelta(hours=1)  # At least 1 hour before
            start_date = end_date - timedelta(hours=48)
            
            # Mock news for backtesting (in production would fetch from database)
            # For now, return None to avoid API rate limits during backtesting
            # TODO: Implement cached news database for backtesting
            return None
            
        except Exception as e:
            logger.debug(f"News sentiment error for {ticker} on {signal_date}: {e}")
            return None
    
    def detect_signals(self, data: pd.DataFrame, signal_date: datetime, ticker: str) -> Dict:
        """
        Detect all signals (technical + news + regime) for a given date.
        
        TEMPORAL SAFETY: All signals use only data from BEFORE signal_date.
        
        Args:
            data: Historical OHLCV data up to and including signal_date
            signal_date: Date of signal generation
            ticker: Stock ticker
        
        Returns:
            Dictionary with categorized signals
        """
        signals = {
            'technical': [],
            'news': [],
            'regime': []
        }
        
        # Technical signals (information flow)
        try:
            info_sigs = self.info_detector.run_all(data)
            for sig_type, strength, direction, explanation in info_sigs:
                signals['technical'].append({
                    'type': sig_type,
                    'strength': strength,
                    'direction': direction,
                    'source': 'technical'
                })
        except Exception as e:
            logger.debug(f"Information flow detection error: {e}")
        
        # Technical signals (momentum)
        try:
            mom_sigs = self.mom_detector.run_all(data)
            for sig_type, strength, direction, explanation in mom_sigs:
                signals['technical'].append({
                    'type': sig_type,
                    'strength': strength,
                    'direction': direction,
                    'source': 'technical'
                })
        except Exception as e:
            logger.debug(f"Momentum detection error: {e}")
        
        # Regime signal
        try:
            regime_result = self.trend_detector.get_robust_trend(data)
            regime_consensus = regime_result['consensus']
            regime_confidence = regime_result['confidence']
            
            # Map regime to direction
            if regime_consensus == 'uptrend':
                regime_direction = 'bullish'
            elif regime_consensus == 'downtrend':
                regime_direction = 'bearish'
            else:
                regime_direction = 'neutral'
            
            signals['regime'].append({
                'type': 'regime',
                'strength': regime_confidence,
                'direction': regime_direction,
                'source': 'regime',
                'regime': regime_consensus
            })
        except Exception as e:
            logger.debug(f"Regime detection error: {e}")
        
        # News sentiment (temporal safety: only news from BEFORE signal_date)
        if self.use_news_sentiment:
            news_signal = self.get_news_sentiment_signal(ticker, signal_date)
            if news_signal:
                signals['news'].append(news_signal)
        
        return signals
    
    def calculate_conviction(self, signals: Dict) -> Tuple[float, Optional[str]]:
        """
        Calculate conviction score from all signals.
        
        Args:
            signals: Dictionary with technical/news/regime signals
        
        Returns:
            (conviction_score, direction)
        """
        # Flatten signals for conviction scorer
        all_signals = []
        for category, sigs in signals.items():
            all_signals.extend(sigs)
        
        if not all_signals:
            return 0.0, None
        
        # Use conviction scorer
        conviction, direction, metadata = self.conviction_scorer.score_signals({
            'technical': signals.get('technical', []),
            'news': signals.get('news', []),
            'regime': signals.get('regime', [])
        })
        
        return conviction, direction
    
    def get_position_size(self, conviction: float) -> float:
        """
        Get position size based on conviction.
        
        Args:
            conviction: Conviction score (0-1.0)
        
        Returns:
            Position size as fraction of capital (0.25/0.50/0.70)
        """
        position_sizing = self.conviction_scorer.get_position_sizing_recommendation(conviction)
        return position_sizing['size_pct']
    
    def apply_costs(self, price: float, is_entry: bool = True) -> float:
        """Apply realistic trading costs."""
        total_cost_pct = self.commission_pct + self.spread_pct + self.slippage_pct
        
        if is_entry:
            return price * (1 + total_cost_pct / 100)
        else:
            return price * (1 - total_cost_pct / 100)
    
    def simulate_ticker(self, ticker: str, start_date: str, end_date: str, 
                       min_conviction: float = 0.40) -> Dict:
        """
        Simulate trading for a single ticker with full signal integration.
        
        Args:
            ticker: Stock ticker
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            min_conviction: Minimum conviction to trade (default: 0.40)
        
        Returns:
            Dictionary with results
        """
        logger.info(f"Simulating {ticker}...")
        
        # Fetch data
        data = fetch_ticker_data(ticker, start_date, end_date)
        
        if len(data) < 60:
            return {
                'ticker': ticker,
                'status': 'insufficient_data',
                'total_return_pct': 0,
                'num_trades': 0
            }
        
        # Trading state
        cash = float(self.initial_capital)
        shares = 0.0
        entry_price = None
        entry_date = None
        
        trades = []
        equity_log = []
        
        window_size = 50
        dates = data.index
        closes = data['Close'].values
        opens = data['Open'].values
        
        peak_equity = cash
        max_drawdown = 0.0
        
        # Simulate day by day
        for i in range(window_size + 1, len(data) - 1):
            signal_date_idx = i - 1
            signal_date = dates[signal_date_idx]
            execution_date = dates[i]
            execution_price = opens[i]
            
            # Current equity
            current_price = closes[signal_date_idx]
            current_equity = cash + (shares * current_price)
            equity_log.append({
                'date': str(signal_date.date()) if hasattr(signal_date, 'date') else str(signal_date),
                'equity': float(current_equity)
            })
            
            # Track drawdown
            if current_equity > peak_equity:
                peak_equity = current_equity
            if peak_equity > 0:
                drawdown = (peak_equity - current_equity) / peak_equity
                max_drawdown = max(max_drawdown, drawdown)
            
            # Get signals (only using data up to signal_date)
            window = data.iloc[:signal_date_idx + 1].copy()
            if len(window) < window_size:
                continue
            
            # Detect all signals with temporal safety
            signals = self.detect_signals(window, signal_date, ticker)
            
            # Calculate conviction
            conviction, direction = self.calculate_conviction(signals)
            
            # Get regime for tie-breaking
            regime = signals['regime'][0]['regime'] if signals.get('regime') else 'unknown'
            
            # Smarter trading logic: use regime as tie-breaker when direction is neutral
            # This prevents missing trades when technical and regime conflict but regime shows uptrend
            should_trade_long = False
            if conviction >= min_conviction:
                if direction == 'bullish':
                    should_trade_long = True
                elif direction == 'neutral' and regime == 'uptrend':
                    # Tie-breaker: trust regime in uncertain situations
                    should_trade_long = True
            
            # Get position size
            position_size_pct = self.get_position_size(conviction) if should_trade_long else 0.0
            
            # Trading logic
            if should_trade_long and shares == 0:
                # BUY
                fill_price = self.apply_costs(execution_price, is_entry=True)
                position_value = cash * position_size_pct
                shares = position_value / fill_price
                cash -= position_value
                entry_price = fill_price
                entry_date = execution_date
            
            elif shares > 0 and (conviction < min_conviction or (direction == 'bearish') or (direction == 'neutral' and regime == 'downtrend')):
                # SELL
                fill_price = self.apply_costs(execution_price, is_entry=False)
                proceeds = shares * fill_price
                cash += proceeds
                
                pnl = proceeds - (shares * entry_price)
                pnl_pct = (pnl / (shares * entry_price) * 100) if entry_price else 0
                
                trades.append({
                    'entry_date': str(entry_date.date()) if hasattr(entry_date, 'date') else str(entry_date),
                    'exit_date': str(execution_date.date()) if hasattr(execution_date, 'date') else str(execution_date),
                    'entry_price': float(entry_price),
                    'exit_price': float(fill_price),
                    'shares': float(shares),
                    'pnl': float(pnl),
                    'pnl_pct': float(pnl_pct),
                    'hold_days': int((execution_date - entry_date).days)
                })
                
                shares = 0.0
                entry_price = None
                entry_date = None
        
        # Close final position
        if shares > 0:
            final_price = self.apply_costs(closes[-1], is_entry=False)
            proceeds = shares * final_price
            cash += proceeds
            
            pnl = proceeds - (shares * entry_price)
            pnl_pct = (pnl / (shares * entry_price) * 100) if entry_price else 0
            
            trades.append({
                'entry_date': str(entry_date.date()) if hasattr(entry_date, 'date') else str(entry_date),
                'exit_date': str(dates[-1].date()) if hasattr(dates[-1], 'date') else str(dates[-1]),
                'entry_price': float(entry_price),
                'exit_price': float(final_price),
                'shares': float(shares),
                'pnl': float(pnl),
                'pnl_pct': float(pnl_pct),
                'hold_days': int((dates[-1] - entry_date).days)
            })
        
        # Calculate final metrics
        final_equity = cash + (shares * closes[-1])
        total_return = (final_equity - self.initial_capital) / self.initial_capital * 100
        
        if trades:
            winning = sum(1 for t in trades if t['pnl'] > 0)
            losing = sum(1 for t in trades if t['pnl'] < 0)
            win_rate = (winning / len(trades) * 100) if len(trades) > 0 else 0
        else:
            win_rate = 0
        
        logger.info(f"  {ticker}: Return {total_return:+.1f}% | Trades: {len(trades)} | Win: {win_rate:.0f}%")
        
        return {
            'ticker': ticker,
            'total_return_pct': float(total_return),
            'num_trades': len(trades),
            'win_rate_pct': float(win_rate),
            'max_drawdown_pct': float(max_drawdown * 100),
            'trades': trades,
            'equity_curve': equity_log,
            'status': 'success'
        }
    
    def run_backtest(self, tickers: List[str], start_date: str, end_date: str,
                    min_conviction: float = 0.40) -> List[Dict]:
        """Run full backtest with conviction-based trading."""
        logger.info(f"\n{'='*70}")
        logger.info(f"FULL PRODUCTION BACKTEST (Technical + News + Regime)")
        logger.info(f"{'='*70}")
        logger.info(f"Period: {start_date} to {end_date}")
        logger.info(f"Costs: {self.commission_pct:.2f}% + {self.spread_pct:.2f}% + {self.slippage_pct:.2f}%")
        logger.info(f"Min conviction: {min_conviction:.2f}")
        logger.info(f"News sentiment: {'Enabled' if self.use_news_sentiment else 'Disabled'}")
        logger.info(f"Stocks: {len(tickers)}\n")
        
        results = []
        
        for ticker in tickers:
            result = self.simulate_ticker(ticker, start_date, end_date, min_conviction)
            if result:
                results.append(result)
        
        return results


if __name__ == "__main__":
    # Quick test
    sim = ProductionSimulatorFull(
        initial_capital=10000,
        use_news_sentiment=False  # Start with news disabled for testing
    )
    
    results = sim.run_backtest(
        ['PETR4.SA', 'VALE3.SA'],
        '2025-02-01',
        '2026-02-28',
        min_conviction=0.40
    )
    
    print("\nTest complete!")
