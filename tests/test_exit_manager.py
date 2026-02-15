"""
Unit tests for ExitManager
"""

import unittest
import pandas as pd
import numpy as np
from src.risk.exit_manager import ExitManager, ExitReason, Position


class TestExitManager(unittest.TestCase):
    
    def setUp(self):
        """Set up test fixtures"""
        self.exit_mgr = ExitManager()
        
        # Create sample price data
        dates = pd.date_range('2025-01-01', periods=100, freq='D')
        np.random.seed(42)
        
        prices = 50 + np.cumsum(np.random.randn(100) * 0.5)
        
        self.df = pd.DataFrame({
            'Open': prices * 0.99,
            'High': prices * 1.02,
            'Low': prices * 0.98,
            'Close': prices,
            'Volume': np.random.randint(1000000, 5000000, 100),
        }, index=dates)
    
    def test_calculate_atr(self):
        """Test ATR calculation"""
        atr = self.exit_mgr.calculate_atr(self.df, period=14)
        
        self.assertIsInstance(atr, float)
        self.assertGreater(atr, 0)
        self.assertLess(atr, self.df['Close'].iloc[-1] * 0.10)  # ATR < 10% of price
    
    def test_initialize_position(self):
        """Test position initialization"""
        position = self.exit_mgr.initialize_position(
            ticker="TEST.SA",
            entry_price=50.0,
            entry_date="2025-06-01",
            size=0.70,
            df=self.df,
        )
        
        self.assertEqual(position.ticker, "TEST.SA")
        self.assertEqual(position.entry_price, 50.0)
        self.assertEqual(position.size, 0.70)
        self.assertLess(position.stop_loss, position.entry_price)
        self.assertFalse(position.trailing_stop_active)
    
    def test_stop_loss_trigger(self):
        """Test stop loss exit"""
        position = self.exit_mgr.initialize_position(
            ticker="TEST.SA",
            entry_price=50.0,
            entry_date="2025-06-01",
            size=0.70,
            df=self.df,
        )
        
        # Price drops below stop loss
        position.current_price = position.stop_loss - 0.01
        
        exit_signal = self.exit_mgr.check_exit(
            position=position,
            current_trend="bearish",
            previous_trend="bullish",
        )
        
        self.assertTrue(exit_signal.should_exit)
        self.assertEqual(exit_signal.exit_percentage, 1.0)
        self.assertEqual(exit_signal.reason, ExitReason.STOP_LOSS)
    
    def test_take_profit_1(self):
        """Test first take profit level (+5%)"""
        position = self.exit_mgr.initialize_position(
            ticker="TEST.SA",
            entry_price=50.0,
            entry_date="2025-06-01",
            size=0.70,
            df=self.df,
        )
        
        # Price +5%
        position.current_price = 52.5
        
        exit_signal = self.exit_mgr.check_exit(
            position=position,
            current_trend="bullish",
            previous_trend="bullish",
        )
        
        self.assertTrue(exit_signal.should_exit)
        self.assertEqual(exit_signal.exit_percentage, 0.30)  # Exit 30%
        self.assertEqual(exit_signal.reason, ExitReason.TAKE_PROFIT_1)
    
    def test_take_profit_2(self):
        """Test second take profit level (+10%)"""
        position = self.exit_mgr.initialize_position(
            ticker="TEST.SA",
            entry_price=50.0,
            entry_date="2025-06-01",
            size=0.70,
            df=self.df,
        )
        
        # Price +10%
        position.current_price = 55.0
        position.highest_price = 55.0
        
        exit_signal = self.exit_mgr.check_exit(
            position=position,
            current_trend="bullish",
            previous_trend="bullish",
        )
        
        self.assertTrue(exit_signal.should_exit)
        self.assertEqual(exit_signal.exit_percentage, 0.40)  # Exit 40%
        self.assertEqual(exit_signal.reason, ExitReason.TAKE_PROFIT_2)
        self.assertIsNotNone(exit_signal.new_stop_loss)
    
    def test_take_profit_3(self):
        """Test third take profit level (+15%)"""
        position = self.exit_mgr.initialize_position(
            ticker="TEST.SA",
            entry_price=50.0,
            entry_date="2025-06-01",
            size=0.70,
            df=self.df,
        )
        
        # Price +15%
        position.current_price = 57.5
        position.highest_price = 57.5
        
        exit_signal = self.exit_mgr.check_exit(
            position=position,
            current_trend="bullish",
            previous_trend="bullish",
        )
        
        self.assertTrue(exit_signal.should_exit)
        self.assertEqual(exit_signal.exit_percentage, 0.30)  # Exit 30%
        self.assertEqual(exit_signal.reason, ExitReason.TAKE_PROFIT_3)
    
    def test_trailing_stop_activation(self):
        """Test trailing stop activation at +8%"""
        position = self.exit_mgr.initialize_position(
            ticker="TEST.SA",
            entry_price=50.0,
            entry_date="2025-06-01",
            size=0.70,
            df=self.df,
        )
        
        # Price +8% (should activate trailing stop)
        position = self.exit_mgr.update_position(position, 54.0, self.df)
        
        self.assertTrue(position.trailing_stop_active)
        self.assertIsNotNone(position.trailing_stop_price)
        self.assertLess(position.trailing_stop_price, position.current_price)
    
    def test_trailing_stop_trigger(self):
        """Test trailing stop exit"""
        position = self.exit_mgr.initialize_position(
            ticker="TEST.SA",
            entry_price=50.0,
            entry_date="2025-06-01",
            size=0.70,
            df=self.df,
        )
        
        # Activate trailing stop
        position = self.exit_mgr.update_position(position, 54.0, self.df)
        trailing_price = position.trailing_stop_price
        
        # Price drops below trailing stop
        position.current_price = trailing_price - 0.01
        
        exit_signal = self.exit_mgr.check_exit(
            position=position,
            current_trend="neutral",
            previous_trend="bullish",
        )
        
        self.assertTrue(exit_signal.should_exit)
        self.assertEqual(exit_signal.exit_percentage, 1.0)
        self.assertEqual(exit_signal.reason, ExitReason.TRAILING_STOP)
    
    def test_regime_change_bearish(self):
        """Test exit on regime change bullish → bearish"""
        position = self.exit_mgr.initialize_position(
            ticker="TEST.SA",
            entry_price=50.0,
            entry_date="2025-06-01",
            size=0.70,
            df=self.df,
        )
        
        position.current_price = 52.0
        
        exit_signal = self.exit_mgr.check_exit(
            position=position,
            current_trend="bearish",
            previous_trend="bullish",
        )
        
        self.assertTrue(exit_signal.should_exit)
        self.assertEqual(exit_signal.exit_percentage, 1.0)  # Exit 100%
        self.assertEqual(exit_signal.reason, ExitReason.REGIME_CHANGE)
    
    def test_regime_change_neutral(self):
        """Test partial exit on regime change bullish → neutral"""
        position = self.exit_mgr.initialize_position(
            ticker="TEST.SA",
            entry_price=50.0,
            entry_date="2025-06-01",
            size=0.70,
            df=self.df,
        )
        
        position.current_price = 52.0
        
        exit_signal = self.exit_mgr.check_exit(
            position=position,
            current_trend="neutral",
            previous_trend="bullish",
        )
        
        self.assertTrue(exit_signal.should_exit)
        self.assertEqual(exit_signal.exit_percentage, 0.5)  # Exit 50%
        self.assertEqual(exit_signal.reason, ExitReason.REGIME_CHANGE)
    
    def test_news_shock_exit(self):
        """Test exit on very negative news"""
        position = self.exit_mgr.initialize_position(
            ticker="TEST.SA",
            entry_price=50.0,
            entry_date="2025-06-01",
            size=0.70,
            df=self.df,
        )
        
        position.current_price = 52.0
        
        exit_signal = self.exit_mgr.check_exit(
            position=position,
            current_trend="bullish",
            previous_trend="bullish",
            news_sentiment=-0.9,  # Very negative
        )
        
        self.assertTrue(exit_signal.should_exit)
        self.assertEqual(exit_signal.exit_percentage, 1.0)  # Exit 100% for catastrophic news
        self.assertEqual(exit_signal.reason, ExitReason.NEWS_SHOCK)
    
    def test_news_shock_graduated(self):
        """Test graduated response to news sentiment"""
        position = self.exit_mgr.initialize_position(
            ticker="TEST.SA",
            entry_price=50.0,
            entry_date="2025-06-01",
            size=0.70,
            df=self.df,
        )
        
        position.current_price = 52.0
        
        # Test -0.7 sentiment (very negative but not catastrophic)
        exit_signal = self.exit_mgr.check_exit(
            position=position,
            current_trend="bullish",
            previous_trend="bullish",
            news_sentiment=-0.7,
        )
        
        self.assertTrue(exit_signal.should_exit)
        self.assertEqual(exit_signal.exit_percentage, 0.5)  # Exit 50%
        self.assertIsNotNone(exit_signal.new_stop_loss)
        
        # Test -0.5 sentiment (moderately negative)
        exit_signal = self.exit_mgr.check_exit(
            position=position,
            current_trend="bullish",
            previous_trend="bullish",
            news_sentiment=-0.5,
        )
        
        self.assertFalse(exit_signal.should_exit)  # Don't exit
        self.assertIsNotNone(exit_signal.new_stop_loss)  # But tighten stop
        self.assertLess(exit_signal.new_stop_loss, position.current_price)
    
    def test_tighten_stop_without_exit(self):
        """Test that stop loss is tightened even when not exiting (news -0.4 to -0.6)"""
        position = self.exit_mgr.initialize_position(
            ticker="TEST.SA",
            entry_price=50.0,
            entry_date="2025-06-01",
            size=0.70,
            df=self.df,
        )
        
        position.current_price = 52.0
        
        # Test with moderately negative news (-0.5)
        exit_signal = self.exit_mgr.check_exit(
            position=position,
            current_trend="bullish",
            previous_trend="bullish",
            news_sentiment=-0.5,
        )
        
        # Should NOT exit
        self.assertFalse(exit_signal.should_exit)
        # But SHOULD have a new stop loss
        self.assertIsNotNone(exit_signal.new_stop_loss)
        # New stop should be tighter (lower) than original
        self.assertLess(exit_signal.new_stop_loss, position.current_price)
        self.assertEqual(exit_signal.new_stop_loss, position.current_price * 0.98)
    
    def test_no_exit_signal(self):
        """Test no exit when conditions not met"""
        position = self.exit_mgr.initialize_position(
            ticker="TEST.SA",
            entry_price=50.0,
            entry_date="2025-06-01",
            size=0.70,
            df=self.df,
        )
        
        position.current_price = 51.0  # +2%, no TP reached
        
        exit_signal = self.exit_mgr.check_exit(
            position=position,
            current_trend="bullish",
            previous_trend="bullish",
        )
        
        self.assertFalse(exit_signal.should_exit)
        self.assertEqual(exit_signal.exit_percentage, 0.0)
    
    def test_position_size_calculation(self):
        """Test dynamic position sizing"""
        # High confidence
        size = self.exit_mgr.calculate_position_size(confidence=0.85, max_position=0.70)
        self.assertEqual(size, 0.70)
        
        # Medium confidence
        size = self.exit_mgr.calculate_position_size(confidence=0.65, max_position=0.70)
        self.assertAlmostEqual(size, 0.50, places=2)
        
        # Low confidence
        size = self.exit_mgr.calculate_position_size(confidence=0.45, max_position=0.70)
        self.assertAlmostEqual(size, 0.25, places=2)
        
        # Too low confidence
        size = self.exit_mgr.calculate_position_size(confidence=0.30, max_position=0.70)
        self.assertEqual(size, 0.0)
    
    def test_trailing_stop_only_moves_up(self):
        """Test that trailing stop never moves down"""
        position = self.exit_mgr.initialize_position(
            ticker="TEST.SA",
            entry_price=50.0,
            entry_date="2025-06-01",
            size=0.70,
            df=self.df,
        )
        
        # Activate trailing at 54
        position = self.exit_mgr.update_position(position, 54.0, self.df)
        initial_trailing = position.trailing_stop_price
        
        # Price goes higher
        position = self.exit_mgr.update_position(position, 56.0, self.df)
        higher_trailing = position.trailing_stop_price
        
        self.assertGreater(higher_trailing, initial_trailing)
        
        # Price drops (trailing should NOT move down)
        position = self.exit_mgr.update_position(position, 54.5, self.df)
        final_trailing = position.trailing_stop_price
        
        self.assertEqual(final_trailing, higher_trailing)


if __name__ == '__main__':
    unittest.main()
