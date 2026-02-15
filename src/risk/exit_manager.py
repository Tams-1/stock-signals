"""
Exit Manager - Intelligent position exit strategies
Implements: stop loss, take profit, trailing stop, regime-based exits
"""

import numpy as np
import pandas as pd
from typing import Dict, Optional, Tuple
from dataclasses import dataclass
from enum import Enum


class ExitReason(Enum):
    """Exit reasons for tracking and analysis"""
    STOP_LOSS = "stop_loss"
    TAKE_PROFIT_1 = "take_profit_1"  # +5%
    TAKE_PROFIT_2 = "take_profit_2"  # +10%
    TAKE_PROFIT_3 = "take_profit_3"  # +15%
    TRAILING_STOP = "trailing_stop"
    REGIME_CHANGE = "regime_change"  # bullish → bearish/neutral
    TREND_REVERSAL = "trend_reversal"  # confidence drop
    NEWS_SHOCK = "news_shock"  # very negative news


@dataclass
class Position:
    """Active position tracking"""
    ticker: str
    entry_price: float
    entry_date: str
    size: float  # 0.0 to 1.0 (percentage of capital)
    current_price: float
    highest_price: float  # For trailing stop
    stop_loss: float
    trailing_stop_active: bool = False
    trailing_stop_price: Optional[float] = None
    

@dataclass
class ExitSignal:
    """Exit signal result"""
    should_exit: bool
    exit_percentage: float  # 0.0 to 1.0 (how much to exit)
    reason: ExitReason
    new_stop_loss: Optional[float] = None  # Updated stop loss if partial exit


class ExitManager:
    """
    Manages intelligent position exits with multiple strategies:
    1. Dynamic stop loss (ATR-based)
    2. Multi-level take profits (5%, 10%, 15%)
    3. Trailing stop (activates at +8%)
    4. Regime change exits
    """
    
    def __init__(
        self,
        atr_multiplier: float = 2.0,  # Stop loss at entry - 2*ATR
        tp1_pct: float = 0.05,  # Take profit 1: +5%
        tp2_pct: float = 0.10,  # Take profit 2: +10%
        tp3_pct: float = 0.15,  # Take profit 3: +15%
        tp1_exit: float = 0.30,  # Exit 30% at TP1
        tp2_exit: float = 0.40,  # Exit 40% at TP2
        tp3_exit: float = 0.30,  # Exit 30% at TP3
        trailing_activation: float = 0.08,  # Activate at +8%
        trailing_distance_multiplier: float = 1.5,  # Trail at 1.5*ATR
    ):
        self.atr_multiplier = atr_multiplier
        self.tp1_pct = tp1_pct
        self.tp2_pct = tp2_pct
        self.tp3_pct = tp3_pct
        self.tp1_exit = tp1_exit
        self.tp2_exit = tp2_exit
        self.tp3_exit = tp3_exit
        self.trailing_activation = trailing_activation
        self.trailing_distance_multiplier = trailing_distance_multiplier
        
    def calculate_atr(self, df: pd.DataFrame, period: int = 14) -> float:
        """
        Calculate Average True Range (ATR) for volatility-based stops
        
        Args:
            df: DataFrame with 'High', 'Low', 'Close' columns
            period: ATR period (default 14 days)
            
        Returns:
            ATR value
        """
        if len(df) < period:
            # Fallback: use simple volatility
            return df['Close'].pct_change().std() * df['Close'].iloc[-1]
        
        high = df['High']
        low = df['Low']
        close = df['Close']
        
        # True Range = max(high-low, abs(high-prev_close), abs(low-prev_close))
        tr1 = high - low
        tr2 = abs(high - close.shift())
        tr3 = abs(low - close.shift())
        
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.rolling(period).mean().iloc[-1]
        
        return atr if not pd.isna(atr) else df['Close'].iloc[-1] * 0.02  # Fallback: 2%
    
    def initialize_position(
        self,
        ticker: str,
        entry_price: float,
        entry_date: str,
        size: float,
        df: pd.DataFrame,
    ) -> Position:
        """
        Initialize a new position with stop loss
        
        Args:
            ticker: Stock ticker
            entry_price: Entry price
            entry_date: Entry date
            size: Position size (0.0 to 1.0)
            df: Price DataFrame for ATR calculation
            
        Returns:
            Position object with stop loss set
        """
        atr = self.calculate_atr(df)
        stop_loss = entry_price - (self.atr_multiplier * atr)
        
        return Position(
            ticker=ticker,
            entry_price=entry_price,
            entry_date=entry_date,
            size=size,
            current_price=entry_price,
            highest_price=entry_price,
            stop_loss=stop_loss,
            trailing_stop_active=False,
            trailing_stop_price=None,
        )
    
    def update_position(
        self,
        position: Position,
        current_price: float,
        df: pd.DataFrame,
    ) -> Position:
        """
        Update position with current price and adjust trailing stop
        
        Args:
            position: Current position
            current_price: Latest price
            df: Price DataFrame for ATR calculation
            
        Returns:
            Updated position
        """
        position.current_price = current_price
        
        # Track highest price for trailing stop
        if current_price > position.highest_price:
            position.highest_price = current_price
        
        # Check if trailing stop should activate
        gain = (current_price - position.entry_price) / position.entry_price
        
        if gain >= self.trailing_activation and not position.trailing_stop_active:
            # Activate trailing stop
            position.trailing_stop_active = True
            atr = self.calculate_atr(df)
            position.trailing_stop_price = position.highest_price - (self.trailing_distance_multiplier * atr)
        
        elif position.trailing_stop_active:
            # Update trailing stop (only moves up, never down)
            atr = self.calculate_atr(df)
            new_trailing = position.highest_price - (self.trailing_distance_multiplier * atr)
            
            if new_trailing > position.trailing_stop_price:
                position.trailing_stop_price = new_trailing
        
        return position
    
    def check_exit(
        self,
        position: Position,
        current_trend: str,  # bullish, bearish, neutral
        previous_trend: str,
        news_sentiment: Optional[float] = None,  # -1.0 to +1.0
    ) -> ExitSignal:
        """
        Check if position should exit (full or partial)
        
        Args:
            position: Current position
            current_trend: Current trend from TrendDetectorV2
            previous_trend: Previous trend
            news_sentiment: News sentiment score (-1.0 to +1.0)
            
        Returns:
            ExitSignal with exit decision
        """
        current_price = position.current_price
        entry_price = position.entry_price
        gain = (current_price - entry_price) / entry_price
        
        # 1. Check stop loss
        if current_price <= position.stop_loss:
            return ExitSignal(
                should_exit=True,
                exit_percentage=1.0,  # Exit 100%
                reason=ExitReason.STOP_LOSS,
            )
        
        # 2. Check trailing stop (if active)
        if position.trailing_stop_active and current_price <= position.trailing_stop_price:
            return ExitSignal(
                should_exit=True,
                exit_percentage=1.0,
                reason=ExitReason.TRAILING_STOP,
            )
        
        # 3. Check regime change (bullish → bearish = immediate exit)
        if previous_trend == "bullish" and current_trend == "bearish":
            return ExitSignal(
                should_exit=True,
                exit_percentage=1.0,  # Exit 100%
                reason=ExitReason.REGIME_CHANGE,
            )
        
        # 4. Check regime change (bullish → neutral = partial exit)
        if previous_trend == "bullish" and current_trend == "neutral":
            return ExitSignal(
                should_exit=True,
                exit_percentage=0.5,  # Exit 50%
                reason=ExitReason.REGIME_CHANGE,
                new_stop_loss=position.current_price * 0.98,  # Tighten stop to -2%
            )
        
        # 5. Check news shock (very negative sentiment)
        if news_sentiment is not None and news_sentiment <= -0.8:
            return ExitSignal(
                should_exit=True,
                exit_percentage=0.5,  # Exit 50% on bad news
                reason=ExitReason.NEWS_SHOCK,
                new_stop_loss=position.current_price * 0.97,  # Tighten stop to -3%
            )
        
        # 6. Check take profit levels (multi-level exit)
        if gain >= self.tp3_pct:  # +15%
            return ExitSignal(
                should_exit=True,
                exit_percentage=self.tp3_exit,  # Exit 30%
                reason=ExitReason.TAKE_PROFIT_3,
            )
        
        elif gain >= self.tp2_pct:  # +10%
            return ExitSignal(
                should_exit=True,
                exit_percentage=self.tp2_exit,  # Exit 40%
                reason=ExitReason.TAKE_PROFIT_2,
                new_stop_loss=entry_price * 1.05,  # Move stop to +5% (breakeven)
            )
        
        elif gain >= self.tp1_pct:  # +5%
            return ExitSignal(
                should_exit=True,
                exit_percentage=self.tp1_exit,  # Exit 30%
                reason=ExitReason.TAKE_PROFIT_1,
                new_stop_loss=entry_price * 1.02,  # Move stop to +2%
            )
        
        # No exit signal
        return ExitSignal(
            should_exit=False,
            exit_percentage=0.0,
            reason=None,
        )
    
    def calculate_position_size(
        self,
        confidence: float,
        max_position: float = 0.70,  # Max 70% of capital in one stock
    ) -> float:
        """
        Calculate position size based on confidence
        
        Args:
            confidence: Signal confidence (0.0 to 1.0)
            max_position: Maximum position size
            
        Returns:
            Position size (0.0 to max_position)
        """
        if confidence >= 0.80:
            return max_position  # 70% high conviction
        elif confidence >= 0.60:
            return max_position * 0.71  # ~50% medium conviction
        elif confidence >= 0.40:
            return max_position * 0.36  # ~25% low conviction
        else:
            return 0.0  # No position if confidence < 0.40


# Example usage
if __name__ == "__main__":
    import yfinance as yf
    
    # Download sample data
    ticker = "VALE3.SA"
    df = yf.download(ticker, start="2025-01-01", end="2026-02-15", progress=False)
    
    # Flatten MultiIndex columns if needed
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = ['_'.join(col).strip('_') if col[1] else col[0] for col in df.columns.values]
        df = df.rename(columns={
            f'Open_{ticker}': 'Open',
            f'High_{ticker}': 'High',
            f'Low_{ticker}': 'Low',
            f'Close_{ticker}': 'Close',
            f'Volume_{ticker}': 'Volume',
        })
    
    # Initialize exit manager
    exit_mgr = ExitManager()
    
    # Simulate entry
    entry_price = 50.0
    position = exit_mgr.initialize_position(
        ticker=ticker,
        entry_price=entry_price,
        entry_date="2025-06-01",
        size=0.70,
        df=df,
    )
    
    print(f"📊 Position initialized: {ticker}")
    print(f"   Entry: R$ {position.entry_price:.2f}")
    print(f"   Stop Loss: R$ {position.stop_loss:.2f} ({(position.stop_loss/entry_price - 1)*100:.2f}%)")
    print()
    
    # Simulate price movements
    test_prices = [52.5, 55.0, 54.0, 58.0, 57.0]
    test_trends = ["bullish", "bullish", "bullish", "bullish", "neutral"]
    
    for i, (price, trend) in enumerate(zip(test_prices, test_trends)):
        position = exit_mgr.update_position(position, price, df)
        
        prev_trend = "bullish" if i == 0 else test_trends[i-1]
        exit_signal = exit_mgr.check_exit(position, trend, prev_trend)
        
        print(f"Day {i+1}: Price R$ {price:.2f}, Trend {trend}")
        print(f"   Gain: {((price/entry_price - 1)*100):.2f}%")
        print(f"   Trailing Stop Active: {position.trailing_stop_active}")
        if position.trailing_stop_active:
            print(f"   Trailing Stop: R$ {position.trailing_stop_price:.2f}")
        
        if exit_signal.should_exit:
            print(f"   🚨 EXIT SIGNAL: {exit_signal.reason.value}")
            print(f"   Exit {exit_signal.exit_percentage*100:.0f}% of position")
        print()
