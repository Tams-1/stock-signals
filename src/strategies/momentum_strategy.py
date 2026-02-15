"""
Phase 4: Momentum Following Strategy

Strategy for bull market trading using momentum signals and conviction scoring.

Entry Conditions:
- Regime = uptrend
- Momentum detected (strength > 0.6)
- News sentiment positive (if available)
- Price breaks above 20-day high

Exit Conditions:
- Momentum breaks (MA cross reverses)
- Price closes below 20-day MA
- Regime changes to consolidation/downtrend
- Take profit: +5% from entry
- Stop loss: -3% from entry

Position sizing: Based on conviction score from signal aggregation
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Optional
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class MomentumStrategy:
    """Momentum following strategy for uptrend periods."""
    
    def __init__(self, lookback_days: int = 20, min_momentum_strength: float = 0.6,
                 take_profit_pct: float = 0.05, stop_loss_pct: float = 0.03):
        """
        Initialize momentum strategy.
        
        Args:
            lookback_days: Window for 20-day high/MA
            min_momentum_strength: Min momentum to trade (0-1.0)
            take_profit_pct: Profit target (default +5%)
            stop_loss_pct: Stop loss level (default -3%)
        """
        self.lookback_days = lookback_days
        self.min_momentum_strength = min_momentum_strength
        self.take_profit_pct = take_profit_pct
        self.stop_loss_pct = stop_loss_pct
    
    def should_enter(self, df: pd.DataFrame, regime: str, momentum_result: Dict,
                    news_sentiment: Optional[str] = None) -> Tuple[bool, str]:
        """
        Check entry conditions.
        
        Args:
            df: DataFrame with OHLCV data
            regime: Current market regime (uptrend/downtrend/consolidation)
            momentum_result: Output from MomentumDetector.detect_momentum()
            news_sentiment: Optional news sentiment (bullish/bearish/neutral)
        
        Returns:
            (should_enter: bool, reason: str)
        """
        # Condition 1: Regime must be uptrend
        if regime != 'uptrend':
            return False, f"Regime is {regime}, not uptrend"
        
        # Condition 2: Momentum must be detected
        momentum_strength = momentum_result.get('momentum_strength', 0)
        if momentum_strength < self.min_momentum_strength:
            return False, f"Momentum too weak ({momentum_strength:.2f} < {self.min_momentum_strength})"
        
        # Condition 3: Momentum type must be bullish
        momentum_type = momentum_result.get('momentum_type', 'none')
        if momentum_type != 'bullish':
            return False, f"Momentum type is {momentum_type}, not bullish"
        
        # Condition 4: Price must break above 20-day high
        if len(df) < self.lookback_days:
            return False, "Insufficient data for 20-day high"
        
        recent_data = df.tail(self.lookback_days)
        twenty_day_high = recent_data['High'].max()
        current_price = df['Close'].iloc[-1]
        
        if current_price <= twenty_day_high:
            return False, f"Price {current_price:.2f} not above 20-day high {twenty_day_high:.2f}"
        
        # Condition 5 (optional): News sentiment should be positive
        if news_sentiment and news_sentiment == 'bearish':
            return False, "News sentiment is bearish"
        
        return True, "Entry conditions met"
    
    def should_exit(self, df: pd.DataFrame, entry_price: float, current_price: float,
                   regime: str, momentum_result: Dict) -> Tuple[bool, str]:
        """
        Check exit conditions.
        
        Args:
            df: DataFrame with OHLCV data
            entry_price: Position entry price
            current_price: Current price
            regime: Current market regime
            momentum_result: Current momentum result
        
        Returns:
            (should_exit: bool, reason: str)
        """
        # Exit Condition 1: Stop loss hit
        stop_loss = entry_price * (1 - self.stop_loss_pct)
        if current_price <= stop_loss:
            return True, f"Stop loss hit ({current_price:.2f} <= {stop_loss:.2f})"
        
        # Exit Condition 2: Take profit hit
        take_profit = entry_price * (1 + self.take_profit_pct)
        if current_price >= take_profit:
            return True, f"Take profit hit ({current_price:.2f} >= {take_profit:.2f})"
        
        # Exit Condition 3: Momentum breaks (MA cross reverses)
        momentum_type = momentum_result.get('momentum_type', 'none')
        if momentum_type != 'bullish':
            return True, "Momentum reversed"
        
        # Exit Condition 4: Price closes below 20-day MA
        if len(df) >= self.lookback_days:
            long_ma = df['Close'].rolling(window=self.lookback_days).mean().iloc[-1]
            if current_price < long_ma:
                return True, f"Price {current_price:.2f} below 20-day MA {long_ma:.2f}"
        
        # Exit Condition 5: Regime changes
        if regime in ['downtrend', 'unknown']:
            return True, f"Regime changed to {regime}"
        
        return False, "No exit conditions met"
    
    def calculate_entry_level(self, df: pd.DataFrame) -> float:
        """
        Calculate optimal entry level (break of 20-day high).
        
        Returns:
            Entry price (20-day high + 0.1% buffer)
        """
        if len(df) < self.lookback_days:
            return df['Close'].iloc[-1]
        
        recent_data = df.tail(self.lookback_days)
        twenty_day_high = recent_data['High'].max()
        
        # Add small buffer for breakout confirmation
        entry_level = twenty_day_high * 1.001
        
        return entry_level
    
    def calculate_exits(self, entry_price: float) -> Tuple[float, float]:
        """
        Calculate stop loss and take profit levels.
        
        Returns:
            (stop_loss_price, take_profit_price)
        """
        stop_loss = entry_price * (1 - self.stop_loss_pct)
        take_profit = entry_price * (1 + self.take_profit_pct)
        
        return stop_loss, take_profit
    
    def get_position_signal(self, df: pd.DataFrame, regime: str, momentum_result: Dict,
                           conviction: float, news_sentiment: Optional[str] = None) -> Dict:
        """
        Generate complete position signal.
        
        Returns:
            {
                'should_enter': bool,
                'entry_reason': str,
                'entry_price': float,
                'stop_loss': float,
                'take_profit': float,
                'position_size_pct': float,
                'risk_reward_ratio': float,
                'confidence': float,
                'details': {...}
            }
        """
        should_enter, entry_reason = self.should_enter(df, regime, momentum_result, news_sentiment)
        
        if not should_enter:
            return {
                'should_enter': False,
                'entry_reason': entry_reason,
                'entry_price': None,
                'stop_loss': None,
                'take_profit': None,
                'position_size_pct': 0.0,
                'risk_reward_ratio': 0.0,
                'confidence': 0.0,
                'details': {}
            }
        
        entry_price = self.calculate_entry_level(df)
        stop_loss, take_profit = self.calculate_exits(entry_price)
        
        # Risk/reward ratio
        risk = entry_price - stop_loss
        reward = take_profit - entry_price
        risk_reward_ratio = reward / risk if risk > 0 else 0
        
        # Position size based on conviction
        position_size_pct = self._conviction_to_position_size(conviction)
        
        return {
            'should_enter': True,
            'entry_reason': entry_reason,
            'entry_price': entry_price,
            'stop_loss': stop_loss,
            'take_profit': take_profit,
            'position_size_pct': position_size_pct,
            'risk_reward_ratio': risk_reward_ratio,
            'confidence': min(1.0, conviction + momentum_result.get('momentum_strength', 0)) / 2,
            'details': {
                'momentum_strength': momentum_result.get('momentum_strength', 0),
                'momentum_persistence': momentum_result.get('persistence', 0),
                'regime': regime,
                'news_sentiment': news_sentiment,
                'risk_pct': (risk / entry_price) * 100,
                'reward_pct': (reward / entry_price) * 100
            }
        }
    
    def _conviction_to_position_size(self, conviction: float) -> float:
        """
        Convert conviction score to position size.
        
        Returns:
            Position size as % of capital
        """
        if conviction >= 0.8:
            return 0.70
        elif conviction >= 0.6:
            return 0.50
        elif conviction >= 0.4:
            return 0.25
        else:
            return 0.0
    
    def track_position(self, position_data: Dict, current_price: float) -> Dict:
        """
        Track active position performance.
        
        Args:
            position_data: Position information
            current_price: Current market price
        
        Returns:
            {
                'entry_price': float,
                'current_price': float,
                'pnl_pct': float,
                'pnl_abs': float,
                'profit_target_pct': float,
                'stop_loss_pct': float,
                'distance_to_tp': float,
                'distance_to_sl': float
            }
        """
        entry_price = position_data['entry_price']
        stop_loss = position_data['stop_loss']
        take_profit = position_data['take_profit']
        
        pnl_abs = current_price - entry_price
        pnl_pct = (pnl_abs / entry_price) * 100
        
        profit_target_pct = ((take_profit - entry_price) / entry_price) * 100
        stop_loss_pct = ((entry_price - stop_loss) / entry_price) * 100
        
        distance_to_tp = take_profit - current_price
        distance_to_sl = current_price - stop_loss
        
        return {
            'entry_price': entry_price,
            'current_price': current_price,
            'pnl_pct': pnl_pct,
            'pnl_abs': pnl_abs,
            'profit_target_pct': profit_target_pct,
            'stop_loss_pct': stop_loss_pct,
            'distance_to_tp': distance_to_tp,
            'distance_to_sl': distance_to_sl,
            'progress_to_tp': (pnl_pct / profit_target_pct * 100) if profit_target_pct > 0 else 0
        }
    
    def generate_entry_signal(self, ticker: str, df: pd.DataFrame, regime: str,
                            momentum_result: Dict, conviction: float,
                            news_sentiment: Optional[str] = None) -> Optional[Dict]:
        """
        Generate complete entry signal for a ticker.
        
        Returns:
            Signal dict or None if no entry
        """
        position_signal = self.get_position_signal(df, regime, momentum_result,
                                                   conviction, news_sentiment)
        
        if not position_signal['should_enter']:
            return None
        
        return {
            'ticker': ticker,
            'signal_type': 'momentum_entry',
            'timestamp': datetime.now().isoformat(),
            'action': 'BUY',
            'entry_price': position_signal['entry_price'],
            'stop_loss': position_signal['stop_loss'],
            'take_profit': position_signal['take_profit'],
            'position_size_pct': position_signal['position_size_pct'],
            'conviction': conviction,
            'confidence': position_signal['confidence'],
            'details': position_signal['details']
        }
    
    def generate_exit_signal(self, ticker: str, entry_price: float,
                           current_price: float, df: pd.DataFrame,
                           regime: str, momentum_result: Dict) -> Optional[Dict]:
        """
        Generate exit signal if conditions are met.
        
        Returns:
            Signal dict or None if no exit
        """
        should_exit, exit_reason = self.should_exit(df, entry_price, current_price,
                                                     regime, momentum_result)
        
        if not should_exit:
            return None
        
        pnl_pct = ((current_price - entry_price) / entry_price) * 100
        
        return {
            'ticker': ticker,
            'signal_type': 'momentum_exit',
            'timestamp': datetime.now().isoformat(),
            'action': 'SELL',
            'exit_price': current_price,
            'entry_price': entry_price,
            'pnl_pct': pnl_pct,
            'exit_reason': exit_reason,
            'details': {
                'regime': regime,
                'momentum_strength': momentum_result.get('momentum_strength', 0)
            }
        }
