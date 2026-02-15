"""
Phase 5.3: Main Execution Loop

Integrates all Phase 1-4 modules into a cohesive system:
- 1-minute update cycle (or configurable)
- Error handling and recovery
- Graceful shutdown
- Heartbeat monitoring
- Real-time signal generation → strategy routing → paper trading
"""

import logging
import signal
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional
import json

sys.path.insert(0, str(Path(__file__).parent.parent))

from execution.live_monitor import LiveMonitor
from execution.paper_trader import PaperTrader
from execution.strategy_router import StrategyRouter
from signals.position_manager import PositionManager

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('executor.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class MainExecutor:
    """Main execution loop integrating all modules."""
    
    def __init__(
        self,
        tickers: List[str],
        initial_capital: float = 100000.0,
        cycle_interval: int = 60,  # seconds
        telegram_token: Optional[str] = None,
        telegram_chat_id: Optional[str] = None,
        paper_trading_enabled: bool = True,
        live_trading_enabled: bool = False,
        db_path: str = 'executor.db'
    ):
        """
        Initialize Main Executor.
        
        Args:
            tickers: List of tickers to monitor
            initial_capital: Initial capital for trading
            cycle_interval: Seconds between monitoring cycles (default 60 = 1-min)
            telegram_token: Telegram bot token (optional)
            telegram_chat_id: Telegram chat ID (optional)
            paper_trading_enabled: Enable paper trading simulation
            live_trading_enabled: Enable live trading (DANGEROUS - set to False by default)
            db_path: Path to SQLite database
        """
        self.tickers = tickers
        self.initial_capital = initial_capital
        self.cycle_interval = cycle_interval
        self.telegram_token = telegram_token
        self.telegram_chat_id = telegram_chat_id
        self.paper_trading_enabled = paper_trading_enabled
        self.live_trading_enabled = live_trading_enabled
        self.db_path = db_path
        
        # Execution state
        self.running = False
        self.cycle_count = 0
        self.last_heartbeat = datetime.now()
        self.last_daily_report = datetime.now()
        
        # Initialize modules
        self.monitor = LiveMonitor(
            tickers=tickers,
            db_path=db_path,
            telegram_token=telegram_token,
            telegram_chat_id=telegram_chat_id,
            initial_capital=initial_capital
        )
        
        self.router = StrategyRouter()
        
        if paper_trading_enabled:
            self.trader = PaperTrader(
                initial_capital=initial_capital,
                db_path=f'paper_{db_path}',
                telegram_token=telegram_token,
                telegram_chat_id=telegram_chat_id
            )
        else:
            self.trader = None
        
        self.position_manager = PositionManager(initial_capital=initial_capital)
        
        # Signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._handle_shutdown)
        signal.signal(signal.SIGTERM, self._handle_shutdown)
        
        logger.info(f"MainExecutor initialized with {len(tickers)} tickers")
        logger.info(f"Paper Trading: {'ENABLED' if paper_trading_enabled else 'DISABLED'}")
        logger.info(f"Live Trading: {'ENABLED' if live_trading_enabled else 'DISABLED (SAFE)'}")
    
    def _handle_shutdown(self, signum, frame):
        """Handle graceful shutdown on Ctrl+C or SIGTERM."""
        logger.info(f"Shutdown signal received ({signum})")
        self.running = False
        logger.info("Executor shutting down gracefully...")
        
        # Send final report
        if self.trader:
            logger.info("Sending final report...")
            self.trader.send_daily_report()
        
        sys.exit(0)
    
    def heartbeat(self):
        """Health check and monitoring."""
        try:
            now = datetime.now()
            elapsed = (now - self.last_heartbeat).total_seconds()
            
            logger.debug(f"Heartbeat: Cycle {self.cycle_count}, Uptime {elapsed:.0f}s")
            
            # Check for long delays
            if elapsed > self.cycle_interval * 3:
                logger.warning(f"Long delay detected: {elapsed:.0f}s")
            
            # Daily report (once per day)
            if (now - self.last_daily_report).total_seconds() > 86400:
                if self.trader:
                    logger.info("Sending daily report...")
                    self.trader.send_daily_report()
                self.last_daily_report = now
            
            self.last_heartbeat = now
        except Exception as e:
            logger.error(f"Heartbeat error: {e}")
    
    def run_cycle(self) -> Dict:
        """
        Run one complete monitoring and execution cycle.
        
        Returns:
            Dict with cycle results
        """
        self.cycle_count += 1
        cycle_start = time.time()
        
        result = {
            'cycle': self.cycle_count,
            'timestamp': datetime.now().isoformat(),
            'duration_sec': 0,
            'tickers_processed': 0,
            'signals_generated': 0,
            'alerts_triggered': 0,
            'trades_executed': 0,
            'errors': 0,
            'details': {}
        }
        
        try:
            logger.info(f"Starting cycle {self.cycle_count}")
            
            for ticker in self.tickers:
                try:
                    # 1. Run live monitoring cycle
                    monitor_result = self.monitor.run_cycle(ticker)
                    result['details'][ticker] = {
                        'price': monitor_result.get('price'),
                        'regime': monitor_result.get('regime'),
                        'signals': len(monitor_result.get('signals', [])),
                        'alerts': len(monitor_result.get('alerts', []))
                    }
                    result['tickers_processed'] += 1
                    
                    if monitor_result.get('error'):
                        logger.warning(f"Monitor error for {ticker}: {monitor_result['error']}")
                        result['errors'] += 1
                        continue
                    
                    # Count signals and alerts
                    result['signals_generated'] += len(monitor_result.get('signals', []))
                    result['alerts_triggered'] += len(monitor_result.get('alerts', []))
                    
                    # 2. Get routing decision for high-conviction signals
                    regime = monitor_result.get('regime', {})
                    if regime:
                        regime_str = regime.get('regime', 'unknown')
                        regime_confidence = regime.get('confidence', 0.5)
                        
                        # For demonstration: route to strategy
                        routing_decision = self.router.route_signal(
                            regime=regime_str,
                            conviction=0.75,  # Would come from actual signal
                            signal_type='ensemble',
                            direction='bullish',
                            signal_strength=0.7,
                            regime_confidence=regime_confidence
                        )
                        
                        logger.info(f"{ticker}: Route → {routing_decision['selected_strategy']}")
                        
                        # 3. Paper trading (if enabled)
                        if self.paper_trading_enabled and self.trader:
                            strategy = routing_decision['selected_strategy']
                            if strategy in ['buy', 'momentum']:
                                # Would enter position here
                                pass
                    
                    logger.info(f"✓ {ticker} processed successfully")
                
                except Exception as e:
                    logger.error(f"Error processing {ticker}: {e}")
                    result['errors'] += 1
                    continue
            
            # Generate cycle summary
            cycle_duration = time.time() - cycle_start
            result['duration_sec'] = cycle_duration
            
            logger.info(f"Cycle {self.cycle_count} complete: {result['tickers_processed']} tickers, "
                       f"{result['signals_generated']} signals, {result['alerts_triggered']} alerts, "
                       f"{cycle_duration:.2f}s")
            
            # Heartbeat check
            self.heartbeat()
            
        except Exception as e:
            logger.error(f"Critical error in cycle: {e}")
            result['error'] = str(e)
        
        return result
    
    def run(self, duration_minutes: Optional[int] = None):
        """
        Run the execution loop continuously.
        
        Args:
            duration_minutes: Max minutes to run, or None for continuous
        """
        self.running = True
        start_time = datetime.now()
        
        logger.info("="*60)
        logger.info("MAIN EXECUTOR STARTED")
        logger.info("="*60)
        
        try:
            while self.running:
                try:
                    # Check duration limit
                    if duration_minutes:
                        elapsed = (datetime.now() - start_time).total_seconds() / 60
                        if elapsed > duration_minutes:
                            logger.info(f"Duration limit reached ({duration_minutes} minutes)")
                            break
                    
                    # Run cycle
                    cycle_result = self.run_cycle()
                    
                    # Wait for next cycle
                    elapsed = time.time()
                    wait_time = self.cycle_interval - (elapsed % self.cycle_interval)
                    if wait_time > 0:
                        logger.debug(f"Waiting {wait_time:.1f}s until next cycle...")
                        time.sleep(wait_time)
                
                except Exception as e:
                    logger.error(f"Cycle error: {e}")
                    # Continue with next cycle after brief delay
                    time.sleep(5)
        
        except KeyboardInterrupt:
            logger.info("Interrupted by user")
        
        finally:
            self.running = False
            self._shutdown()
    
    def _shutdown(self):
        """Clean shutdown."""
        logger.info("="*60)
        logger.info("MAIN EXECUTOR SHUTDOWN")
        logger.info("="*60)
        
        # Final report
        if self.trader:
            metrics = self.trader.get_portfolio_metrics()
            logger.info(f"Final Portfolio Metrics:")
            logger.info(f"  Total Trades: {metrics.get('total_trades', 0)}")
            logger.info(f"  Win Rate: {metrics.get('win_rate_pct', 0):.1f}%")
            logger.info(f"  Total Return: {metrics.get('total_return_pct', 0):.2f}%")
            logger.info(f"  Max Drawdown: {metrics.get('max_drawdown_pct', 0):.2f}%")
        
        logger.info(f"Total cycles executed: {self.cycle_count}")
        logger.info("Executor stopped")
    
    def get_status(self) -> Dict:
        """Get current executor status."""
        status = {
            'running': self.running,
            'cycles': self.cycle_count,
            'uptime_sec': (datetime.now() - self.last_heartbeat).total_seconds(),
            'tickers_monitored': len(self.tickers),
            'paper_trading_enabled': self.paper_trading_enabled,
            'live_trading_enabled': self.live_trading_enabled,
            'last_heartbeat': self.last_heartbeat.isoformat(),
            'cycle_interval_sec': self.cycle_interval
        }
        
        if self.trader:
            metrics = self.trader.get_portfolio_metrics()
            status['trading_metrics'] = {
                'total_trades': metrics.get('total_trades', 0),
                'win_rate_pct': metrics.get('win_rate_pct', 0),
                'total_return_pct': metrics.get('total_return_pct', 0),
                'equity': metrics.get('current_equity', self.initial_capital)
            }
        
        return status
    
    def get_performance_summary(self) -> Dict:
        """Get performance summary."""
        summary = {
            'timestamp': datetime.now().isoformat(),
            'cycles_completed': self.cycle_count
        }
        
        # Monitor stats
        total_signals = 0
        total_alerts = 0
        for ticker in self.tickers:
            alerts = self.monitor.get_alert_history(ticker, limit=1000)
            total_alerts += len(alerts)
            
            signals = self.monitor.get_signal_history(ticker, limit=1000)
            total_signals += len(signals)
        
        summary['total_signals_generated'] = total_signals
        summary['total_alerts_triggered'] = total_alerts
        
        # Trading stats
        if self.trader:
            metrics = self.trader.get_portfolio_metrics()
            summary['trading'] = {
                'total_trades': metrics.get('total_trades', 0),
                'winning_trades': metrics.get('winning_trades', 0),
                'losing_trades': metrics.get('losing_trades', 0),
                'win_rate_pct': metrics.get('win_rate_pct', 0),
                'gross_pnl': metrics.get('gross_pnl', 0),
                'total_return_pct': metrics.get('total_return_pct', 0),
                'max_drawdown_pct': metrics.get('max_drawdown_pct', 0),
                'current_equity': metrics.get('current_equity', self.initial_capital),
                'open_positions': metrics.get('open_positions', 0),
                'signal_quality_pct': metrics.get('signal_quality_pct', 0)
            }
        
        return summary


def main():
    """Demo: Run the main executor."""
    # Configuration
    tickers = ['VALE3.SA', 'PETR4.SA', 'ITUB4.SA']
    initial_capital = 100000.0
    cycle_interval = 60  # seconds (1-min)
    
    # Create executor
    executor = MainExecutor(
        tickers=tickers,
        initial_capital=initial_capital,
        cycle_interval=cycle_interval,
        paper_trading_enabled=True,
        live_trading_enabled=False  # Always False for safety
    )
    
    # Print initial status
    print("\n" + "="*60)
    print("MAIN EXECUTOR INITIALIZATION")
    print("="*60)
    status = executor.get_status()
    print(f"Tickers: {status['tickers_monitored']}")
    print(f"Initial Capital: ${initial_capital:.2f}")
    print(f"Cycle Interval: {status['cycle_interval_sec']}s")
    print(f"Paper Trading: {'ENABLED' if status['paper_trading_enabled'] else 'DISABLED'}")
    print(f"Live Trading: {'ENABLED' if status['live_trading_enabled'] else 'DISABLED (SAFE)'}")
    print("="*60 + "\n")
    
    # Run for demo (5 minutes)
    print("Running for 5 minutes of demo...\n")
    executor.run(duration_minutes=5)
    
    # Print final status
    print("\n" + "="*60)
    print("FINAL PERFORMANCE SUMMARY")
    print("="*60)
    summary = executor.get_performance_summary()
    print(f"Cycles Completed: {summary['cycles_completed']}")
    print(f"Total Signals: {summary['total_signals_generated']}")
    print(f"Total Alerts: {summary['total_alerts_triggered']}")
    
    if 'trading' in summary:
        trading = summary['trading']
        print(f"\nTrading Performance:")
        print(f"  Total Trades: {trading['total_trades']}")
        print(f"  Win Rate: {trading['win_rate_pct']:.1f}%")
        print(f"  Total Return: {trading['total_return_pct']:.2f}%")
        print(f"  Max Drawdown: {trading['max_drawdown_pct']:.2f}%")
        print(f"  Current Equity: ${trading['current_equity']:.2f}")
    print("="*60 + "\n")


if __name__ == '__main__':
    main()
