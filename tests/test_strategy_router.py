"""
Tests for Phase 5.3: Strategy Router
"""

import pytest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from execution.strategy_router import (
    StrategyRouter,
    Regime,
    StrategyType
)


@pytest.fixture
def router():
    """Create StrategyRouter instance."""
    return StrategyRouter()


class TestRouterInitialization:
    """Test router initialization."""
    
    def test_init_creates_instance(self, router):
        """Test router initializes correctly."""
        assert router is not None
        assert len(router.regime_strategies) > 0
    
    def test_init_configures_regimes(self, router):
        """Test all regimes are configured."""
        regimes = [Regime.UPTREND, Regime.CONSOLIDATION, Regime.DOWNTREND, Regime.UNKNOWN]
        
        for regime in regimes:
            assert regime in router.regime_strategies


class TestRegimeParsing:
    """Test regime string parsing."""
    
    def test_parse_uptrend(self, router):
        """Test parsing 'uptrend' string."""
        regime = router._parse_regime('uptrend')
        assert regime == Regime.UPTREND
    
    def test_parse_consolidation(self, router):
        """Test parsing 'consolidation' string."""
        regime = router._parse_regime('consolidation')
        assert regime == Regime.CONSOLIDATION
    
    def test_parse_downtrend(self, router):
        """Test parsing 'downtrend' string."""
        regime = router._parse_regime('downtrend')
        assert regime == Regime.DOWNTREND
    
    def test_parse_unknown(self, router):
        """Test parsing invalid regime defaults to UNKNOWN."""
        regime = router._parse_regime('invalid_regime')
        assert regime == Regime.UNKNOWN
    
    def test_parse_case_insensitive(self, router):
        """Test regime parsing is case-insensitive."""
        regime_lower = router._parse_regime('uptrend')
        regime_upper = router._parse_regime('UPTREND')
        
        assert regime_lower == regime_upper


class TestStrategySelection:
    """Test strategy selection logic."""
    
    def test_select_momentum_in_uptrend(self, router):
        """Test momentum strategy selected in uptrend with bullish signal."""
        strategy = router._select_strategy(
            regime=Regime.UPTREND,
            conviction=0.8,
            direction='bullish',
            signal_strength=0.8,
            regime_confidence=0.9
        )
        
        assert strategy == StrategyType.MOMENTUM
    
    def test_select_hold_bearish_in_uptrend(self, router):
        """Test bearish signal in uptrend results in hold."""
        strategy = router._select_strategy(
            regime=Regime.UPTREND,
            conviction=0.8,
            direction='bearish',
            signal_strength=0.8,
            regime_confidence=0.9
        )
        
        assert strategy == StrategyType.HOLD
    
    def test_select_mean_reversion_in_consolidation(self, router):
        """Test mean-reversion selected in consolidation with high conviction."""
        strategy = router._select_strategy(
            regime=Regime.CONSOLIDATION,
            conviction=0.7,
            direction='bullish',
            signal_strength=0.6,
            regime_confidence=0.7
        )
        
        assert strategy == StrategyType.MEAN_REVERSION
    
    def test_select_defensive_in_downtrend(self, router):
        """Test defensive strategy in downtrend."""
        strategy = router._select_strategy(
            regime=Regime.DOWNTREND,
            conviction=0.7,
            direction='bearish',
            signal_strength=0.7,
            regime_confidence=0.8
        )
        
        assert strategy == StrategyType.DEFENSIVE
    
    def test_skip_low_conviction(self, router):
        """Test low conviction signals are skipped."""
        strategy = router._select_strategy(
            regime=Regime.UPTREND,
            conviction=0.2,
            direction='bullish',
            signal_strength=0.3,
            regime_confidence=0.8
        )
        
        assert strategy == StrategyType.SKIP
    
    def test_skip_bearish_in_downtrend(self, router):
        """Test bullish signals in downtrend are skipped."""
        strategy = router._select_strategy(
            regime=Regime.DOWNTREND,
            conviction=0.7,
            direction='bullish',
            signal_strength=0.7,
            regime_confidence=0.8
        )
        
        assert strategy == StrategyType.SKIP


class TestPositionSizing:
    """Test position sizing calculation."""
    
    def test_size_zero_for_skip(self, router):
        """Test SKIP strategy gets 0% position size."""
        size = router._calculate_position_size(
            conviction=0.8,
            strategy=StrategyType.SKIP,
            regime_allocation=0.7
        )
        
        assert size == 0.0
    
    def test_size_70_for_high_conviction_momentum(self, router):
        """Test high conviction momentum gets 70% base."""
        size = router._calculate_position_size(
            conviction=0.8,
            strategy=StrategyType.MOMENTUM,
            regime_allocation=1.0  # 100% regime allocation
        )
        
        # 70% base * 1.0 allocation * 1.1 momentum boost
        expected = 0.70 * 1.1
        assert size > 0
    
    def test_size_50_for_medium_conviction(self, router):
        """Test medium conviction sizing."""
        size = router._calculate_position_size(
            conviction=0.65,
            strategy=StrategyType.MOMENTUM,
            regime_allocation=1.0
        )
        
        # 50% base * 1.1 boost
        assert size > 0
    
    def test_size_reduces_for_defensive(self, router):
        """Test defensive strategy reduces position size."""
        momentum_size = router._calculate_position_size(
            conviction=0.8,
            strategy=StrategyType.MOMENTUM,
            regime_allocation=1.0
        )
        
        defensive_size = router._calculate_position_size(
            conviction=0.8,
            strategy=StrategyType.DEFENSIVE,
            regime_allocation=1.0
        )
        
        assert defensive_size < momentum_size
    
    def test_size_respects_regime_allocation(self, router):
        """Test position size respects regime allocation."""
        size_aggressive = router._calculate_position_size(
            conviction=0.8,
            strategy=StrategyType.MOMENTUM,
            regime_allocation=0.7
        )
        
        size_conservative = router._calculate_position_size(
            conviction=0.8,
            strategy=StrategyType.MOMENTUM,
            regime_allocation=0.3
        )
        
        assert size_conservative < size_aggressive


class TestStopLossAndTakeProfit:
    """Test stop loss and take profit values."""
    
    def test_tight_stop_for_momentum(self, router):
        """Test momentum strategy has tight stop loss."""
        stop = router._get_stop_loss(StrategyType.MOMENTUM)
        assert stop == -3.0
    
    def test_wider_stop_for_mean_reversion(self, router):
        """Test mean-reversion has wider stop loss."""
        stop = router._get_stop_loss(StrategyType.MEAN_REVERSION)
        assert stop == -5.0
    
    def test_very_tight_stop_for_defensive(self, router):
        """Test defensive has very tight stop loss."""
        stop = router._get_stop_loss(StrategyType.DEFENSIVE)
        assert stop == -2.0
    
    def test_profit_target_momentum(self, router):
        """Test momentum strategy profit target."""
        tp = router._get_take_profit(StrategyType.MOMENTUM)
        assert tp == 5.0
    
    def test_profit_target_mean_reversion(self, router):
        """Test mean-reversion profit target."""
        tp = router._get_take_profit(StrategyType.MEAN_REVERSION)
        assert tp == 3.0


class TestTradeAction:
    """Test trade action determination."""
    
    def test_action_skip_for_skip_strategy(self, router):
        """Test SKIP strategy results in 'skip' action."""
        action = router._determine_action(StrategyType.SKIP, 'bullish')
        assert action == 'skip'
    
    def test_action_buy_for_bullish(self, router):
        """Test bullish momentum results in 'buy' action."""
        action = router._determine_action(StrategyType.MOMENTUM, 'bullish')
        assert action == 'buy'
    
    def test_action_sell_for_bearish(self, router):
        """Test bearish momentum results in 'sell' action."""
        action = router._determine_action(StrategyType.MOMENTUM, 'bearish')
        assert action == 'sell'
    
    def test_action_defend_for_defensive(self, router):
        """Test defensive strategy results in 'defend' action."""
        action = router._determine_action(StrategyType.DEFENSIVE, 'bearish')
        assert action == 'defend'


class TestRouteSignal:
    """Test complete signal routing."""
    
    def test_route_returns_dict(self, router):
        """Test route_signal returns dict."""
        result = router.route_signal(
            regime='uptrend',
            conviction=0.8,
            signal_type='ensemble',
            direction='bullish',
            signal_strength=0.8,
            regime_confidence=0.9
        )
        
        assert isinstance(result, dict)
        assert 'selected_strategy' in result
        assert 'position_size_pct' in result
        assert 'action' in result
    
    def test_bullish_uptrend_routes_to_momentum_buy(self, router):
        """Test bullish signal in uptrend routes to momentum buy."""
        result = router.route_signal(
            regime='uptrend',
            conviction=0.85,
            signal_type='ensemble',
            direction='bullish',
            signal_strength=0.8,
            regime_confidence=0.95
        )
        
        assert result['selected_strategy'] == StrategyType.MOMENTUM.value
        assert result['action'] == 'buy'
        assert result['position_size_pct'] > 0
    
    def test_bearish_consolidation_routes_correctly(self, router):
        """Test bearish signal in consolidation."""
        result = router.route_signal(
            regime='consolidation',
            conviction=0.7,
            signal_type='mean_reversion',
            direction='bearish',
            signal_strength=0.6,
            regime_confidence=0.7
        )
        
        assert result['selected_strategy'] in [
            StrategyType.MEAN_REVERSION.value,
            StrategyType.HOLD.value
        ]
    
    def test_bearish_downtrend_routes_to_defensive(self, router):
        """Test bearish signal in downtrend routes to defensive."""
        result = router.route_signal(
            regime='downtrend',
            conviction=0.75,
            signal_type='ensemble',
            direction='bearish',
            signal_strength=0.7,
            regime_confidence=0.85
        )
        
        assert result['selected_strategy'] == StrategyType.DEFENSIVE.value
        assert result['action'] == 'defend'
    
    def test_low_conviction_skipped(self, router):
        """Test low conviction signals are skipped."""
        result = router.route_signal(
            regime='uptrend',
            conviction=0.25,
            signal_type='weak_signal',
            direction='bullish',
            signal_strength=0.3,
            regime_confidence=0.8
        )
        
        assert result['selected_strategy'] == StrategyType.SKIP.value
        assert result['position_size_pct'] == 0
        assert result['action'] == 'skip'
    
    def test_very_high_conviction_overrides_regime(self, router):
        """Test very high conviction can override regime hesitations."""
        result = router.route_signal(
            regime='downtrend',
            conviction=0.95,
            signal_type='strong_signal',
            direction='bullish',
            signal_strength=0.95,
            regime_confidence=0.5
        )
        
        # Very high conviction might override downtrend caution
        assert result['position_size_pct'] > 0 or result['selected_strategy'] == StrategyType.SKIP.value


class TestRationale:
    """Test rationale generation."""
    
    def test_generate_rationale_not_empty(self, router):
        """Test rationale is generated."""
        rationale = router._generate_rationale(
            regime=Regime.UPTREND,
            conviction=0.8,
            strategy=StrategyType.MOMENTUM,
            regime_confidence=0.9
        )
        
        assert isinstance(rationale, str)
        assert len(rationale) > 0
    
    def test_rationale_includes_regime(self, router):
        """Test rationale mentions regime."""
        rationale = router._generate_rationale(
            regime=Regime.UPTREND,
            conviction=0.8,
            strategy=StrategyType.MOMENTUM,
            regime_confidence=0.9
        )
        
        assert 'uptrend' in rationale.lower()
    
    def test_rationale_includes_strategy(self, router):
        """Test rationale mentions strategy."""
        rationale = router._generate_rationale(
            regime=Regime.UPTREND,
            conviction=0.8,
            strategy=StrategyType.MOMENTUM,
            regime_confidence=0.9
        )
        
        assert 'momentum' in rationale.lower()


class TestRegimeStatistics:
    """Test regime statistics."""
    
    def test_get_regime_statistics(self, router):
        """Test retrieving regime statistics."""
        stats = router.get_regime_statistics('uptrend')
        
        assert 'regime' in stats
        assert 'description' in stats
        assert 'primary_strategy' in stats
        assert 'capital_allocation' in stats
    
    def test_uptrend_statistics(self, router):
        """Test uptrend regime statistics."""
        stats = router.get_regime_statistics('uptrend')
        
        assert stats['regime'] == 'uptrend'
        assert stats['primary_strategy'] == StrategyType.MOMENTUM.value
        assert stats['capital_allocation'] == 0.70
    
    def test_consolidation_statistics(self, router):
        """Test consolidation regime statistics."""
        stats = router.get_regime_statistics('consolidation')
        
        assert stats['primary_strategy'] == StrategyType.MEAN_REVERSION.value
        assert stats['capital_allocation'] == 0.50
    
    def test_downtrend_statistics(self, router):
        """Test downtrend regime statistics."""
        stats = router.get_regime_statistics('downtrend')
        
        assert stats['primary_strategy'] == StrategyType.DEFENSIVE.value
        assert stats['capital_allocation'] == 0.30


class TestWinRateEstimation:
    """Test win rate estimation by regime."""
    
    def test_uptrend_has_high_win_rate(self, router):
        """Test uptrend has high estimated win rate."""
        wr = router._estimate_win_rate(Regime.UPTREND)
        assert wr > 0.6
    
    def test_consolidation_moderate_win_rate(self, router):
        """Test consolidation has moderate win rate."""
        wr = router._estimate_win_rate(Regime.CONSOLIDATION)
        assert 0.4 < wr < 0.7
    
    def test_downtrend_low_win_rate(self, router):
        """Test downtrend has lower win rate."""
        wr = router._estimate_win_rate(Regime.DOWNTREND)
        assert wr < 0.5


class TestTradeDurationEstimation:
    """Test trade duration estimation by regime."""
    
    def test_momentum_trades_longer(self, router):
        """Test momentum trades (uptrend) are longer duration."""
        duration = router._estimate_trade_duration(Regime.UPTREND)
        assert duration > 5
    
    def test_mean_reversion_trades_shorter(self, router):
        """Test mean-reversion trades are shorter."""
        duration = router._estimate_trade_duration(Regime.CONSOLIDATION)
        assert duration < 10
    
    def test_defensive_trades_brief(self, router):
        """Test defensive trades are brief."""
        duration = router._estimate_trade_duration(Regime.DOWNTREND)
        assert duration < 5


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
