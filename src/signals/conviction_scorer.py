"""
Phase 3: Multi-Signal Conviction Scoring Framework

Aggregates signals from multiple sources (technical, news, regime) into a unified
conviction score (0-1.0) that indicates trading confidence and position sizing.

Signal Types:
- Technical: volume_anomaly, volatility_shift, order_imbalance, mean_reversion, momentum_continuation
- News: positive_sentiment, negative_sentiment, high_velocity
- Regime: uptrend_confirmation, downtrend_confirmation, consolidation_confirmation

Conviction Rules:
- All signals agree (bullish) = 0.8+
- Tech + news agree but regime disagrees = 0.5-0.7
- Signals conflict = 0.2-0.4 (skip trade)
- Single signal only = 0.3-0.5
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Optional
import logging

logger = logging.getLogger(__name__)


class ConvictionScorer:
    """Multi-signal conviction scoring framework."""
    
    # Signal definitions with default weights
    SIGNAL_CATEGORIES = {
        'technical': {
            'signals': ['volume_anomaly', 'volatility_shift', 'order_imbalance', 
                       'mean_reversion', 'momentum_continuation'],
            'weight': 0.40,  # 40% of conviction score
            'bias': 'neutral'
        },
        'news': {
            'signals': ['positive_sentiment', 'negative_sentiment', 'high_velocity'],
            'weight': 0.30,  # 30% of conviction score
            'bias': 'confirmatory'  # News confirms technical
        },
        'regime': {
            'signals': ['uptrend_confirmation', 'downtrend_confirmation', 'consolidation_confirmation'],
            'weight': 0.30,  # 30% of conviction score
            'bias': 'primary'  # Regime is primary filter
        }
    }
    
    def __init__(self, weights: Optional[Dict] = None):
        """
        Initialize conviction scorer.
        
        Args:
            weights: Optional custom weights for signal categories
                    {
                        'technical': 0.4,
                        'news': 0.3,
                        'regime': 0.3
                    }
        """
        self.weights = weights or {
            'technical': 0.40,
            'news': 0.30,
            'regime': 0.30
        }
        
        # Validate weights sum to 1.0
        if abs(sum(self.weights.values()) - 1.0) > 0.01:
            raise ValueError(f"Weights must sum to 1.0, got {sum(self.weights.values())}")
        
        self.signal_history = []
    
    def score_signals(self, signals: Dict) -> Tuple[float, str, Dict]:
        """
        Calculate conviction score from aggregated signals.
        
        Args:
            signals: Dictionary with signal categories:
                    {
                        'technical': [
                            {'signal': 'volume_anomaly', 'strength': 0.8, 'direction': 'bullish'},
                            ...
                        ],
                        'news': [...],
                        'regime': [...]
                    }
        
        Returns:
            (conviction_score: float, direction: str, details: dict)
        """
        scores_by_category = {}
        directions_by_category = {}
        agreement_matrix = {}
        
        # Score each category
        for category in ['technical', 'news', 'regime']:
            category_signals = signals.get(category, [])
            
            if not category_signals:
                scores_by_category[category] = 0.0
                directions_by_category[category] = None
                agreement_matrix[category] = 0
                continue
            
            # Calculate category score
            score, direction, agreement = self._score_category(
                category_signals, category
            )
            
            scores_by_category[category] = score
            directions_by_category[category] = direction
            agreement_matrix[category] = agreement
        
        # Apply conviction rules
        conviction, rule_applied = self._apply_conviction_rules(
            scores_by_category,
            directions_by_category,
            agreement_matrix
        )
        
        # Determine overall direction
        overall_direction = self._determine_direction(directions_by_category)
        
        # Build details
        details = {
            'scores_by_category': scores_by_category,
            'directions_by_category': directions_by_category,
            'agreement_matrix': agreement_matrix,
            'rule_applied': rule_applied,
            'signals_received': {k: len(v) for k, v in signals.items()}
        }
        
        return conviction, overall_direction, details
    
    def _score_category(self, signals: List[Dict], category: str) -> Tuple[float, Optional[str], int]:
        """
        Score signals within a category.
        
        Returns:
            (score: float 0-1.0, direction: str or None, agreement: int)
        """
        if not signals:
            return 0.0, None, 0
        
        strengths = [s.get('strength', 0.5) for s in signals]
        directions = [s.get('direction', None) for s in signals if s.get('direction')]
        
        # Average strength across signals
        avg_strength = np.mean(strengths) if strengths else 0.0
        
        # Determine direction by consensus
        if directions:
            bullish = sum(1 for d in directions if d == 'bullish')
            bearish = sum(1 for d in directions if d == 'bearish')
            direction = 'bullish' if bullish > bearish else ('bearish' if bearish > bullish else None)
            agreement = max(bullish, bearish)
        else:
            direction = None
            agreement = 0
        
        # Boost score if signals agree
        score = avg_strength
        if agreement > 0:
            agreement_boost = min(0.15, agreement * 0.05)
            score = min(1.0, score + agreement_boost)
        
        return score, direction, agreement
    
    def _apply_conviction_rules(self, scores: Dict, directions: Dict, 
                               agreements: Dict) -> Tuple[float, str]:
        """
        Apply conviction rules based on signal agreement.
        
        Rules:
        - All signals agree (bullish) = 0.8+
        - Tech + news agree but regime disagrees = 0.5-0.7
        - Signals conflict = 0.2-0.4 (skip trade)
        - Single signal only = 0.3-0.5
        """
        tech_dir = directions.get('technical')
        news_dir = directions.get('news')
        regime_dir = directions.get('regime')
        
        tech_score = scores.get('technical', 0.0)
        news_score = scores.get('news', 0.0)
        regime_score = scores.get('regime', 0.0)
        
        tech_agreement = agreements.get('technical', 0)
        news_agreement = agreements.get('news', 0)
        regime_agreement = agreements.get('regime', 0)
        
        # Count active signals (non-zero scores)
        active_categories = sum(1 for s in scores.values() if s > 0.1)
        
        # Rule 1: All signals agree (bullish or bearish)
        if (tech_dir == news_dir == regime_dir) and tech_dir is not None:
            if tech_agreement > 0 and news_agreement > 0 and regime_agreement > 0:
                # Strong agreement across all categories
                conviction = min(1.0, max(tech_score, news_score, regime_score) * 0.85 + 0.80)
                return conviction, "all_signals_agree"
        
        # Rule 2: Tech + news agree but regime disagrees
        if tech_dir == news_dir and tech_dir is not None:
            if regime_dir is None or (regime_dir and regime_dir != tech_dir):
                # Tech + news agreement with neutral or conflicting regime
                conviction = 0.5 + (tech_score + news_score) / 4
                conviction = min(0.7, conviction)
                return conviction, "tech_news_agreement"
        
        # Rule 3: Signals conflict
        if (tech_dir and news_dir and regime_dir and 
            not (tech_dir == news_dir == regime_dir)):
            # Conflicting signals
            avg_conflict_score = (tech_score + news_score + regime_score) / 3
            conviction = 0.2 + avg_conflict_score * 0.2
            return conviction, "signal_conflict"
        
        # Rule 4: Single signal only
        if active_categories == 1:
            max_score = max(scores.values())
            conviction = 0.3 + max_score * 0.2
            return conviction, "single_signal_only"
        
        # Default: Weighted average with slight penalty for disagreement
        weighted_conviction = (
            tech_score * self.weights['technical'] +
            news_score * self.weights['news'] +
            regime_score * self.weights['regime']
        )
        
        return weighted_conviction, "weighted_average"
    
    def _determine_direction(self, directions: Dict[str, Optional[str]]) -> Optional[str]:
        """Determine overall direction from category directions."""
        bullish_count = sum(1 for d in directions.values() if d == 'bullish')
        bearish_count = sum(1 for d in directions.values() if d == 'bearish')
        
        if bullish_count > bearish_count:
            return 'bullish'
        elif bearish_count > bullish_count:
            return 'bearish'
        else:
            return 'neutral' if bullish_count > 0 else None
    
    def get_position_sizing_recommendation(self, conviction: float) -> Dict:
        """
        Get position sizing based on conviction score.
        
        Returns:
            {
                'size_pct': float,  # % of capital to allocate
                'recommendation': str,
                'rationale': str
            }
        """
        if conviction >= 0.8:
            return {
                'size_pct': 0.70,
                'recommendation': 'full_position',
                'rationale': 'High conviction: 70% of capital'
            }
        elif conviction >= 0.6:
            return {
                'size_pct': 0.50,
                'recommendation': 'large_position',
                'rationale': 'Good conviction: 50% of capital'
            }
        elif conviction >= 0.4:
            return {
                'size_pct': 0.25,
                'recommendation': 'small_position',
                'rationale': 'Moderate conviction: 25% of capital'
            }
        else:
            return {
                'size_pct': 0.0,
                'recommendation': 'skip_trade',
                'rationale': 'Low conviction: skip trade'
            }
    
    def aggregate_signals_from_detectors(self, info_signals: List = None,
                                        mom_signals: List = None,
                                        regime_signals: List = None,
                                        news_signals: List = None) -> Dict:
        """
        Aggregate signals from various detectors into structured format.
        
        Args:
            info_signals: List from InformationFlowDetector
            mom_signals: List from MomentumReversalDetector
            regime_signals: Dict from RegimeDetector
            news_signals: List from sentiment analyzer
        
        Returns:
            Structured signals dict ready for scoring
        """
        signals = {
            'technical': [],
            'news': [],
            'regime': []
        }
        
        # Process information flow signals (technical)
        if info_signals:
            for sig_type, strength, direction, explanation in info_signals:
                signals['technical'].append({
                    'signal': sig_type,
                    'strength': strength,
                    'direction': direction
                })
        
        # Process momentum signals (technical)
        if mom_signals:
            for sig_type, strength, direction, explanation in mom_signals:
                signals['technical'].append({
                    'signal': sig_type,
                    'strength': strength,
                    'direction': direction
                })
        
        # Process regime signals
        if regime_signals:
            regime = regime_signals.get('regime', 'unknown')
            confidence = regime_signals.get('confidence', 0.0)
            
            # Map regime to confirmation signal
            if regime == 'uptrend':
                signals['regime'].append({
                    'signal': 'uptrend_confirmation',
                    'strength': confidence,
                    'direction': 'bullish'
                })
            elif regime == 'downtrend':
                signals['regime'].append({
                    'signal': 'downtrend_confirmation',
                    'strength': confidence,
                    'direction': 'bearish'
                })
            elif regime == 'consolidation':
                signals['regime'].append({
                    'signal': 'consolidation_confirmation',
                    'strength': confidence,
                    'direction': None
                })
        
        # Process news signals
        if news_signals:
            for signal_item in news_signals:
                if isinstance(signal_item, dict):
                    sig_type = signal_item.get('type', 'sentiment')
                    strength = signal_item.get('strength', 0.5)
                    direction = signal_item.get('direction')
                    signals['news'].append({
                        'signal': sig_type,
                        'strength': strength,
                        'direction': direction
                    })
        
        return signals
    
    def explain_conviction(self, conviction: float, direction: Optional[str], 
                          details: Dict) -> str:
        """Generate human-readable explanation of conviction score."""
        rule = details.get('rule_applied', 'unknown')
        
        explanations = {
            'all_signals_agree': f"All signal categories in agreement ({direction}). Conviction: {conviction:.2f}",
            'tech_news_agreement': f"Technical & news signals agree ({direction}), regime neutral/different. Conviction: {conviction:.2f}",
            'signal_conflict': f"Conflicting signals detected. Low conviction trading avoided. Conviction: {conviction:.2f}",
            'single_signal_only': f"Only {details.get('signals_received', {})['technical']} technical signal detected. Limited conviction. Conviction: {conviction:.2f}",
            'weighted_average': f"Weighted average of signals: {conviction:.2f}"
        }
        
        return explanations.get(rule, f"Conviction score: {conviction:.2f}")
