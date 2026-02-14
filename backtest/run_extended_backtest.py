"""
Extended Backtest Runner: 1-2 years, realistic costs, multi-market
Produces comprehensive results with signal quality metrics
"""

import pandas as pd
import numpy as np
import logging
import sys
from pathlib import Path
from datetime import datetime
import json

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from data.extended_fetcher import ExtendedDataFetcher, SP500_TOP_50, IBOV_TOP_30
from signals.ensemble_signal_generator import EnsembleSignalGenerator
from backtest.production_backtest import ProductionBacktest

logger = logging.getLogger(__name__)

class ExtendedBacktestRunner:
    """Run comprehensive 1-2 year backtest across multiple markets"""
    
    def __init__(self, end_date: str = '2026-02-13', periods: int = 504):  # 2 years
        self.end_date = end_date
        self.periods = periods
        self.fetcher = ExtendedDataFetcher(end_date=end_date, periods=periods)
        self.signal_gen = EnsembleSignalGenerator()
        
        self.us_results = None
        self.br_results = None
        self.all_trades = []
    
    def run_market_backtest(self, market: str = 'US') -> Dict:
        """Run backtest for one market"""
        logger.info(f"\n{'='*60}")
        logger.info(f"BACKTEST: {market} Market")
        logger.info(f"Period: {self.periods} days")
        logger.info(f"{'='*60}")
        
        # Fetch data
        logger.info(f"\n[1] Fetching {market} data...")
        market_data = self.fetcher.get_market_data(market)
        logger.info(f"✓ Fetched {len(market_data)} stocks")
        
        if not market_data:
            logger.error("No data fetched!")
            return {'trades': [], 'summary': {}}
        
        # Add forward returns to avoid look-ahead bias
        logger.info(f"\n[2] Processing data (adding forward returns)...")
        for ticker in market_data:
            market_data[ticker] = ExtendedDataFetcher.add_forward_returns(market_data[ticker])
        
        # Generate signals for all stocks
        logger.info(f"\n[3] Generating signals for {len(market_data)} stocks...")
        signals = {}
        
        for i, ticker in enumerate(market_data):
            df = market_data[ticker]
            signals[ticker] = df.copy()
            
            # Add signal columns
            signals[ticker]['signal_score'] = np.nan
            signals[ticker]['signal_direction'] = 'neutral'
            signals[ticker]['signal_reason'] = ''
            signals[ticker]['confidence'] = 0.0
            
            # Generate signal for each bar
            for idx in range(20, len(df)):  # Need 20 bars of history
                lookback_df = df.iloc[:idx]
                
                score, direction, reasoning = self.signal_gen.generate_signal(lookback_df)
                
                signals[ticker].iloc[idx, signals[ticker].columns.get_loc('signal_score')] = score
                signals[ticker].iloc[idx, signals[ticker].columns.get_loc('signal_direction')] = direction
                signals[ticker].iloc[idx, signals[ticker].columns.get_loc('signal_reason')] = reasoning
                signals[ticker].iloc[idx, signals[ticker].columns.get_loc('confidence')] = score
            
            if (i + 1) % 10 == 0:
                logger.info(f"  Processed {i+1}/{len(market_data)} stocks")
        
        logger.info(f"✓ Signals generated")
        
        # Run backtest
        logger.info(f"\n[4] Running backtest with realistic costs...")
        backtest = ProductionBacktest(
            initial_capital=10000,
            position_size_pct=0.05,
            market=market
        )
        
        # Convert signals to format needed
        trades_df = self._run_backtest_loop(backtest, market_data, signals)
        
        # Generate report
        logger.info(f"\n[5] Generating report...")
        report = self._generate_report(trades_df, market)
        
        return {
            'market': market,
            'trades': trades_df,
            'summary': report,
            'data': market_data
        }
    
    def _run_backtest_loop(self, backtest, market_data, signals):
        """Iterate through dates and execute trades"""
        # Get all dates sorted
        all_dates = set()
        for df in market_data.values():
            all_dates.update(df.index)
        all_dates = sorted(list(all_dates))
        
        trades = []
        
        for i in range(len(all_dates) - 1):
            curr_date = all_dates[i]
            next_date = all_dates[i + 1]
            
            # Process each stock
            for ticker in market_data:
                df = market_data[ticker]
                sig_df = signals[ticker]
                
                if curr_date not in df.index or next_date not in df.index:
                    continue
                
                curr_row = df.loc[curr_date]
                next_row = df.loc[next_date]
                sig_row = sig_df.loc[curr_date]
                
                # Get signal
                signal_score = sig_row.get('signal_score', 0)
                direction = sig_row.get('signal_direction', 'neutral')
                reason = sig_row.get('signal_reason', '')
                confidence = sig_row.get('confidence', 0)
                
                if pd.isna(signal_score) or signal_score == 0:
                    continue
                
                # Execute at next open (no look-ahead bias)
                next_open = next_row['open']
                
                # Check if we should trade
                if ticker in backtest.positions:
                    if direction == 'bearish':
                        # Exit
                        trade = backtest.close_position(next_date, ticker, next_open)
                        if trade:
                            trades.append(trade)
                else:
                    if direction == 'bullish' and confidence > 0.4:
                        # Entry
                        trade = backtest.open_position(next_date, ticker, next_open, 
                                                      confidence, reason)
                        if trade:
                            trades.append(trade)
            
            if (i + 1) % 100 == 0:
                logger.info(f"  Processed {curr_date.date()}: {len(trades)} trades")
        
        # Close remaining positions
        last_date = all_dates[-1]
        for ticker in list(backtest.positions.keys()):
            if ticker in market_data and last_date in market_data[ticker].index:
                row = market_data[ticker].loc[last_date]
                trade = backtest.close_position(last_date, ticker, row['close'])
                if trade:
                    trades.append(trade)
        
        return pd.DataFrame([t.to_dict() for t in trades]) if trades else pd.DataFrame()
    
    def _generate_report(self, trades_df: pd.DataFrame, market: str) -> Dict:
        """Generate comprehensive report"""
        if trades_df.empty:
            logger.warning(f"No trades executed for {market}")
            return {
                'market': market,
                'total_trades': 0,
                'win_rate': 0,
                'profit_factor': 0,
                'sharpe_ratio': 0,
                'max_drawdown': 0,
                'total_pnl': 0,
                'avg_trade': 0
            }
        
        # Basic stats
        total_trades = len(trades_df)
        winners = trades_df[trades_df['is_win']].shape[0]
        losers = trades_df[~trades_df['is_win']].shape[0]
        win_rate = winners / total_trades if total_trades > 0 else 0
        
        # P&L
        total_pnl = trades_df['pnl_dollars'].sum()
        avg_trade = total_pnl / total_trades
        
        # Profit factor
        wins_sum = trades_df[trades_df['is_win']]['pnl_dollars'].sum()
        losses_sum = abs(trades_df[~trades_df['is_win']]['pnl_dollars'].sum())
        profit_factor = wins_sum / losses_sum if losses_sum > 0 else np.inf
        
        # Sharpe ratio
        returns = trades_df['pnl_percent'].values
        if len(returns) > 1 and np.std(returns) > 0:
            sharpe = np.mean(returns) / np.std(returns) * np.sqrt(252)
        else:
            sharpe = 0
        
        # Max drawdown (approximate from trade returns)
        cumulative = np.cumsum(trades_df['pnl_dollars'].values)
        running_max = np.maximum.accumulate(cumulative)
        drawdowns = (cumulative - running_max) / (running_max + 1e-10)
        max_drawdown = np.min(drawdowns) if len(drawdowns) > 0 else 0
        
        # Per-stock breakdown
        stock_stats = {}
        for ticker in trades_df['ticker'].unique():
            ticker_trades = trades_df[trades_df['ticker'] == ticker]
            ticker_wins = ticker_trades[ticker_trades['is_win']].shape[0]
            ticker_total = len(ticker_trades)
            ticker_wr = ticker_wins / ticker_total if ticker_total > 0 else 0
            ticker_pnl = ticker_trades['pnl_dollars'].sum()
            
            stock_stats[ticker] = {
                'trades': ticker_total,
                'win_rate': round(ticker_wr * 100, 1),
                'pnl': round(ticker_pnl, 2)
            }
        
        report = {
            'market': market,
            'total_trades': total_trades,
            'winners': winners,
            'losers': losers,
            'win_rate': round(win_rate * 100, 1),
            'avg_win': round(trades_df[trades_df['is_win']]['pnl_dollars'].mean(), 2),
            'avg_loss': round(trades_df[~trades_df['is_win']]['pnl_dollars'].mean(), 2),
            'profit_factor': round(profit_factor, 2),
            'total_pnl': round(total_pnl, 2),
            'avg_trade': round(avg_trade, 2),
            'sharpe_ratio': round(sharpe, 2),
            'max_drawdown': round(max_drawdown * 100, 2),
            'avg_duration_days': round(trades_df['duration_days'].mean(), 1),
            'by_stock': stock_stats
        }
        
        return report
    
    def run_all(self):
        """Run backtest for all markets"""
        logger.info(f"""
        
╔═══════════════════════════════════════════════════════════╗
║     EXTENDED STOCK SIGNAL DETECTOR - PRODUCTION BACKTEST   ║
║     1-2 Years | Realistic Costs | No Look-Ahead Bias       ║
╚═══════════════════════════════════════════════════════════╝
""")
        
        # US Market
        self.us_results = self.run_market_backtest('US')
        
        # BR Market
        self.br_results = self.run_market_backtest('BR')
        
        # Combined analysis
        self._print_summary()
        
        return self.us_results, self.br_results
    
    def _print_summary(self):
        """Print final summary"""
        logger.info(f"\n{'='*60}")
        logger.info(f"COMBINED SUMMARY")
        logger.info(f"{'='*60}\n")
        
        for result in [self.us_results, self.br_results]:
            if result['trades'].empty:
                continue
            
            summary = result['summary']
            logger.info(f"{summary['market']} Market:")
            logger.info(f"  Trades: {summary['total_trades']}")
            logger.info(f"  Win Rate: {summary['win_rate']:.1f}%")
            logger.info(f"  Total P&L: ${summary['total_pnl']:,.2f}")
            logger.info(f"  Profit Factor: {summary['profit_factor']:.2f}")
            logger.info(f"  Sharpe Ratio: {summary['sharpe_ratio']:.2f}")
            logger.info(f"  Max Drawdown: {summary['max_drawdown']:.1f}%")
            logger.info()
        
        logger.info(f"{'='*60}")
        logger.info("✓ Backtest complete")
    
    def save_results(self, output_dir: str = 'backtest_results'):
        """Save all results to files"""
        Path(output_dir).mkdir(exist_ok=True)
        
        # Save US trades
        if not self.us_results['trades'].empty:
            self.us_results['trades'].to_csv(f'{output_dir}/us_trades.csv', index=False)
            
        # Save BR trades
        if not self.br_results['trades'].empty:
            self.br_results['trades'].to_csv(f'{output_dir}/br_trades.csv', index=False)
        
        # Save summaries
        with open(f'{output_dir}/us_summary.json', 'w') as f:
            json.dump(self.us_results['summary'], f, indent=2)
        
        with open(f'{output_dir}/br_summary.json', 'w') as f:
            json.dump(self.br_results['summary'], f, indent=2)
        
        logger.info(f"✓ Results saved to {output_dir}/")


if __name__ == '__main__':
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Run extended backtest (2 years, realistic costs)
    runner = ExtendedBacktestRunner(end_date='2026-02-13', periods=504)
    runner.run_all()
    runner.save_results()
