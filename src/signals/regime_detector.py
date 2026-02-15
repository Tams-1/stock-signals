"""
Market Regime Detector: Classification of market conditions using ensemble methods.
- 4-method ensemble: Slope, MA Cross, ADX, Price Structure
- Regime classification: uptrend, downtrend, consolidation
- Confidence scoring (0-1.0)
- 60-day regime history tracking
- Regime-specific strategy allocation
"""

import numpy as np
import pandas as pd
from scipy import stats
import sqlite3
from datetime import datetime, timedelta
import logging
from typing import Dict, Tuple, List, Optional

logger = logging.getLogger(__name__)


class RegimeDetector:
    """Detect and classify market regime."""
    
    # Regime definitions for strategy allocation
    REGIME_STRATEGIES = {
        'uptrend': {
            'description': 'Follow momentum, aggressive trading',
            'allocation': 0.70,  # Use 70% of capital
            'direction': 'long',
            'mode': 'aggressive'
        },
        'downtrend': {
            'description': 'Defensive, avoid longs',
            'allocation': 0.30,  # Use 30% of capital
            'direction': 'short',
            'mode': 'defensive'
        },
        'consolidation': {
            'description': 'Mean reversion, balanced',
            'allocation': 0.50,  # Use 50% of capital
            'direction': 'neutral',
            'mode': 'balanced'
        }
    }
    
    def __init__(self, lookback_period: int = 20, adx_period: int = 14, db_path: str = 'stock_signals.db'):
        """
        Initialize Regime Detector.
        
        Args:
            lookback_period: Period for trend detection (days)
            adx_period: Period for ADX calculation
            db_path: Path to SQLite database
        """
        self.lookback_period = lookback_period
        self.adx_period = adx_period
        self.db_path = db_path
        self._init_database()
    
    def _init_database(self):
        """Initialize SQLite database for regime history."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS regime_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ticker TEXT NOT NULL,
                    regime TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    slope_method REAL,
                    ma_cross_method REAL,
                    adx_method REAL,
                    structure_method REAL,
                    detected_at TEXT NOT NULL,
                    UNIQUE(ticker, detected_at)
                )
            ''')
            
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Database initialization error: {e}")
    
    def detect_regime(self, df: pd.DataFrame) -> Dict:
        """
        Detect market regime using ensemble of 4 methods.
        
        Args:
            df: DataFrame with OHLCV data (columns: Open, High, Low, Close, Volume)
        
        Returns:
            Dictionary with regime, confidence, and method scores
        """
        if len(df) < max(self.lookback_period, self.adx_period):
            return {
                'regime': 'unknown',
                'confidence': 0.0,
                'explanation': 'Insufficient data'
            }
        
        try:
            # Use recent data for analysis
            recent_data = df.tail(self.lookback_period)
            
            # Method 1: Slope-based (Linear Regression)
            slope_signal = self._detect_slope(recent_data)
            
            # Method 2: MA Crossover
            ma_signal = self._detect_ma_cross(recent_data)
            
            # Method 3: ADX (Trend Strength)
            adx_signal = self._detect_adx(df.tail(self.lookback_period + self.adx_period))
            
            # Method 4: Price Structure
            structure_signal = self._detect_price_structure(recent_data)
            
            # Ensemble voting
            regime, confidence = self._ensemble_vote(
                slope_signal, ma_signal, adx_signal, structure_signal
            )
            
            return {
                'regime': regime,
                'confidence': round(confidence, 3),
                'methods': {
                    'slope': slope_signal,
                    'ma_cross': ma_signal,
                    'adx': adx_signal,
                    'structure': structure_signal
                },
                'strategy': self.REGIME_STRATEGIES.get(regime, {})
            }
            
        except Exception as e:
            logger.error(f"Error detecting regime: {e}")
            return {
                'regime': 'unknown',
                'confidence': 0.0,
                'explanation': f"Detection error: {str(e)}"
            }
    
    def _detect_slope(self, df: pd.DataFrame) -> Dict:
        """
        Method 1: Detect trend via linear regression slope.
        
        Returns:
            {regime: str, strength: float}
        """
        try:
            closes = df['Close'].values.flatten()  # Ensure 1D array
            
            if len(closes) < 3:
                return {'regime': 'unknown', 'strength': 0.0}
            
            x = np.arange(len(closes)).astype(float)
            try:
                slope, intercept, r_value, p_value, std_err = stats.linregress(x, closes)
            except (ValueError, RuntimeError):
                return {'regime': 'consolidation', 'strength': 0.0}
            
            # Normalize slope relative to price level
            price_range = closes.max() - closes.min()
            if price_range == 0:
                return {'regime': 'consolidation', 'strength': 0.0}
            
            slope_pct = (slope / closes[0]) * 100
            trend_strength = abs(r_value)
            
            # Classify
            if slope > 0:
                regime = 'uptrend'
            elif slope < 0:
                regime = 'downtrend'
            else:
                regime = 'consolidation'
            
            return {
                'regime': regime,
                'strength': round(trend_strength * (1 if slope != 0 else 0.5), 3)
            }
            
        except Exception as e:
            logger.error(f"Error in slope detection: {e}")
            return {'regime': 'unknown', 'strength': 0.0}
    
    def _detect_ma_cross(self, df: pd.DataFrame) -> Dict:
        """
        Method 2: Detect trend via MA crossover (10 & 20 & 50 day MA).
        
        FIXES (v2.1):
        - Added MA50 check for better uptrend confirmation (if available)
        - Relaxed price vs MA10 requirement (price can be near MA10, not just above)
        - Strength based on price vs MA20, not MA10
        - Better downtrend detection
        - Graceful fallback to MA10/MA20 if less than 50 days available
        
        Returns:
            {regime: str, strength: float}
        """
        try:
            closes = df['Close'].values.flatten()  # Ensure 1D array
            
            if len(closes) < 20:
                return {'regime': 'unknown', 'strength': 0.0}
            
            ma10 = float(pd.Series(closes).rolling(10).mean().values[-1])
            ma20 = float(pd.Series(closes).rolling(20).mean().values[-1])
            current_price = float(closes[-1])
            
            # MA50 only if we have 50+ days
            has_ma50 = len(closes) >= 50
            if has_ma50:
                ma50 = float(pd.Series(closes).rolling(50).mean().values[-1])
            
            # Determine regime with improved logic
            # UPTREND: (MA10 > MA20 > MA50) OR (MA10 > MA20 AND no MA50) AND price near MA20
            # This is more robust than requiring price > MA10
            
            # Check uptrend structure
            is_uptrend_structure = False
            if has_ma50:
                is_uptrend_structure = (ma10 > ma20 > ma50)
            else:
                is_uptrend_structure = (ma10 > ma20)
            
            # Check downtrend structure
            is_downtrend_structure = False
            if has_ma50:
                is_downtrend_structure = (ma10 < ma20 < ma50)
            else:
                is_downtrend_structure = (ma10 < ma20)
            
            if is_uptrend_structure:
                # Uptrend structure detected
                if current_price > ma20:
                    regime = 'uptrend'
                    # Strength: how far price is above MA20 (more stable than MA10)
                    strength = min((current_price - ma20) / ma20 * 3, 1.0)
                else:
                    # Price pulled back but structure still intact
                    # This is a buying dip, still uptrend but weaker
                    regime = 'uptrend'
                    ma_gap = (ma20 - current_price) / ma20
                    # Penalize slightly if price too far below MA20, but still recognize uptrend
                    strength = max(0.5, 1.0 - ma_gap * 2)
                    
            elif is_downtrend_structure:
                # Downtrend structure detected
                if current_price < ma20:
                    regime = 'downtrend'
                    strength = min((ma20 - current_price) / ma20 * 3, 1.0)
                else:
                    # Price bounced up but structure still down
                    regime = 'downtrend'
                    ma_gap = (current_price - ma20) / ma20
                    strength = max(0.5, 1.0 - ma_gap * 2)
                    
            else:
                # No clear MA structure = consolidation
                regime = 'consolidation'
                # Strength: how tight MAs are
                ma_distance = abs(ma10 - ma20) / ma20
                strength = 1.0 - min(ma_distance * 10, 1.0)
            
            return {
                'regime': regime,
                'strength': round(min(strength, 1.0), 3)
            }
            
        except Exception as e:
            logger.error(f"Error in MA cross detection: {e}")
            return {'regime': 'unknown', 'strength': 0.0}
    
    def _detect_adx(self, df: pd.DataFrame) -> Dict:
        """
        Method 3: Calculate ADX (Average Directional Index) for trend strength.
        
        Returns:
            {regime: str, strength: float}
        """
        try:
            high = df['High'].values.flatten()  # Ensure 1D array
            low = df['Low'].values.flatten()    # Ensure 1D array
            close = df['Close'].values.flatten()  # Ensure 1D array
            
            # Calculate +DM, -DM, TR (True Range)
            plus_dm = np.zeros(len(high))
            minus_dm = np.zeros(len(high))
            tr = np.zeros(len(high))
            
            for i in range(1, len(high)):
                # True Range
                tr[i] = max(
                    high[i] - low[i],
                    abs(high[i] - close[i-1]),
                    abs(low[i] - close[i-1])
                )
                
                # Directional Movement
                up_move = high[i] - high[i-1]
                down_move = low[i-1] - low[i]
                
                if up_move > down_move and up_move > 0:
                    plus_dm[i] = up_move
                if down_move > up_move and down_move > 0:
                    minus_dm[i] = down_move
            
            # Smooth using EMA
            tr_ema = self._ema(tr, self.adx_period)
            plus_dm_ema = self._ema(plus_dm, self.adx_period)
            minus_dm_ema = self._ema(minus_dm, self.adx_period)
            
            # Avoid division by zero
            tr_ema = np.clip(tr_ema, 1e-10, None)
            
            plus_di = plus_dm_ema / tr_ema * 100
            minus_di = minus_dm_ema / tr_ema * 100
            
            # DX
            di_sum = plus_di + minus_di
            dx = 100 * np.abs(plus_di - minus_di) / (di_sum + 1e-10)
            
            # ADX
            adx = self._ema(dx, self.adx_period)
            current_adx = float(adx[-1]) if len(adx) > 0 else 0.0
            
            # Current DI values - ensure they're scalars
            current_plus_di = float(plus_di[-1]) if len(plus_di) > 0 else 0.0
            current_minus_di = float(minus_di[-1]) if len(minus_di) > 0 else 0.0
            
            # Classify regime
            if current_plus_di > current_minus_di:
                regime = 'uptrend'
            elif current_minus_di > current_plus_di:
                regime = 'downtrend'
            else:
                regime = 'consolidation'
            
            # IMPROVED: Strength calculation (v2.1)
            # - ADX alone is not enough (0-100 scale doesn't map well to 0-1)
            # - Better: combine ADX (trend strength) + DI difference (directional clarity)
            # - Formula: (ADX/50) * (DI_difference/50) for 0-1 range
            
            di_diff = abs(current_plus_di - current_minus_di)
            adx_normalized = min(current_adx / 50, 1.0)  # ADX > 25 is strong, normalize to 50
            di_normalized = min(di_diff / 50, 1.0)       # DI diff > 50 is very clear
            
            # Combined strength: both ADX and DI difference must be high
            # This prevents false signals when trend is weak or directionality unclear
            combined_strength = (adx_normalized + di_normalized) / 2
            strength = min(combined_strength, 1.0)
            
            return {
                'regime': regime,
                'strength': round(strength, 3),
                'adx': round(current_adx, 2),
                'plus_di': round(current_plus_di, 2),
                'minus_di': round(current_minus_di, 2)
            }
            
        except Exception as e:
            logger.error(f"Error in ADX detection: {e}")
            return {'regime': 'unknown', 'strength': 0.0}
    
    def _detect_price_structure(self, df: pd.DataFrame) -> Dict:
        """
        Method 4: Detect trend via price structure (HH/LL for uptrend, LL/HH for downtrend).
        
        Returns:
            {regime: str, strength: float}
        """
        try:
            high = df['High'].values.flatten()  # Ensure 1D array
            low = df['Low'].values.flatten()    # Ensure 1D array
            close = df['Close'].values.flatten()  # Ensure 1D array
            
            if len(high) < 5:
                return {'regime': 'unknown', 'strength': 0.0}
            
            # Find recent swing highs and lows
            # Simple method: compare each bar to neighbors
            
            # Count higher highs and higher lows (uptrend)
            higher_highs = sum(1 for i in range(2, len(high)) if high[i] > high[i-2])
            higher_lows = sum(1 for i in range(2, len(low)) if low[i] > low[i-2])
            
            # Count lower highs and lower lows (downtrend)
            lower_highs = sum(1 for i in range(2, len(high)) if high[i] < high[i-2])
            lower_lows = sum(1 for i in range(2, len(low)) if low[i] < low[i-2])
            
            hh_ratio = higher_highs / (len(high) - 2)
            hl_ratio = higher_lows / (len(low) - 2)
            lh_ratio = lower_highs / (len(high) - 2)
            ll_ratio = lower_lows / (len(low) - 2)
            
            # Uptrend: HH and HL
            uptrend_score = (hh_ratio + hl_ratio) / 2
            downtrend_score = (lh_ratio + ll_ratio) / 2
            
            if uptrend_score > downtrend_score and uptrend_score > 0.5:
                regime = 'uptrend'
                strength = uptrend_score
            elif downtrend_score > uptrend_score and downtrend_score > 0.5:
                regime = 'downtrend'
                strength = downtrend_score
            else:
                regime = 'consolidation'
                strength = 1.0 - max(uptrend_score, downtrend_score)
            
            return {
                'regime': regime,
                'strength': round(min(strength, 1.0), 3)
            }
            
        except Exception as e:
            logger.error(f"Error in price structure detection: {e}")
            return {'regime': 'unknown', 'strength': 0.0}
    
    def _ensemble_vote(self, slope: Dict, ma: Dict, adx: Dict, structure: Dict) -> Tuple[str, float]:
        """
        Ensemble voting of all 4 methods with ADAPTIVE WEIGHTING (v2.1).
        
        IMPROVEMENTS:
        - Each method gets a vote weighted by its confidence (strength)
        - Methods with high confidence get higher weight
        - Adaptive weighting: if slope shows very clear trend, weight it more
        - Prevents weak contradictory votes from drowning out strong signals
        
        Returns:
            (regime, confidence)
        """
        methods_data = [
            ('slope', slope.get('regime'), slope.get('strength', 0)),
            ('ma', ma.get('regime'), ma.get('strength', 0)),
            ('adx', adx.get('regime'), adx.get('strength', 0)),
            ('structure', structure.get('regime'), structure.get('strength', 0))
        ]
        
        # Remove 'unknown' regimes
        methods_data = [(n, r, s) for n, r, s in methods_data if r != 'unknown']
        
        if not methods_data:
            return 'consolidation', 0.0
        
        # ADAPTIVE WEIGHTING: if strongest signal is very high confidence,
        # give it extra weight to avoid weak contradictions
        # Find the strongest method
        max_strength = max(s for _, _, s in methods_data)
        
        # If any method has very high confidence, apply boost
        weight_boost = 1.0
        if max_strength > 0.75:
            # Strong signal detected - boost weighting to prevent weak contradictions
            weight_boost = 1.5
        
        # Calculate weighted votes
        uptrend_votes = 0.0
        downtrend_votes = 0.0
        consolidation_votes = 0.0
        
        for method_name, regime, strength in methods_data:
            # Apply weight boost to the highest confidence method
            if strength == max_strength:
                weight = strength * weight_boost
            else:
                weight = strength
            
            if regime == 'uptrend':
                uptrend_votes += weight
            elif regime == 'downtrend':
                downtrend_votes += weight
            else:  # consolidation
                consolidation_votes += weight
        
        total_votes = uptrend_votes + downtrend_votes + consolidation_votes
        
        if total_votes == 0:
            return 'consolidation', 0.0
        
        # Determine winning regime
        max_votes = max(uptrend_votes, downtrend_votes, consolidation_votes)
        
        if uptrend_votes == max_votes:
            regime = 'uptrend'
        elif downtrend_votes == max_votes:
            regime = 'downtrend'
        else:
            regime = 'consolidation'
        
        # Confidence: how strong is the consensus?
        # Higher when there's clear agreement
        confidence = max_votes / total_votes
        
        return regime, confidence
    
    def _ema(self, data: np.ndarray, period: int) -> np.ndarray:
        """Calculate Exponential Moving Average."""
        if len(data) < period:
            return np.full(len(data), np.mean(data))
        
        ema = np.zeros(len(data))
        sma = np.mean(data[:period])
        ema[period-1] = sma
        
        multiplier = 2 / (period + 1)
        
        for i in range(period, len(data)):
            ema[i] = data[i] * multiplier + ema[i-1] * (1 - multiplier)
        
        # Fill initial period
        ema[:period-1] = ema[period-1]
        
        return ema
    
    def store_regime(self, ticker: str, regime_data: Dict):
        """
        Store regime detection result in database.
        
        Args:
            ticker: Stock ticker
            regime_data: Dictionary with regime detection results
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            methods = regime_data.get('methods', {})
            
            cursor.execute('''
                INSERT OR REPLACE INTO regime_history
                (ticker, regime, confidence, slope_method, ma_cross_method, adx_method, 
                 structure_method, detected_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                ticker,
                regime_data.get('regime', 'unknown'),
                regime_data.get('confidence', 0),
                methods.get('slope', {}).get('strength', 0),
                methods.get('ma_cross', {}).get('strength', 0),
                methods.get('adx', {}).get('strength', 0),
                methods.get('structure', {}).get('strength', 0),
                datetime.now().isoformat()
            ))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"Error storing regime: {e}")
    
    def get_regime_history(self, ticker: str, days: int = 60) -> List[Dict]:
        """
        Retrieve regime history for a ticker.
        
        Args:
            ticker: Stock ticker
            days: Number of days of history
        
        Returns:
            List of regime detection results
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cutoff_date = (datetime.now() - timedelta(days=days)).isoformat()
            
            cursor.execute('''
                SELECT regime, confidence, slope_method, ma_cross_method, adx_method,
                       structure_method, detected_at
                FROM regime_history
                WHERE ticker = ? AND detected_at > ?
                ORDER BY detected_at DESC
                LIMIT 60
            ''', (ticker, cutoff_date))
            
            results = cursor.fetchall()
            conn.close()
            
            return [
                {
                    'regime': r[0],
                    'confidence': r[1],
                    'slope_strength': r[2],
                    'ma_cross_strength': r[3],
                    'adx_strength': r[4],
                    'structure_strength': r[5],
                    'detected_at': r[6]
                }
                for r in results
            ]
            
        except Exception as e:
            logger.error(f"Error retrieving regime history: {e}")
            return []
    
    def get_regime_summary(self, ticker: str, days: int = 7) -> Dict:
        """
        Get summary of recent regime for a ticker.
        
        Args:
            ticker: Stock ticker
            days: Number of days to consider
        
        Returns:
            Summary statistics of recent regime
        """
        history = self.get_regime_history(ticker, days=days)
        
        if not history:
            return {'summary': 'No regime data available'}
        
        regimes = [h['regime'] for h in history]
        confidences = [h['confidence'] for h in history]
        
        # Most common regime
        from collections import Counter
        regime_counts = Counter(regimes)
        dominant_regime = regime_counts.most_common(1)[0][0]
        dominant_pct = regime_counts.most_common(1)[0][1] / len(regimes) * 100
        
        return {
            'dominant_regime': dominant_regime,
            'dominance_pct': round(dominant_pct, 1),
            'avg_confidence': round(np.mean(confidences), 3),
            'max_confidence': round(np.max(confidences), 3),
            'latest_regime': history[0]['regime'],
            'latest_confidence': history[0]['confidence'],
            'regime_changes': sum(1 for i in range(1, len(regimes)) if regimes[i] != regimes[i-1])
        }
