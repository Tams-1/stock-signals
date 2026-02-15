"""
Phase 5.1: Live Monitoring System

Real-time data pipeline that:
- Fetches 1-minute price updates from yfinance
- Fetches news sentiment hourly from NewsAPI
- Recalculates regime hourly
- Generates signals on each price update (1-min)
- Triggers alerts for high-conviction signals (0.8+), regime changes, and news spikes
- Sends Telegram alerts with full context
- Logs all alerts and signals to SQLite for analysis
"""

import yfinance as yf
import pandas as pd
import numpy as np
import sqlite3
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import time
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from signals.conviction_scorer import ConvictionScorer
from signals.regime_detector import RegimeDetector
from signals.momentum_detector import MomentumDetector
from signals.information_flow import InformationFlowDetector
from signals.momentum_reversal import MomentumReversalDetector
from signals.position_manager import PositionManager
from data.news_sentiment import NewsSentimentAnalyzer

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class LiveMonitor:
    """Real-time monitoring system for live signals and alerts."""
    
    def __init__(
        self,
        tickers: List[str],
        db_path: str = 'stock_signals.db',
        telegram_token: Optional[str] = None,
        telegram_chat_id: Optional[str] = None,
        price_interval: int = 60,  # seconds, 1-min updates
        news_interval: int = 3600,  # seconds, hourly news updates
        regime_interval: int = 3600,  # seconds, hourly regime recalc
        initial_capital: float = 100000.0
    ):
        """
        Initialize Live Monitor.
        
        Args:
            tickers: List of stock tickers to monitor
            db_path: Path to SQLite database
            telegram_token: Telegram bot token (optional)
            telegram_chat_id: Telegram chat ID (optional)
            price_interval: Seconds between price updates (default 60 = 1-min)
            news_interval: Seconds between news updates (default 3600 = 1-hour)
            regime_interval: Seconds between regime recalc (default 3600 = 1-hour)
            initial_capital: Initial capital for position sizing
        """
        self.tickers = tickers
        self.db_path = db_path
        self.telegram_token = telegram_token
        self.telegram_chat_id = telegram_chat_id
        self.price_interval = price_interval
        self.news_interval = news_interval
        self.regime_interval = regime_interval
        self.initial_capital = initial_capital
        
        # Initialize modules
        self.conviction_scorer = ConvictionScorer()
        self.regime_detector = RegimeDetector(db_path=db_path)
        self.momentum_detector = MomentumDetector()
        self.info_detector = InformationFlowDetector()
        self.mom_detector = MomentumReversalDetector()
        self.position_manager = PositionManager(initial_capital=initial_capital)
        self.news_analyzer = NewsSentimentAnalyzer()
        
        # State tracking
        self.last_price_update = {}  # {ticker: datetime}
        self.last_news_update = {}  # {ticker: datetime}
        self.last_regime_update = {}  # {ticker: datetime}
        self.current_regimes = {}  # {ticker: regime}
        self.price_cache = {}  # {ticker: latest_price}
        self.news_cache = {}  # {ticker: latest_sentiment}
        
        self._init_db()
        logger.info(f"LiveMonitor initialized for {len(tickers)} tickers")
    
    def _init_db(self):
        """Initialize SQLite database for storing alerts and signals."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Alerts table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT,
                ticker TEXT,
                alert_type TEXT,
                signal_type TEXT,
                conviction REAL,
                regime TEXT,
                news_sentiment REAL,
                recommended_action TEXT,
                position_size_pct REAL,
                stop_loss REAL,
                take_profit REAL,
                confirmed INTEGER DEFAULT 0,
                confirmation_time TEXT,
                execution_time TEXT,
                message TEXT,
                UNIQUE(ticker, timestamp, alert_type)
            )
        ''')
        
        # Signals table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS signals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT,
                ticker TEXT,
                signal_type TEXT,
                direction TEXT,
                strength REAL,
                conviction REAL,
                regime TEXT,
                details TEXT,
                UNIQUE(ticker, timestamp, signal_type)
            )
        ''')
        
        # Regime changes table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS regime_changes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT,
                ticker TEXT,
                old_regime TEXT,
                new_regime TEXT,
                confidence REAL,
                alert_sent INTEGER DEFAULT 0,
                UNIQUE(ticker, timestamp, new_regime)
            )
        ''')
        
        conn.commit()
        conn.close()
        logger.info("Database initialized")
    
    def fetch_latest_price(self, ticker: str, lookback_days: int = 30) -> Optional[pd.DataFrame]:
        """
        Fetch latest price data from yfinance (1-min to daily).
        
        Args:
            ticker: Stock ticker
            lookback_days: Number of days to fetch
            
        Returns:
            DataFrame with OHLCV data, or None if error
        """
        try:
            df = yf.download(ticker, period=f"{lookback_days}d", interval="1d", progress=False)
            if df.empty:
                logger.warning(f"No data for {ticker}")
                return None
            
            # Ensure required columns
            df = df.rename(columns=str.lower)
            required = ['open', 'high', 'low', 'close', 'volume']
            if not all(col in df.columns for col in required):
                logger.error(f"Missing OHLCV columns for {ticker}")
                return None
            
            self.price_cache[ticker] = df['close'].iloc[-1]
            return df
        except Exception as e:
            logger.error(f"Error fetching price for {ticker}: {e}")
            return None
    
    def fetch_news_sentiment(self, ticker: str, hours_lookback: int = 24) -> Optional[Dict]:
        """
        Fetch and analyze news sentiment for ticker.
        
        Args:
            ticker: Stock ticker
            hours_lookback: Hours to look back for news
            
        Returns:
            Dict with sentiment metrics, or None if error
        """
        try:
            articles = self.news_analyzer.fetch_news(ticker, days=hours_lookback // 24)
            if not articles:
                return {'sentiment': 'neutral', 'polarity': 0.0, 'velocity': 0}
            
            # Analyze sentiment
            sentiments = []
            for article in articles:
                title_sentiment = self.news_analyzer.analyze_sentiment(article.get('title', ''))
                sentiments.append(title_sentiment['polarity'])
            
            avg_polarity = np.mean(sentiments) if sentiments else 0.0
            velocity = len(articles)  # Number of articles in period
            
            if avg_polarity > 0.1:
                sentiment = 'positive'
            elif avg_polarity < -0.1:
                sentiment = 'negative'
            else:
                sentiment = 'neutral'
            
            result = {
                'sentiment': sentiment,
                'polarity': avg_polarity,
                'velocity': velocity,
                'article_count': len(articles)
            }
            
            self.news_cache[ticker] = result
            return result
        except Exception as e:
            logger.error(f"Error fetching news for {ticker}: {e}")
            return None
    
    def generate_signals(self, ticker: str, df: pd.DataFrame) -> List[Dict]:
        """
        Generate all signals for a ticker.
        
        Args:
            ticker: Stock ticker
            df: OHLCV DataFrame
            
        Returns:
            List of signal dicts
        """
        signals = []
        
        try:
            # Information flow signals
            info_signals = self.info_detector.run_all(df)
            if info_signals:
                signals.append({
                    'type': 'information_flow',
                    'signals': info_signals,
                    'timestamp': datetime.now().isoformat()
                })
            
            # Momentum/reversal signals
            mom_signals = self.mom_detector.run_all(df)
            if mom_signals:
                signals.append({
                    'type': 'momentum_reversal',
                    'signals': mom_signals,
                    'timestamp': datetime.now().isoformat()
                })
            
            # Momentum detection
            try:
                momentum = self.momentum_detector.detect_momentum(df)
                if momentum and momentum.get('strength', 0) > 0.3:
                    signals.append({
                        'type': 'momentum_detection',
                        'strength': momentum['strength'],
                        'direction': momentum.get('type', 'unknown'),
                        'timestamp': datetime.now().isoformat()
                    })
            except:
                pass
            
            # Regime detection
            try:
                regime_result = self.regime_detector.detect_regime(df)
                if regime_result:
                    regime, confidence = regime_result
                    signals.append({
                        'type': 'regime',
                        'regime': regime,
                        'confidence': confidence,
                        'timestamp': datetime.now().isoformat()
                    })
            except:
                pass
            
            return signals
        except Exception as e:
            logger.error(f"Error generating signals for {ticker}: {e}")
            return []
    
    def calculate_conviction_with_context(
        self,
        ticker: str,
        signals: List[Dict],
        regime: str,
        news_sentiment: Dict
    ) -> Tuple[float, str, Dict]:
        """
        Calculate conviction score with full market context.
        
        Args:
            ticker: Stock ticker
            signals: List of generated signals
            regime: Current market regime
            news_sentiment: News sentiment data
            
        Returns:
            (conviction_score, direction, details_dict)
        """
        try:
            # Aggregate signals for conviction scorer
            aggregated = {
                'technical': [],
                'news': [],
                'regime': []
            }
            
            # Extract technical signals
            for sig in signals:
                if sig['type'] in ['information_flow', 'momentum_reversal', 'momentum_detection']:
                    if isinstance(sig.get('signals'), list):
                        aggregated['technical'].extend(sig['signals'])
            
            # Add news signals
            if news_sentiment:
                if news_sentiment.get('sentiment') == 'positive':
                    aggregated['news'].append({
                        'type': 'positive_sentiment',
                        'strength': abs(news_sentiment.get('polarity', 0))
                    })
                elif news_sentiment.get('sentiment') == 'negative':
                    aggregated['news'].append({
                        'type': 'negative_sentiment',
                        'strength': abs(news_sentiment.get('polarity', 0))
                    })
                
                if news_sentiment.get('velocity', 0) > 5:
                    aggregated['news'].append({
                        'type': 'high_velocity',
                        'strength': min(news_sentiment.get('velocity', 0) / 20, 1.0)
                    })
            
            # Add regime signals
            if regime == 'uptrend':
                aggregated['regime'].append({'type': 'uptrend_confirmation', 'strength': 0.8})
            elif regime == 'downtrend':
                aggregated['regime'].append({'type': 'downtrend_confirmation', 'strength': 0.8})
            else:
                aggregated['regime'].append({'type': 'consolidation_confirmation', 'strength': 0.6})
            
            # Score conviction
            conviction, direction, details = self.conviction_scorer.score_signals(aggregated)
            
            return conviction, direction, details
        except Exception as e:
            logger.error(f"Error calculating conviction for {ticker}: {e}")
            return 0.3, 'neutral', {'error': str(e)}
    
    def trigger_alert(
        self,
        ticker: str,
        alert_type: str,
        signal_type: str,
        conviction: float,
        regime: str,
        news_sentiment: Dict,
        recommended_action: str,
        position_size_pct: float,
        stop_loss: float,
        take_profit: float
    ) -> int:
        """
        Trigger and log an alert.
        
        Args:
            ticker: Stock ticker
            alert_type: Type of alert (signal, regime_change, news_spike)
            signal_type: Type of signal detected
            conviction: Conviction score (0-1.0)
            regime: Current regime
            news_sentiment: News sentiment data
            recommended_action: Action recommendation (buy/sell/hold)
            position_size_pct: Recommended position size (%)
            stop_loss: Stop loss price
            take_profit: Take profit price
            
        Returns:
            Alert ID
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            timestamp = datetime.now().isoformat()
            news_sentiment_val = news_sentiment.get('polarity', 0) if news_sentiment else 0
            
            message = self._format_alert_message(
                ticker, alert_type, signal_type, conviction, regime,
                news_sentiment, recommended_action, position_size_pct
            )
            
            cursor.execute('''
                INSERT INTO alerts (
                    timestamp, ticker, alert_type, signal_type, conviction, regime,
                    news_sentiment, recommended_action, position_size_pct,
                    stop_loss, take_profit, message
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                timestamp, ticker, alert_type, signal_type, conviction, regime,
                news_sentiment_val, recommended_action, position_size_pct,
                stop_loss, take_profit, message
            ))
            
            conn.commit()
            alert_id = cursor.lastrowid
            conn.close()
            
            logger.info(f"Alert {alert_id} triggered for {ticker}: {alert_type}")
            
            # Send Telegram notification if configured
            if self.telegram_token and self.telegram_chat_id:
                self._send_telegram_alert(message, alert_id)
            
            return alert_id
        except Exception as e:
            logger.error(f"Error triggering alert for {ticker}: {e}")
            return -1
    
    def _format_alert_message(
        self,
        ticker: str,
        alert_type: str,
        signal_type: str,
        conviction: float,
        regime: str,
        news_sentiment: Dict,
        recommended_action: str,
        position_size_pct: float
    ) -> str:
        """Format alert message for display/Telegram."""
        msg = f"🚨 *{alert_type.upper()} ALERT*\n\n"
        msg += f"Ticker: *{ticker}*\n"
        msg += f"Signal: {signal_type}\n"
        msg += f"Conviction: {conviction:.1%}\n"
        msg += f"Regime: {regime.upper()}\n"
        
        if news_sentiment:
            sentiment_emoji = "📈" if news_sentiment.get('sentiment') == 'positive' else "📉" if news_sentiment.get('sentiment') == 'negative' else "➡️"
            msg += f"News: {sentiment_emoji} {news_sentiment.get('sentiment', 'neutral')} "
            msg += f"(polarity: {news_sentiment.get('polarity', 0):.2f})\n"
        
        msg += f"\nRecommended Action: *{recommended_action}*\n"
        msg += f"Position Size: {position_size_pct:.0%}\n"
        msg += f"\n⏰ Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        msg += f"⚠️ *Confirm execution manually before trading*"
        
        return msg
    
    def _send_telegram_alert(self, message: str, alert_id: int):
        """Send alert via Telegram (placeholder)."""
        try:
            import requests
            url = f"https://api.telegram.org/bot{self.telegram_token}/sendMessage"
            data = {
                'chat_id': self.telegram_chat_id,
                'text': message,
                'parse_mode': 'Markdown'
            }
            response = requests.post(url, json=data, timeout=5)
            if response.status_code == 200:
                logger.info(f"Telegram alert {alert_id} sent")
            else:
                logger.warning(f"Telegram send failed: {response.text}")
        except Exception as e:
            logger.warning(f"Error sending Telegram alert: {e}")
    
    def log_signal(
        self,
        ticker: str,
        signal_type: str,
        direction: str,
        strength: float,
        conviction: float,
        regime: str,
        details: Dict
    ):
        """Log a signal to database."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            timestamp = datetime.now().isoformat()
            details_json = json.dumps(details)
            
            cursor.execute('''
                INSERT OR IGNORE INTO signals (
                    timestamp, ticker, signal_type, direction, strength, conviction, regime, details
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (timestamp, ticker, signal_type, direction, strength, conviction, regime, details_json))
            
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Error logging signal for {ticker}: {e}")
    
    def check_regime_change(self, ticker: str, old_regime: str, new_regime: str, confidence: float):
        """Check for and log regime changes."""
        if old_regime != new_regime:
            try:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                
                timestamp = datetime.now().isoformat()
                cursor.execute('''
                    INSERT INTO regime_changes (timestamp, ticker, old_regime, new_regime, confidence)
                    VALUES (?, ?, ?, ?, ?)
                ''', (timestamp, ticker, old_regime, new_regime, confidence))
                
                conn.commit()
                conn.close()
                
                logger.info(f"Regime change detected for {ticker}: {old_regime} -> {new_regime}")
                
                # Trigger alert for regime change
                self.trigger_alert(
                    ticker=ticker,
                    alert_type='regime_change',
                    signal_type='regime_transition',
                    conviction=confidence,
                    regime=new_regime,
                    news_sentiment={},
                    recommended_action='adjust_positions',
                    position_size_pct=0.5,
                    stop_loss=0,
                    take_profit=0
                )
            except Exception as e:
                logger.error(f"Error logging regime change for {ticker}: {e}")
    
    def run_cycle(self, ticker: str) -> Dict:
        """
        Run one complete monitoring cycle for a ticker.
        
        Returns:
            Dict with cycle results (signals, alerts, regime)
        """
        result = {
            'ticker': ticker,
            'timestamp': datetime.now().isoformat(),
            'price': None,
            'signals': [],
            'alerts': [],
            'regime': None,
            'news_sentiment': None,
            'error': None
        }
        
        try:
            # Fetch latest price data
            df = self.fetch_latest_price(ticker, lookback_days=30)
            if df is None or df.empty:
                result['error'] = f"Failed to fetch price data for {ticker}"
                return result
            
            result['price'] = self.price_cache.get(ticker, None)
            
            # Generate signals
            signals = self.generate_signals(ticker, df)
            result['signals'] = signals
            
            # Fetch news sentiment
            news_sentiment = self.fetch_news_sentiment(ticker)
            result['news_sentiment'] = news_sentiment
            
            # Detect regime
            try:
                regime_result = self.regime_detector.detect_regime(df)
                if regime_result:
                    regime, confidence = regime_result
                    result['regime'] = {'regime': regime, 'confidence': confidence}
                    
                    # Check for regime change
                    old_regime = self.current_regimes.get(ticker)
                    if old_regime and old_regime != regime:
                        self.check_regime_change(ticker, old_regime, regime, confidence)
                    
                    self.current_regimes[ticker] = regime
            except Exception as e:
                logger.warning(f"Regime detection failed for {ticker}: {e}")
                result['regime'] = None
            
            # Calculate conviction and check for high-conviction signals
            if result['regime']:
                conviction, direction, details = self.calculate_conviction_with_context(
                    ticker=ticker,
                    signals=signals,
                    regime=result['regime']['regime'],
                    news_sentiment=news_sentiment
                )
                
                # Log signal
                self.log_signal(
                    ticker=ticker,
                    signal_type='ensemble',
                    direction=direction,
                    strength=conviction,
                    conviction=conviction,
                    regime=result['regime']['regime'],
                    details=details
                )
                
                # Trigger alert if high conviction
                if conviction >= 0.8:
                    position_sizing = self.position_manager.calculate_position_size(conviction)
                    alert_id = self.trigger_alert(
                        ticker=ticker,
                        alert_type='high_conviction_signal',
                        signal_type='ensemble',
                        conviction=conviction,
                        regime=result['regime']['regime'],
                        news_sentiment=news_sentiment,
                        recommended_action=f"{'BUY' if direction == 'bullish' else 'SELL' if direction == 'bearish' else 'HOLD'}",
                        position_size_pct=position_sizing.get('size_pct', 0),
                        stop_loss=position_sizing.get('stop_loss', 0),
                        take_profit=position_sizing.get('take_profit', 0)
                    )
                    result['alerts'].append(alert_id)
                
                # Check for news sentiment spike
                if news_sentiment and news_sentiment.get('velocity', 0) > 5:
                    alert_id = self.trigger_alert(
                        ticker=ticker,
                        alert_type='news_spike',
                        signal_type='news_velocity',
                        conviction=min(news_sentiment.get('velocity', 0) / 20, 1.0),
                        regime=result['regime']['regime'],
                        news_sentiment=news_sentiment,
                        recommended_action='investigate',
                        position_size_pct=0.2,
                        stop_loss=0,
                        take_profit=0
                    )
                    result['alerts'].append(alert_id)
        
        except Exception as e:
            logger.error(f"Error in monitoring cycle for {ticker}: {e}")
            result['error'] = str(e)
        
        return result
    
    def get_alert_history(self, ticker: str, limit: int = 100) -> List[Dict]:
        """Get recent alerts for a ticker."""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT * FROM alerts WHERE ticker = ? ORDER BY timestamp DESC LIMIT ?
            ''', (ticker, limit))
            
            rows = cursor.fetchall()
            conn.close()
            
            return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Error fetching alert history for {ticker}: {e}")
            return []
    
    def get_signal_history(self, ticker: str, limit: int = 100) -> List[Dict]:
        """Get recent signals for a ticker."""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT * FROM signals WHERE ticker = ? ORDER BY timestamp DESC LIMIT ?
            ''', (ticker, limit))
            
            rows = cursor.fetchall()
            conn.close()
            
            return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Error fetching signal history for {ticker}: {e}")
            return []
    
    def get_regime_history(self, ticker: str, limit: int = 100) -> List[Dict]:
        """Get recent regime changes for a ticker."""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT * FROM regime_changes WHERE ticker = ? ORDER BY timestamp DESC LIMIT ?
            ''', (ticker, limit))
            
            rows = cursor.fetchall()
            conn.close()
            
            return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Error fetching regime history for {ticker}: {e}")
            return []


def main():
    """Demo: Run live monitor for a few tickers."""
    # Example tickers (Brazilian stocks)
    tickers = ['VALE3.SA', 'PETR4.SA', 'ITUB4.SA']
    
    monitor = LiveMonitor(
        tickers=tickers,
        db_path='live_monitor.db',
        initial_capital=100000.0
    )
    
    # Run one cycle per ticker
    print("\n📊 Running Live Monitoring Cycle...")
    for ticker in tickers:
        result = monitor.run_cycle(ticker)
        print(f"\n{ticker}:")
        print(f"  Price: {result['price']}")
        print(f"  Regime: {result['regime']}")
        print(f"  Signals: {len(result['signals'])}")
        print(f"  Alerts: {len(result['alerts'])}")
        if result['error']:
            print(f"  Error: {result['error']}")


if __name__ == '__main__':
    main()
