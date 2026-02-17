"""
Comprehensive tests for APIBudgetTracker - rate limiting and budget enforcement.

Tests cover:
- Budget recording and tracking
- Limit enforcement
- Daily reset
- Persistence
- Usage statistics
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock
import tempfile
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))
from src.news.api_budget_tracker import APIBudgetTracker, get_budget_tracker


class TestAPIBudgetCore:
    """Core budget tracking tests."""
    
    @pytest.fixture
    def tracker(self):
        """Create tracker with temporary file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            budget_file = Path(tmpdir) / "test_budget.json"
            yield APIBudgetTracker(budget_file=str(budget_file))
    
    def test_initial_usage_zero(self, tracker):
        """Test that initial usage is zero."""
        usage = tracker.get_usage()
        
        assert usage['used'] == 0
        assert usage['calls'] == 0
        assert usage['remaining'] == tracker.CONSERVATIVE_LIMIT
    
    def test_record_single_call(self, tracker):
        """Test recording a single API call."""
        tracker.record_call(credits_used=1, ticker='PETR4.SA')
        
        usage = tracker.get_usage()
        assert usage['used'] == 1
        assert usage['calls'] == 1
    
    def test_record_multiple_calls(self, tracker):
        """Test recording multiple API calls."""
        for i in range(5):
            tracker.record_call(credits_used=1, ticker=f'STOCK{i}.SA')
        
        usage = tracker.get_usage()
        assert usage['used'] == 5
        assert usage['calls'] == 5
    
    def test_record_different_credits(self, tracker):
        """Test recording calls with different credit amounts."""
        tracker.record_call(credits_used=2, ticker='TEST1.SA')
        tracker.record_call(credits_used=3, ticker='TEST2.SA')
        
        usage = tracker.get_usage()
        assert usage['used'] == 5
        assert usage['calls'] == 2


class TestBudgetEnforcement:
    """Tests for budget limit enforcement."""
    
    @pytest.fixture
    def tracker(self):
        """Create tracker with temporary file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            budget_file = Path(tmpdir) / "test_budget.json"
            yield APIBudgetTracker(budget_file=str(budget_file))
    
    def test_can_make_request_when_under_limit(self, tracker):
        """Test that requests are allowed under limit."""
        # Record 100 calls (under 150 limit)
        for i in range(100):
            tracker.record_call(credits_used=1)
        
        assert tracker.can_make_request(), "Should allow request under limit"
    
    def test_cannot_make_request_at_limit(self, tracker):
        """Test that requests are blocked at limit."""
        # Exhaust budget
        for i in range(tracker.CONSERVATIVE_LIMIT):
            tracker.record_call(credits_used=1)
        
        assert not tracker.can_make_request(), "Should block request at limit"
    
    def test_can_make_request_checks_credits_needed(self, tracker):
        """Test that can_make_request considers credits needed."""
        # Use 148 credits
        for i in range(148):
            tracker.record_call(credits_used=1)
        
        # Should allow 1 credit request
        assert tracker.can_make_request(credits_needed=1)
        
        # Should not allow 5 credit request
        assert not tracker.can_make_request(credits_needed=5)
    
    def test_conservative_limit_vs_daily_limit(self, tracker):
        """Test that conservative limit is used, not daily limit."""
        # CONSERVATIVE_LIMIT should be less than DAILY_LIMIT
        assert tracker.CONSERVATIVE_LIMIT < tracker.DAILY_LIMIT
        assert tracker.CONSERVATIVE_LIMIT == 150
        assert tracker.DAILY_LIMIT == 200


class TestDailyReset:
    """Tests for daily budget reset."""
    
    def test_reset_creates_new_day_entry(self):
        """Test that reset creates entry for new day."""
        with tempfile.TemporaryDirectory() as tmpdir:
            budget_file = Path(tmpdir) / "test_budget.json"
            tracker = APIBudgetTracker(budget_file=str(budget_file))
            
            # Record some calls
            tracker.record_call(credits_used=1)
            
            # Reset (simulates new day)
            tracker.reset_daily_budget()
            
            usage = tracker.get_usage()
            assert usage['used'] == 0
    
    def test_different_day_starts_fresh(self):
        """Test that different day starts with fresh budget."""
        with tempfile.TemporaryDirectory() as tmpdir:
            budget_file = Path(tmpdir) / "test_budget.json"
            
            # Create tracker with today's date
            tracker1 = APIBudgetTracker(budget_file=str(budget_file))
            tracker1.record_call(credits_used=50)
            
            # Manually change date to simulate new day
            yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
            today = datetime.now().strftime("%Y-%m-%d")
            
            # Modify budget data to have yesterday's usage
            tracker1.budget_data[yesterday] = {'used': 100, 'calls': 100}
            tracker1._save_budget()
            
            # Create new tracker (simulates next day)
            tracker2 = APIBudgetTracker(budget_file=str(budget_file))
            
            usage = tracker2.get_usage()
            assert usage['used'] == 50, "Should only have today's usage"


class TestBudgetPersistence:
    """Tests for budget persistence to disk."""
    
    def test_budget_saves_to_disk(self):
        """Test that budget saves to disk."""
        with tempfile.TemporaryDirectory() as tmpdir:
            budget_file = Path(tmpdir) / "test_budget.json"
            tracker = APIBudgetTracker(budget_file=str(budget_file))
            
            tracker.record_call(credits_used=1, ticker='TEST.SA')
            
            # Verify file exists
            assert budget_file.exists()
            
            # Verify content
            with open(budget_file, 'r') as f:
                data = json.load(f)
            
            today = datetime.now().strftime("%Y-%m-%d")
            assert today in data
            assert data[today]['used'] == 1
    
    def test_budget_loads_from_disk(self):
        """Test that budget loads existing data from disk."""
        with tempfile.TemporaryDirectory() as tmpdir:
            budget_file = Path(tmpdir) / "test_budget.json"
            
            # Create initial tracker with data
            tracker1 = APIBudgetTracker(budget_file=str(budget_file))
            tracker1.record_call(credits_used=25, ticker='TEST.SA')
            
            # Create new tracker (should load from disk)
            tracker2 = APIBudgetTracker(budget_file=str(budget_file))
            
            usage = tracker2.get_usage()
            assert usage['used'] == 25
    
    def test_cleanup_removes_old_entries(self):
        """Test that old entries (> 7 days) are cleaned up."""
        with tempfile.TemporaryDirectory() as tmpdir:
            budget_file = Path(tmpdir) / "test_budget.json"
            
            # Create tracker
            tracker = APIBudgetTracker(budget_file=str(budget_file))
            
            # Add old entry
            old_date = (datetime.now() - timedelta(days=10)).strftime("%Y-%m-%d")
            tracker.budget_data[old_date] = {'used': 100, 'calls': 100}
            tracker._save_budget()
            
            # Create new tracker (should cleanup)
            tracker2 = APIBudgetTracker(budget_file=str(budget_file))
            
            assert old_date not in tracker2.budget_data


class TestUsageStatistics:
    """Tests for usage statistics."""
    
    @pytest.fixture
    def tracker(self):
        """Create tracker with temporary file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            budget_file = Path(tmpdir) / "test_budget.json"
            yield APIBudgetTracker(budget_file=str(budget_file))
    
    def test_get_usage_returns_dict(self, tracker):
        """Test that get_usage returns proper dict."""
        usage = tracker.get_usage()
        
        assert 'date' in usage
        assert 'used' in usage
        assert 'calls' in usage
        assert 'remaining' in usage
        assert 'percent_used' in usage
    
    def test_percent_used_calculation(self, tracker):
        """Test percent used calculation."""
        tracker.record_call(credits_used=75)
        
        usage = tracker.get_usage()
        expected_percent = 75 / tracker.CONSERVATIVE_LIMIT * 100
        
        assert abs(usage['percent_used'] - expected_percent) < 0.1
    
    def test_remaining_calculation(self, tracker):
        """Test remaining credits calculation."""
        tracker.record_call(credits_used=50)
        
        usage = tracker.get_usage()
        expected_remaining = tracker.CONSERVATIVE_LIMIT - 50
        
        assert usage['remaining'] == expected_remaining


class TestGlobalTracker:
    """Tests for global tracker singleton."""
    
    def test_get_budget_tracker_returns_instance(self):
        """Test that get_budget_tracker returns APIBudgetTracker."""
        from src.news.api_budget_tracker import _budget_tracker
        
        # Reset global tracker
        import src.news.api_budget_tracker as module
        module._budget_tracker = None
        
        tracker = get_budget_tracker()
        
        assert isinstance(tracker, APIBudgetTracker)
    
    def test_get_budget_tracker_returns_same_instance(self):
        """Test that get_budget_tracker returns same instance (singleton)."""
        import src.news.api_budget_tracker as module
        module._budget_tracker = None
        
        tracker1 = get_budget_tracker()
        tracker2 = get_budget_tracker()
        
        assert tracker1 is tracker2


class TestEdgeCases:
    """Tests for edge cases and error handling."""
    
    def test_handles_corrupted_file(self):
        """Test handling of corrupted JSON file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            budget_file = Path(tmpdir) / "test_budget.json"
            
            # Write corrupted JSON
            with open(budget_file, 'w') as f:
                f.write("{ corrupted")
            
            # Should not crash
            tracker = APIBudgetTracker(budget_file=str(budget_file))
            
            assert tracker.budget_data == {}
    
    def test_record_call_zero_credits(self):
        """Test recording call with zero credits."""
        with tempfile.TemporaryDirectory() as tmpdir:
            budget_file = Path(tmpdir) / "test_budget.json"
            tracker = APIBudgetTracker(budget_file=str(budget_file))
            
            tracker.record_call(credits_used=0)
            
            usage = tracker.get_usage()
            assert usage['used'] == 0
            assert usage['calls'] == 1
    
    def test_can_make_request_at_exact_limit(self):
        """Test behavior at exactly the limit."""
        with tempfile.TemporaryDirectory() as tmpdir:
            budget_file = Path(tmpdir) / "test_budget.json"
            tracker = APIBudgetTracker(budget_file=str(budget_file))
            
            # Use all but 1 credit
            for i in range(tracker.CONSERVATIVE_LIMIT - 1):
                tracker.record_call(credits_used=1)
            
            # Should allow 1 more
            assert tracker.can_make_request(credits_needed=1)
            
            # Use the last credit
            tracker.record_call(credits_used=1)
            
            # Should now block
            assert not tracker.can_make_request(credits_needed=1)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
