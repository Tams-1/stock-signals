"""
Phase 5.3: Strategy Router

Routes signals to appropriate strategy based on market regime:
- Uptrend → Momentum strategy
- Consolidation → Mean-reversion strategy
- Downtrend → Defensive strategy (or shorts if allowed)
"""

import logging
from typing import Dict, Optional, Tuple
from enum import Enum

logger = logging.getLogger(__name__)


class Regime(Enum):
    """Market regime classification."""
    UPTREND = 'uptrend'
    DOWNTREND = 'downtrend'
    CONSOLIDATION = 'consolidation'
    UNKNOWN = 'unknown'


class StrategyType(Enum):
    """Strategy types to route to."""
    MOMENTUM = 'momentum'
    MEAN_REVERSION = 'mean_reversion'
    DEFENSIVE = 'defensive'
    HOLD = 'hold'
    SKIP = 'skip'


class StrategyRouter:
    """Route signals to appropriate strategy based on regime and conviction."""
    
    def __init__(self):
        """Initialize strategy router."""
        self.regime_strategies = {
            Regime.UPTREND: {
                'primary_strategy': StrategyType.MOMENTUM,
                'secondary_strategy': StrategyType.MEAN_REVERSION,
                'allocation': 0.70,
                'description': 'Bullish momentum focus: Follow trends, breakouts'
            },
            Regime.CONSOLIDATION: {
                'primary_strategy': StrategyType.MEAN_REVERSION,
                'secondary_strategy': StrategyType.HOLD,
                'allocation': 0.50,
                'description': 'Balanced approach: Mean reversion on range extremes'
            },
            Regime.DOWNTREND: {
                'primary_strategy': StrategyType.DEFENSIVE,
                'secondary_strategy': StrategyType.SKIP,
                'allocation': 0.30,
                'description': 'Defensive stance: Avoid longs, watch for bounces'
            },
            Regime.UNKNOWN: {
                'primary_strategy': StrategyType.HOLD,
                'secondary_strategy': StrategyType.SKIP,
                'allocation': 0.10,
                'description': 'Unknown regime: Skip trading until clarity'
            }
        }
        
        logger.info("StrategyRouter initialized")
    
    def route_signal(
        self,
        regime: str,
        conviction: float,
        signal_type: str,
        direction: str,
        signal_strength: float,
        regime_confidence: float = 0.5
    ) -> Dict:
        """
        Route a signal to the appropriate strategy.
        
        Args:
            regime: Market regime (uptrend/downtrend/consolidation)
            conviction: Conviction score (0-1.0)
            signal_type: Type of signal (ensemble, momentum, etc.)
            direction: Signal direction (bullish/bearish/neutral)
            signal_strength: Strength of signal (0-1.0)
            regime_confidence: Confidence in regime classification (0-1.0)
            
        Returns:
            Dict with routing decision and strategy parameters
        """
        try:
            # Convert regime string to Enum
            regime_enum = self._parse_regime(regime)
            
            # Get regime strategy mapping
            regime_config = self.regime_strategies.get(
                regime_enum,
                self.regime_strategies[Regime.UNKNOWN]
            )
            
            # Determine strategy based on signal and regime
            strategy = self._select_strategy(
                regime_enum,
                conviction,
                direction,
                signal_strength,
                regime_confidence
            )
            
            # Calculate position sizing
            position_size = self._calculate_position_size(
                conviction,
                strategy,
                regime_config['allocation']
            )
            
            # Generate routing decision
            decision = {
                'regime': regime,
                'regime_confidence': regime_confidence,
                'signal_type': signal_type,
                'signal_direction': direction,
                'signal_strength': signal_strength,
                'conviction': conviction,
                'selected_strategy': strategy.value,
                'position_size_pct': position_size,
                'stop_loss_pct': self._get_stop_loss(strategy),
                'take_profit_pct': self._get_take_profit(strategy),
                'rationale': self._generate_rationale(
                    regime_enum,
                    conviction,
                    strategy,
                    regime_confidence
                ),
                'action': self._determine_action(strategy, direction)
            }
            
            logger.info(f"Routed signal: {signal_type} → {strategy.value} "
                       f"(conviction: {conviction:.2f}, regime: {regime})")
            
            return decision
        except Exception as e:
            logger.error(f"Error routing signal: {e}")
            return {
                'regime': regime,
                'selected_strategy': StrategyType.SKIP.value,
                'position_size_pct': 0,
                'action': 'skip',
                'error': str(e)
            }
    
    def _parse_regime(self, regime_str: str) -> Regime:
        """Convert regime string to Enum."""
        regime_lower = regime_str.lower() if regime_str else 'unknown'
        
        for regime_enum in Regime:
            if regime_enum.value == regime_lower:
                return regime_enum
        
        return Regime.UNKNOWN
    
    def _select_strategy(
        self,
        regime: Regime,
        conviction: float,
        direction: str,
        signal_strength: float,
        regime_confidence: float
    ) -> StrategyType:
        """Select strategy based on regime and signal characteristics."""
        
        # Skip if low conviction
        if conviction < 0.3:
            return StrategyType.SKIP
        
        # Skip if weak regime confidence
        if regime_confidence < 0.4 and conviction < 0.6:
            return StrategyType.SKIP
        
        # Uptrend regime
        if regime == Regime.UPTREND:
            # Bullish signals: use momentum
            if direction == 'bullish' and conviction >= 0.5:
                return StrategyType.MOMENTUM
            # Bearish signals in uptrend: be careful, hold
            elif direction == 'bearish':
                return StrategyType.HOLD
            else:
                return StrategyType.HOLD
        
        # Consolidation regime
        elif regime == Regime.CONSOLIDATION:
            # High conviction signals: use mean reversion
            if conviction >= 0.6:
                return StrategyType.MEAN_REVERSION
            # Watch for breakouts
            elif signal_strength > 0.7 and direction in ['bullish', 'bearish']:
                return StrategyType.MOMENTUM  # Breakout play
            else:
                return StrategyType.HOLD
        
        # Downtrend regime
        elif regime == Regime.DOWNTREND:
            # Bearish signals: defensive
            if direction == 'bearish':
                return StrategyType.DEFENSIVE
            # Bullish signals in downtrend: risky, skip
            elif direction == 'bullish':
                return StrategyType.SKIP
            else:
                return StrategyType.DEFENSIVE
        
        # Unknown regime
        else:
            if conviction >= 0.75:
                # Very high conviction: trade anyway
                return (StrategyType.MOMENTUM if direction == 'bullish'
                       else StrategyType.DEFENSIVE if direction == 'bearish'
                       else StrategyType.HOLD)
            else:
                return StrategyType.HOLD
    
    def _calculate_position_size(
        self,
        conviction: float,
        strategy: StrategyType,
        regime_allocation: float
    ) -> float:
        """Calculate position size based on conviction and strategy."""
        
        # Base sizing by conviction
        if conviction >= 0.8:
            conviction_size = 0.70
        elif conviction >= 0.6:
            conviction_size = 0.50
        elif conviction >= 0.4:
            conviction_size = 0.25
        else:
            conviction_size = 0.0
        
        # Adjust by regime allocation
        regime_adjusted = conviction_size * regime_allocation
        
        # Strategy adjustments
        if strategy == StrategyType.SKIP:
            return 0.0
        elif strategy == StrategyType.HOLD:
            return 0.0
        elif strategy == StrategyType.MOMENTUM:
            return regime_adjusted * 1.1  # 10% boost for momentum
        elif strategy == StrategyType.MEAN_REVERSION:
            return regime_adjusted * 0.9  # 10% reduction for mean reversion
        elif strategy == StrategyType.DEFENSIVE:
            return min(regime_adjusted * 0.7, 0.30)  # Cap at 30% in defensive
        
        return regime_adjusted
    
    def _get_stop_loss(self, strategy: StrategyType) -> float:
        """Get stop loss percentage for strategy."""
        if strategy == StrategyType.MOMENTUM:
            return -3.0  # Tight stops for momentum
        elif strategy == StrategyType.MEAN_REVERSION:
            return -5.0  # Wider stops for mean reversion
        elif strategy == StrategyType.DEFENSIVE:
            return -2.0  # Very tight for defensive
        else:
            return -0.0  # No stop for hold/skip
    
    def _get_take_profit(self, strategy: StrategyType) -> float:
        """Get take profit percentage for strategy."""
        if strategy == StrategyType.MOMENTUM:
            return 5.0  # Quick profit targets for momentum
        elif strategy == StrategyType.MEAN_REVERSION:
            return 3.0  # Smaller targets for mean reversion
        elif strategy == StrategyType.DEFENSIVE:
            return 1.5  # Micro targets for defensive
        else:
            return 0.0  # No target for hold/skip
    
    def _determine_action(self, strategy: StrategyType, direction: str) -> str:
        """Determine trading action."""
        
        if strategy == StrategyType.SKIP:
            return 'skip'
        elif strategy == StrategyType.HOLD:
            return 'hold'
        elif strategy == StrategyType.DEFENSIVE:
            return 'defend'  # Reduce exposure, tighten stops
        
        # For momentum/mean-reversion
        if direction == 'bullish':
            return 'buy'
        elif direction == 'bearish':
            return 'sell'
        else:
            return 'hold'
    
    def _generate_rationale(
        self,
        regime: Regime,
        conviction: float,
        strategy: StrategyType,
        regime_confidence: float
    ) -> str:
        """Generate human-readable rationale for routing decision."""
        
        parts = []
        
        # Regime context
        regime_config = self.regime_strategies[regime]
        parts.append(f"Regime: {regime.value} ({regime_confidence:.0%} confidence)")
        parts.append(f"Primary strategy: {regime_config['primary_strategy'].value}")
        
        # Conviction context
        if conviction >= 0.8:
            conviction_text = "Very high conviction"
        elif conviction >= 0.6:
            conviction_text = "High conviction"
        elif conviction >= 0.4:
            conviction_text = "Medium conviction"
        else:
            conviction_text = "Low conviction"
        
        parts.append(f"Signal strength: {conviction_text} ({conviction:.2f})")
        
        # Strategy selection
        if strategy == StrategyType.SKIP:
            parts.append("Action: SKIP - signal conflicts with regime or conviction too low")
        elif strategy == StrategyType.HOLD:
            parts.append("Action: HOLD - wait for clearer signals")
        elif strategy == StrategyType.MOMENTUM:
            parts.append("Action: MOMENTUM - follow the trend")
        elif strategy == StrategyType.MEAN_REVERSION:
            parts.append("Action: MEAN-REVERSION - fade the move")
        elif strategy == StrategyType.DEFENSIVE:
            parts.append("Action: DEFENSIVE - preserve capital")
        
        return " | ".join(parts)
    
    def get_regime_statistics(self, regime: str) -> Dict:
        """Get statistics for a regime."""
        regime_enum = self._parse_regime(regime)
        config = self.regime_strategies.get(regime_enum, {})
        
        return {
            'regime': regime,
            'description': config.get('description', 'Unknown'),
            'primary_strategy': config.get('primary_strategy', 'unknown').value,
            'secondary_strategy': config.get('secondary_strategy', 'unknown').value,
            'capital_allocation': config.get('allocation', 0),
            'typical_win_rate': self._estimate_win_rate(regime_enum),
            'typical_avg_trade_days': self._estimate_trade_duration(regime_enum)
        }
    
    def _estimate_win_rate(self, regime: Regime) -> float:
        """Estimate typical win rate for a regime (historical assumption)."""
        if regime == Regime.UPTREND:
            return 0.65  # Trends work well
        elif regime == Regime.CONSOLIDATION:
            return 0.55  # Mean reversion works moderately
        elif regime == Regime.DOWNTREND:
            return 0.40  # Downtrends are tricky, skip most
        else:
            return 0.40  # Unknown
    
    def _estimate_trade_duration(self, regime: Regime) -> int:
        """Estimate typical trade duration for a regime (days)."""
        if regime == Regime.UPTREND:
            return 8  # Momentum trades last longer
        elif regime == Regime.CONSOLIDATION:
            return 5  # Mean reversion is quicker
        elif regime == Regime.DOWNTREND:
            return 2  # Defensive trades are brief
        else:
            return 3


def main():
    """Demo: Route signals based on different regimes."""
    router = StrategyRouter()
    
    print("\n🔀 Strategy Router Demo\n")
    
    # Test 1: Bullish signal in uptrend
    decision1 = router.route_signal(
        regime='uptrend',
        conviction=0.85,
        signal_type='ensemble',
        direction='bullish',
        signal_strength=0.8,
        regime_confidence=0.9
    )
    print(f"Test 1 - Bullish in Uptrend:")
    print(f"  Strategy: {decision1['selected_strategy']}")
    print(f"  Position Size: {decision1['position_size_pct']:.0%}")
    print(f"  Action: {decision1['action']}")
    print(f"  Rationale: {decision1['rationale']}\n")
    
    # Test 2: Bearish signal in consolidation
    decision2 = router.route_signal(
        regime='consolidation',
        conviction=0.65,
        signal_type='momentum_reversal',
        direction='bearish',
        signal_strength=0.6,
        regime_confidence=0.6
    )
    print(f"Test 2 - Bearish in Consolidation:")
    print(f"  Strategy: {decision2['selected_strategy']}")
    print(f"  Position Size: {decision2['position_size_pct']:.0%}")
    print(f"  Action: {decision2['action']}")
    print(f"  Rationale: {decision2['rationale']}\n")
    
    # Test 3: Bullish signal in downtrend (risky)
    decision3 = router.route_signal(
        regime='downtrend',
        conviction=0.55,
        signal_type='mean_reversion',
        direction='bullish',
        signal_strength=0.4,
        regime_confidence=0.8
    )
    print(f"Test 3 - Bullish in Downtrend (risky):")
    print(f"  Strategy: {decision3['selected_strategy']}")
    print(f"  Position Size: {decision3['position_size_pct']:.0%}")
    print(f"  Action: {decision3['action']}")
    print(f"  Rationale: {decision3['rationale']}\n")


if __name__ == '__main__':
    main()
