#!/usr/bin/env python3
"""
Production simulator with REAL NEWS integration.

Uses FreeNewsClient for:
- Google News RSS (recent/real-time)
- Investing.com scraping (historical)
- FinBERT sentiment analysis (local, no API costs)

This version replaces mock sentiment with real news data for backtesting.
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
from src.news.free_news_client import get_client as get_news_client
from src.data.fetch_data import fetch_ticker_data

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ProductionSimulatorRealNews:
    """
    Production simulator with REAL news sentiment.
    
    Uses FreeNewsClient for historical + real-time news data.
    """
    
    def __init__(self, 
                 initial_capital=10000,
                 commission_pct=0.1,
                 spread_pct=0.05,
                 use_news_sentiment: bool = True):
        """
        Initialize simulator with real news integration.
        
        Args:
            initial_capital: Starting capital (default: 10000)
            commission_pct: Commission percentage per trade (default: 0.1%)
            spread_pct: Bid-ask spread percentage (default: 0.05%)
            use_news_sentiment: Whether to use news (default: True)
        """
        self.initial_capital = initial_capital
        self.commission_pct = commission_pct / 100
        self.spread_pct = spread_pct / 100
        self.use_news_sentiment = use_news_sentiment
        
        # Initialize technical signal detectors
        self.info_flow = InformationFlowDetector()
        self.momentum = MomentumReversalDetector()
        self.trend_detector = RobustTrendDetector()
        
        # Initialize news client (real news!)
        if use_news_sentiment:
            self.news_client = get_news_client()
            logger.info("Real news client initialized (Google News + FinBERT)")
        
        # Initialize conviction scorer
        self.conviction_scorer = ConvictionScorer(
            weights={
                'technical': 0.40 if use_news_sentiment else 0.70,
                'news': 0.30 if use_news_sentiment else 0.0,
                'regime': 0.30 if use_news_sentiment else 0.30
            }
        )
        
        logger.info(f"ProductionSimulatorRealNews initialized")
        logger.info(f"News sentiment: {'Enabled (REAL)' if use_news_sentiment else 'Disabled'}")
    
    def get_news_sentiment(self, ticker: str, date: str) -> float:
        """
        Get news sentiment for a ticker on a given date.
        
        Uses FreeNewsClient which automatically chooses:
        - Google News RSS for recent dates
        - Investing.com scraping for historical dates
        - FinBERT for sentiment analysis
        
        Args:
            ticker: Stock ticker
            date: Date string (YYYY-MM-DD)
        
        Returns:
            Sentiment score (-1.0 to +1.0)
        """
        if not self.use_news_sentiment:
            return 0.0
        
        try:
            sentiment = self.news_client.get_sentiment(ticker, date)
            return sentiment
        except Exception as e:
            logger.warning(f"Failed to get sentiment for {ticker} on {date}: {e}")
            return 0.0
    
    def simulate_ticker(self, ticker: str, start_date: str, end_date: str,
                       min_conviction: float = 0.40) -> Dict:
        """
        Simulate trading for a single ticker with REAL news.
        
        Args:
            ticker: Stock ticker (e.g., PETR4.SA)
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            min_conviction: Minimum conviction to trade (default: 0.40)
        
        Returns:
            Dict with simulation results
        """
        logger.info(f"Simulating {ticker} with REAL news...")
        
        # Fetch data
        df = fetch_ticker_data(ticker, start_date, end_date)
        
        if df is None or len(df) < 60:
            logger.warning(f"Insufficient data for {ticker}")
            return {'status': 'failed', 'reason': 'insufficient_data'}
        
        # State
        capital = self.initial_capital
        position = None
        trades = []
        equity_curve = []
        
        for i in range(50, len(df)):
            current_date = df.index[i].strftime('%Y-%m-%d')
            current_price = df['Close'].iloc[i]
            
            equity_curve.append({
                'date': current_date,
                'equity': capital if position is None else capital + position['shares'] * current_price
            })
            
            # Generate signals using T-1 data
            window = df.iloc[max(0, i-50):i]
            
            # Technical signals
            info_signal = self.info_flow.detect(window)
            momentum_signal = self.momentum.detect(window)
            
            # Combine technical signals
            if info_signal['direction'] == 'bullish' or momentum_signal['direction'] == 'bullish':
                technical_signal = 1.0
            elif info_signal['direction'] == 'bearish' or momentum_signal['direction'] == 'bearish':
                technical_signal = -1.0
            else:
                technical_signal = 0.0
            
            # News sentiment (REAL!)
            news_sentiment = self.get_news_sentiment(ticker, current_date)
            
            # Regime detection
            trend = self.trend_detector.detect_trend(window['Close'].values)
            regime_signal = 1.0 if trend == 'uptrend' else (-1.0 if trend == 'downtrend' else 0.0)
            
            # Calculate conviction
            conviction_input = {
                'technical': technical_signal,
                'news': news_sentiment,
                'regime': regime_signal
            }
            
            conviction = self.conviction_scorer.calculate_conviction(conviction_input)
            
            # Trading logic
            if position is None:
                # Entry logic
                if conviction >= min_conviction:
                    # Determine position size based on conviction
                    if conviction >= 0.80:
                        position_pct = 0.70
                    elif conviction >= 0.60:
                        position_pct = 0.50
                    else:
                        position_pct = 0.25
                    
                    position_value = capital * position_pct
                    entry_price = current_price * (1 + self.spread_pct)
                    shares = position_value / entry_price
                    commission = position_value * self.commission_pct
                    
                    position = {
                        'entry_date': current_date,
                        'entry_price': entry_price,
                        'shares': shares,
                        'conviction': conviction
                    }
                    
                    capital -= (position_value + commission)
            
            else:
                # Exit logic
                exit_signal = False
                
                # 1. Conviction dropped below threshold
                if conviction < 0.35:
                    exit_signal = True
                
                # 2. Technical signals turned bearish
                if technical_signal < -0.3:
                    exit_signal = True
                
                # 3. Regime turned bearish
                if regime_signal < -0.5:
                    exit_signal = True
                
                if exit_signal:
                    # Close position
                    exit_price = current_price * (1 - self.spread_pct)
                    position_value = position['shares'] * exit_price
                    commission = position_value * self.commission_pct
                    
                    capital += (position_value - commission)
                    
                    pnl = position_value - (position['shares'] * position['entry_price'])
                    pnl_pct = (pnl / (position['shares'] * position['entry_price'])) * 100
                    
                    trades.append({
                        'entry_date': position['entry_date'],
                        'exit_date': current_date,
                        'entry_price': position['entry_price'],
                        'exit_price': exit_price,
                        'shares': position['shares'],
                        'pnl': pnl,
                        'pnl_pct': pnl_pct,
                        'hold_days': (df.index[i] - pd.to_datetime(position['entry_date'])).days
                    })
                    
                    position = None
        
        # Close final position if open
        if position is not None:
            final_price = df['Close'].iloc[-1] * (1 - self.spread_pct)
            position_value = position['shares'] * final_price
            commission = position_value * self.commission_pct
            capital += (position_value - commission)
            
            pnl = position_value - (position['shares'] * position['entry_price'])
            pnl_pct = (pnl / (position['shares'] * position['entry_price'])) * 100
            
            trades.append({
                'entry_date': position['entry_date'],
                'exit_date': df.index[-1].strftime('%Y-%m-%d'),
                'entry_price': position['entry_price'],
                'exit_price': final_price,
                'shares': position['shares'],
                'pnl': pnl,
                'pnl_pct': pnl_pct,
                'hold_days': (df.index[-1] - pd.to_datetime(position['entry_date'])).days
            })
        
        # Calculate metrics
        total_return_pct = ((capital - self.initial_capital) / self.initial_capital) * 100
        
        if trades:
            winning_trades = [t for t in trades if t['pnl'] > 0]
            win_rate_pct = (len(winning_trades) / len(trades)) * 100
        else:
            win_rate_pct = 0.0
        
        # Max drawdown
        equity_values = [e['equity'] for e in equity_curve]
        peak = equity_values[0]
        max_dd = 0
        for value in equity_values:
            if value > peak:
                peak = value
            dd = ((peak - value) / peak) * 100
            if dd > max_dd:
                max_dd = dd
        
        return {
            'status': 'success',
            'ticker': ticker,
            'total_return_pct': total_return_pct,
            'num_trades': len(trades),
            'win_rate_pct': win_rate_pct,
            'max_drawdown_pct': max_dd,
            'trades': trades,
            'equity_curve': equity_curve
        }


def main():
    """Test with real news."""
    print("="*80)
    print("BACKTEST WITH REAL NEWS")
    print("="*80)
    print()
    
    # Test tickers
    tickers = [
        "PETR4.SA", "VALE3.SA", "ITUB4.SA", "BBDC4.SA", "BBAS3.SA",
        "ABEV3.SA", "B3SA3.SA", "SUZB3.SA", "RENT3.SA", "WEGE3.SA",
        "MGLU3.SA", "PCAR3.SA", "LREN3.SA", "RAIZ4.SA", "GGBR4.SA",
        "ASAI3.SA", "JBSS3.SA", "RDOR3.SA"
    ]
    
    # Test WITHOUT news first (baseline)
    print("="*80)
    print("Test 1: WITHOUT News (Baseline)")
    print("="*80)
    print()
    
    sim_no_news = ProductionSimulatorRealNews(
        initial_capital=10000,
        use_news_sentiment=False
    )
    
    results_no_news = []
    for ticker in tickers:
        result = sim_no_news.simulate_ticker(ticker, "2025-02-01", "2026-02-28")
        if result['status'] == 'success':
            results_no_news.append(result)
            print(f"  {ticker}: {result['total_return_pct']:+.1f}% | Trades: {result['num_trades']}")
    
    returns_no_news = [r['total_return_pct'] for r in results_no_news]
    avg_no_news = np.mean(returns_no_news) if returns_no_news else 0
    
    print()
    print(f"Portfolio (no news): {avg_no_news:+.2f}%")
    print()
    
    # Test WITH real news
    print("="*80)
    print("Test 2: WITH REAL News (Google News + FinBERT)")
    print("="*80)
    print()
    
    sim_with_news = ProductionSimulatorRealNews(
        initial_capital=10000,
        use_news_sentiment=True
    )
    
    results_with_news = []
    for ticker in tickers:
        result = sim_with_news.simulate_ticker(ticker, "2025-02-01", "2026-02-28")
        if result['status'] == 'success':
            results_with_news.append(result)
            print(f"  {ticker}: {result['total_return_pct']:+.1f}% | Trades: {result['num_trades']}")
    
    returns_with_news = [r['total_return_pct'] for r in results_with_news]
    avg_with_news = np.mean(returns_with_news) if returns_with_news else 0
    
    print()
    print(f"Portfolio (with REAL news): {avg_with_news:+.2f}%")
    print()
    
    # Summary
    print("="*80)
    print("FINAL COMPARISON")
    print("="*80)
    print()
    print(f"WITHOUT news: {avg_no_news:+.2f}%")
    print(f"WITH REAL news: {avg_with_news:+.2f}%")
    print(f"News impact: {avg_with_news - avg_no_news:+.2f}%")
    print()
    print(f"Total improvement over baseline (+12.73%): {avg_with_news - 12.73:+.2f}%")
    print()
    print("="*80)


if __name__ == "__main__":
    main()
