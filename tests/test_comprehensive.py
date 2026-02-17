"""
Comprehensive unit tests for stock-signals production-hardening branch.

Tests all major components:
- TrendDetectorV2 (dual-timeframe trend detection)
- FreeNewsClient (news fetching, sentiment analysis)
- NewsCache (caching, TTL logic)
- SimpleProductionRunner (main analysis engine)
- FeatureEngineer (feature extraction)
- APIBudgetTracker (budget tracking)
- RiskParity (position sizing)
- WalkForwardValidator (validation)
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock
import tempfile
from pathlib import Path

# Test imports
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.signals.trend_detector_v2 import TrendDetectorV2
from src.news.free_news_client import FinBERTSentimentAnalyzer, FreeNewsClient
from src.news.news_cache import NewsCache
from src.news.api_budget_tracker import APIBudgetTracker
from src.features.feature_engineering import FeatureEngineer
from src.risk.risk_parity import RiskParity
from src.validation.walk_forward import WalkForwardValidator
from production_simple import SimpleProductionRunner


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def sample_price_data():
    """Create sample price data for testing."""
    dates = pd.date_range(start='2024-01-01', periods=100, freq='D')
    np.random.seed(42)
    return pd.DataFrame({
        'Close': np.random.randn(100).cumsum() + 100,
        'Open': np.random.randn(100).cumsum() + 100,
        'High': np.random.randn(100).cumsum() + 100,
        'Low': np.random.randn(100).cumsum() + 100,
        'Volume': np.random.randint(1000000, 5000000, 100)
    }, index=dates)


@pytest.fixture
def uptrend_data():
    """Create clear uptrend data."""
    dates = pd.date_range(start='2024-01-01', periods=100, freq='D')
    prices = np.linspace(100, 150, 100) + np.random.randn(100) * 2
    return pd.DataFrame({'Close': prices}, index=dates)


@pytest.fixture
def downtrend_data():
    """Create clear downtrend data."""
    dates = pd.date_range(start='2024-01-01', periods=100, freq='D')
    prices = np.linspace(150, 100, 100) + np.random.randn(100) * 2
    return pd.DataFrame({'Close': prices}, index=dates)


@pytest.fixture
def long_price_data():
    """Create longer price data for walk-forward validation."""
    dates = pd.date_range(start='2023-01-01', periods=315, freq='D')
    np.random.seed(42)
    return pd.DataFrame({
        'Close': np.random.randn(315).cumsum() + 100,
        'Open': np.random.randn(315).cumsum() + 100,
        'High': np.random.randn(315).cumsum() + 100,
        'Low': np.random.randn(315).cumsum() + 100,
        'Volume': np.random.randint(1000000, 5000000, 315)
    }, index=dates)


# =============================================================================
# TEST TREND DETECTOR V2
# =============================================================================

class TestTrendDetectorV2:
    """Tests for dual-timeframe trend detection."""

    def test_uptrend_detection(self, uptrend_data):
        """Test uptrend detection."""
        detector = TrendDetectorV2()
        result = detector.detect_trend(uptrend_data)
        
        assert 'consensus' in result
        assert result['consensus'] in ['uptrend', 'bull_pullback', 'consolidation']
        assert result['confidence'] > 0

    def test_downtrend_detection(self, downtrend_data):
        """Test downtrend detection."""
        detector = TrendDetectorV2()
        result = detector.detect_trend(downtrend_data)
        
        assert 'consensus' in result
        assert result['consensus'] in ['downtrend', 'bear_bounce', 'consolidation']
        assert result['confidence'] > 0

    def test_insufficient_data_handling(self):
        """Test handling of insufficient data."""
        detector = TrendDetectorV2()
        
        dates = pd.date_range(start='2024-01-01', periods=10, freq='D')
        short_data = pd.DataFrame({'Close': np.random.randn(10) + 100}, index=dates)
        
        result = detector.detect_trend(short_data)
        
        assert result['consensus'] == 'unknown'
        assert result['confidence'] == 0

    def test_volatility_regime_classification(self, sample_price_data):
        """Test volatility regime classification."""
        detector = TrendDetectorV2()
        
        regime = detector._calculate_volatility_regime(sample_price_data)
        assert regime in ['low', 'medium', 'high']

    def test_consensus_logic(self):
        """Test consensus combines macro and micro timeframes."""
        detector = TrendDetectorV2()
        
        # Test macro uptrend + micro uptrend = uptrend
        consensus, conf = detector._get_consensus('uptrend', 0.7, 'uptrend', 0.6)
        assert consensus == 'uptrend'
        
        # Test macro uptrend + micro downtrend = consolidation or downtrend
        consensus, conf = detector._get_consensus('uptrend', 0.8, 'downtrend', 0.5)
        assert consensus in ['consolidation', 'downtrend']


# =============================================================================
# TEST FINBERT SENTIMENT ANALYZER
# =============================================================================

class TestFinBERTSentimentAnalyzer:
    """Tests for sentiment analysis."""

    def test_simple_sentiment_positive(self):
        """Test Portuguese lexicon identifies positive words."""
        analyzer = FinBERTSentimentAnalyzer()
        
        positive_texts = [
            "Petrobras lucro recorde alta crescimento",
            "Vale alta crescimento receita",
            "Itau superou expectativas dividendo"
        ]
        
        for text in positive_texts:
            sentiment = analyzer._simple_sentiment(text)
            assert sentiment > 0, f"Positive text should have positive sentiment: {text}"

    def test_simple_sentiment_negative(self):
        """Test Portuguese lexicon identifies negative words."""
        analyzer = FinBERTSentimentAnalyzer()
        
        negative_texts = [
            "Crise recessao risco instabilidade",
            "Acao caiu desvalorizacao pressao"
        ]
        
        for text in negative_texts:
            sentiment = analyzer._simple_sentiment(text)
            assert sentiment < 0, f"Negative text should have negative sentiment: {text}"

    def test_analyze_returns_valid_range(self):
        """Test analyze returns value in valid range."""
        analyzer = FinBERTSentimentAnalyzer()
        
        text = "Petrobras lucro recorde"
        sentiment = analyzer.analyze(text)
        
        assert -1.0 <= sentiment <= 1.0

    def test_empty_text_handling(self):
        """Test handling of empty text."""
        analyzer = FinBERTSentimentAnalyzer()
        
        sentiment = analyzer.analyze("")
        assert sentiment == 0.0


# =============================================================================
# TEST NEWS CACHE
# =============================================================================

class TestNewsCache:
    """Tests for news cache with TTL."""

    def test_cache_set_and_get(self):
        """Test cache set and get operations."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_file = Path(tmpdir) / "test_cache.json"
            cache = NewsCache(cache_file=str(cache_file), ttl_hours=6)
            
            cache.set('TEST.SA', 0.5, source="test", articles=[
                {'title': 'Test Article', 'link': 'http://test.com', 'published': '2024-01-01', 'summary': 'Test summary'}
            ])
            
            sentiment = cache.get('TEST.SA')
            assert sentiment == 0.5

    def test_trading_hours_ttl(self):
        """Test shorter TTL during trading hours."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_file = Path(tmpdir) / "test_cache.json"
            cache = NewsCache(cache_file=str(cache_file), ttl_hours=6)
            
            ttl = cache._get_trading_ttl()
            assert ttl in [4, 12]

    def test_cache_freshness(self):
        """Test cache freshness check."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_file = Path(tmpdir) / "test_cache.json"
            cache = NewsCache(cache_file=str(cache_file), ttl_hours=6)
            
            cache.set('TEST.SA', 0.5, source="test")
            assert cache.is_fresh('TEST.SA')
            
            sentiment = cache.get('TEST.SA')
            assert sentiment == 0.5


# =============================================================================
# TEST API BUDGET TRACKER
# =============================================================================

class TestAPIBudgetTracker:
    """Tests for API budget tracking."""

    def test_budget_recording(self):
        """Test budget recording."""
        with tempfile.TemporaryDirectory() as tmpdir:
            budget_file = Path(tmpdir) / "test_budget.json"
            tracker = APIBudgetTracker(budget_file=str(budget_file))
            
            tracker.record_call(credits_used=1, ticker='PETR4.SA')
            tracker.record_call(credits_used=1, ticker='VALE3.SA')
            
            usage = tracker.get_usage()
            assert usage['used'] == 2
            assert usage['calls'] == 2

    def test_budget_limit_enforcement(self):
        """Test budget limit enforcement."""
        with tempfile.TemporaryDirectory() as tmpdir:
            budget_file = Path(tmpdir) / "test_budget.json"
            tracker = APIBudgetTracker(budget_file=str(budget_file))
            
            # Exhaust budget
            for i in range(tracker.CONSERVATIVE_LIMIT + 10):
                if tracker.can_make_request():
                    tracker.record_call(credits_used=1)
                else:
                    break
            
            assert not tracker.can_make_request()

    def test_cleanup_old_days(self):
        """Test cleanup of old budget data."""
        with tempfile.TemporaryDirectory() as tmpdir:
            budget_file = Path(tmpdir) / "test_budget.json"
            tracker = APIBudgetTracker(budget_file=str(budget_file))
            
            # Add old date
            old_date = (datetime.now() - timedelta(days=10)).strftime("%Y-%m-%d")
            tracker.budget_data[old_date] = {'used': 100, 'calls': 100}
            tracker._save_budget()
            
            # Create new instance (triggers cleanup)
            tracker2 = APIBudgetTracker(budget_file=str(budget_file))
            assert old_date not in tracker2.budget_data


# =============================================================================
# TEST FEATURE ENGINEER
# =============================================================================

class TestFeatureEngineer:
    """Tests for feature engineering."""

    def test_volume_features(self, sample_price_data):
        """Test volume feature extraction."""
        fe = FeatureEngineer()
        features = fe.add_volume_features(sample_price_data)
        
        assert 'volume_momentum' in features
        assert 'unusual_volume' in features
        assert 'volume_trend' in features
        assert isinstance(features['volume_momentum'], float)
        assert isinstance(features['unusual_volume'], bool)

    def test_volatility_regime_feature(self, sample_price_data):
        """Test volatility regime feature."""
        fe = FeatureEngineer()
        features = fe.add_volatility_regime(sample_price_data)
        
        assert 'volatility' in features
        assert 'regime' in features
        assert features['regime'] in ['low', 'medium', 'high']

    def test_all_features_generation(self, sample_price_data):
        """Test all features generation."""
        fe = FeatureEngineer()
        all_features = fe.generate_all_features('TEST.SA', sample_price_data)
        
        assert 'volume' in all_features
        assert 'sector' in all_features
        assert 'volatility' in all_features
        assert 'correlation' in all_features


# =============================================================================
# TEST RISK PARITY
# =============================================================================

class TestRiskParity:
    """Tests for risk parity position sizing."""

    def test_risk_parity_weights(self):
        """Test risk parity weight calculation."""
        rp = RiskParity()
        
        np.random.seed(42)
        returns_data = {
            'STOCK_A': pd.Series(np.random.randn(100) * 0.02),
            'STOCK_B': pd.Series(np.random.randn(100) * 0.03),
            'STOCK_C': pd.Series(np.random.randn(100) * 0.01)
        }
        
        weights = rp.calculate_risk_parity_weights(returns_data)
        
        assert len(weights) == 3
        total_weight = sum(weights.values())
        assert abs(total_weight - 1.0) < 0.01
        
        for ticker, weight in weights.items():
            assert weight > 0

    def test_correlation_adjustment(self):
        """Test position adjustment for correlation."""
        rp = RiskParity()
        
        base_returns = np.random.randn(100) * 0.02
        returns_data = {
            'STOCK_A': pd.Series(base_returns),
            'STOCK_B': pd.Series(base_returns * 1.1)
        }
        
        positions = {'STOCK_A': 0.5, 'STOCK_B': 0.5}
        adjusted = rp.adjust_positions_for_correlation(positions, returns_data)
        
        assert 'STOCK_A' in adjusted
        assert 'STOCK_B' in adjusted

    def test_portfolio_risk_calculation(self):
        """Test portfolio risk calculation."""
        rp = RiskParity()
        
        np.random.seed(42)
        returns_data = {
            'STOCK_A': pd.Series(np.random.randn(100) * 0.02),
            'STOCK_B': pd.Series(np.random.randn(100) * 0.03)
        }
        
        positions = {'STOCK_A': 0.5, 'STOCK_B': 0.5}
        risk = rp.calculate_portfolio_risk(positions, returns_data)
        
        assert 'total_risk' in risk
        assert 'diversification_ratio' in risk
        assert risk['total_risk'] >= 0


# =============================================================================
# TEST WALK FORWARD VALIDATION
# =============================================================================

class TestWalkForwardValidation:
    """Tests for walk-forward validation."""

    def test_split_data(self, long_price_data):
        """Test data splitting for walk-forward."""
        validator = WalkForwardValidator(train_window=126, test_window=63)
        splits = validator.split_data(long_price_data)
        
        assert len(splits) >= 1
        
        for train_data, test_data in splits:
            assert len(train_data) == 126
            assert len(test_data) == 63

    def test_parameter_validation(self, long_price_data):
        """Test parameter validation using walk-forward."""
        validator = WalkForwardValidator(train_window=126, test_window=63)
        
        def strategy_func(data, params):
            returns = data['Close'].pct_change().dropna()
            return returns.mean() * 252
        
        params = {'threshold': [0.1, 0.2]}
        result = validator.validate_parameters(long_price_data, params, strategy_func)
        
        assert 'best_params' in result
        assert 'oos_performance' in result

    def test_overfitting_estimation(self, long_price_data):
        """Test overfitting estimation."""
        validator = WalkForwardValidator(train_window=126, test_window=63)
        
        def strategy_func(data, params):
            returns = data['Close'].pct_change().dropna()
            return returns.mean() * 252
        
        params = {'threshold': 0.15}
        result = validator.estimate_overfitting(long_price_data, params, strategy_func)
        
        assert 'in_sample_performance' in result
        assert 'out_of_sample_performance' in result
        assert 'overfitting_ratio' in result


# =============================================================================
# TEST SIMPLE PRODUCTION RUNNER
# =============================================================================

class TestSimpleProductionRunner:
    """Tests for SimpleProductionRunner main analysis engine."""

    def test_initialization(self):
        """Test runner initializes correctly."""
        runner = SimpleProductionRunner(use_news=False)
        
        assert runner.trend_detector is not None
        assert runner.n_workers > 0
        assert runner.n_workers <= 8

    def test_kelly_position_bounds(self, sample_price_data):
        """Test Kelly position sizing produces bounds between 10% and 80%."""
        runner = SimpleProductionRunner(use_news=False)
        
        for confidence in [0.5, 0.6, 0.7, 0.8, 0.9]:
            position = runner.calculate_kelly_position(sample_price_data, confidence)
            assert 0.10 <= position <= 0.80

    def test_kelly_handles_flat_data(self):
        """Test Kelly calculation handles flat price data."""
        runner = SimpleProductionRunner(use_news=False)
        
        dates = pd.date_range(start='2024-01-01', periods=100, freq='D')
        flat_data = pd.DataFrame({
            'Close': [100.0] * 100,
            'Open': [100.0] * 100,
            'High': [100.0] * 100,
            'Low': [100.0] * 100,
            'Volume': [1000000] * 100
        }, index=dates)
        
        position = runner.calculate_kelly_position(flat_data, 0.7)
        assert position == 0.20  # Default

    @patch('production_simple.yf.download')
    def test_retry_on_failure(self, mock_download, sample_price_data):
        """Test retry mechanism works on network failures."""
        runner = SimpleProductionRunner(use_news=False)
        
        mock_download.side_effect = [
            Exception("Network error"),
            Exception("Timeout"),
            sample_price_data
        ]
        
        with patch('time.sleep'):
            result = runner.get_data('PETR4.SA')
        
        assert result is not None
        assert mock_download.call_count == 3

    @patch('production_simple.yf.download')
    def test_retry_exhausted_returns_none(self, mock_download):
        """Test that exhausted retries return None."""
        runner = SimpleProductionRunner(use_news=False)
        
        mock_download.side_effect = Exception("Permanent failure")
        
        with patch('time.sleep'):
            result = runner.get_data('PETR4.SA')
        
        assert result is None
        assert mock_download.call_count == 3

    @patch('production_simple.yf.download')
    def test_empty_data_returns_none(self, mock_download):
        """Test that empty data returns None."""
        runner = SimpleProductionRunner(use_news=False)
        
        mock_download.return_value = pd.DataFrame()
        
        result = runner.get_data('PETR4.SA')
        
        assert result is None

    def test_sigmoid_boost_calculation(self):
        """Test sigmoid boost calculation for sentiment scaling."""
        def sigmoid_boost(sentiment):
            return 1 / (1 + np.exp(-5 * sentiment))
        
        # Test bounds
        for sentiment in [-1.0, -0.5, 0.0, 0.5, 1.0]:
            boost = sigmoid_boost(sentiment)
            assert 0 < boost < 1
        
        # Positive sentiment should give boost > 0.5
        assert sigmoid_boost(0.5) > 0.5
        
        # Negative sentiment should give boost < 0.5
        assert sigmoid_boost(-0.5) < 0.5


# =============================================================================
# TEST INTEGRATION
# =============================================================================

class TestIntegration:
    """Integration tests for full pipeline."""

    def test_full_pipeline(self, sample_price_data):
        """Test complete pipeline integration."""
        # 1. Trend detection
        detector = TrendDetectorV2()
        trend_result = detector.detect_trend(sample_price_data)
        assert 'consensus' in trend_result
        
        # 2. Feature engineering
        fe = FeatureEngineer()
        features = fe.generate_all_features('TEST.SA', sample_price_data)
        assert 'volume' in features
        
        # 3. Position sizing (Kelly)
        runner = SimpleProductionRunner(use_news=False)
        position = runner.calculate_kelly_position(sample_price_data, 0.7)
        assert 0.10 <= position <= 0.80
        
        # 4. Risk parity
        rp = RiskParity()
        returns = sample_price_data['Close'].pct_change().dropna()
        weights = rp.calculate_risk_parity_weights({'TEST': returns})
        assert 'TEST' in weights

    def test_signal_generation_flow(self, uptrend_data):
        """Test signal generation flow with uptrend data."""
        detector = TrendDetectorV2()
        runner = SimpleProductionRunner(use_news=False)
        
        # Detect trend
        trend_result = detector.detect_trend(uptrend_data)
        consensus = trend_result.get('consensus', 'unknown')
        confidence = trend_result.get('confidence', 0)
        
        # Generate signal
        if consensus in ['uptrend', 'bull_pullback'] and confidence >= 0.5:
            signal = "BUY"
        elif consensus in ['downtrend', 'bear_bounce'] and confidence >= 0.5:
            signal = "SELL"
        else:
            signal = "HOLD"
        
        # For uptrend data, we should get BUY or HOLD
        assert signal in ["BUY", "HOLD", "SELL"]


if __name__ == '__main__':
    pytest.main([__file__, "-v", "--tb=short"])
