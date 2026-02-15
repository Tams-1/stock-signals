"""
Position Manager: Dynamic position sizing and portfolio constraints.

Enforces:
- Conviction-based position sizing
- Max 3 concurrent positions
- Max 100% gross exposure (no leverage)
- Min 15% cash reserve
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class Position:
    """Represents a single position in the portfolio."""
    ticker: str
    entry_price: float
    quantity: int
    entry_date: str
    size_pct: float  # % of initial capital
    conviction: float  # Conviction score at entry
    stop_loss: float
    take_profit: float
    status: str = 'open'  # open, closed, stopped_out, profit_taken
    exit_price: Optional[float] = None
    exit_date: Optional[str] = None
    pnl: Optional[float] = None
    pnl_pct: Optional[float] = None
    
    def calculate_pnl(self, current_price: float):
        """Calculate current P&L."""
        if self.status == 'open':
            self.pnl = (current_price - self.entry_price) * self.quantity
            self.pnl_pct = (current_price - self.entry_price) / self.entry_price * 100
        return self.pnl, self.pnl_pct
    
    def check_exit_conditions(self, current_price: float) -> Optional[str]:
        """Check if exit conditions are met.
        
        Returns:
            'stop_loss' if stop hit
            'take_profit' if profit target hit
            None if still open
        """
        if current_price <= self.stop_loss:
            return 'stop_loss'
        elif current_price >= self.take_profit:
            return 'take_profit'
        return None


class PositionManager:
    """Manage portfolio positions with conviction-based sizing and constraints."""
    
    # Portfolio constraints
    MAX_POSITIONS = 3
    MAX_GROSS_EXPOSURE = 1.0  # 100% (no leverage)
    MIN_CASH_RESERVE = 0.15  # 15% minimum
    
    def __init__(self, initial_capital: float = 10000.0, 
                 max_positions: int = 3,
                 max_gross_exposure: float = 1.0,
                 min_cash_reserve: float = 0.15):
        """
        Initialize position manager.
        
        Args:
            initial_capital: Starting portfolio value
            max_positions: Max concurrent positions (default 3)
            max_gross_exposure: Max gross exposure as % of capital (default 100%)
            min_cash_reserve: Min cash to keep (default 15%)
        """
        self.initial_capital = initial_capital
        self.current_capital = initial_capital
        self.cash = initial_capital
        
        self.MAX_POSITIONS = max_positions
        self.MAX_GROSS_EXPOSURE = max_gross_exposure
        self.MIN_CASH_RESERVE = min_cash_reserve
        
        self.positions: List[Position] = []
        self.closed_positions: List[Position] = []
        self.trades_log: List[Dict] = []
    
    def can_open_position(self, conviction: float) -> Tuple[bool, str]:
        """
        Check if new position can be opened given constraints.
        
        Args:
            conviction: Conviction score (0-1.0)
        
        Returns:
            (can_open: bool, reason: str)
        """
        # Check if conviction is high enough
        if conviction < 0.4:
            return False, "Conviction too low (<0.4)"
        
        # Check max positions constraint
        open_count = len([p for p in self.positions if p.status == 'open'])
        if open_count >= self.MAX_POSITIONS:
            return False, f"Max positions ({self.MAX_POSITIONS}) reached"
        
        # Check cash constraint (need at least 15%)
        min_cash_needed = self.initial_capital * self.MIN_CASH_RESERVE
        if self.cash < min_cash_needed:
            return False, f"Insufficient cash (need {min_cash_needed:.2f}, have {self.cash:.2f})"
        
        return True, "OK"
    
    def calculate_position_size(self, conviction: float) -> float:
        """
        Calculate position size based on conviction.
        
        Returns:
            Size as % of capital (0.0-0.7)
        
        Conviction levels:
        - 0.8+: 70% of capital
        - 0.6-0.8: 50%
        - 0.4-0.6: 25%
        - <0.4: Skip trade
        """
        if conviction >= 0.8:
            return 0.70
        elif conviction >= 0.6:
            return 0.50
        elif conviction >= 0.4:
            return 0.25
        else:
            return 0.0
    
    def calculate_stop_and_profit_targets(self, entry_price: float) -> Tuple[float, float]:
        """
        Calculate stop loss and take profit levels.
        
        Returns:
            (stop_loss_price, take_profit_price)
        
        Defaults:
        - Stop loss: -3% from entry
        - Take profit: +5% from entry
        """
        stop_loss = entry_price * (1 - 0.03)
        take_profit = entry_price * (1 + 0.05)
        
        return stop_loss, take_profit
    
    def open_position(self, ticker: str, entry_price: float, conviction: float,
                     entry_date: str) -> Tuple[Optional[Position], str]:
        """
        Open a new position.
        
        Args:
            ticker: Stock ticker
            entry_price: Entry price
            conviction: Conviction score
            entry_date: Entry date
        
        Returns:
            (position: Position or None, message: str)
        """
        # Check constraints
        can_open, reason = self.can_open_position(conviction)
        if not can_open:
            return None, reason
        
        # Calculate size
        size_pct = self.calculate_position_size(conviction)
        if size_pct == 0:
            return None, "Conviction insufficient for position sizing"
        
        # Check gross exposure
        current_exposure = self._calculate_gross_exposure()
        if current_exposure + size_pct > self.MAX_GROSS_EXPOSURE:
            # Reduce size to fit constraint
            available_exposure = self.MAX_GROSS_EXPOSURE - current_exposure
            if available_exposure < 0.05:  # Less than 5% available
                return None, f"Gross exposure limit reached ({current_exposure:.1%})"
            size_pct = min(size_pct, available_exposure)
        
        # Calculate quantities and prices
        capital_to_invest = self.initial_capital * size_pct
        quantity = int(capital_to_invest / entry_price)
        
        if quantity == 0:
            return None, "Position size too small"
        
        # Calculate stop and profit
        stop_loss, take_profit = self.calculate_stop_and_profit_targets(entry_price)
        
        # Create position
        position = Position(
            ticker=ticker,
            entry_price=entry_price,
            quantity=quantity,
            entry_date=entry_date,
            size_pct=size_pct,
            conviction=conviction,
            stop_loss=stop_loss,
            take_profit=take_profit
        )
        
        # Update cash
        self.cash -= quantity * entry_price
        self.positions.append(position)
        
        # Log trade
        self.trades_log.append({
            'type': 'open',
            'ticker': ticker,
            'date': entry_date,
            'entry_price': entry_price,
            'quantity': quantity,
            'conviction': conviction,
            'size_pct': size_pct
        })
        
        logger.info(f"Opened {ticker}: {quantity} @ ${entry_price:.2f} (conviction={conviction:.2f})")
        
        return position, "Position opened"
    
    def close_position(self, ticker: str, exit_price: float, exit_date: str,
                      reason: str = 'manual') -> Tuple[bool, str]:
        """
        Close an open position.
        
        Args:
            ticker: Stock ticker
            exit_price: Exit price
            exit_date: Exit date
            reason: Reason for closure (manual, stop_loss, take_profit, regime_change)
        
        Returns:
            (success: bool, message: str)
        """
        # Find position
        position = None
        for p in self.positions:
            if p.ticker == ticker and p.status == 'open':
                position = p
                break
        
        if position is None:
            return False, f"No open position found for {ticker}"
        
        # Calculate P&L
        pnl = (exit_price - position.entry_price) * position.quantity
        pnl_pct = (exit_price - position.entry_price) / position.entry_price * 100
        
        # Update position
        position.exit_price = exit_price
        position.exit_date = exit_date
        position.pnl = pnl
        position.pnl_pct = pnl_pct
        position.status = 'closed'
        
        # Return capital
        self.cash += position.quantity * exit_price
        
        # Move to closed
        self.positions.remove(position)
        self.closed_positions.append(position)
        
        # Log trade
        self.trades_log.append({
            'type': 'close',
            'ticker': ticker,
            'date': exit_date,
            'exit_price': exit_price,
            'pnl': pnl,
            'pnl_pct': pnl_pct,
            'reason': reason
        })
        
        logger.info(f"Closed {ticker}: P&L = ${pnl:.2f} ({pnl_pct:.2f}%)")
        
        return True, f"Position closed: P&L = ${pnl:.2f} ({pnl_pct:.2f}%)"
    
    def update_prices(self, prices: Dict[str, float]):
        """
        Update current prices for all positions.
        
        Args:
            prices: {ticker: current_price}
        """
        for position in self.positions:
            if position.ticker in prices:
                position.calculate_pnl(prices[position.ticker])
    
    def check_exit_signals(self, prices: Dict[str, float]) -> List[Tuple[str, str]]:
        """
        Check for positions that should be closed.
        
        Returns:
            List of (ticker, reason) tuples
        """
        exits = []
        
        for position in self.positions:
            if position.ticker not in prices:
                continue
            
            current_price = prices[position.ticker]
            exit_reason = position.check_exit_conditions(current_price)
            
            if exit_reason:
                exits.append((position.ticker, exit_reason))
        
        return exits
    
    def get_portfolio_metrics(self, prices: Dict[str, float]) -> Dict:
        """
        Calculate current portfolio metrics.
        
        Returns:
            {
                'total_value': float,
                'cash': float,
                'gross_exposure': float,
                'net_exposure': float,
                'open_positions': int,
                'unrealized_pnl': float,
                'unrealized_pnl_pct': float,
                'positions': [...]
            }
        """
        # Update prices
        self.update_prices(prices)
        
        # Calculate portfolio value
        position_value = sum(p.quantity * prices.get(p.ticker, p.entry_price) 
                           for p in self.positions)
        total_value = self.cash + position_value
        
        # Calculate exposure
        gross_exposure = self._calculate_gross_exposure()
        net_exposure = sum(p.size_pct for p in self.positions)
        
        # Calculate P&L
        unrealized_pnl = sum(p.pnl or 0 for p in self.positions if p.status == 'open')
        unrealized_pnl_pct = (unrealized_pnl / self.initial_capital * 100) if self.initial_capital > 0 else 0
        
        # Realized P&L
        realized_pnl = sum(p.pnl or 0 for p in self.closed_positions)
        
        return {
            'total_value': total_value,
            'cash': self.cash,
            'cash_pct': self.cash / self.initial_capital * 100,
            'gross_exposure': gross_exposure,
            'net_exposure': net_exposure,
            'open_positions': len(self.positions),
            'unrealized_pnl': unrealized_pnl,
            'unrealized_pnl_pct': unrealized_pnl_pct,
            'realized_pnl': realized_pnl,
            'total_pnl': unrealized_pnl + realized_pnl,
            'total_pnl_pct': ((total_value - self.initial_capital) / self.initial_capital * 100),
            'positions': [self._position_to_dict(p) for p in self.positions]
        }
    
    def _calculate_gross_exposure(self) -> float:
        """Calculate total gross exposure as % of initial capital."""
        return sum(p.size_pct for p in self.positions if p.status == 'open')
    
    def _position_to_dict(self, position: Position) -> Dict:
        """Convert position to dictionary."""
        return {
            'ticker': position.ticker,
            'entry_price': position.entry_price,
            'quantity': position.quantity,
            'size_pct': position.size_pct,
            'conviction': position.conviction,
            'stop_loss': position.stop_loss,
            'take_profit': position.take_profit,
            'pnl': position.pnl,
            'pnl_pct': position.pnl_pct
        }
    
    def get_portfolio_summary(self) -> str:
        """Generate human-readable portfolio summary."""
        open_count = len(self.positions)
        closed_count = len(self.closed_positions)
        gross_exposure = self._calculate_gross_exposure()
        
        return (
            f"Portfolio Summary:\n"
            f"  Open positions: {open_count}/{self.MAX_POSITIONS}\n"
            f"  Closed positions: {closed_count}\n"
            f"  Gross exposure: {gross_exposure:.1%}\n"
            f"  Cash reserve: {self.cash / self.initial_capital:.1%}\n"
        )
