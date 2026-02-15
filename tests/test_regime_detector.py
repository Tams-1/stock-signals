"""Unit tests for Regime Detector module."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
import tempfile
import os

from src.signals.regime_detector import RegimeDetector


class TestRegimeDetector:
    """Test market regime detection functionality."""
    
    @pytest.fixture
    def temp_db(self):
        """Create temporary database for testing."""
        fd, path = tempfile.mkstemp(suffix='.db')
        os.close(fd)
        yield path
        if os.path.exists(path):
            os.unlink(path)
    
    @pytest.fixture
    def detector(self, temp_db):
        """Create RegimeDetector instance."""
        return RegimeDetector(lookback_period=20, adx_period=14, db_path=temp_db)
    
    def create_sample_data(self, length=30, trend='uptrend', volatility=0.5):
        """Create sample OHLCV data for testing."""
        dates = pd.date_range(end=datetime.now(), periods=length, freq='D')
        
        if trend == 'uptrend':
            # Strong uptrend
            close = np.linspace(100, 120, length)
            noise = np.random.normal(0, volatility, length)
        elif trend == 'downtrend':
            # Strong downtrend
            close = np.linspace(120, 100, length)
            noise = np.random.normal(0, volatility, length)
        else:  # consolidation
            # Ranging market
            close = np.full(length, 110) + np.random.normal(0, volatility * 2, length)
            noise = np.zeros(length)
        
        close = close + noise
        
        data = pd.DataFrame({
            'Open': close - 0.5,
            'High': close + 1.5,
            'Low': close - 1.5,
            'Close': close,
            'Volume': np.random.randint(1000000, 5000000, length)
        }, index=dates)
        
        return data
    
    def test_detector_initialization(self, detector):
        """Test detector initialization."""
        assert detector.lookback_period == 20
        assert detector.adx_period == 14
        assert detector.REGIME_STRATEGIES is not None
        assert 'uptrend' in detector.REGIME_STRATEGIES
        assert 'downtrend' in detector.REGIME_STRATEGIES
        assert 'consolidation' in detector.REGIME_STRATEGIES
    
    def test_regime_strategies_config(self, detector):
        """Test regime strategy configurations."""
        # Uptrend should be aggressive
        assert detector.REGIME_STRATEGIES['uptrend']['allocation'] == 0.70
        assert detector.REGIME_STRATEGIES['uptrend']['mode'] == 'aggressive'
        
        # Downtrend should be defensive
        assert detector.REGIME_STRATEGIES['downtrend']['allocation'] == 0.30
        assert detector.REGIME_STRATEGIES['downtrend']['mode'] == 'defensive'
        
        # Consolidation should be balanced
        assert detector.REGIME_STRATEGIES['consolidation']['allocation'] == 0.50
        assert detector.REGIME_STRATEGIES['consolidation']['mode'] == 'balanced'
    
    def test_detect_uptrend(self, detector):
        """Test detection of uptrend regime."""
        data = self.create_sample_data(length=30, trend='uptrend')
        
        result = detector.detect_regime(data)
        
        assert result['regime'] == 'uptrend'
        assert result['confidence'] > 0.5
        assert 'methods' in result
        assert 'strategy' in result
    
    def test_detect_downtrend(self, detector):
        """Test detection of downtrend regime."""
        data = self.create_sample_data(length=30, trend='downtrend')
        
        result = detector.detect_regime(data)
        
        assert result['regime'] == 'downtrend'
        assert result['confidence'] > 0.5
    
    def test_detect_consolidation(self, detector):
        """Test detection of consolidation/ranging regime."""
        data = self.create_sample_data(length=30, trend='consolidation')
        
        result = detector.detect_regime(data)
        
        # Should detect consolidation or weak trend
        assert result['regime'] in ['consolidation', 'uptrend', 'downtrend']
        assert 0 <= result['confidence'] <= 1.0
    
    def test_detect_slope_method(self, detector):
        """Test slope-based trend detection."""
        # Strong uptrend
        data = self.create_sample_data(length=20, trend='uptrend', volatility=0.1)
        result = detector._detect_slope(data)
        
        assert result['regime'] == 'uptrend'
        assert result['strength'] > 0.5
    
    def test_detect_ma_cross_method(self, detector):
        """Test MA crossover trend detection."""
        # Strong uptrend should have MA crossover signal
        data = self.create_sample_data(length=25, trend='uptrend', volatility=0.1)
        result = detector._detect_ma_cross(data)
        
        assert result['regime'] in ['uptrend', 'consolidation']
        assert 0 <= result['strength'] <= 1.0
    
    def test_detect_adx_method(self, detector):
        """Test ADX trend strength detection."""
        data = self.create_sample_data(length=35, trend='uptrend', volatility=0.1)
        result = detector._detect_adx(data)
        
        assert result['regime'] in ['uptrend', 'downtrend', 'consolidation']
        assert 0 <= result['strength'] <= 1.0
    
    def test_detect_price_structure_method(self, detector):
        """Test price structure trend detection."""
        # Strong uptrend should show higher highs and higher lows
        data = self.create_sample_data(length=25, trend='uptrend', volatility=0.1)
        result = detector._detect_price_structure(data)
        
        assert result['regime'] in ['uptrend', 'downtrend', 'consolidation']
        assert 0 <= result['strength'] <= 1.0
    
    def test_ensemble_voting(self, detector):
        """Test ensemble voting mechanism."""
        # Create signals from different methods
        slope_signal = {'regime': 'uptrend', 'strength': 0.8}
        ma_signal = {'regime': 'uptrend', 'strength': 0.7}
        adx_signal = {'regime': 'uptrend', 'strength': 0.9}
        structure_signal = {'regime': 'consolidation', 'strength': 0.5}
        
        regime, confidence = detector._ensemble_vote(
            slope_signal, ma_signal, adx_signal, structure_signal
        )
        
        # 3 out of 4 vote uptrend, so should be uptrend
        assert regime == 'uptrend'
        assert confidence > 0.6
    
    def test_ensemble_voting_all_unknown(self, detector):
        """Test ensemble voting when all methods return unknown."""
        signal = {'regime': 'unknown', 'strength': 0.0}
        
        regime, confidence = detector._ensemble_vote(signal, signal, signal, signal)
        
        # Should default to consolidation
        assert regime == 'consolidation'
        assert confidence == 0.0
    
    def test_ema_calculation(self, detector):
        """Test EMA calculation."""
        data = np.array([1, 2, 3, 4, 5, 6, 7, 8, 9, 10], dtype=float)
        period = 3
        
        ema = detector._ema(data, period)
        
        assert len(ema) == len(data)
        assert not np.isnan(ema).any()
        assert not np.isinf(ema).any()
    
    def test_store_regime(self, detector, temp_db):
        """Test storing regime detection result."""
        data = self.create_sample_data(length=30, trend='uptrend')
        regime_data = detector.detect_regime(data)
        
        detector.store_regime('PETR4', regime_data)
        
        # Verify it was stored
        history = detector.get_regime_history('PETR4', days=1)
        
        assert len(history) > 0
        assert history[0]['regime'] == 'uptrend'
    
    def test_get_regime_history(self, detector):
        """Test retrieving regime history."""
        data = self.create_sample_data(length=30, trend='uptrend')
        
        # Store multiple regimes
        for i in range(3):
            regime_data = detector.detect_regime(data)
            detector.store_regime('PETR4', regime_data)
        
        history = detector.get_regime_history('PETR4', days=1)
        
        assert len(history) > 0
        assert all('regime' in h for h in history)
        assert all('confidence' in h for h in history)
    
    def test_get_regime_summary(self, detector):
        """Test regime summary calculation."""
        data_up = self.create_sample_data(length=30, trend='uptrend')
        data_down = self.create_sample_data(length=30, trend='downtrend')
        
        # Store uptrend regimes
        for i in range(3):
            regime_data = detector.detect_regime(data_up)
            detector.store_regime('PETR4', regime_data)
        
        summary = detector.get_regime_summary('PETR4', days=1)
        
        assert 'dominant_regime' in summary
        assert 'dominance_pct' in summary
        assert 'avg_confidence' in summary
        assert 'latest_regime' in summary
    
    def test_insufficient_data_handling(self, detector):
        """Test handling of insufficient data."""
        # Create very short data
        short_data = self.create_sample_data(length=5)
        
        result = detector.detect_regime(short_data)
        
        assert result['regime'] == 'unknown'
        assert result['confidence'] == 0.0
    
    def test_all_methods_return_values(self, detector):
        """Test that all methods return expected values."""
        data = self.create_sample_data(length=30, trend='uptrend')
        
        result = detector.detect_regime(data)
        
        methods = result.get('methods', {})
        
        # All 4 methods should be present
        assert 'slope' in methods
        assert 'ma_cross' in methods
        assert 'adx' in methods
        assert 'structure' in methods
        
        # Each should have regime and strength
        for method_name, method_result in methods.items():
            assert 'regime' in method_result
            assert 'strength' in method_result
            assert 0 <= method_result['strength'] <= 1.0
    
    def test_confidence_scoring(self, detector):
        """Test confidence scoring of regime detection."""
        data = self.create_sample_data(length=30, trend='uptrend', volatility=0.1)
        
        result = detector.detect_regime(data)
        
        # Strong uptrend should have high confidence
        assert result['confidence'] > 0.5
        
        # Strong consolidation should have lower confidence
        data_cons = self.create_sample_data(length=30, trend='consolidation', volatility=2.0)
        result_cons = detector.detect_regime(data_cons)
        
        assert 0 <= result_cons['confidence'] <= 1.0
    
    def test_multiple_stocks_regime_tracking(self, detector):
        """Test tracking regimes for multiple stocks."""
        stocks = ['PETR4', 'VALE3', 'BBDC4']
        data = self.create_sample_data(length=30, trend='uptrend')
        
        # Store regimes for multiple stocks
        for ticker in stocks:
            regime_data = detector.detect_regime(data)
            detector.store_regime(ticker, regime_data)
        
        # Verify each stock has history
        for ticker in stocks:
            history = detector.get_regime_history(ticker, days=1)
            assert len(history) > 0
    
    def test_regime_change_detection(self, detector):
        """Test detection of regime changes."""
        data_up = self.create_sample_data(length=30, trend='uptrend')
        data_down = self.create_sample_data(length=30, trend='downtrend')
        
        # Store uptrend
        regime_up = detector.detect_regime(data_up)
        detector.store_regime('PETR4', regime_up)
        
        # Store downtrend
        regime_down = detector.detect_regime(data_down)
        detector.store_regime('PETR4', regime_down)
        
        summary = detector.get_regime_summary('PETR4', days=1)
        
        # Should detect regime changes
        assert 'regime_changes' in summary
        assert summary['regime_changes'] >= 0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
