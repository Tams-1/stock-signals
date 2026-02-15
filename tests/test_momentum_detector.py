"""Unit tests for momentum detection module."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
import numpy as np
import pandas as pd
from datetime import datetime, timedelta

from src.signals.momentum_detector import MomentumDetector


class TestMomentumDetector:
    """Test momentum detection functionality."""
    
    def setup_method(self):
        self.detector = MomentumDetector()
    
    def create_sample_data(self, length=30, trend='stable', volume_mult=1.0):
        """Create sample OHLCV data for testing."""
        dates = pd.date_range(end=datetime.now(), periods=length, freq='D')
        
        if trend == 'stable':
            close = np.linspace(100, 102, length)
        elif trend == 'uptrend':
            close = np.linspace(100, 120, length) + np.random.normal(0, 1, length)
        elif trend == 'downtrend':
            close = np.linspace(100, 80, length) + np.random.normal(0, 1, length)
        elif trend == 'high_volatility':
            close = 100 + np.cumsum(np.random.normal(0, 2, length))
        else:
            close = np.linspace(100, 102, length)
        
        data = pd.DataFrame({
            'Open': close - 0.5,
            'High': close + 1.5,
            'Low': close - 1.5,
            'Close': close,
            'Volume': (1000000 + np.random.normal(0, 100000, length)) * volume_mult
        }, index=dates)
        
        return data
    
    def test_initialization(self):
        """Test detector initialization."""
        assert self.detector.short_ma_period == 5
        assert self.detector.long_ma_period == 20
        assert self.detector.volume_multiplier == 1.2
        assert self.detector.persistence_days == 3
    
    def test_insufficient_data(self):
        """Test behavior with insufficient data."""
        data = self.create_sample_data(length=5)
        result = self.detector.detect_momentum(data)
        
        assert result['momentum_strength'] == 0.0
        assert result['momentum_type'] == 'none'
        assert 'error' in result['details']
    
    def test_bullish_momentum_detection(self):
        """Test detection of bullish momentum."""
        # Create strong uptrend data
        data = self.create_sample_data(length=40, trend='uptrend')
        result = self.detector.detect_momentum(data)
        
        # Should detect bullish momentum
        assert result['momentum_strength'] > 0.3
        assert result['ma_cross'] == True
        # Price momentum should be positive
        assert result['price_momentum'] >= 0
    
    def test_downtrend_momentum(self):
        """Test detection of downtrend momentum."""
        # Create strong downtrend
        dates = pd.date_range(end=datetime.now(), periods=40, freq='D')
        close = np.linspace(100, 80, 40)
        
        data = pd.DataFrame({
            'Open': close - 0.5,
            'High': close + 1.5,
            'Low': close - 1.5,
            'Close': close,
            'Volume': 1000000 + np.random.normal(0, 100000, 40)
        }, index=dates)
        
        result = self.detector.detect_momentum(data)
        
        # Short MA should be below long MA
        assert result['ma_cross'] == False
    
    def test_volume_momentum_detection(self):
        """Test volume momentum detection."""
        # Create data with volume spike
        data = self.create_sample_data(length=30, trend='uptrend', volume_mult=1.0)
        
        # Add volume spike on last day
        data.iloc[-1, data.columns.get_loc('Volume')] = data['Volume'].mean() * 1.5
        
        result = self.detector.detect_momentum(data)
        
        # Volume momentum should be positive
        assert result['volume_momentum'] > 0
    
    def test_persistence_check(self):
        """Test momentum persistence checking."""
        data = self.create_sample_data(length=40, trend='uptrend')
        result = self.detector.detect_momentum(data)
        
        # Should have some persistence days detected
        assert result['persistence'] >= 0
    
    def test_no_momentum_detection(self):
        """Test when no momentum is detected."""
        # Create sideways/consolidation data
        dates = pd.date_range(end=datetime.now(), periods=30, freq='D')
        close = np.full(30, 100.0) + np.random.normal(0, 0.5, 30)
        
        data = pd.DataFrame({
            'Open': close - 0.2,
            'High': close + 0.5,
            'Low': close - 0.5,
            'Close': close,
            'Volume': 1000000 + np.random.normal(0, 50000, 30)
        }, index=dates)
        
        result = self.detector.detect_momentum(data)
        
        # Should detect low or no momentum
        assert result['momentum_strength'] < 0.7
    
    def test_get_momentum_signals(self):
        """Test signal generation."""
        data = self.create_sample_data(length=40, trend='uptrend')
        signals = self.detector.get_momentum_signals(data)
        
        # Should return list of tuples
        assert isinstance(signals, list)
        assert len(signals) > 0
        
        # Each signal should be (type, strength, direction, explanation)
        for sig in signals:
            assert len(sig) == 4
            assert isinstance(sig[0], str)  # type
            assert isinstance(sig[1], (float, int))  # strength
            assert sig[2] in [None, 'bullish', 'bearish', 'neutral']  # direction
            assert isinstance(sig[3], str)  # explanation
    
    def test_ma_crossover_logic(self):
        """Test MA crossover detection."""
        # Create data where short MA crosses above long MA
        dates = pd.date_range(end=datetime.now(), periods=30, freq='D')
        
        # First part: short MA below long MA
        part1 = np.linspace(100, 102, 15)
        # Second part: acceleration (short MA overtakes long MA)
        part2 = np.linspace(102, 112, 15)
        close = np.concatenate([part1, part2])
        
        data = pd.DataFrame({
            'Open': close - 0.5,
            'High': close + 1.5,
            'Low': close - 1.5,
            'Close': close,
            'Volume': 1000000 + np.random.normal(0, 100000, 30)
        }, index=dates)
        
        result = self.detector.detect_momentum(data)
        
        # Should detect bullish momentum
        assert result['ma_cross'] == True
    
    def test_slope_calculation(self):
        """Test slope calculation."""
        # Create strong uptrend with clear slope
        dates = pd.date_range(end=datetime.now(), periods=30, freq='D')
        close = np.linspace(100, 115, 30)  # 50% gain
        
        data = pd.DataFrame({
            'Open': close - 0.5,
            'High': close + 1.5,
            'Low': close - 1.5,
            'Close': close,
            'Volume': 1000000 + np.random.normal(0, 100000, 30)
        }, index=dates)
        
        result = self.detector.detect_momentum(data)
        
        # Slope should be positive
        assert result['slope'] > 0
    
    def test_momentum_signal_format(self):
        """Test that momentum signals are properly formatted."""
        data = self.create_sample_data(length=40, trend='uptrend')
        signals = self.detector.get_momentum_signals(data)
        
        # Should have momentum signal
        assert len(signals) >= 1
        
        signal = signals[0]
        signal_type, strength, direction, explanation = signal
        
        # Check format
        assert isinstance(signal_type, str)
        assert 'momentum' in signal_type.lower()
        assert 0.0 <= strength <= 1.0
        assert direction in [None, 'bullish', 'bearish']
        assert len(explanation) > 0
    
    def test_custom_parameters(self):
        """Test initialization with custom parameters."""
        detector = MomentumDetector(
            short_ma_period=3,
            long_ma_period=15,
            volume_multiplier=1.5,
            persistence_days=2
        )
        
        assert detector.short_ma_period == 3
        assert detector.long_ma_period == 15
        assert detector.volume_multiplier == 1.5
        assert detector.persistence_days == 2
    
    def test_momentum_historical(self):
        """Test historical momentum calculation."""
        data = self.create_sample_data(length=40, trend='uptrend')
        historical = self.detector.get_momentum_historical(data, lookback=10)
        
        # Should return DataFrame
        assert isinstance(historical, pd.DataFrame)
        
        # Should have momentum_strength column
        if len(historical) > 0:
            assert 'momentum_strength' in historical.columns
            assert len(historical) <= 10
    
    def test_bullish_vs_bearish_momentum_type(self):
        """Test correct momentum type classification."""
        # Uptrend should be bullish
        uptrend_data = self.create_sample_data(length=40, trend='uptrend')
        uptrend_result = self.detector.detect_momentum(uptrend_data)
        
        if uptrend_result['momentum_strength'] > 0.6:
            assert uptrend_result['momentum_type'] == 'bullish'
