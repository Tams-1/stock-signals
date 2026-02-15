"""Unit tests for conviction scoring module."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
import numpy as np
import pandas as pd
from datetime import datetime

from src.signals.conviction_scorer import ConvictionScorer


class TestConvictionScorer:
    """Test conviction scoring framework."""
    
    def setup_method(self):
        self.scorer = ConvictionScorer()
    
    def test_initialization(self):
        """Test scorer initialization."""
        assert self.scorer.weights['technical'] == 0.40
        assert self.scorer.weights['news'] == 0.30
        assert self.scorer.weights['regime'] == 0.30
        assert sum(self.scorer.weights.values()) == 1.0
    
    def test_invalid_weights(self):
        """Test that invalid weights are rejected."""
        with pytest.raises(ValueError):
            ConvictionScorer(weights={'technical': 0.5, 'news': 0.3, 'regime': 0.1})
    
    def test_single_technical_signal_bullish(self):
        """Test scoring with single bullish technical signal."""
        signals = {
            'technical': [
                {'signal': 'volume_anomaly', 'strength': 0.8, 'direction': 'bullish'}
            ],
            'news': [],
            'regime': []
        }
        
        conviction, direction, details = self.scorer.score_signals(signals)
        
        assert conviction > 0.3  # Single signal rule
        assert conviction < 0.5
        assert direction == 'bullish'
        assert details['rule_applied'] == 'single_signal_only'
    
    def test_all_signals_agree_bullish(self):
        """Test all signals agreeing (bullish)."""
        signals = {
            'technical': [
                {'signal': 'volume_anomaly', 'strength': 0.8, 'direction': 'bullish'},
                {'signal': 'momentum_continuation', 'strength': 0.75, 'direction': 'bullish'}
            ],
            'news': [
                {'signal': 'positive_sentiment', 'strength': 0.7, 'direction': 'bullish'}
            ],
            'regime': [
                {'signal': 'uptrend_confirmation', 'strength': 0.85, 'direction': 'bullish'}
            ]
        }
        
        conviction, direction, details = self.scorer.score_signals(signals)
        
        assert conviction >= 0.8  # All signals agree rule
        assert direction == 'bullish'
        assert details['rule_applied'] == 'all_signals_agree'
    
    def test_tech_news_agree_regime_disagrees(self):
        """Test tech + news agreement with disagreeing regime."""
        signals = {
            'technical': [
                {'signal': 'volume_anomaly', 'strength': 0.8, 'direction': 'bullish'},
                {'signal': 'momentum_continuation', 'strength': 0.75, 'direction': 'bullish'}
            ],
            'news': [
                {'signal': 'positive_sentiment', 'strength': 0.7, 'direction': 'bullish'}
            ],
            'regime': [
                {'signal': 'downtrend_confirmation', 'strength': 0.6, 'direction': 'bearish'}
            ]
        }
        
        conviction, direction, details = self.scorer.score_signals(signals)
        
        assert 0.5 <= conviction <= 0.7  # Tech + news agreement rule
        assert direction == 'bullish'
        assert details['rule_applied'] == 'tech_news_agreement'
    
    def test_signals_conflict(self):
        """Test conflicting signals."""
        signals = {
            'technical': [
                {'signal': 'volume_anomaly', 'strength': 0.8, 'direction': 'bullish'}
            ],
            'news': [
                {'signal': 'negative_sentiment', 'strength': 0.7, 'direction': 'bearish'}
            ],
            'regime': [
                {'signal': 'downtrend_confirmation', 'strength': 0.6, 'direction': 'bearish'}
            ]
        }
        
        conviction, direction, details = self.scorer.score_signals(signals)
        
        assert 0.2 <= conviction <= 0.4  # Signal conflict rule
        assert details['rule_applied'] == 'signal_conflict'
    
    def test_position_sizing_high_conviction(self):
        """Test position sizing for high conviction."""
        rec = self.scorer.get_position_sizing_recommendation(0.85)
        assert rec['size_pct'] == 0.70
        assert rec['recommendation'] == 'full_position'
    
    def test_position_sizing_medium_conviction(self):
        """Test position sizing for medium conviction."""
        rec = self.scorer.get_position_sizing_recommendation(0.70)
        assert rec['size_pct'] == 0.50
        assert rec['recommendation'] == 'large_position'
    
    def test_position_sizing_low_conviction(self):
        """Test position sizing for low conviction."""
        rec = self.scorer.get_position_sizing_recommendation(0.35)
        assert rec['size_pct'] == 0.0
        assert rec['recommendation'] == 'skip_trade'
    
    def test_aggregate_signals_from_detectors(self):
        """Test aggregating signals from various detectors."""
        info_signals = [
            ('volume_anomaly', 0.8, 'bullish', 'Volume spike detected'),
            ('volatility_shift', 0.6, None, 'Volatility increased')
        ]
        
        regime_signals = {
            'regime': 'uptrend',
            'confidence': 0.85
        }
        
        aggregated = self.scorer.aggregate_signals_from_detectors(
            info_signals=info_signals,
            regime_signals=regime_signals
        )
        
        assert len(aggregated['technical']) == 2
        assert len(aggregated['regime']) == 1
        assert aggregated['regime'][0]['signal'] == 'uptrend_confirmation'
        assert aggregated['regime'][0]['direction'] == 'bullish'
    
    def test_explain_conviction(self):
        """Test conviction explanation generation."""
        signals = {
            'technical': [
                {'signal': 'volume_anomaly', 'strength': 0.8, 'direction': 'bullish'}
            ],
            'news': [],
            'regime': []
        }
        
        conviction, direction, details = self.scorer.score_signals(signals)
        explanation = self.scorer.explain_conviction(conviction, direction, details)
        
        assert 'single signal' in explanation.lower() or 'conviction' in explanation.lower()
    
    def test_empty_signals(self):
        """Test scoring with empty signals."""
        signals = {
            'technical': [],
            'news': [],
            'regime': []
        }
        
        conviction, direction, details = self.scorer.score_signals(signals)
        
        assert conviction == 0.0
        assert direction is None
    
    def test_neutral_direction(self):
        """Test neutral direction determination."""
        signals = {
            'technical': [
                {'signal': 'volatility_shift', 'strength': 0.5, 'direction': None}
            ],
            'news': [],
            'regime': []
        }
        
        conviction, direction, details = self.scorer.score_signals(signals)
        
        # When no clear direction, should be None or neutral
        assert direction is None or direction == 'neutral'
    
    def test_custom_weights(self):
        """Test custom weight configuration."""
        weights = {'technical': 0.50, 'news': 0.20, 'regime': 0.30}
        scorer = ConvictionScorer(weights=weights)
        
        assert scorer.weights['technical'] == 0.50
        assert scorer.weights['news'] == 0.20
        assert scorer.weights['regime'] == 0.30
    
    def test_position_sizing_boundary_values(self):
        """Test position sizing at boundary values."""
        # Test boundaries
        assert self.scorer.get_position_sizing_recommendation(0.40)['size_pct'] == 0.25
        assert self.scorer.get_position_sizing_recommendation(0.39)['size_pct'] == 0.0
        assert self.scorer.get_position_sizing_recommendation(0.60)['size_pct'] == 0.50
        assert self.scorer.get_position_sizing_recommendation(0.80)['size_pct'] == 0.70
    
    def test_multiple_signals_same_category(self):
        """Test scoring with multiple signals in same category."""
        signals = {
            'technical': [
                {'signal': 'volume_anomaly', 'strength': 0.8, 'direction': 'bullish'},
                {'signal': 'momentum_continuation', 'strength': 0.7, 'direction': 'bullish'},
                {'signal': 'volatility_shift', 'strength': 0.6, 'direction': 'bullish'}
            ],
            'news': [],
            'regime': []
        }
        
        conviction, direction, details = self.scorer.score_signals(signals)
        
        # Multiple signals in same category should increase confidence
        assert details['agreement_matrix']['technical'] == 3
        assert direction == 'bullish'
