"""
Comprehensive tests for FeatureEngineer - advanced feature generation.

Tests cover:
- Volume features
- Sector momentum
- Volatility regime
- Correlation features
- Feature pipeline
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from src.features.feature_engineering import FeatureEngineer, get_feature_engineer


class TestVolumeFeatures:
    """Tests for volume-based features."""
    
    @pytest.fixture
    def fe(self):
        return FeatureEngineer()
    
    @pytest.fixture
    def sample_data(self):
        """Create sample price data with volume."""
        dates = pd.date_range(start='2024-01-01', periods=100, freq='D')
        np.random.seed(42)
        return pd.DataFrame({
            'Close': np.random.randn(100).cumsum() + 100,
            'Open': np.random.randn(100).cumsum() + 100,
            'High': np.random.randn(100).cumsum() + 100,
            'Low': np.random.randn(100).cumsum() + 100,
            'Volume': np.random.randint(1000000, 5000000, 100)
        }, index=dates)
    
    def test_volume_momentum_calculation(self, fe, sample_data):
        """Test volume momentum (5-day vs 20-day ratio)."""
        features = fe.add_volume_features(sample_data)
        
        assert 'volume_momentum' in features
        assert isinstance(features['volume_momentum'], float)
        assert features['volume_momentum'] > 0, "Volume momentum should be positive"
    
    def test_unusual_volume_detection(self, fe, sample_data):
        """Test unusual volume detection."""
        features = fe.add_volume_features(sample_data)
        
        assert 'unusual_volume' in features
        assert isinstance(features['unusual_volume'], bool)
    
    def test_volume_trend_detection(self, fe, sample_data):
        """Test volume trend detection."""
        features = fe.add_volume_features(sample_data)
        
        assert 'volume_trend' in features
        assert features['volume_trend'] in ['increasing', 'decreasing', 'neutral']
    
    def test_volume_features_handles_missing_volume(self, fe):
        """Test handling of data without volume."""
        dates = pd.date_range(start='2024-01-01', periods=100, freq='D')
        data = pd.DataFrame({
            'Close': np.random.randn(100).cumsum() + 100
        }, index=dates)
        
        features = fe.add_volume_features(data)
        
        # Should return defaults
        assert features['volume_momentum'] == 1.0
        assert features['unusual_volume'] == False
        assert features['volume_trend'] == 'neutral'
    
    def test_volume_features_handles_insufficient_data(self, fe):
        """Test handling of insufficient data."""
        data = pd.DataFrame({
            'Close': [100, 101, 102],
            'Volume': [1000000, 1100000, 1200000]
        })
        
        features = fe.add_volume_features(data)
        
        # Should return defaults
        assert 'volume_momentum' in features
    
    def test_unusual_volume_with_spike(self, fe):
        """Test unusual volume detection with volume spike."""
        dates = pd.date_range(start='2024-01-01', periods=100, freq='D')
        volume = [1000000] * 99 + [10000000]  # Big spike at end
        
        data = pd.DataFrame({
            'Close': np.random.randn(100).cumsum() + 100,
            'Volume': volume
        }, index=dates)
        
        features = fe.add_volume_features(data)
        
        # Should detect unusual volume
        assert features['unusual_volume'] == True


class TestSectorMomentum:
    """Tests for sector momentum features."""
    
    @pytest.fixture
    def fe(self):
        return FeatureEngineer()
    
    @pytest.fixture
    def sample_data(self):
        """Create sample price data."""
        dates = pd.date_range(start='2024-01-01', periods=100, freq='D')
        return pd.DataFrame({
            'Close': np.linspace(100, 120, 100)  # Uptrend
        }, index=dates)
    
    @pytest.fixture
    def market_data(self):
        """Create market data (IBOV proxy)."""
        dates = pd.date_range(start='2024-01-01', periods=100, freq='D')
        return pd.DataFrame({
            'Close': np.linspace(100, 110, 100)  # Slower uptrend
        }, index=dates)
    
    def test_relative_strength_calculation(self, fe, sample_data, market_data):
        """Test relative strength vs market."""
        features = fe.add_sector_momentum('TEST.SA', sample_data, market_data)
        
        assert 'relative_strength' in features
        assert isinstance(features['relative_strength'], float)
    
    def test_relative_strength_without_market_data(self, fe, sample_data):
        """Test relative strength without market data."""
        features = fe.add_sector_momentum('TEST.SA', sample_data, None)
        
        assert features['relative_strength'] == 1.0
    
    def test_sector_rank(self, fe, sample_data):
        """Test sector rank (placeholder)."""
        features = fe.add_sector_momentum('TEST.SA', sample_data)
        
        assert 'sector_rank' in features
        assert 0 <= features['sector_rank'] <= 1
    
    def test_sector_momentum_insufficient_data(self, fe):
        """Test sector momentum with insufficient data."""
        data = pd.DataFrame({'Close': [100, 101, 102]})
        
        features = fe.add_sector_momentum('TEST.SA', data)
        
        assert features['relative_strength'] == 1.0
        assert features['sector_rank'] == 0.5


class TestVolatilityRegime:
    """Tests for volatility regime features."""
    
    @pytest.fixture
    def fe(self):
        return FeatureEngineer()
    
    @pytest.fixture
    def low_vol_data(self):
        """Create low volatility data."""
        dates = pd.date_range(start='2024-01-01', periods=100, freq='D')
        return pd.DataFrame({
            'Close': 100 + np.random.randn(100) * 0.5
        }, index=dates)
    
    @pytest.fixture
    def high_vol_data(self):
        """Create high volatility data."""
        dates = pd.date_range(start='2024-01-01', periods=100, freq='D')
        return pd.DataFrame({
            'Close': 100 + np.random.randn(100) * 5
        }, index=dates)
    
    def test_volatility_calculation(self, fe, low_vol_data):
        """Test annualized volatility calculation."""
        features = fe.add_volatility_regime(low_vol_data)
        
        assert 'volatility' in features
        assert isinstance(features['volatility'], float)
        assert features['volatility'] >= 0
    
    def test_volatility_regime_low(self, fe, low_vol_data):
        """Test low volatility regime classification."""
        features = fe.add_volatility_regime(low_vol_data)
        
        assert features['regime'] in ['low', 'medium', 'high']
    
    def test_volatility_regime_high(self, fe, high_vol_data):
        """Test high volatility regime classification."""
        features = fe.add_volatility_regime(high_vol_data)
        
        # High vol data should generally be medium or high
        assert features['regime'] in ['medium', 'high']
    
    def test_vix_equivalent(self, fe, low_vol_data):
        """Test VIX-like measure."""
        features = fe.add_volatility_regime(low_vol_data)
        
        assert 'vix_equivalent' in features
        assert features['vix_equivalent'] >= 0
    
    def test_volatility_regime_insufficient_data(self, fe):
        """Test volatility regime with insufficient data."""
        data = pd.DataFrame({'Close': [100, 101, 102]})
        
        features = fe.add_volatility_regime(data)
        
        # Should return defaults
        assert features['volatility'] == 0.20
        assert features['regime'] == 'medium'
        assert features['vix_equivalent'] == 20.0


class TestCorrelationFeatures:
    """Tests for correlation features."""
    
    @pytest.fixture
    def fe(self):
        return FeatureEngineer()
    
    @pytest.fixture
    def sample_data(self):
        """Create sample price data."""
        dates = pd.date_range(start='2024-01-01', periods=100, freq='D')
        return pd.DataFrame({
            'Close': np.linspace(100, 150, 100)
        }, index=dates)
    
    def test_correlation_features_return_dict(self, fe, sample_data):
        """Test correlation features return proper dict."""
        features = fe.add_correlation_features('TEST.SA', sample_data)
        
        assert 'market_correlation' in features
        assert 'peer_correlation' in features
        assert 'correlation_stability' in features
    
    def test_correlation_values_in_range(self, fe, sample_data):
        """Test correlation values are in valid range."""
        features = fe.add_correlation_features('TEST.SA', sample_data)
        
        assert -1 <= features['market_correlation'] <= 1
        assert -1 <= features['peer_correlation'] <= 1
    
    def test_correlation_insufficient_data(self, fe):
        """Test correlation with insufficient data."""
        data = pd.DataFrame({'Close': [100, 101, 102]})
        
        features = fe.add_correlation_features('TEST.SA', data)
        
        # Should return defaults
        assert features['market_correlation'] == 0.5
        assert features['peer_correlation'] == 0.5


class TestFeaturePipeline:
    """Tests for complete feature pipeline."""
    
    @pytest.fixture
    def fe(self):
        return FeatureEngineer()
    
    @pytest.fixture
    def sample_data(self):
        """Create sample price data."""
        dates = pd.date_range(start='2024-01-01', periods=100, freq='D')
        np.random.seed(42)
        return pd.DataFrame({
            'Close': np.random.randn(100).cumsum() + 100,
            'Volume': np.random.randint(1000000, 5000000, 100)
        }, index=dates)
    
    def test_generate_all_features(self, fe, sample_data):
        """Test generating all features."""
        features = fe.generate_all_features('TEST.SA', sample_data)
        
        assert 'volume' in features
        assert 'sector' in features
        assert 'volatility' in features
        assert 'correlation' in features
    
    def test_all_features_contain_expected_keys(self, fe, sample_data):
        """Test that all feature categories have expected keys."""
        features = fe.generate_all_features('TEST.SA', sample_data)
        
        # Volume features
        assert 'volume_momentum' in features['volume']
        assert 'unusual_volume' in features['volume']
        assert 'volume_trend' in features['volume']
        
        # Sector features
        assert 'relative_strength' in features['sector']
        assert 'sector_rank' in features['sector']
        
        # Volatility features
        assert 'volatility' in features['volatility']
        assert 'regime' in features['volatility']
        assert 'vix_equivalent' in features['volatility']
        
        # Correlation features
        assert 'market_correlation' in features['correlation']
        assert 'peer_correlation' in features['correlation']
        assert 'correlation_stability' in features['correlation']
    
    def test_generate_with_market_data(self, fe, sample_data):
        """Test generating features with market data."""
        dates = pd.date_range(start='2024-01-01', periods=100, freq='D')
        market_data = pd.DataFrame({
            'Close': np.linspace(100, 110, 100)
        }, index=dates)
        
        features = fe.generate_all_features('TEST.SA', sample_data, market_data=market_data)
        
        assert 'sector' in features


class TestGlobalFeatureEngineer:
    """Tests for global feature engineer singleton."""
    
    def test_get_feature_engineer_returns_instance(self):
        """Test that get_feature_engineer returns FeatureEngineer."""
        fe = get_feature_engineer()
        
        assert isinstance(fe, FeatureEngineer)
    
    def test_get_feature_engineer_returns_same_instance(self):
        """Test that get_feature_engineer returns same instance."""
        import src.features.feature_engineering as module
        module._feature_engineer = None
        
        fe1 = get_feature_engineer()
        fe2 = get_feature_engineer()
        
        assert fe1 is fe2


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
