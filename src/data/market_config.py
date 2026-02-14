"""
Market configuration and ticker management.
Supports multiple markets: US (S&P500), BR (IBOV)
"""

from pathlib import Path

# Market definitions
MARKETS = {
    'us': {
        'name': 'S&P500 (USA)',
        'currency': 'USD',
        'lookback_days': 30,
        'min_avg_volume': 1e6,
        'tickers_file': 'configs/top_100_tickers.txt'
    },
    'br': {
        'name': 'IBOV (Brazil)',
        'currency': 'BRL',
        'lookback_days': 30,
        'min_avg_volume': 1e6,
        'tickers_file': 'configs/ibov_top_20_tickers.txt'
    }
}


def get_market_config(market='us'):
    """Get configuration for a market."""
    if market not in MARKETS:
        raise ValueError(f"Unknown market: {market}. Available: {list(MARKETS.keys())}")
    return MARKETS[market]


def get_tickers(market='us', config_dir=None):
    """Load tickers for a market."""
    config = get_market_config(market)
    
    if config_dir is None:
        config_dir = Path(__file__).parent.parent.parent / 'configs'
    else:
        config_dir = Path(config_dir)
    
    ticker_file = config_dir / Path(config['tickers_file']).name
    
    if not ticker_file.exists():
        raise FileNotFoundError(f"Ticker file not found: {ticker_file}")
    
    with open(ticker_file) as f:
        tickers = [line.strip() for line in f if line.strip()]
    
    return tickers


def get_market_name(market='us'):
    """Get human-readable market name."""
    return get_market_config(market)['name']


if __name__ == '__main__':
    print("Available markets:")
    for market_key, config in MARKETS.items():
        print(f"  {market_key:4s}: {config['name']}")
        tickers = get_tickers(market_key)
        print(f"         {len(tickers)} stocks")
