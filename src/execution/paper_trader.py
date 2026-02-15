"""
Phase 5.2: Paper Trading Simulation

Live paper trader that:
- Tracks hypothetical entries/exits using live prices
- Applies realistic costs (0.1% slippage + $5/trade)
- Calculates daily P&L
- Tracks win rate, avg trade size, drawdown
- Reports daily to Telegram
"""

import pandas as pd
import numpy as np
import sqlite3
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass, asdict
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class PaperTrade:
    """Single paper trade record."""
    id: Optional[int] = None
    ticker: str = ""
    entry_date: str = ""
    entry_price: float = 0.0
    quantity: int = 0
    entry_cost: float = 0.0  # entry_price * quantity + fees
    exit_date: Optional[str] = None
    exit_price: Optional[float] = None
    exit_cost: float = 0.0  # exit_price * quantity - fees
    pnl: Optional[float] = None
    pnl_pct: Optional[float] = None
    win: bool = False
    days_held: int = 0
    signal_type: str = ""
    conviction: float = 0.0
    status: str = "open"  # open, closed
    
    def to_dict(self) -> Dict:
        """Convert to dict."""
        return asdict(self)
    
    def close(self, exit_price: float, exit_date: str, slippage: float = 0.001, commission: float = 5.0):
        """Close the trade."""
        self.exit_price = exit_price * (1 - slippage)  # Apply slippage
        self.exit_date = exit_date
        self.exit_cost = self.exit_price * self.quantity - commission
        self.pnl = self.exit_cost - self.entry_cost
        self.pnl_pct = (self.pnl / self.entry_cost) * 100 if self.entry_cost > 0 else 0
        self.win = self.pnl > 0
        
        # Calculate days held
        entry_dt = datetime.fromisoformat(self.entry_date)
        exit_dt = datetime.fromisoformat(self.exit_date)
        self.days_held = (exit_dt - entry_dt).days
        
        self.status = "closed"
        return self.pnl


class PaperTrader:
    """Simulate paper trading with realistic costs and tracking."""
    
    def __init__(
        self,
        initial_capital: float = 100000.0,
        db_path: str = 'paper_trading.db',
        slippage_pct: float = 0.001,  # 0.1% slippage
        commission_per_trade: float = 5.0,  # $5 per trade
        telegram_token: Optional[str] = None,
        telegram_chat_id: Optional[str] = None
    ):
        """
        Initialize Paper Trader.
        
        Args:
            initial_capital: Starting capital
            db_path: Path to SQLite database
            slippage_pct: Slippage as % of trade (default 0.1%)
            commission_per_trade: Fixed commission per trade (default $5)
            telegram_token: Telegram bot token (optional)
            telegram_chat_id: Telegram chat ID (optional)
        """
        self.initial_capital = initial_capital
        self.db_path = db_path
        self.slippage_pct = slippage_pct
        self.commission_per_trade = commission_per_trade
        self.telegram_token = telegram_token
        self.telegram_chat_id = telegram_chat_id
        
        # State
        self.current_capital = initial_capital
        self.open_positions = {}  # {ticker: PaperTrade}
        self.closed_trades = []
        self.daily_pnl = {}  # {date: pnl}
        self.daily_returns = {}  # {date: return_pct}
        
        self._init_db()
        self._load_trades()
        
        logger.info(f"PaperTrader initialized with ${initial_capital:.2f}")
    
    def _init_db(self):
        """Initialize SQLite database."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Trades table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker TEXT,
                entry_date TEXT,
                entry_price REAL,
                quantity INTEGER,
                entry_cost REAL,
                exit_date TEXT,
                exit_price REAL,
                exit_cost REAL,
                pnl REAL,
                pnl_pct REAL,
                win INTEGER,
                days_held INTEGER,
                signal_type TEXT,
                conviction REAL,
                status TEXT,
                created_at TEXT
            )
        ''')
        
        # Daily P&L table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS daily_pnl (
                date TEXT PRIMARY KEY,
                total_pnl REAL,
                return_pct REAL,
                equity REAL,
                open_positions INTEGER,
                closed_trades INTEGER
            )
        ''')
        
        conn.commit()
        conn.close()
        logger.info("Paper trading database initialized")
    
    def _load_trades(self):
        """Load existing trades from database."""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Load open positions
            cursor.execute('SELECT * FROM trades WHERE status = ?', ('open',))
            for row in cursor.fetchall():
                trade = self._row_to_trade(row)
                self.open_positions[trade.ticker] = trade
            
            # Load closed trades
            cursor.execute('SELECT * FROM trades WHERE status = ?', ('closed',))
            self.closed_trades = [self._row_to_trade(row) for row in cursor.fetchall()]
            
            conn.close()
            logger.info(f"Loaded {len(self.open_positions)} open positions and {len(self.closed_trades)} closed trades")
        except Exception as e:
            logger.error(f"Error loading trades: {e}")
    
    @staticmethod
    def _row_to_trade(row) -> PaperTrade:
        """Convert database row to PaperTrade object."""
        return PaperTrade(
            id=row['id'],
            ticker=row['ticker'],
            entry_date=row['entry_date'],
            entry_price=row['entry_price'],
            quantity=row['quantity'],
            entry_cost=row['entry_cost'],
            exit_date=row['exit_date'],
            exit_price=row['exit_price'],
            exit_cost=row['exit_cost'],
            pnl=row['pnl'],
            pnl_pct=row['pnl_pct'],
            win=bool(row['win']),
            days_held=row['days_held'],
            signal_type=row['signal_type'],
            conviction=row['conviction'],
            status=row['status']
        )
    
    def enter_trade(
        self,
        ticker: str,
        entry_price: float,
        quantity: int,
        entry_date: str,
        signal_type: str = "",
        conviction: float = 0.0
    ) -> Optional[PaperTrade]:
        """
        Enter a new paper trade.
        
        Args:
            ticker: Stock ticker
            entry_price: Entry price per share
            quantity: Number of shares
            entry_date: Entry date (ISO format)
            signal_type: Type of signal that triggered entry
            conviction: Conviction score of signal
            
        Returns:
            PaperTrade object, or None if insufficient capital
        """
        try:
            # Check if already have position in this ticker
            if ticker in self.open_positions:
                logger.warning(f"Already have open position in {ticker}")
                return None
            
            # Calculate costs with slippage and commission
            gross_cost = entry_price * quantity
            slippage_cost = gross_cost * self.slippage_pct
            total_cost = gross_cost + slippage_cost + self.commission_per_trade
            
            # Check capital
            if total_cost > self.current_capital:
                logger.warning(f"Insufficient capital for {ticker}: need ${total_cost:.2f}, have ${self.current_capital:.2f}")
                return None
            
            # Create trade
            trade = PaperTrade(
                ticker=ticker,
                entry_date=entry_date,
                entry_price=entry_price,
                quantity=quantity,
                entry_cost=total_cost,
                signal_type=signal_type,
                conviction=conviction,
                status="open"
            )
            
            # Update capital
            self.current_capital -= total_cost
            
            # Store trade
            self.open_positions[ticker] = trade
            self._save_trade(trade)
            
            logger.info(f"Entered {ticker}: {quantity} @ ${entry_price:.2f}, cost ${total_cost:.2f}")
            return trade
        except Exception as e:
            logger.error(f"Error entering trade for {ticker}: {e}")
            return None
    
    def exit_trade(
        self,
        ticker: str,
        exit_price: float,
        exit_date: str
    ) -> Optional[PaperTrade]:
        """
        Exit an open paper trade.
        
        Args:
            ticker: Stock ticker
            exit_price: Exit price per share
            exit_date: Exit date (ISO format)
            
        Returns:
            Closed PaperTrade object, or None if no open position
        """
        try:
            if ticker not in self.open_positions:
                logger.warning(f"No open position in {ticker}")
                return None
            
            trade = self.open_positions[ticker]
            
            # Close the trade
            pnl = trade.close(exit_price, exit_date, self.slippage_pct, self.commission_per_trade)
            
            # Update capital
            self.current_capital += trade.exit_cost
            
            # Move to closed trades
            del self.open_positions[ticker]
            self.closed_trades.append(trade)
            self._save_trade(trade)
            
            logger.info(f"Exited {ticker}: P&L ${pnl:.2f} ({trade.pnl_pct:.2f}%), held {trade.days_held} days")
            return trade
        except Exception as e:
            logger.error(f"Error exiting trade for {ticker}: {e}")
            return None
    
    def _save_trade(self, trade: PaperTrade):
        """Save trade to database."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            if trade.id is None:
                # Insert new trade
                cursor.execute('''
                    INSERT INTO trades (
                        ticker, entry_date, entry_price, quantity, entry_cost,
                        exit_date, exit_price, exit_cost, pnl, pnl_pct, win,
                        days_held, signal_type, conviction, status, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    trade.ticker, trade.entry_date, trade.entry_price, trade.quantity,
                    trade.entry_cost, trade.exit_date, trade.exit_price, trade.exit_cost,
                    trade.pnl, trade.pnl_pct, int(trade.win), trade.days_held,
                    trade.signal_type, trade.conviction, trade.status, datetime.now().isoformat()
                ))
                trade.id = cursor.lastrowid
            else:
                # Update existing trade
                cursor.execute('''
                    UPDATE trades SET
                        exit_date=?, exit_price=?, exit_cost=?, pnl=?, pnl_pct=?,
                        win=?, days_held=?, status=?
                    WHERE id=?
                ''', (
                    trade.exit_date, trade.exit_price, trade.exit_cost, trade.pnl,
                    trade.pnl_pct, int(trade.win), trade.days_held, trade.status,
                    trade.id
                ))
            
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Error saving trade: {e}")
    
    def calculate_daily_pnl(self) -> Dict:
        """Calculate daily P&L metrics."""
        try:
            today = datetime.now().strftime('%Y-%m-%d')
            
            # Calculate P&L from closed trades today
            today_closed = [t for t in self.closed_trades if t.exit_date and t.exit_date.startswith(today)]
            today_pnl = sum(t.pnl for t in today_closed) if today_closed else 0.0
            
            # Calculate current unrealized P&L from open positions
            unrealized_pnl = 0.0
            for trade in self.open_positions.values():
                unrealized_pnl += (trade.entry_price - trade.entry_price) * trade.quantity  # Placeholder
            
            total_pnl = today_pnl + unrealized_pnl
            total_equity = self.initial_capital + total_pnl
            daily_return = (total_pnl / self.initial_capital) * 100
            
            result = {
                'date': today,
                'pnl_realized': today_pnl,
                'pnl_unrealized': unrealized_pnl,
                'pnl_total': total_pnl,
                'equity': total_equity,
                'return_pct': daily_return,
                'trades_closed': len(today_closed),
                'positions_open': len(self.open_positions)
            }
            
            self.daily_pnl[today] = total_pnl
            self.daily_returns[today] = daily_return
            
            return result
        except Exception as e:
            logger.error(f"Error calculating daily P&L: {e}")
            return {}
    
    def get_portfolio_metrics(self) -> Dict:
        """Calculate comprehensive portfolio metrics."""
        try:
            # Total metrics
            total_trades = len(self.closed_trades)
            winning_trades = sum(1 for t in self.closed_trades if t.win)
            losing_trades = total_trades - winning_trades
            win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
            
            # P&L metrics
            gross_pnl = sum(t.pnl for t in self.closed_trades) if self.closed_trades else 0.0
            avg_win = np.mean([t.pnl for t in self.closed_trades if t.win]) if winning_trades > 0 else 0.0
            avg_loss = np.mean([t.pnl for t in self.closed_trades if not t.win]) if losing_trades > 0 else 0.0
            win_loss_ratio = abs(avg_win / avg_loss) if avg_loss != 0 else float('inf')
            
            # Drawdown metrics
            equity_curve = [self.initial_capital]
            for trade in sorted(self.closed_trades, key=lambda t: t.exit_date):
                equity_curve.append(equity_curve[-1] + trade.pnl)
            
            max_equity = max(equity_curve) if equity_curve else self.initial_capital
            current_equity = equity_curve[-1] if equity_curve else self.initial_capital
            max_drawdown = min((x - max_equity) / max_equity * 100 for x in equity_curve) if equity_curve else 0
            
            # Average trade metrics
            avg_trade_size = np.mean([t.entry_cost for t in self.closed_trades]) if self.closed_trades else 0
            avg_days_held = np.mean([t.days_held for t in self.closed_trades]) if self.closed_trades else 0
            
            # Signal quality (% of signals that hit targets)
            high_conviction_trades = [t for t in self.closed_trades if t.conviction >= 0.8]
            signal_quality = (len([t for t in high_conviction_trades if t.win]) / len(high_conviction_trades) * 100) if high_conviction_trades else 0
            
            result = {
                'total_trades': total_trades,
                'winning_trades': winning_trades,
                'losing_trades': losing_trades,
                'win_rate_pct': win_rate,
                'gross_pnl': gross_pnl,
                'avg_win': avg_win,
                'avg_loss': avg_loss,
                'win_loss_ratio': win_loss_ratio,
                'max_drawdown_pct': max_drawdown,
                'max_equity': max_equity,
                'current_equity': current_equity,
                'total_return_pct': ((current_equity - self.initial_capital) / self.initial_capital * 100),
                'avg_trade_size': avg_trade_size,
                'avg_days_held': avg_days_held,
                'signal_quality_pct': signal_quality,
                'open_positions': len(self.open_positions)
            }
            
            return result
        except Exception as e:
            logger.error(f"Error calculating portfolio metrics: {e}")
            return {}
    
    def generate_daily_report(self) -> str:
        """Generate daily report for Telegram."""
        try:
            daily = self.calculate_daily_pnl()
            metrics = self.get_portfolio_metrics()
            
            report = "📊 *DAILY PAPER TRADING REPORT*\n\n"
            report += f"Date: {daily.get('date', 'N/A')}\n\n"
            
            # Daily P&L
            report += "*Daily P&L*\n"
            report += f"Realized: ${daily.get('pnl_realized', 0):.2f}\n"
            report += f"Unrealized: ${daily.get('pnl_unrealized', 0):.2f}\n"
            report += f"Total: ${daily.get('pnl_total', 0):.2f} ({daily.get('return_pct', 0):.2f}%)\n\n"
            
            # Equity
            report += "*Portfolio*\n"
            report += f"Equity: ${daily.get('equity', 0):.2f}\n"
            report += f"Open Positions: {daily.get('positions_open', 0)}\n"
            report += f"Trades Closed Today: {daily.get('trades_closed', 0)}\n\n"
            
            # Overall metrics
            report += "*Overall Performance*\n"
            report += f"Total Return: {metrics.get('total_return_pct', 0):.2f}%\n"
            report += f"Win Rate: {metrics.get('win_rate_pct', 0):.1f}%\n"
            report += f"Max Drawdown: {metrics.get('max_drawdown_pct', 0):.2f}%\n"
            report += f"Win/Loss Ratio: {metrics.get('win_loss_ratio', 0):.2f}x\n"
            report += f"Signal Quality: {metrics.get('signal_quality_pct', 0):.1f}%\n"
            
            return report
        except Exception as e:
            logger.error(f"Error generating daily report: {e}")
            return f"Error generating report: {e}"
    
    def send_daily_report(self):
        """Send daily report via Telegram."""
        try:
            if not self.telegram_token or not self.telegram_chat_id:
                logger.warning("Telegram not configured, skipping report")
                return
            
            report = self.generate_daily_report()
            
            import requests
            url = f"https://api.telegram.org/bot{self.telegram_token}/sendMessage"
            data = {
                'chat_id': self.telegram_chat_id,
                'text': report,
                'parse_mode': 'Markdown'
            }
            response = requests.post(url, json=data, timeout=5)
            if response.status_code == 200:
                logger.info("Daily report sent via Telegram")
            else:
                logger.warning(f"Telegram send failed: {response.text}")
        except Exception as e:
            logger.warning(f"Error sending Telegram report: {e}")
    
    def get_trade_history(self, limit: int = 100) -> List[Dict]:
        """Get closed trades history."""
        return [t.to_dict() for t in self.closed_trades[-limit:]]
    
    def get_open_positions(self) -> List[Dict]:
        """Get current open positions."""
        return [t.to_dict() for t in self.open_positions.values()]


def main():
    """Demo: Run paper trader."""
    trader = PaperTrader(initial_capital=100000.0, db_path='paper_trading_demo.db')
    
    # Simulate some trades
    print("\n📈 Paper Trading Simulation Demo\n")
    
    # Enter a trade
    trade1 = trader.enter_trade(
        ticker='VALE3.SA',
        entry_price=55.50,
        quantity=100,
        entry_date=datetime.now().isoformat(),
        signal_type='momentum',
        conviction=0.85
    )
    if trade1:
        print(f"✅ Entered: {trade1.ticker} - Entry cost: ${trade1.entry_cost:.2f}")
    
    # Exit the trade
    time.sleep(1)
    closed = trader.exit_trade(
        ticker='VALE3.SA',
        exit_price=56.00,
        exit_date=datetime.now().isoformat()
    )
    if closed:
        print(f"✅ Exited: {closed.ticker} - P&L: ${closed.pnl:.2f} ({closed.pnl_pct:.2f}%)")
    
    # Print metrics
    metrics = trader.get_portfolio_metrics()
    print(f"\n📊 Portfolio Metrics:")
    print(f"  Total Trades: {metrics['total_trades']}")
    print(f"  Win Rate: {metrics['win_rate_pct']:.1f}%")
    print(f"  Total Return: {metrics['total_return_pct']:.2f}%")
    print(f"  Gross P&L: ${metrics['gross_pnl']:.2f}")
    
    # Generate daily report
    print(f"\n{trader.generate_daily_report()}")


if __name__ == '__main__':
    import time
    main()
