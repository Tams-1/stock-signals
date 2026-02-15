"""
Tests for Phase 5.2: Paper Trading Simulation
"""

import pytest
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from execution.paper_trader import PaperTrader, PaperTrade


@pytest.fixture
def temp_db():
    """Create temporary database."""
    import os
    db_path = tempfile.mktemp(suffix='.db')
    yield db_path
    # Cleanup
    try:
        if os.path.exists(db_path):
            os.remove(db_path)
    except:
        pass


@pytest.fixture
def trader(temp_db):
    """Create PaperTrader instance."""
    return PaperTrader(
        initial_capital=100000.0,
        db_path=temp_db,
        slippage_pct=0.001,
        commission_per_trade=5.0
    )


class TestPaperTradeDataclass:
    """Test PaperTrade dataclass."""
    
    def test_init_creates_instance(self):
        """Test creating PaperTrade instance."""
        trade = PaperTrade(
            ticker='TEST',
            entry_date=datetime.now().isoformat(),
            entry_price=50.0,
            quantity=100
        )
        
        assert trade.ticker == 'TEST'
        assert trade.quantity == 100
        assert trade.status == 'open'
    
    def test_to_dict_conversion(self):
        """Test converting trade to dict."""
        trade = PaperTrade(
            ticker='TEST',
            entry_date=datetime.now().isoformat(),
            entry_price=50.0,
            quantity=100
        )
        
        trade_dict = trade.to_dict()
        assert isinstance(trade_dict, dict)
        assert trade_dict['ticker'] == 'TEST'
        assert trade_dict['quantity'] == 100
    
    def test_close_trade_calculation(self):
        """Test closing a trade and P&L calculation."""
        entry_date = datetime.now()
        exit_date = entry_date + timedelta(days=5)
        
        trade = PaperTrade(
            ticker='TEST',
            entry_date=entry_date.isoformat(),
            entry_price=50.0,
            quantity=100
        )
        trade.entry_cost = 5000.0
        
        # Close with profit
        pnl = trade.close(
            exit_price=55.0,
            exit_date=exit_date.isoformat(),
            slippage=0.001,
            commission=5.0
        )
        
        assert trade.status == 'closed'
        assert trade.exit_price is not None
        assert trade.pnl is not None
        assert trade.pnl > 0  # Profit
        assert trade.win == True
        assert trade.days_held == 5


class TestPaperTraderInitialization:
    """Test paper trader initialization."""
    
    def test_init_creates_instance(self, trader):
        """Test trader initializes correctly."""
        assert trader is not None
        assert trader.initial_capital == 100000.0
        assert trader.current_capital == 100000.0
    
    def test_init_with_custom_slippage(self, temp_db):
        """Test initialization with custom slippage."""
        trader = PaperTrader(
            initial_capital=100000.0,
            db_path=temp_db,
            slippage_pct=0.005,  # 0.5%
            commission_per_trade=10.0
        )
        
        assert trader.slippage_pct == 0.005
        assert trader.commission_per_trade == 10.0
    
    def test_init_creates_database(self, temp_db):
        """Test database is created with required tables."""
        trader = PaperTrader(
            initial_capital=100000.0,
            db_path=temp_db
        )
        
        import sqlite3
        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()
        
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = {row[0] for row in cursor.fetchall()}
        
        assert 'trades' in tables
        assert 'daily_pnl' in tables
        
        conn.close()


class TestEnterTrade:
    """Test entering trades."""
    
    def test_enter_trade_success(self, trader):
        """Test entering a trade successfully."""
        entry_date = datetime.now().isoformat()
        
        trade = trader.enter_trade(
            ticker='TEST',
            entry_price=50.0,
            quantity=100,
            entry_date=entry_date,
            signal_type='momentum',
            conviction=0.85
        )
        
        assert trade is not None
        assert trade.ticker == 'TEST'
        assert trade.quantity == 100
        assert trade.status == 'open'
    
    def test_enter_trade_updates_capital(self, trader):
        """Test entering trade reduces available capital."""
        initial_capital = trader.current_capital
        
        trader.enter_trade(
            ticker='TEST',
            entry_price=50.0,
            quantity=100,
            entry_date=datetime.now().isoformat()
        )
        
        # Capital should be reduced by cost
        assert trader.current_capital < initial_capital
    
    def test_enter_trade_insufficient_capital(self, trader):
        """Test entering trade with insufficient capital."""
        # Try to trade more than capital
        trade = trader.enter_trade(
            ticker='TEST',
            entry_price=50.0,
            quantity=100000,  # Huge quantity
            entry_date=datetime.now().isoformat()
        )
        
        # Should fail
        assert trade is None
    
    def test_enter_trade_duplicate_position_fails(self, trader):
        """Test entering duplicate position fails."""
        entry_date = datetime.now().isoformat()
        
        # First entry succeeds
        trade1 = trader.enter_trade(
            ticker='TEST',
            entry_price=50.0,
            quantity=100,
            entry_date=entry_date
        )
        assert trade1 is not None
        
        # Second entry for same ticker should fail
        trade2 = trader.enter_trade(
            ticker='TEST',
            entry_price=51.0,
            quantity=50,
            entry_date=entry_date
        )
        assert trade2 is None
    
    def test_enter_trade_stores_signal_info(self, trader):
        """Test trade stores signal information."""
        trade = trader.enter_trade(
            ticker='TEST',
            entry_price=50.0,
            quantity=100,
            entry_date=datetime.now().isoformat(),
            signal_type='ensemble',
            conviction=0.80
        )
        
        assert trade.signal_type == 'ensemble'
        assert trade.conviction == 0.80


class TestExitTrade:
    """Test exiting trades."""
    
    def test_exit_trade_success(self, trader):
        """Test exiting a trade successfully."""
        entry_date = datetime.now().isoformat()
        
        # Enter trade
        trader.enter_trade(
            ticker='TEST',
            entry_price=50.0,
            quantity=100,
            entry_date=entry_date
        )
        
        # Exit trade
        exit_date = (datetime.now() + timedelta(days=5)).isoformat()
        closed = trader.exit_trade(
            ticker='TEST',
            exit_price=55.0,
            exit_date=exit_date
        )
        
        assert closed is not None
        assert closed.status == 'closed'
        assert closed.pnl > 0  # Profit
    
    def test_exit_trade_calculates_pnl(self, trader):
        """Test exit trade calculates P&L correctly."""
        # Enter at 50, exit at 55 (10% profit, before costs)
        trader.enter_trade(
            ticker='TEST',
            entry_price=50.0,
            quantity=100,
            entry_date=datetime.now().isoformat()
        )
        
        closed = trader.exit_trade(
            ticker='TEST',
            exit_price=55.0,
            exit_date=datetime.now().isoformat()
        )
        
        # P&L should be calculated
        assert closed.pnl is not None
        assert closed.pnl_pct is not None
    
    def test_exit_trade_non_existent_fails(self, trader):
        """Test exiting non-existent position fails."""
        result = trader.exit_trade(
            ticker='NONEXISTENT',
            exit_price=50.0,
            exit_date=datetime.now().isoformat()
        )
        
        assert result is None
    
    def test_exit_trade_updates_capital(self, trader):
        """Test exiting trade adds proceeds back to capital."""
        initial_capital = trader.current_capital
        
        # Enter trade
        trader.enter_trade(
            ticker='TEST',
            entry_price=50.0,
            quantity=100,
            entry_date=datetime.now().isoformat()
        )
        
        capital_after_entry = trader.current_capital
        
        # Exit with profit
        trader.exit_trade(
            ticker='TEST',
            exit_price=55.0,
            exit_date=datetime.now().isoformat()
        )
        
        capital_after_exit = trader.current_capital
        
        # Capital should increase due to profit
        assert capital_after_exit > capital_after_entry


class TestPortfolioMetrics:
    """Test portfolio metrics calculation."""
    
    def test_calculate_daily_pnl(self, trader):
        """Test daily P&L calculation."""
        daily = trader.calculate_daily_pnl()
        
        assert 'date' in daily
        assert 'pnl_realized' in daily
        assert 'pnl_unrealized' in daily
        assert 'pnl_total' in daily
        assert 'equity' in daily
        assert 'return_pct' in daily
    
    def test_get_portfolio_metrics(self, trader):
        """Test portfolio metrics structure."""
        metrics = trader.get_portfolio_metrics()
        
        assert 'total_trades' in metrics
        assert 'winning_trades' in metrics
        assert 'losing_trades' in metrics
        assert 'win_rate_pct' in metrics
        assert 'gross_pnl' in metrics
        assert 'max_drawdown_pct' in metrics
        assert 'total_return_pct' in metrics
    
    def test_metrics_with_trades(self, trader):
        """Test metrics calculation with actual trades."""
        # Enter and exit multiple trades
        for i in range(3):
            trader.enter_trade(
                ticker=f'TEST{i}',
                entry_price=50.0 + i,
                quantity=100,
                entry_date=(datetime.now() - timedelta(days=10-i)).isoformat()
            )
            
            trader.exit_trade(
                ticker=f'TEST{i}',
                exit_price=55.0 + i,
                exit_date=(datetime.now() - timedelta(days=5-i)).isoformat()
            )
        
        metrics = trader.get_portfolio_metrics()
        
        assert metrics['total_trades'] == 3
        assert metrics['winning_trades'] == 3
        assert metrics['win_rate_pct'] == 100.0
        assert metrics['total_return_pct'] > 0
    
    def test_win_rate_calculation(self, trader):
        """Test win rate calculation."""
        # Winning trade
        trader.enter_trade(
            ticker='WIN',
            entry_price=50.0,
            quantity=100,
            entry_date=datetime.now().isoformat()
        )
        trader.exit_trade(
            ticker='WIN',
            exit_price=55.0,
            exit_date=datetime.now().isoformat()
        )
        
        # Losing trade
        trader.enter_trade(
            ticker='LOSE',
            entry_price=50.0,
            quantity=100,
            entry_date=datetime.now().isoformat()
        )
        trader.exit_trade(
            ticker='LOSE',
            exit_price=45.0,
            exit_date=datetime.now().isoformat()
        )
        
        metrics = trader.get_portfolio_metrics()
        
        assert metrics['total_trades'] == 2
        assert metrics['winning_trades'] == 1
        assert metrics['losing_trades'] == 1
        assert metrics['win_rate_pct'] == 50.0
    
    def test_max_drawdown_calculation(self, trader):
        """Test max drawdown calculation."""
        # Create winning then losing trades to simulate drawdown
        for i in range(3):
            ticker = f'TEST{i}'
            entry_price = 50.0 + (i * 5)
            
            trader.enter_trade(
                ticker=ticker,
                entry_price=entry_price,
                quantity=100,
                entry_date=(datetime.now() - timedelta(days=10)).isoformat()
            )
            
            # Alternate wins and losses
            if i % 2 == 0:
                exit_price = entry_price * 1.10  # 10% gain
            else:
                exit_price = entry_price * 0.90  # 10% loss
            
            trader.exit_trade(
                ticker=ticker,
                exit_price=exit_price,
                exit_date=(datetime.now() - timedelta(days=5)).isoformat()
            )
        
        metrics = trader.get_portfolio_metrics()
        
        # Max drawdown should be negative
        assert metrics['max_drawdown_pct'] <= 0


class TestReporting:
    """Test reporting functionality."""
    
    def test_generate_daily_report(self, trader):
        """Test daily report generation."""
        report = trader.generate_daily_report()
        
        assert isinstance(report, str)
        assert 'DAILY' in report or 'Daily' in report or 'daily' in report
        assert 'P&L' in report or 'P&L' in report or 'pnl' in report.lower()
    
    def test_daily_report_with_trades(self, trader):
        """Test report includes trade data."""
        trader.enter_trade(
            ticker='TEST',
            entry_price=50.0,
            quantity=100,
            entry_date=datetime.now().isoformat()
        )
        
        trader.exit_trade(
            ticker='TEST',
            exit_price=55.0,
            exit_date=datetime.now().isoformat()
        )
        
        report = trader.generate_daily_report()
        
        # Report should mention win rate, equity, etc.
        assert 'Win Rate' in report or 'win' in report.lower()


class TestTradeHistory:
    """Test trade history retrieval."""
    
    def test_get_trade_history(self, trader):
        """Test getting closed trade history."""
        history = trader.get_trade_history(limit=100)
        assert isinstance(history, list)
    
    def test_get_open_positions(self, trader):
        """Test getting open positions."""
        positions = trader.get_open_positions()
        
        assert isinstance(positions, list)
        assert len(positions) == 0  # None open initially
        
        # Enter a position
        trader.enter_trade(
            ticker='TEST',
            entry_price=50.0,
            quantity=100,
            entry_date=datetime.now().isoformat()
        )
        
        positions = trader.get_open_positions()
        assert len(positions) == 1
        assert positions[0]['ticker'] == 'TEST'


class TestSlippageAndCommission:
    """Test slippage and commission handling."""
    
    def test_slippage_applied_on_entry(self, trader):
        """Test slippage is applied on entry."""
        initial = trader.current_capital
        
        trade = trader.enter_trade(
            ticker='TEST',
            entry_price=50.0,
            quantity=100,
            entry_date=datetime.now().isoformat()
        )
        
        # Cost should include slippage
        # 100 * 50 = 5000, slippage = 5000 * 0.001 = 5, commission = 5
        # Total = 5010
        expected_cost = 50.0 * 100 + (50.0 * 100 * 0.001) + 5.0
        
        assert abs(trade.entry_cost - expected_cost) < 1.0
    
    def test_commission_deducted(self):
        """Test commission is properly deducted."""
        # Create trader with higher commission
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            temp_db = f.name
        
        try:
            trader = PaperTrader(
                initial_capital=100000.0,
                db_path=temp_db,
                commission_per_trade=20.0
            )
            
            initial = trader.current_capital
            
            trade = trader.enter_trade(
                ticker='TEST',
                entry_price=50.0,
                quantity=100,
                entry_date=datetime.now().isoformat()
            )
            
            # Commission should be $20
            reduction = initial - trader.current_capital
            assert reduction > 50 * 100  # More than price due to commission
        finally:
            import os
            try:
                os.remove(temp_db)
            except:
                pass


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
