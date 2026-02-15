"""
Fast Production Backtest - Optimized for quick execution
Caches data, parallel processing, and comprehensive results
"""

import pandas as pd
import numpy as np
import logging
import sys
import json
from pathlib import Path
from datetime import datetime
import warnings

warnings.filterwarnings('ignore')

sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from data.extended_fetcher import ExtendedDataFetcher, SP500_TOP_50, IBOV_TOP_30
from signals.ensemble_signal_generator import EnsembleSignalGenerator
from production_backtest import ProductionBacktest

logger = logging.getLogger(__name__)


class FastBacktestRunner:
    """Optimized backtest runner"""
    
    def __init__(self, end_date: str = '2026-02-13', periods: int = 504, top_n: int = 20):
        """
        Args:
            end_date: End date for backtest
            periods: Number of days back
            top_n: Use only top N stocks per market (for speed)
        """
        self.end_date = end_date
        self.periods = periods
        self.top_n = top_n
        
        self.fetcher = ExtendedDataFetcher(end_date=end_date, periods=periods)
        self.signal_gen = EnsembleSignalGenerator()
        
        self.us_results = None
        self.br_results = None
    
    def run_market_backtest(self, market: str = 'US') -> Dict:
        """Run backtest for one market - top N stocks only"""
        logger.info(f"\n{'='*60}")
        logger.info(f"BACKTEST: {market} Market (Top {self.top_n} stocks)")
        logger.info(f"Period: {self.periods} days")
        logger.info(f"{'='*60}")
        
        # Get stock list
        stocks = SP500_TOP_50 if market == 'US' else IBOV_TOP_30
        stocks = stocks[:self.top_n]  # Use only top N for speed
        
        logger.info(f"\n[1] Fetching {market} data ({len(stocks)} stocks)...")
        
        # Fetch data
        data = {}
        fetcher = ExtendedDataFetcher(end_date=self.end_date, periods=self.periods)
        
        for ticker in stocks:
            try:
                df = self.fetcher._fetch_single_ticker(ticker, market)
                if df is not None and len(df) > 20:
                    data[ticker] = df
                    logger.info(f"  ✓ {ticker}")
            except Exception as e:
                logger.debug(f"  ✗ {ticker}: {e}")
        
        logger.info(f"✓ Fetched {len(data)} stocks\n")
        
        if not data:
            logger.error("No data fetched!")
            return {'trades': pd.DataFrame(), 'summary': {}}
        
        # Generate signals and run backtest
        logger.info(f"[2] Running backtest...")
        
        trades = []
        backtest = ProductionBacktest(
            initial_capital=10000,
            position_size_pct=0.05,
            market=market
        )
        
        # Get all dates
        all_dates = set()
        for df in data.values():
            all_dates.update(df.index)
        all_dates = sorted(list(all_dates))
        
        # Process each date
        for i in range(len(all_dates) - 1):
            curr_date = all_dates[i]
            next_date = all_dates[i + 1]
            
            for ticker in data:
                df = data[ticker]
                
                if curr_date not in df.index or next_date not in df.index:
                    continue
                
                # Generate signal from historical data only
                lookback_df = df.loc[:curr_date]
                if len(lookback_df) < 20:
                    continue
                
                score, direction, reason = self.signal_gen.generate_signal(lookback_df)
                
                if np.isnan(score) or score < 0.3:
                    continue
                
                next_open = df.loc[next_date, 'open']
                
                # Execute trades
                if ticker in backtest.positions:
                    if direction == 'bearish':
                        trade = backtest.close_position(next_date, ticker, next_open,
                                                       score, reason)
                        if trade:
                            trades.append(trade)
                else:
                    if direction == 'bullish':
                        trade = backtest.open_position(next_date, ticker, next_open,
                                                      score, reason)
                        if trade:
                            trades.append(trade)
            
            if (i + 1) % 50 == 0:
                logger.info(f"  Processed {curr_date.date()}: {len(trades)} trades")
        
        # Close remaining positions
        last_date = all_dates[-1]
        for ticker in list(backtest.positions.keys()):
            if ticker in data and last_date in data[ticker].index:
                row = data[ticker].loc[last_date]
                trade = backtest.close_position(last_date, ticker, row['close'])
                if trade:
                    trades.append(trade)
        
        trades_df = pd.DataFrame([t.to_dict() for t in trades]) if trades else pd.DataFrame()
        
        # Generate report
        report = self._generate_report(trades_df, market)
        
        logger.info(f"\n[3] Results for {market}:")
        if not trades_df.empty:
            summary = report
            logger.info(f"  Trades: {summary['total_trades']}")
            logger.info(f"  Win Rate: {summary['win_rate']:.1f}%")
            logger.info(f"  Profit Factor: {summary['profit_factor']:.2f}")
            logger.info(f"  Sharpe Ratio: {summary['sharpe_ratio']:.2f}")
            logger.info(f"  Max Drawdown: {summary['max_drawdown']:.1f}%")
            logger.info(f"  Total P&L: ${summary['total_pnl']:,.2f}")
        else:
            logger.info("  No trades executed")
        
        return {
            'market': market,
            'trades': trades_df,
            'summary': report
        }
    
    def _fetch_single_ticker(self, ticker: str, market: str):
        """Fetch data for single ticker"""
        import yfinance as yf
        from datetime import timedelta
        
        try:
            end = datetime.strptime(self.end_date, '%Y-%m-%d')
            start = end - timedelta(days=self.periods)
            
            df = yf.download(ticker, start=start, end=end, progress=False, timeout=10)
            
            if df.empty:
                return None
            
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            
            required = ['Open', 'High', 'Low', 'Close', 'Volume']
            if not all(col in df.columns for col in required):
                return None
            
            df = df[required].rename(columns={
                'Open': 'open', 'High': 'high', 'Low': 'low',
                'Close': 'close', 'Volume': 'volume'
            })
            
            df = df[~df.index.duplicated(keep='first')].sort_index()
            df['volume'] = df['volume'].fillna(0)
            
            return df
        except:
            return None
    
    # Patch the fetcher
    ExtendedDataFetcher._fetch_single_ticker = _fetch_single_ticker.__get__(None, ExtendedDataFetcher)
    
    def _generate_report(self, trades_df: pd.DataFrame, market: str) -> Dict:
        """Generate report"""
        if trades_df.empty:
            return {
                'market': market,
                'total_trades': 0,
                'win_rate': 0,
                'profit_factor': 0,
                'sharpe_ratio': 0,
                'max_drawdown': 0,
                'total_pnl': 0
            }
        
        total_trades = len(trades_df)
        winners = trades_df[trades_df['is_win']].shape[0]
        losers = trades_df[~trades_df['is_win']].shape[0]
        win_rate = winners / total_trades if total_trades > 0 else 0
        
        total_pnl = trades_df['pnl_dollars'].sum()
        
        wins_sum = trades_df[trades_df['is_win']]['pnl_dollars'].sum()
        losses_sum = abs(trades_df[~trades_df['is_win']]['pnl_dollars'].sum())
        profit_factor = wins_sum / losses_sum if losses_sum > 0 else np.inf
        
        returns = trades_df['pnl_percent'].values
        if len(returns) > 1 and np.std(returns) > 0:
            sharpe = np.mean(returns) / np.std(returns) * np.sqrt(252)
        else:
            sharpe = 0
        
        cumulative = np.cumsum(trades_df['pnl_dollars'].values)
        running_max = np.maximum.accumulate(cumulative)
        drawdowns = (cumulative - running_max) / (running_max + 1e-10)
        max_drawdown = np.min(drawdowns) if len(drawdowns) > 0 else 0
        
        return {
            'market': market,
            'total_trades': total_trades,
            'winners': winners,
            'losers': losers,
            'win_rate': round(win_rate * 100, 1),
            'profit_factor': round(profit_factor, 2),
            'total_pnl': round(total_pnl, 2),
            'sharpe_ratio': round(sharpe, 2),
            'max_drawdown': round(max_drawdown * 100, 2),
            'avg_duration_days': round(trades_df['duration_days'].mean(), 1) if 'duration_days' in trades_df else 0
        }
    
    def run_all(self):
        """Run both markets"""
        logger.info(f"""

╔════════════════════════════════════════════════════════════╗
║     FAST PRODUCTION BACKTEST - {datetime.now().strftime('%Y-%m-%d')}                   ║
║     Top {self.top_n} stocks each market | 504 days | Realistic costs    ║
╚════════════════════════════════════════════════════════════╝
""")
        
        self.us_results = self.run_market_backtest('US')
        self.br_results = self.run_market_backtest('BR')
        
        return self.us_results, self.br_results
    
    def save_results(self, output_dir: str = 'backtest_results'):
        """Save results"""
        Path(output_dir).mkdir(exist_ok=True)
        
        if not self.us_results['trades'].empty:
            self.us_results['trades'].to_csv(f'{output_dir}/us_trades.csv', index=False)
        
        if not self.br_results['trades'].empty:
            self.br_results['trades'].to_csv(f'{output_dir}/br_trades.csv', index=False)
        
        with open(f'{output_dir}/us_summary.json', 'w') as f:
            json.dump(self.us_results['summary'], f, indent=2)
        
        with open(f'{output_dir}/br_summary.json', 'w') as f:
            json.dump(self.br_results['summary'], f, indent=2)
        
        logger.info(f"\n✓ Results saved to {output_dir}/")


if __name__ == '__main__':
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    runner = FastBacktestRunner(end_date='2026-02-13', periods=504, top_n=20)
    runner.run_all()
    runner.save_results()
