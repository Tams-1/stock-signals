#!/usr/bin/env python3
"""
Daily Signal Generation - Deploy on Monday
Runs at market open (9:30 AM ET) to generate live trading signals
"""

import sys
from pathlib import Path
import pandas as pd
import numpy as np
import logging
from datetime import datetime

# Add paths
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))
sys.path.insert(0, str(Path(__file__).parent.parent / 'backtest'))

from data.extended_fetcher import ExtendedDataFetcher, SP500_TOP_50, IBOV_TOP_30
from signals.ensemble_signal_generator import EnsembleSignalGenerator
from live_signal_generator import LiveSignalGenerator

logger = logging.getLogger(__name__)

class DailySignalRunner:
    """Generate and export live signals for Monday deployment"""
    
    def __init__(self, market: str = 'US', output_dir: str = 'signals'):
        self.market = market
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        
        self.fetcher = ExtendedDataFetcher(periods=504)  # Use 2 years for signal generation
        self.signal_gen = EnsembleSignalGenerator()
        self.live_gen = LiveSignalGenerator()
    
    def run(self, export_formats: list = ['json', 'csv', 'txt']) -> dict:
        """
        Generate signals for entire market
        Returns: {format: filepath, ...}
        """
        logger.info(f"\n{'='*60}")
        logger.info(f"LIVE SIGNAL GENERATION: {self.market} Market")
        logger.info(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info(f"{'='*60}\n")
        
        # Fetch current data
        logger.info(f"[1] Fetching latest {self.market} market data...")
        market_data = self.fetcher.get_market_data(self.market)
        logger.info(f"✓ Fetched {len(market_data)} stocks\n")
        
        if not market_data:
            logger.error("Failed to fetch data!")
            return {}
        
        # Generate live signals
        logger.info(f"[2] Generating live signals using 6-method ensemble...")
        signals = self.live_gen.generate_live_portfolio(market_data, self.signal_gen)
        logger.info(f"✓ Generated {len(signals)} signals")
        
        # Count actionable signals
        actionable = sum(1 for s in signals if s['actionable'])
        buys = sum(1 for s in signals if s['signal']['direction'] == 'bullish' and s['actionable'])
        sells = sum(1 for s in signals if s['signal']['direction'] == 'bearish' and s['actionable'])
        
        logger.info(f"  • Actionable signals: {actionable}")
        logger.info(f"  • BUY signals: {buys}")
        logger.info(f"  • SELL signals: {sells}\n")
        
        # Export signals
        results = {}
        
        if 'json' in export_formats:
            json_file = str(self.output_dir / f'signals_{self.market}_{datetime.now().strftime("%Y%m%d")}.json')
            self.live_gen.export_to_json(signals, json_file)
            results['json'] = json_file
        
        if 'csv' in export_formats:
            csv_file = str(self.output_dir / f'signals_{self.market}_{datetime.now().strftime("%Y%m%d")}.csv')
            self.live_gen.export_to_csv(signals, csv_file)
            results['csv'] = csv_file
        
        if 'txt' in export_formats:
            txt_file = str(self.output_dir / f'trading_plan_{self.market}_{datetime.now().strftime("%Y%m%d")}.txt')
            self.live_gen.save_trading_plan(signals, txt_file)
            results['txt'] = txt_file
        
        # Print summary
        logger.info(f"[3] Summary\n")
        self._print_top_signals(signals, 'bullish', limit=5)
        self._print_top_signals(signals, 'bearish', limit=5)
        
        logger.info(f"\n[4] Export Complete")
        for fmt, path in results.items():
            logger.info(f"  ✓ {fmt.upper()}: {path}")
        
        return results
    
    def _print_top_signals(self, signals: list, direction: str, limit: int = 5):
        """Print top signals for direction"""
        filtered = [s for s in signals 
                   if s['signal']['direction'] == direction and s['actionable']]
        
        if not filtered:
            return
        
        action = 'BUY' if direction == 'bullish' else 'SELL'
        logger.info(f"\nTop {limit} {action} Signals:")
        logger.info("-" * 60)
        
        for sig in sorted(filtered, key=lambda x: x['signal']['confidence'], reverse=True)[:limit]:
            conf = int(sig['signal']['confidence'])
            ticker = sig['ticker']
            price = sig['current_price']
            target = sig['risk_management']['target_price']
            stop = sig['risk_management']['stop_loss_price']
            rr = sig['risk_management']['risk_reward_ratio']
            
            emoji = "🚀" if conf >= 70 else "📈"
            logger.info(f"{emoji} {ticker:8} {price:7.2f} → T:{target:7.2f} S:{stop:7.2f} RR:{rr:4.2f}x ({conf}%)")
    
    def generate_telegram_message(self, signals: list) -> str:
        """Generate Telegram-friendly message"""
        buys = [s for s in signals if s['signal']['direction'] == 'bullish' and s['actionable']]
        
        if not buys:
            return f"📊 No strong signals at {datetime.now().strftime('%H:%M')}"
        
        return self.live_gen.format_for_telegram(buys[:5], self.market)


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Generate daily trading signals')
    parser.add_argument('--market', choices=['US', 'BR'], default='US', help='Market to generate signals for')
    parser.add_argument('--export', nargs='+', choices=['json', 'csv', 'txt'], 
                       default=['json', 'csv', 'txt'], help='Export formats')
    parser.add_argument('--output', default='signals', help='Output directory')
    parser.add_argument('--telegram', action='store_true', help='Send to Telegram (requires setup)')
    
    args = parser.parse_args()
    
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(message)s'
    )
    
    # Run signal generation
    runner = DailySignalRunner(market=args.market, output_dir=args.output)
    results = runner.run(export_formats=args.export)
    
    # Optional: Send to Telegram
    if args.telegram:
        logger.warning("Telegram integration not yet implemented")
        logger.warning("Requires: telegram bot token + chat ID")
    
    logger.info(f"\n✓ Daily signals complete. Ready for execution.\n")


if __name__ == '__main__':
    main()
