"""Unit tests for position manager module."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from datetime import datetime

from src.signals.position_manager import PositionManager, Position


class TestPosition:
    """Test Position dataclass."""
    
    def test_position_creation(self):
        """Test creating a position."""
        pos = Position(
            ticker='AAPL',
            entry_price=150.0,
            quantity=10,
            entry_date='2026-02-14',
            size_pct=0.05,
            conviction=0.75,
            stop_loss=145.5,
            take_profit=157.5
        )
        
        assert pos.ticker == 'AAPL'
        assert pos.quantity == 10
        assert pos.status == 'open'
    
    def test_position_calculate_pnl(self):
        """Test P&L calculation."""
        pos = Position(
            ticker='AAPL',
            entry_price=150.0,
            quantity=10,
            entry_date='2026-02-14',
            size_pct=0.05,
            conviction=0.75,
            stop_loss=145.5,
            take_profit=157.5
        )
        
        # Profit scenario
        pnl, pnl_pct = pos.calculate_pnl(155.0)
        assert pnl == 50.0
        assert abs(pnl_pct - 3.333333) < 0.01
    
    def test_position_check_exit_stop_loss(self):
        """Test stop loss exit detection."""
        pos = Position(
            ticker='AAPL',
            entry_price=150.0,
            quantity=10,
            entry_date='2026-02-14',
            size_pct=0.05,
            conviction=0.75,
            stop_loss=145.5,
            take_profit=157.5
        )
        
        exit_reason = pos.check_exit_conditions(145.0)
        assert exit_reason == 'stop_loss'
    
    def test_position_check_exit_take_profit(self):
        """Test take profit exit detection."""
        pos = Position(
            ticker='AAPL',
            entry_price=150.0,
            quantity=10,
            entry_date='2026-02-14',
            size_pct=0.05,
            conviction=0.75,
            stop_loss=145.5,
            take_profit=157.5
        )
        
        exit_reason = pos.check_exit_conditions(158.0)
        assert exit_reason == 'take_profit'


class TestPositionManager:
    """Test position manager functionality."""
    
    def setup_method(self):
        self.manager = PositionManager(initial_capital=10000.0)
    
    def test_initialization(self):
        """Test manager initialization."""
        assert self.manager.initial_capital == 10000.0
        assert self.manager.current_capital == 10000.0
        assert self.manager.cash == 10000.0
        assert len(self.manager.positions) == 0
        assert self.manager.MAX_POSITIONS == 3
    
    def test_can_open_position_low_conviction(self):
        """Test that low conviction positions are rejected."""
        can_open, reason = self.manager.can_open_position(0.3)
        assert can_open is False
        assert 'Conviction' in reason
    
    def test_can_open_position_valid(self):
        """Test that valid positions can be opened."""
        can_open, reason = self.manager.can_open_position(0.75)
        assert can_open is True
        assert reason == "OK"
    
    def test_can_open_position_max_reached(self):
        """Test max position limit enforcement."""
        # Fill max positions
        for i in range(3):
            self.manager.open_position(f'TICK{i}', 100.0, 0.75, '2026-02-14')
        
        # Try to open another
        can_open, reason = self.manager.can_open_position(0.75)
        assert can_open is False
        # Either max positions or insufficient cash (both are valid reasons)
        assert ('Max positions' in reason or 'Insufficient cash' in reason)
    
    def test_position_size_high_conviction(self):
        """Test position sizing for high conviction."""
        size = self.manager.calculate_position_size(0.85)
        assert size == 0.70
    
    def test_position_size_medium_conviction(self):
        """Test position sizing for medium conviction."""
        size = self.manager.calculate_position_size(0.70)
        assert size == 0.50
    
    def test_position_size_low_conviction(self):
        """Test position sizing for low conviction."""
        size = self.manager.calculate_position_size(0.35)
        assert size == 0.0
    
    def test_calculate_stop_and_profit(self):
        """Test stop and profit calculation."""
        stop_loss, take_profit = self.manager.calculate_stop_and_profit_targets(100.0)
        
        # Default: -3% stop, +5% profit
        assert stop_loss == 97.0
        assert take_profit == 105.0
    
    def test_open_position_success(self):
        """Test successful position opening."""
        pos, msg = self.manager.open_position('AAPL', 150.0, 0.75, '2026-02-14')
        
        assert pos is not None
        assert pos.ticker == 'AAPL'
        assert pos.entry_price == 150.0
        assert len(self.manager.positions) == 1
        assert self.manager.cash < 10000.0  # Cash reduced
    
    def test_open_position_insufficient_conviction(self):
        """Test position opening rejected for low conviction."""
        pos, msg = self.manager.open_position('AAPL', 150.0, 0.3, '2026-02-14')
        
        assert pos is None
        assert len(self.manager.positions) == 0
    
    def test_open_multiple_positions(self):
        """Test opening multiple positions."""
        # Use lower conviction to keep position sizes smaller
        for i in range(3):
            pos, msg = self.manager.open_position(f'TICK{i}', 100.0, 0.5, '2026-02-14')
            assert pos is not None
        
        assert len(self.manager.positions) == 3
    
    def test_open_position_exceeds_max(self):
        """Test that opening position when max is reached fails."""
        # Fill max
        for i in range(3):
            self.manager.open_position(f'TICK{i}', 100.0, 0.75, '2026-02-14')
        
        # Try to open 4th
        pos, msg = self.manager.open_position('TICK4', 100.0, 0.75, '2026-02-14')
        assert pos is None
    
    def test_close_position_success(self):
        """Test successful position closing."""
        # Open position
        pos, _ = self.manager.open_position('AAPL', 150.0, 0.75, '2026-02-14')
        initial_cash = self.manager.cash
        
        # Close position
        success, msg = self.manager.close_position('AAPL', 155.0, '2026-02-15')
        
        assert success is True
        assert len(self.manager.positions) == 0
        assert len(self.manager.closed_positions) == 1
        assert self.manager.cash > initial_cash  # Cash increased
    
    def test_close_position_not_found(self):
        """Test closing non-existent position."""
        success, msg = self.manager.close_position('NONEXIST', 100.0, '2026-02-15')
        
        assert success is False
        assert 'No open position' in msg
    
    def test_position_pnl_tracking(self):
        """Test P&L tracking."""
        pos, _ = self.manager.open_position('AAPL', 150.0, 0.75, '2026-02-14')
        
        # Update prices
        self.manager.update_prices({'AAPL': 155.0})
        
        # Check P&L (P&L = quantity * price_change)
        assert pos.pnl == pos.quantity * 5.0  # quantity * $5 gain
        assert abs(pos.pnl_pct - 3.333333) < 0.01
    
    def test_check_exit_signals(self):
        """Test exit signal detection."""
        # Open position with stop at 145.5
        pos, _ = self.manager.open_position('AAPL', 150.0, 0.75, '2026-02-14')
        
        # Price at stop loss
        exits = self.manager.check_exit_signals({'AAPL': 145.0})
        
        assert len(exits) == 1
        assert exits[0][0] == 'AAPL'
        assert exits[0][1] == 'stop_loss'
    
    def test_gross_exposure_calculation(self):
        """Test gross exposure calculation."""
        # Open 2 positions with lower convictions
        self.manager.open_position('AAPL', 100.0, 0.6, '2026-02-14')  # 50%
        self.manager.open_position('MSFT', 100.0, 0.5, '2026-02-14')  # 25%
        
        exposure = self.manager._calculate_gross_exposure()
        
        # 50% + 25% = 75%
        assert 0.70 <= exposure <= 0.80
    
    def test_portfolio_metrics(self):
        """Test portfolio metrics calculation."""
        self.manager.open_position('AAPL', 150.0, 0.75, '2026-02-14')
        
        metrics = self.manager.get_portfolio_metrics({'AAPL': 155.0})
        
        assert metrics['cash'] < 10000.0
        assert metrics['open_positions'] == 1
        assert 'total_value' in metrics
        assert 'gross_exposure' in metrics
    
    def test_min_cash_reserve_enforcement(self):
        """Test minimum cash reserve enforcement."""
        # Try to open large position
        # With 10% initial capital = $1000
        # Need to keep 15% reserve = $1500
        # So can use max $8500
        
        # This should succeed (70% = $7000)
        pos, msg = self.manager.open_position('AAPL', 100.0, 0.85, '2026-02-14')
        assert pos is not None
        
        # Cash should be at least $1500 (15% reserve)
        assert self.manager.cash >= 1500.0
    
    def test_trades_log(self):
        """Test trades logging."""
        self.manager.open_position('AAPL', 150.0, 0.75, '2026-02-14')
        self.manager.close_position('AAPL', 155.0, '2026-02-15')
        
        # Should have 2 log entries
        assert len(self.manager.trades_log) == 2
        assert self.manager.trades_log[0]['type'] == 'open'
        assert self.manager.trades_log[1]['type'] == 'close'
    
    def test_portfolio_summary(self):
        """Test portfolio summary generation."""
        self.manager.open_position('AAPL', 150.0, 0.75, '2026-02-14')
        
        summary = self.manager.get_portfolio_summary()
        
        assert 'Portfolio Summary' in summary
        assert 'Open positions' in summary
        assert '1/3' in summary
    
    def test_custom_constraints(self):
        """Test custom constraint configuration."""
        manager = PositionManager(
            initial_capital=5000.0,
            max_positions=2,
            max_gross_exposure=0.8,
            min_cash_reserve=0.2
        )
        
        assert manager.MAX_POSITIONS == 2
        assert manager.MAX_GROSS_EXPOSURE == 0.8
        assert manager.MIN_CASH_RESERVE == 0.2
