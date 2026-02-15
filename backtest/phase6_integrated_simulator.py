"""
Phase 6 Integrated Simulator - Using Fixed RegimeDetector & MomentumStrategy (v2.1)

This simulator integrates:
1. Fixed RegimeDetector (commit 693058e) - improved MA Cross, ADX methods
2. Fixed MomentumStrategy (commit 693058e) - regime-dependent thresholds & position sizing
3. Realistic trading costs (0.1% slippage + $5/trade)
4. No look-ahead bias (signals on day N-1, trades on day N)

Key improvements over original:
- MA Cross method now uses MA10/MA20/MA50 hierarchy
- Relaxed price threshold (within 1% of MA)
- Improved ADX method with DI difference
- Regime-dependent thresholds: 0.4 (uptrend), 0.6 (consolidation), 0.8 (downtrend)
- Position sizing multipliers: 1.2x (uptrend), 1.0x (consolidation), 0.5x (downtrend)
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
import yfinance as yf
import logging
from typing import Dict, Tuple, Optional

# Import fixed modules from commit 693058e
from src.signals.regime_detector import RegimeDetector
from src.strategies.momentum_strategy import MomentumStrategy
from src.signals.momentum_reversal import MomentumReversalDetector

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class Phase6IntegratedSimulator:
    """
    Production-grade simulator using fixed RegimeDetector & MomentumStrategy.
    
    KEY FEATURES:
    - NO look-ahead bias (signals use prior day's data)
    - Realistic costs: 0.1% slippage + $5/trade + 0.05% spread
    - Next-day execution (realistic gaps)
    - Regime-dependent thresholds and position sizing
    - Proper stop loss and take profit management
    """
    
    def __init__(self, 
                 initial_capital: float = 50000,
                 position_size: float = 0.05,
                 commission_pct: float = 0.1,
                 spread_pct: float = 0.05,
                 slippage_pct: float = 0.1,
                 fixed_commission: float = 5.0):
        """
        Initialize integrated simulator.
        
        Args:
            initial_capital: Starting capital
            position_size: Base position size (0-1.0)
            commission_pct: Broker commission (%)
            spread_pct: Bid-ask spread (%)
            slippage_pct: Market impact slippage (%)
            fixed_commission: Fixed commission per trade ($)
        """
        self.initial_capital = initial_capital
        self.position_size = position_size
        self.commission_pct = commission_pct
        self.spread_pct = spread_pct
        self.slippage_pct = slippage_pct
        self.fixed_commission = fixed_commission
        
        # Initialize strategy modules
        self.regime_detector = RegimeDetector(lookback_period=20, adx_period=14)
        self.momentum_strategy = MomentumStrategy(
            lookback_days=20,
            min_momentum_strength=0.6,  # baseline for consolidation
            take_profit_pct=0.05,
            stop_loss_pct=0.03
        )
        self.momentum_detector = MomentumReversalDetector()
        
        # Trading state
        self.trades = []
        self.equity_curve = []
        self.regime_history = []
        
    def calculate_total_cost(self, price: float, quantity: float, is_entry: bool = True) -> float:
        """Calculate total cost including commissions and slippage."""
        if is_entry:
            # Entry: price + spread/2 + slippage + commission%
            spread_cost = price * (self.spread_pct / 2 / 100)
            slippage_cost = price * (self.slippage_pct / 100)
            commission_cost = price * (self.commission_pct / 100)
            adjusted_price = price + spread_cost + slippage_cost + commission_cost
            
            # Add fixed commission to total
            total_value = (adjusted_price * quantity) + self.fixed_commission
            return total_value
        else:
            # Exit: price - spread/2 - slippage - commission%
            spread_cost = price * (self.spread_pct / 2 / 100)
            slippage_cost = price * (self.slippage_pct / 100)
            commission_cost = price * (self.commission_pct / 100)
            adjusted_price = price - spread_cost - slippage_cost - commission_cost
            
            # Subtract fixed commission from proceeds
            total_value = (adjusted_price * quantity) - self.fixed_commission
            return total_value
    
    def simulate_ticker(self, ticker: str, start_date: datetime, end_date: datetime) -> Dict:
        """
        Simulate trading a single ticker using integrated regime detector + momentum strategy.
        
        NO LOOK-AHEAD BIAS:
        - Day 0: Analyze data through day -1, generate signal
        - Day 1: Execute trade based on yesterday's signal
        """
        
        try:
            # Fetch OHLCV data
            df = yf.download(ticker, start=start_date, end=end_date, progress=False)
            
            if df is None or len(df) < 40:
                return {
                    'ticker': ticker,
                    'status': 'insufficient_data',
                    'return_pct': 0,
                    'trades_count': 0,
                    'win_rate': 0,
                    'sharpe_ratio': 0,
                    'max_drawdown': 0
                }
            
            # Prepare data
            df = df.sort_index()
            df['Date'] = df.index
            df = df.reset_index(drop=True)
            
            # Initialize backtest state
            capital = self.initial_capital
            position = None
            trades = []
            equity_values = [capital]
            
            # Main backtest loop - NO LOOK-AHEAD
            for i in range(1, len(df)):
                current_close = df.loc[i, 'Close']
                
                # Use data through i-1 (yesterday) to generate signals TODAY
                lookback_df = df.loc[:i-1].copy()
                
                if len(lookback_df) < 40:
                    continue
                
                # Step 1: Detect regime using data through yesterday
                try:
                    regime_result = self.regime_detector.detect_regime(lookback_df)
                    regime = regime_result.get('regime', 'unknown')
                    confidence = regime_result.get('confidence', 0)
                except Exception as e:
                    regime = 'unknown'
                    confidence = 0
                
                # Store regime history
                self.regime_history.append({
                    'date': df.loc[i, 'Date'],
                    'ticker': ticker,
                    'regime': regime,
                    'confidence': confidence
                })
                
                # Step 2: No open position - check entry conditions
                if position is None:
                    # Detect momentum using data through yesterday
                    try:
                        momentum_result = self.momentum_detector.detect_momentum(lookback_df)
                    except:
                        momentum_result = {'momentum_type': 'none', 'momentum_strength': 0}
                    
                    # Check entry with regime-dependent thresholds
                    should_enter, reason = self.momentum_strategy.should_enter(
                        lookback_df,
                        regime,
                        momentum_result
                    )
                    
                    if should_enter:
                        # Calculate position size with regime multiplier
                        base_size = self.position_size
                        regime_multiplier = self.momentum_strategy.position_size_multipliers.get(regime, 1.0)
                        
                        # Conviction-weighted sizing
                        conviction = momentum_result.get('momentum_strength', 0)
                        final_size = base_size * regime_multiplier * (0.5 + conviction * 0.5)
                        
                        # Calculate quantity to buy
                        entry_cost = self.calculate_total_cost(current_close, 1, is_entry=True)
                        quantity = int((capital * final_size) / entry_cost)
                        
                        if quantity > 0:
                            entry_price = current_close
                            tp_price = entry_price * (1 + self.momentum_strategy.take_profit_pct)
                            sl_price = entry_price * (1 - self.momentum_strategy.stop_loss_pct)
                            
                            position = {
                                'entry_date': df.loc[i, 'Date'],
                                'entry_price': entry_price,
                                'quantity': quantity,
                                'tp_price': tp_price,
                                'sl_price': sl_price,
                                'entry_regime': regime,
                                'entry_conviction': conviction
                            }
                            
                            # Reduce capital
                            capital -= self.calculate_total_cost(current_close, quantity, is_entry=True)
                
                # Step 3: Have open position - check exit conditions
                elif position is not None:
                    exit_trigger = None
                    exit_price = current_close
                    exit_reason = None
                    
                    # Check stop loss
                    if current_close <= position['sl_price']:
                        exit_trigger = True
                        exit_reason = 'stop_loss'
                    
                    # Check take profit
                    elif current_close >= position['tp_price']:
                        exit_trigger = True
                        exit_reason = 'take_profit'
                    
                    # Check regime change (exit on regime change if not highly confident)
                    elif regime != position['entry_regime'] and confidence < 0.7:
                        exit_trigger = True
                        exit_reason = 'regime_change'
                    
                    # Exit if open (daily check)
                    if exit_trigger:
                        exit_proceeds = self.calculate_total_cost(
                            exit_price, 
                            position['quantity'], 
                            is_entry=False
                        )
                        capital += exit_proceeds
                        
                        # Record trade
                        pnl = exit_proceeds - (
                            self.calculate_total_cost(position['entry_price'], position['quantity'], is_entry=True)
                        )
                        pnl_pct = (pnl / (position['entry_price'] * position['quantity'])) * 100
                        
                        trades.append({
                            'entry_date': position['entry_date'],
                            'exit_date': df.loc[i, 'Date'],
                            'entry_price': position['entry_price'],
                            'exit_price': exit_price,
                            'quantity': position['quantity'],
                            'pnl': pnl,
                            'pnl_pct': pnl_pct,
                            'reason': exit_reason,
                            'entry_regime': position['entry_regime']
                        })
                        
                        position = None
                
                # Track equity (mark-to-market)
                if position is not None:
                    position_value = self.calculate_total_cost(
                        current_close,
                        position['quantity'],
                        is_entry=False
                    )
                    equity = capital + position_value
                else:
                    equity = capital
                
                equity_values.append(equity)
            
            # Close any remaining position at market close
            if position is not None:
                exit_proceeds = self.calculate_total_cost(
                    df.loc[-1, 'Close'],
                    position['quantity'],
                    is_entry=False
                )
                capital += exit_proceeds
                
                pnl = exit_proceeds - (
                    self.calculate_total_cost(position['entry_price'], position['quantity'], is_entry=True)
                )
                
                trades.append({
                    'entry_date': position['entry_date'],
                    'exit_date': df.loc[-1, 'Date'],
                    'entry_price': position['entry_price'],
                    'exit_price': df.loc[-1, 'Close'],
                    'quantity': position['quantity'],
                    'pnl': pnl,
                    'reason': 'end_of_period',
                    'entry_regime': position['entry_regime']
                })
            
            # Calculate metrics
            final_equity = capital
            return_pct = ((final_equity - self.initial_capital) / self.initial_capital) * 100
            
            if len(trades) > 0:
                win_rate = sum(1 for t in trades if t['pnl'] > 0) / len(trades) * 100
                pnls = [t['pnl'] for t in trades]
                sharpe = self._calculate_sharpe(pnls) if len(pnls) > 1 else 0
            else:
                win_rate = 0
                sharpe = 0
            
            max_drawdown = self._calculate_max_drawdown(equity_values)
            
            return {
                'ticker': ticker,
                'status': 'success',
                'return_pct': return_pct,
                'trades_count': len(trades),
                'win_rate': win_rate,
                'sharpe_ratio': sharpe,
                'max_drawdown': max_drawdown,
                'final_equity': final_equity,
                'trades': trades,
                'equity_curve': equity_values
            }
            
        except Exception as e:
            logger.error(f"Error simulating {ticker}: {e}")
            return {
                'ticker': ticker,
                'status': f'error: {str(e)}',
                'return_pct': 0,
                'trades_count': 0,
                'win_rate': 0,
                'sharpe_ratio': 0,
                'max_drawdown': 0
            }
    
    @staticmethod
    def _calculate_sharpe(returns: list, risk_free_rate: float = 0.06) -> float:
        """Calculate Sharpe ratio of returns."""
        if len(returns) < 2:
            return 0
        
        returns = np.array(returns)
        excess_return = np.mean(returns) - (risk_free_rate / 252)
        std_return = np.std(returns)
        
        if std_return == 0:
            return 0
        
        return (excess_return / std_return) * np.sqrt(252)
    
    @staticmethod
    def _calculate_max_drawdown(equity_curve: list) -> float:
        """Calculate maximum drawdown."""
        if len(equity_curve) < 2:
            return 0
        
        equity = np.array(equity_curve)
        cummax = np.maximum.accumulate(equity)
        drawdown = (equity - cummax) / cummax
        return np.min(drawdown) * 100
