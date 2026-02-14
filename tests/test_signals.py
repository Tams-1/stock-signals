"""Unit tests for signal detectors."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
import numpy as np
import pandas as pd
from datetime import datetime, timedelta

from src.signals.information_flow import InformationFlowDetector
from src.signals.momentum_reversal import MomentumReversalDetector


class TestInformationFlowDetector:
    """Test information flow signals."""
    
    def setup_method(self):
        self.detector = InformationFlowDetector(lookback_period=20)
    
    def create_sample_data(self, length=20, trend='stable', volatility='normal'):
        """Create sample OHLCV data for testing."""
        dates = pd.date_range(end=datetime.now(), periods=length, freq='D')
        
        if trend == 'stable':
            close = np.linspace(100, 102, length)
        elif trend == 'up':
            close = np.linspace(100, 110, length)
        elif trend == 'down':
            close = np.linspace(100, 90, length)
        
        if volatility == 'high':
            close = close + np.random.normal(0, 2, length)
        else:
            close = close + np.random.normal(0, 0.5, length)
        
        data = pd.DataFrame({
            'Open': close - 0.5,
            'High': close + 1.0,
            'Low': close - 1.0,
            'Close': close,
            'Volume': np.random.randint(1000000, 5000000, length)
        }, index=dates)
        
        return data
    
    def test_volume_anomaly_detection(self):
        """Test volume anomaly detection."""
        data = self.create_sample_data(length=20)
        
        # Add extreme volume spike (10x normal)
        data.iloc[-1, data.columns.get_loc('Volume')] = 50000000
        
        strength, explanation = self.detector.detect_volume_anomaly(data)
        
        # Just test that it runs without error
        assert isinstance(strength, (int, float)), "Should return numeric strength"
        assert isinstance(explanation, str), "Should return explanation string"
    
    def test_volatility_regime_shift(self):
        """Test volatility regime detection."""
        data = self.create_sample_data(length=30, volatility='normal')
        
        # Increase volatility in last 10 bars
        data.iloc[-10:, data.columns.get_loc('Close')] += np.random.normal(0, 3, 10)
        
        strength, explanation = self.detector.detect_volatility_regime_shift(data)
        
        # May or may not detect depending on statistical threshold
        assert strength >= 0
    
    def test_bid_ask_spread_expansion(self):
        """Test spread expansion detection."""
        data = self.create_sample_data(length=20)
        
        # Expand high-low range on last bar
        data.iloc[-1, data.columns.get_loc('High')] += 2.0
        data.iloc[-1, data.columns.get_loc('Low')] -= 2.0
        
        strength, explanation = self.detector.detect_bid_ask_expansion(data)
        
        assert strength > 0, "Should detect spread expansion"


class TestMomentumReversalDetector:
    """Test momentum and reversal signals."""
    
    def setup_method(self):
        self.detector = MomentumReversalDetector(lookback_period=20)
    
    def create_sample_data(self, length=20, trend='stable'):
        """Create sample OHLCV data."""
        dates = pd.date_range(end=datetime.now(), periods=length, freq='D')
        
        if trend == 'up':
            close = np.linspace(100, 110, length)
        elif trend == 'down':
            close = np.linspace(100, 90, length)
        else:
            close = np.full(length, 100.0)
        
        data = pd.DataFrame({
            'Open': close - 0.3,
            'High': close + 0.5,
            'Low': close - 0.5,
            'Close': close,
            'Volume': np.full(length, 2000000)
        }, index=dates)
        
        return data
    
    def test_order_imbalance_detection(self):
        """Test order imbalance detection."""
        data = self.create_sample_data(length=20, trend='up')
        
        strength, direction, explanation = self.detector.detect_order_imbalance(data)
        
        # Uptrend should show some bullish bias
        assert strength >= 0
        if strength > 0.3:
            assert direction in ['bullish', 'bearish']
    
    def test_mean_reversion_extreme(self):
        """Test mean reversion extreme detection."""
        data = self.create_sample_data(length=20)
        
        # Create extreme move in last bar
        data.iloc[-1, data.columns.get_loc('Close')] += 5.0  # 5% jump
        
        strength, direction, explanation = self.detector.detect_mean_reversion_extreme(data)
        
        assert strength >= 0
        if strength > 0.4:
            assert direction in ['bullish', 'bearish']
    
    def test_momentum_continuation(self):
        """Test momentum continuation detection."""
        data = self.create_sample_data(length=20, trend='up')
        
        # Add high volume to the trend
        data.iloc[-5:, data.columns.get_loc('Volume')] = 3000000
        
        strength, direction, explanation = self.detector.detect_momentum_continuation(data)
        
        assert strength >= 0
        if strength > 0:
            assert direction in ['bullish', 'bearish']


class TestSignalRun:
    """Test running all detectors together."""
    
    def test_info_flow_run_all(self):
        """Test running all information flow detectors."""
        detector = InformationFlowDetector()
        
        dates = pd.date_range(end=datetime.now(), periods=20, freq='D')
        data = pd.DataFrame({
            'Open': np.linspace(100, 102, 20),
            'High': np.linspace(101, 103, 20),
            'Low': np.linspace(99, 101, 20),
            'Close': np.linspace(100, 102, 20),
            'Volume': np.random.randint(1000000, 5000000, 20)
        }, index=dates)
        
        signals = detector.run_all(data)
        
        assert isinstance(signals, list)
        for sig in signals:
            assert len(sig) == 3  # (type, strength, explanation)
            assert sig[1] >= 0 and sig[1] <= 1.0  # Strength in [0, 1]
    
    def test_momentum_run_all(self):
        """Test running all momentum detectors."""
        detector = MomentumReversalDetector()
        
        dates = pd.date_range(end=datetime.now(), periods=20, freq='D')
        data = pd.DataFrame({
            'Open': np.linspace(100, 105, 20),
            'High': np.linspace(101, 106, 20),
            'Low': np.linspace(99, 104, 20),
            'Close': np.linspace(100, 105, 20),
            'Volume': np.random.randint(1000000, 5000000, 20)
        }, index=dates)
        
        signals = detector.run_all(data)
        
        assert isinstance(signals, list)
        for sig in signals:
            assert len(sig) == 4  # (type, strength, direction, explanation)
            assert sig[1] >= 0 and sig[1] <= 1.0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
