"""
Get top 100 most liquid S&P500 stocks by average volume.
"""

import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta

def get_sp500_tickers():
    """Fetch list of S&P500 tickers from Wikipedia."""
    try:
        url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
        table = pd.read_html(url)
        df = table[0]
        return df['Symbol'].tolist()
    except Exception as e:
        print(f"Error fetching S&P500 list: {e}")
        return []

def get_top_100_liquid(n_days=20, min_avg_volume=1e6):
    """
    Get top 100 most liquid S&P500 stocks by average volume.
    """
    print("Fetching S&P500 tickers...")
    tickers = get_sp500_tickers()
    
    if not tickers:
        print("Failed to fetch tickers")
        return []
    
    print(f"Found {len(tickers)} S&P500 tickers, filtering by liquidity...")
    
    # Get average volume for last N days
    end_date = datetime.now()
    start_date = end_date - timedelta(days=n_days)
    
    liquidity_data = []
    
    for i, ticker in enumerate(tickers):
        if (i + 1) % 50 == 0:
            print(f"  Processed {i + 1}/{len(tickers)}...")
        
        try:
            data = yf.download(ticker, start=start_date, end=end_date, progress=False)
            if len(data) > 0:
                avg_volume = data['Volume'].mean()
                if avg_volume >= min_avg_volume:
                    liquidity_data.append({
                        'ticker': ticker,
                        'avg_volume': avg_volume,
                        'price': data['Close'].iloc[-1]
                    })
        except Exception as e:
            pass
    
    # Sort by average volume and get top 100
    liquidity_df = pd.DataFrame(liquidity_data)
    liquidity_df = liquidity_df.sort_values('avg_volume', ascending=False).head(100)
    
    print(f"\nTop 100 most liquid S&P500 stocks:")
    print(liquidity_df.to_string())
    
    # Save to file
    tickers_list = liquidity_df['ticker'].tolist()
    with open('/home/ulluboz/.openclaw/workspace/stock-signals/configs/top_100_tickers.txt', 'w') as f:
        for ticker in tickers_list:
            f.write(f"{ticker}\n")
    
    print(f"\nSaved {len(tickers_list)} tickers to configs/top_100_tickers.txt")
    
    return tickers_list

if __name__ == '__main__':
    tickers = get_top_100_liquid()
