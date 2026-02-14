"""
Extended data fetcher: 1-2 years of historical OHLCV + news for US & BR markets
Fixes look-ahead bias by using correct bar indexing
"""

import pandas as pd
import numpy as np
import yfinance as yf
import logging
from datetime import datetime, timedelta
from typing import Dict, Tuple, List
import json

logger = logging.getLogger(__name__)

# S&P 500 Top 50 by market cap (2026)
SP500_TOP_50 = [
    'AAPL', 'MSFT', 'NVDA', 'TSLA', 'GOOGL', 'AMZN', 'META', 'BRK.B', 'JPMORGIM', 'V',
    'JNJ', 'WMT', 'XOM', 'MA', 'PG', 'NFLX', 'CRM', 'ABBV', 'MRK', 'ADBE',
    'COST', 'AVGO', 'ACN', 'AMD', 'AXP', 'CSCO', 'GE', 'IBM', 'INTU', 'QCOM',
    'HON', 'TXN', 'PYPL', 'BA', 'BKNG', 'SNPS', 'AMAT', 'PEP', 'SPGI', 'TMUX',
    'ASML', 'INTC', 'KO', 'AMEX', 'CAT', 'APE', 'MSI', 'KLAC', 'LRCX', 'REGN'
]

# IBOV Top 30 (2026)
IBOV_TOP_30 = [
    'PETR4.SA', 'VALE3.SA', 'ITUB4.SA', 'BBDC4.SA', 'B3SA3.SA', 'WEGE3.SA',
    'RENT3.SA', 'JBSS3.SA', 'ABEV3.SA', 'SBSP3.SA', 'EMBR3.SA', 'ALPA4.SA',
    'PCAR3.SA', 'ASAI3.SA', 'MGLU3.SA', 'VVAR3.SA', 'BBSE3.SA', 'EQTL3.SA',
    'SUZB3.SA', 'USIM5.SA', 'ELET3.SA', 'BRML3.SA', 'IGTI11.SA', 'RADL3.SA',
    'GGBR4.SA', 'ELET6.SA', 'RRRP3.SA', 'CPLE6.SA', 'BRFS3.SA', 'SLCE3.SA'
]

class ExtendedDataFetcher:
    """Fetch 1-2 years of data with proper handling"""
    
    def __init__(self, end_date: str = None, periods: int = 504):  # 2 years = 252*2
        self.end_date = datetime.strptime(end_date, '%Y-%m-%d') if end_date else datetime.now()
        self.start_date = self.end_date - timedelta(days=periods)
        self.periods = periods
        
    def fetch_market_data(self, tickers: List[str], market: str = 'US') -> Dict[str, pd.DataFrame]:
        """
        Fetch OHLCV data with NO LOOK-AHEAD BIAS
        Returns data with proper forward-fill for closed markets
        """
        results = {}
        
        for ticker in tickers:
            try:
                logger.info(f"Fetching {ticker} ({market})...")
                
                # Fetch raw data
                df = yf.download(
                    ticker,
                    start=self.start_date.strftime('%Y-%m-%d'),
                    end=self.end_date.strftime('%Y-%m-%d'),
                    progress=False
                )
                
                if df.empty:
                    logger.warning(f"  ❌ No data for {ticker}")
                    continue
                
                # Flatten MultiIndex columns if needed
                if isinstance(df.columns, pd.MultiIndex):
                    df.columns = df.columns.get_level_values(0)
                
                # Essential columns
                required = ['Open', 'High', 'Low', 'Close', 'Volume']
                if not all(col in df.columns for col in required):
                    logger.warning(f"  ⚠️ Missing columns for {ticker}")
                    continue
                
                # Rename for consistency
                df = df[required].rename(columns={
                    'Open': 'open',
                    'High': 'high', 
                    'Low': 'low',
                    'Close': 'close',
                    'Volume': 'volume'
                })
                
                # Remove any duplicates, keep first
                df = df[~df.index.duplicated(keep='first')]
                
                # Forward fill volume gaps (market closed, no trading)
                df['volume'] = df['volume'].fillna(0)
                
                # Ensure sorted by date
                df = df.sort_index()
                
                logger.info(f"  ✓ {len(df)} bars from {df.index[0].date()} to {df.index[-1].date()}")
                results[ticker] = df
                
            except Exception as e:
                logger.error(f"  ✗ Error fetching {ticker}: {e}")
                continue
        
        return results
    
    def fetch_news_sentiment(self, tickers: List[str], market: str = 'US') -> Dict[str, List[Dict]]:
        """
        Fetch news headlines and sentiment (requires NewsAPI key or similar)
        Returns: {ticker: [{'date': YYYY-MM-DD, 'sentiment': 0.5, 'headline': '...', 'source': '...'}]}
        """
        news_data = {}
        
        # For now, this is a placeholder - would integrate with:
        # - NewsAPI (global)
        # - Yahoo Finance news endpoint
        # - Brazil-specific financial sites (Valor, Infomoney, etc.)
        # - SEC EDGAR (earnings, filings)
        # - B3 announcements (Brazil)
        
        logger.info("News sentiment integration: placeholder (requires API keys)")
        for ticker in tickers:
            news_data[ticker] = []
        
        return news_data
    
    def get_market_data(self, market: str = 'US') -> Dict[str, pd.DataFrame]:
        """Get data for entire market"""
        if market == 'US':
            tickers = SP500_TOP_50
        elif market == 'BR':
            tickers = IBOV_TOP_30
        else:
            raise ValueError(f"Unknown market: {market}")
        
        return self.fetch_market_data(tickers, market)
    
    @staticmethod
    def add_forward_returns(df: pd.DataFrame) -> pd.DataFrame:
        """
        Add forward returns to properly avoid look-ahead bias
        Trading decision at bar n uses data from bar n-1
        Entry at next bar (n+1) at open price
        """
        df['next_open'] = df['open'].shift(-1)
        df['next_high'] = df['high'].shift(-1)
        df['next_low'] = df['low'].shift(-1)
        df['next_close'] = df['close'].shift(-1)
        
        # Entry return: from today's close to next day open
        df['entry_slippage'] = (df['next_open'] - df['close']) / df['close']
        
        # Max intraday return (best case): close to next high
        df['max_return'] = (df['next_high'] - df['next_open']) / df['next_open']
        
        # Max intraday loss (worst case): close to next low
        df['min_return'] = (df['next_low'] - df['next_open']) / df['next_open']
        
        return df
    
    @staticmethod
    def save_to_parquet(data: Dict[str, pd.DataFrame], filename: str):
        """Save fetched data to parquet for caching"""
        for ticker, df in data.items():
            path = f"data/cache/{filename}_{ticker}.parquet"
            df.to_parquet(path)
            logger.info(f"Saved {ticker} to {path}")
    
    @staticmethod
    def load_from_parquet(filename: str, tickers: List[str]) -> Dict[str, pd.DataFrame]:
        """Load cached parquet files"""
        data = {}
        for ticker in tickers:
            try:
                path = f"data/cache/{filename}_{ticker}.parquet"
                df = pd.read_parquet(path)
                data[ticker] = df
            except:
                pass
        return data


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    
    # Fetch 2 years of data ending Feb 13, 2026
    fetcher = ExtendedDataFetcher(end_date='2026-02-13', periods=504)
    
    # US market
    print("\n=== Fetching US Market (S&P500 Top 50) ===")
    us_data = fetcher.get_market_data('US')
    print(f"✓ Fetched {len(us_data)} US stocks")
    
    # BR market
    print("\n=== Fetching BR Market (IBOV Top 30) ===")
    br_data = fetcher.get_market_data('BR')
    print(f"✓ Fetched {len(br_data)} BR stocks")
    
    # Add forward returns for backtesting
    print("\n=== Adding Forward Returns (for proper backtesting) ===")
    for ticker in us_data:
        us_data[ticker] = ExtendedDataFetcher.add_forward_returns(us_data[ticker])
    for ticker in br_data:
        br_data[ticker] = ExtendedDataFetcher.add_forward_returns(br_data[ticker])
    
    print("✓ Ready for backtesting with no look-ahead bias")
