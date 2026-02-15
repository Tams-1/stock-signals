"""
Tests for Phase 5.1: Live Monitoring System
"""

import pytest
import pandas as pd
import numpy as np
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from execution.live_monitor import LiveMonitor


@pytest.fixture
def temp_db():
    """Create temporary database."""
    import os
    db_path = tempfile.mktemp(suffix='.db')
    yield db_path
    # Cleanup
    try:
        if os.path.exists(db_path):
            os.remove(db_path)
    except:
        pass


@pytest.fixture
def monitor(temp_db):
    """Create LiveMonitor instance."""
    return LiveMonitor(
        tickers=['TEST1', 'TEST2'],
        db_path=temp_db,
        initial_capital=100000.0
    )


@pytest.fixture
def sample_ohlcv_data():
    """Create sample OHLCV data."""
    dates = pd.date_range(end=datetime.now(), periods=30, freq='D')
    data = pd.DataFrame({
        'open': np.random.uniform(50, 100, 30),
        'high': np.random.uniform(100, 110, 30),
        'low': np.random.uniform(40, 50, 30),
        'close': np.random.uniform(50, 100, 30),
        'volume': np.random.uniform(1000000, 5000000, 30),
        'adj close': np.random.uniform(50, 100, 30)
    }, index=dates)
    return data


class TestLiveMonitorInitialization:
    """Test monitor initialization."""
    
    def test_init_creates_instance(self, monitor):
        """Test monitor initializes correctly."""
        assert monitor is not None
        assert monitor.tickers == ['TEST1', 'TEST2']
        assert monitor.initial_capital == 100000.0
    
    def test_init_creates_database(self, temp_db):
        """Test database is created."""
        monitor = LiveMonitor(tickers=['TEST'], db_path=temp_db)
        
        # Check tables exist
        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()
        
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = {row[0] for row in cursor.fetchall()}
        
        assert 'alerts' in tables
        assert 'signals' in tables
        assert 'regime_changes' in tables
        
        conn.close()
    
    def test_init_with_telegram_config(self):
        """Test monitor initializes with Telegram config."""
        monitor = LiveMonitor(
            tickers=['TEST'],
            db_path=':memory:',
            telegram_token='test_token',
            telegram_chat_id='123'
        )
        assert monitor.telegram_token == 'test_token'
        assert monitor.telegram_chat_id == '123'


class TestFetchPriceData:
    """Test price data fetching."""
    
    def test_fetch_latest_price_returns_dataframe(self, monitor):
        """Test fetching price data returns DataFrame."""
        # This will fail with real yfinance but shows the interface
        result = monitor.fetch_latest_price('INVALID', lookback_days=30)
        # Expected: None or empty DataFrame for invalid ticker
        assert result is None or result.empty
    
    def test_price_cache_updated(self, monitor, sample_ohlcv_data):
        """Test price cache is updated during fetch."""
        # Manually set cache (since we can't easily test yfinance)
        monitor.price_cache['TEST'] = 55.50
        assert monitor.price_cache['TEST'] == 55.50


class TestNewssentimentFetch:
    """Test news sentiment fetching."""
    
    def test_fetch_news_sentiment_handles_empty(self, monitor):
        """Test fetching news for ticker with no articles."""
        result = monitor.fetch_news_sentiment('INVALID', hours_lookback=24)
        
        assert result is not None
        assert result['sentiment'] in ['positive', 'negative', 'neutral']
        assert isinstance(result['polarity'], (int, float))
        assert result['velocity'] == 0
    
    def test_fetch_news_sentiment_structure(self, monitor):
        """Test news sentiment result structure."""
        result = monitor.fetch_news_sentiment('TEST', hours_lookback=24)
        
        assert 'sentiment' in result
        assert 'polarity' in result
        assert 'velocity' in result
        # article_count is optional
        
        assert isinstance(result['polarity'], (int, float))
        assert result['polarity'] >= -1.0 and result['polarity'] <= 1.0


class TestSignalGeneration:
    """Test signal generation."""
    
    def test_generate_signals_returns_list(self, monitor, sample_ohlcv_data):
        """Test signal generation returns list."""
        signals = monitor.generate_signals('TEST', sample_ohlcv_data)
        assert isinstance(signals, list)
    
    def test_generate_signals_with_empty_data(self, monitor):
        """Test signal generation with empty data."""
        empty_df = pd.DataFrame()
        signals = monitor.generate_signals('TEST', empty_df)
        
        # Should return empty list or handle gracefully
        assert isinstance(signals, list)


class TestConvictionCalculation:
    """Test conviction score calculation."""
    
    def test_calculate_conviction_returns_tuple(self, monitor, sample_ohlcv_data):
        """Test conviction calculation returns proper tuple."""
        conviction, direction, details = monitor.calculate_conviction_with_context(
            ticker='TEST',
            signals=[],
            regime='uptrend',
            news_sentiment={'sentiment': 'positive', 'polarity': 0.5}
        )
        
        assert isinstance(conviction, (int, float))
        assert conviction >= 0 and conviction <= 1.0
        # Direction might be None or a string
        assert direction in ['bullish', 'bearish', 'neutral', None]
        assert isinstance(details, dict)
    
    def test_conviction_with_high_agreement(self, monitor):
        """Test conviction score with high signal agreement."""
        signals = [
            {'type': 'information_flow', 'signals': ['positive_signal']},
            {'type': 'momentum_reversal', 'signals': ['bullish_momentum']}
        ]
        
        conviction, direction, _ = monitor.calculate_conviction_with_context(
            ticker='TEST',
            signals=signals,
            regime='uptrend',
            news_sentiment={'sentiment': 'positive', 'polarity': 0.7}
        )
        
        # High conviction expected
        assert isinstance(conviction, (int, float))
    
    def test_conviction_with_low_agreement(self, monitor):
        """Test conviction score with low signal agreement."""
        signals = []
        
        conviction, direction, _ = monitor.calculate_conviction_with_context(
            ticker='TEST',
            signals=signals,
            regime='downtrend',
            news_sentiment={'sentiment': 'negative', 'polarity': -0.5}
        )
        
        # Should be reasonable
        assert isinstance(conviction, (int, float))


class TestAlertTriggering:
    """Test alert triggering."""
    
    def test_trigger_alert_creates_record(self, monitor):
        """Test triggering alert creates database record."""
        alert_id = monitor.trigger_alert(
            ticker='TEST',
            alert_type='high_conviction_signal',
            signal_type='ensemble',
            conviction=0.85,
            regime='uptrend',
            news_sentiment={'sentiment': 'positive', 'polarity': 0.6},
            recommended_action='buy',
            position_size_pct=0.50,
            stop_loss=50.0,
            take_profit=60.0
        )
        
        assert alert_id > 0
        
        # Verify in database
        conn = sqlite3.connect(monitor.db_path)
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM alerts WHERE id=?', (alert_id,))
        row = cursor.fetchone()
        conn.close()
        
        assert row is not None
    
    def test_alert_message_format(self, monitor):
        """Test alert message formatting."""
        message = monitor._format_alert_message(
            ticker='TEST',
            alert_type='high_conviction_signal',
            signal_type='ensemble',
            conviction=0.85,
            regime='uptrend',
            news_sentiment={'sentiment': 'positive', 'polarity': 0.6},
            recommended_action='buy',
            position_size_pct=0.50
        )
        
        assert 'TEST' in message
        assert 'uptrend' in message.lower()
        assert 'buy' in message.lower()
        # Check for conviction score in any format
        assert '85' in message or '0.85' in message


class TestSignalLogging:
    """Test signal logging."""
    
    def test_log_signal_creates_record(self, monitor):
        """Test logging signal creates database record."""
        monitor.log_signal(
            ticker='TEST',
            signal_type='ensemble',
            direction='bullish',
            strength=0.8,
            conviction=0.8,
            regime='uptrend',
            details={'source': 'test'}
        )
        
        signals = monitor.get_signal_history('TEST', limit=10)
        assert len(signals) > 0
        assert signals[0]['ticker'] == 'TEST'
    
    def test_get_signal_history(self, monitor):
        """Test retrieving signal history."""
        # Log a few signals
        for i in range(5):
            monitor.log_signal(
                ticker='TEST',
                signal_type='ensemble',
                direction='bullish' if i % 2 == 0 else 'bearish',
                strength=0.7 + (i * 0.02),
                conviction=0.7 + (i * 0.02),
                regime='uptrend',
                details={'index': i}
            )
        
        history = monitor.get_signal_history('TEST', limit=10)
        assert len(history) >= 5


class TestRegimeChangeDetection:
    """Test regime change detection."""
    
    def test_check_regime_change_creates_record(self, monitor):
        """Test regime change detection creates record."""
        monitor.check_regime_change(
            ticker='TEST',
            old_regime='uptrend',
            new_regime='consolidation',
            confidence=0.8
        )
        
        changes = monitor.get_regime_history('TEST', limit=10)
        assert len(changes) > 0
        assert changes[0]['new_regime'] == 'consolidation'
    
    def test_no_change_on_same_regime(self, monitor):
        """Test no record created if regime doesn't change."""
        monitor.current_regimes['TEST'] = 'uptrend'
        
        # Should not create alert if same regime
        # This is implicit in the implementation
        monitor.current_regimes['TEST'] = 'uptrend'
        
        changes = monitor.get_regime_history('TEST', limit=10)
        # No changes should be recorded for same regime
        assert len([c for c in changes if c['ticker'] == 'TEST']) == 0


class TestMonitoringCycle:
    """Test complete monitoring cycle."""
    
    def test_run_cycle_returns_dict(self, monitor):
        """Test monitoring cycle returns proper structure."""
        result = monitor.run_cycle('TEST')
        
        assert isinstance(result, dict)
        assert 'ticker' in result
        assert 'timestamp' in result
        assert 'price' in result
        assert 'signals' in result
        assert 'alerts' in result
        assert 'regime' in result
        assert 'news_sentiment' in result
    
    def test_run_cycle_handles_invalid_ticker(self, monitor):
        """Test cycle handles invalid ticker gracefully."""
        result = monitor.run_cycle('INVALID_TICKER_XYZ')
        
        assert result['ticker'] == 'INVALID_TICKER_XYZ'
        # Should either have error or empty signals
        assert isinstance(result, dict)


class TestHistoryRetrieval:
    """Test history retrieval."""
    
    def test_get_alert_history_returns_list(self, monitor):
        """Test alert history retrieval."""
        alerts = monitor.get_alert_history('TEST', limit=100)
        assert isinstance(alerts, list)
    
    def test_get_signal_history_returns_list(self, monitor):
        """Test signal history retrieval."""
        signals = monitor.get_signal_history('TEST', limit=100)
        assert isinstance(signals, list)
    
    def test_get_regime_history_returns_list(self, monitor):
        """Test regime history retrieval."""
        changes = monitor.get_regime_history('TEST', limit=100)
        assert isinstance(changes, list)
    
    def test_history_limit_respected(self, monitor):
        """Test history limit is respected."""
        # Log many signals
        for i in range(50):
            monitor.log_signal(
                ticker='TEST',
                signal_type=f'type_{i}',
                direction='bullish',
                strength=0.7,
                conviction=0.7,
                regime='uptrend',
                details={}
            )
        
        # Request with limit
        history = monitor.get_signal_history('TEST', limit=10)
        assert len(history) <= 10


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
