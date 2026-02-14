"""
Data fetching utilities with proper column handling for yfinance.
"""

import yfinance as yf
import pandas as pd


def fetch_ticker_data(ticker, start=None, end=None, period=None, interval='1d', progress=False):
    """
    Fetch ticker data and fix multi-index columns from yfinance.
    
    Args:
        ticker: Ticker symbol
        start: Start date (YYYY-MM-DD)
        end: End date (YYYY-MM-DD)
        period: Period string (e.g., '1y', '6mo')
        interval: Interval (e.g., '1d', '1m'), default '1d'
        progress: Show progress bar
    
    Returns:
        DataFrame with standard columns: Close, High, Low, Open, Volume
    """
    # Build kwargs to pass only non-None values
    kwargs = {
        'tickers': ticker,
        'progress': progress
    }
    
    if start is not None:
        kwargs['start'] = start
    if end is not None:
        kwargs['end'] = end
    if period is not None:
        kwargs['period'] = period
    if interval is not None:
        kwargs['interval'] = interval
    
    data = yf.download(**kwargs)
    
    # Fix multi-index columns if present (happens when downloading single ticker)
    if isinstance(data.columns, pd.MultiIndex):
        data.columns = data.columns.droplevel(-1)
    
    return data
