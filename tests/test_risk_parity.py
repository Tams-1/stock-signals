"""
Comprehensive tests for RiskParity - correlation-adjusted position sizing.

Tests cover:
- Risk parity weight calculation
- Correlation adjustment
- Portfolio risk metrics
- Diversification ratio
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from src.risk.risk_parity import RiskParity, apply_risk_parity


class TestRiskParityWeights:
    """Tests for risk parity weight calculation."""
    
    @pytest.fixture
    def rp(self):
        return RiskParity(target_volatility=0.15)
    
    @pytest.fixture
    def returns_data(self):
        """Create returns data for multiple assets."""
        np.random.seed(42)
        return {
            'STOCK_A': pd.Series(np.random.randn(100) * 0.02),
            'STOCK_B': pd.Series(np.random.randn(100) * 0.03),
            'STOCK_C': pd.Series(np.random.randn(100) * 0.01)
        }
    
    def test_weights_sum_to_one(self, rp, returns_data):
        """Test that weights sum to approximately 1.0."""
        weights = rp.calculate_risk_parity_weights(returns_data)
        
        total_weight = sum(weights.values())
        assert abs(total_weight - 1.0) < 0.01, f"Weights should sum to ~1.0, got {total_weight}"
    
    def test_all_weights_positive(self, rp, returns_data):
        """Test that all weights are positive."""
        weights = rp.calculate_risk_parity_weights(returns_data)
        
        for ticker, weight in weights.items():
            assert weight > 0, f"Weight for {ticker} should be positive"
    
    def test_weights_for_different_volatilities(self, rp):
        """Test that lower volatility assets get higher weights."""
        np.random.seed(42)
        
        # Stock A has low vol, Stock B has high vol
        returns_data = {
            'LOW_VOL': pd.Series(np.random.randn(100) * 0.01),
            'HIGH_VOL': pd.Series(np.random.randn(100) * 0.05)
        }
        
        weights = rp.calculate_risk_parity_weights(returns_data)
        
        # Lower vol should get higher weight (inverse volatility)
        assert weights['LOW_VOL'] > weights['HIGH_VOL'], \
            "Low volatility asset should have higher weight"
    
    def test_weights_handles_empty_data(self, rp):
        """Test weights calculation with empty data."""
        weights = rp.calculate_risk_parity_weights({})
        
        assert weights == {}, "Should return empty dict for empty input"
    
    def test_weights_handles_single_asset(self, rp):
        """Test weights calculation for single asset."""
        np.random.seed(42)
        returns_data = {
            'SINGLE': pd.Series(np.random.randn(100) * 0.02)
        }
        
        weights = rp.calculate_risk_parity_weights(returns_data)
        
        assert weights['SINGLE'] == 1.0, "Single asset should have weight 1.0"


class TestCorrelationAdjustment:
    """Tests for correlation-based position adjustment."""
    
    @pytest.fixture
    def rp(self):
        return RiskParity()
    
    def test_correlation_adjustment_reduces_high_corr(self, rp):
        """Test that highly correlated assets are reduced."""
        np.random.seed(42)
        
        # Highly correlated assets
        base_returns = np.random.randn(100) * 0.02
        returns_data = {
            'STOCK_A': pd.Series(base_returns),
            'STOCK_B': pd.Series(base_returns * 1.1)  # High correlation
        }
        
        positions = {'STOCK_A': 0.5, 'STOCK_B': 0.5}
        
        adjusted = rp.adjust_positions_for_correlation(positions, returns_data)
        
        # Total exposure should be reduced
        total_original = sum(positions.values())
        total_adjusted = sum(adjusted.values())
        
        assert total_adjusted <= total_original
    
    def test_adjustment_for_low_correlation(self, rp):
        """Test that low correlation has less adjustment."""
        np.random.seed(42)
        
        # Low correlation assets
        returns_data = {
            'STOCK_A': pd.Series(np.random.randn(100) * 0.02),
            'STOCK_B': pd.Series(np.random.randn(100) * 0.02)  # Uncorrelated
        }
        
        positions = {'STOCK_A': 0.5, 'STOCK_B': 0.5}
        
        adjusted = rp.adjust_positions_for_correlation(positions, returns_data)
        
        # Low correlation should have minimal adjustment
        assert 'STOCK_A' in adjusted
        assert 'STOCK_B' in adjusted
    
    def test_adjustment_handles_single_position(self, rp):
        """Test adjustment with single position."""
        np.random.seed(42)
        returns_data = {
            'SINGLE': pd.Series(np.random.randn(100) * 0.02)
        }
        
        positions = {'SINGLE': 1.0}
        
        adjusted = rp.adjust_positions_for_correlation(positions, returns_data)
        
        # Single position should not be adjusted
        assert adjusted == positions
    
    def test_adjustment_normalizes_total(self, rp):
        """Test that total exposure is normalized if > 1.0."""
        np.random.seed(42)
        
        returns_data = {
            'STOCK_A': pd.Series(np.random.randn(100) * 0.02),
            'STOCK_B': pd.Series(np.random.randn(100) * 0.02)
        }
        
        # Positions > 1.0 total
        positions = {'STOCK_A': 0.6, 'STOCK_B': 0.6}  # Total 1.2
        
        adjusted = rp.adjust_positions_for_correlation(positions, returns_data)
        
        # After normalization, total should be <= 1.0
        total = sum(adjusted.values())
        assert total <= 1.01  # Allow small floating point error


class TestPortfolioRisk:
    """Tests for portfolio risk calculation."""
    
    @pytest.fixture
    def rp(self):
        return RiskParity()
    
    @pytest.fixture
    def portfolio_data(self):
        """Create portfolio returns data."""
        np.random.seed(42)
        return {
            'STOCK_A': pd.Series(np.random.randn(100) * 0.02),
            'STOCK_B': pd.Series(np.random.randn(100) * 0.03)
        }
    
    def test_portfolio_risk_returns_dict(self, rp, portfolio_data):
        """Test that portfolio risk returns proper dict."""
        positions = {'STOCK_A': 0.5, 'STOCK_B': 0.5}
        
        risk = rp.calculate_portfolio_risk(positions, portfolio_data)
        
        assert 'total_risk' in risk
        assert 'diversification_ratio' in risk
    
    def test_total_risk_positive(self, rp, portfolio_data):
        """Test that total risk is positive."""
        positions = {'STOCK_A': 0.5, 'STOCK_B': 0.5}
        
        risk = rp.calculate_portfolio_risk(positions, portfolio_data)
        
        assert risk['total_risk'] >= 0
    
    def test_diversification_ratio(self, rp, portfolio_data):
        """Test diversification ratio calculation."""
        positions = {'STOCK_A': 0.5, 'STOCK_B': 0.5}
        
        risk = rp.calculate_portfolio_risk(positions, portfolio_data)
        
        # Diversification ratio should be >= 1.0 for diversified portfolio
        assert risk['diversification_ratio'] >= 1.0 or risk['diversification_ratio'] == 1.0
    
    def test_portfolio_risk_handles_empty_positions(self, rp, portfolio_data):
        """Test portfolio risk with empty positions."""
        risk = rp.calculate_portfolio_risk({}, portfolio_data)
        
        assert risk['total_risk'] == 0.0
        assert risk['diversification_ratio'] == 1.0
    
    def test_portfolio_risk_handles_empty_returns(self, rp):
        """Test portfolio risk with empty returns."""
        positions = {'STOCK_A': 0.5}
        
        risk = rp.calculate_portfolio_risk(positions, {})
        
        assert risk['total_risk'] == 0.0


class TestCorrelationMatrix:
    """Tests for correlation matrix calculation."""
    
    @pytest.fixture
    def rp(self):
        return RiskParity()
    
    def test_correlation_matrix_shape(self, rp):
        """Test correlation matrix has correct shape."""
        np.random.seed(42)
        returns_data = {
            'A': pd.Series(np.random.randn(50)),
            'B': pd.Series(np.random.randn(50)),
            'C': pd.Series(np.random.randn(50))
        }
        
        corr_matrix = rp.calculate_correlation_matrix(returns_data)
        
        assert corr_matrix.shape == (3, 3)
    
    def test_correlation_diagonal_is_one(self, rp):
        """Test that diagonal elements are 1.0."""
        np.random.seed(42)
        returns_data = {
            'A': pd.Series(np.random.randn(50)),
            'B': pd.Series(np.random.randn(50))
        }
        
        corr_matrix = rp.calculate_correlation_matrix(returns_data)
        
        for ticker in corr_matrix.index:
            assert abs(corr_matrix.loc[ticker, ticker] - 1.0) < 0.01
    
    def test_correlation_symmetric(self, rp):
        """Test that correlation matrix is symmetric."""
        np.random.seed(42)
        returns_data = {
            'A': pd.Series(np.random.randn(50)),
            'B': pd.Series(np.random.randn(50))
        }
        
        corr_matrix = rp.calculate_correlation_matrix(returns_data)
        
        assert corr_matrix.loc['A', 'B'] == corr_matrix.loc['B', 'A']


class TestVolatilityCalculation:
    """Tests for volatility calculation."""
    
    @pytest.fixture
    def rp(self):
        return RiskParity()
    
    def test_volatility_annualized(self, rp):
        """Test that volatility is annualized."""
        np.random.seed(42)
        returns = pd.Series(np.random.randn(252) * 0.01)  # Daily returns
        
        vol = rp.calculate_volatility(returns)
        
        # Should be approximately 1% * sqrt(252) ≈ 15.9%
        expected = 0.01 * np.sqrt(252)
        assert abs(vol - expected) < 0.05
    
    def test_volatility_zero_returns(self, rp):
        """Test volatility with zero returns."""
        returns = pd.Series([0.0] * 100)
        
        vol = rp.calculate_volatility(returns)
        
        assert vol == 0.0
    
    def test_volatility_higher_for_volatile_data(self, rp):
        """Test that higher volatility data gives higher result."""
        np.random.seed(42)
        low_vol = pd.Series(np.random.randn(100) * 0.01)
        high_vol = pd.Series(np.random.randn(100) * 0.05)
        
        vol_low = rp.calculate_volatility(low_vol)
        vol_high = rp.calculate_volatility(high_vol)
        
        assert vol_high > vol_low


class TestApplyRiskParity:
    """Tests for convenience function."""
    
    def test_apply_risk_parity_returns_dict(self):
        """Test that apply_risk_parity returns dict."""
        np.random.seed(42)
        positions = {'A': 0.5, 'B': 0.5}
        returns_data = {
            'A': pd.Series(np.random.randn(100) * 0.02),
            'B': pd.Series(np.random.randn(100) * 0.03)
        }
        
        result = apply_risk_parity(positions, returns_data)
        
        assert isinstance(result, dict)
        assert 'A' in result
        assert 'B' in result
    
    def test_apply_risk_parity_with_target_vol(self):
        """Test apply_risk_parity with custom target volatility."""
        np.random.seed(42)
        positions = {'A': 0.5, 'B': 0.5}
        returns_data = {
            'A': pd.Series(np.random.randn(100) * 0.02),
            'B': pd.Series(np.random.randn(100) * 0.03)
        }
        
        result = apply_risk_parity(positions, returns_data, target_volatility=0.20)
        
        assert isinstance(result, dict)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
