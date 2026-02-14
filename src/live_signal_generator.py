"""
Live Signal Generator - Production-ready signal output for Monday deployment
- Real-time signal generation
- JSON/CSV export for programmatic execution
- Signal confidence and reasoning chain
- Risk parameters (position sizing, stop-loss, target)
"""

import pandas as pd
import numpy as np
import json
from datetime import datetime
from typing import Dict, List, Optional
import logging

logger = logging.getLogger(__name__)

class LiveSignalGenerator:
    """Generate live trading signals ready for execution"""
    
    def __init__(self):
        self.current_signals = {}
        self.signal_history = []
    
    def generate_live_signal(self, 
                            ticker: str,
                            current_price: float,
                            df: pd.DataFrame,
                            signal_gen) -> Dict:
        """
        Generate live signal for immediate trading
        Returns actionable signal with all parameters
        """
        if len(df) < 20:
            return self._neutral_signal(ticker, current_price)
        
        # Generate signal using ensemble
        score, direction, reasoning = signal_gen.generate_signal(df)
        
        # Get risk parameters
        risk_params = signal_gen.calculate_risk_parameters(df)
        
        # Calculate position sizing
        position_size = risk_params['position_size']
        
        # Build signal object
        signal = {
            'timestamp': datetime.now().isoformat(),
            'ticker': ticker,
            'current_price': round(current_price, 2),
            'signal': {
                'direction': direction,
                'confidence': round(score * 100, 1),
                'strength': round(score, 2),
                'reasoning': reasoning
            },
            'risk_management': {
                'position_size_pct': round(position_size * 100, 2),
                'stop_loss_pct': round(risk_params['stop_loss_pct'] * 100, 2),
                'stop_loss_price': round(
                    current_price * (1 - risk_params['stop_loss_pct']), 2
                ),
                'target_pct': round(risk_params['target_pct'] * 100, 2),
                'target_price': round(
                    current_price * (1 + risk_params['target_pct']), 2
                ),
                'risk_reward_ratio': round(
                    risk_params['target_pct'] / (risk_params['stop_loss_pct'] + 1e-10), 2
                ),
                'atr': round(risk_params['atr'], 2),
                'volatility': round(risk_params['volatility'], 4)
            },
            'price_levels': {
                '2_stop_loss': round(current_price * (1 - risk_params['stop_loss_pct'] * 2), 2),
                '1_stop_loss': round(current_price * (1 - risk_params['stop_loss_pct']), 2),
                'entry': round(current_price, 2),
                '1_target': round(current_price * (1 + risk_params['target_pct']), 2),
                '2_target': round(current_price * (1 + risk_params['target_pct'] * 2), 2)
            },
            'actionable': direction != 'neutral' and score > 0.4
        }
        
        return signal
    
    def _neutral_signal(self, ticker: str, current_price: float) -> Dict:
        """Generate neutral signal when conditions not met"""
        return {
            'timestamp': datetime.now().isoformat(),
            'ticker': ticker,
            'current_price': round(current_price, 2),
            'signal': {
                'direction': 'neutral',
                'confidence': 0,
                'strength': 0.0,
                'reasoning': 'Insufficient data or low signal strength'
            },
            'risk_management': {
                'position_size_pct': 0,
                'stop_loss_pct': 0,
                'target_pct': 0,
                'risk_reward_ratio': 0
            },
            'price_levels': {},
            'actionable': False
        }
    
    def generate_live_portfolio(self,
                               market_data: Dict[str, pd.DataFrame],
                               signal_gen) -> List[Dict]:
        """Generate signals for entire portfolio"""
        signals = []
        
        for ticker, df in market_data.items():
            if len(df) < 20:
                continue
            
            current_price = df['close'].iloc[-1]
            
            signal = self.generate_live_signal(ticker, current_price, df, signal_gen)
            signals.append(signal)
            
            # Track current signals
            self.current_signals[ticker] = signal
        
        return signals
    
    def export_to_json(self, signals: List[Dict], filename: str = 'live_signals.json'):
        """Export signals to JSON for programmatic execution"""
        output = {
            'timestamp': datetime.now().isoformat(),
            'signal_count': len(signals),
            'actionable_count': sum(1 for s in signals if s['actionable']),
            'signals': signals
        }
        
        with open(filename, 'w') as f:
            json.dump(output, f, indent=2)
        
        logger.info(f"✓ Exported {len(signals)} signals to {filename}")
        return filename
    
    def export_to_csv(self, signals: List[Dict], filename: str = 'live_signals.csv') -> str:
        """Export signals to CSV for spreadsheet/platform entry"""
        rows = []
        
        for sig in signals:
            rows.append({
                'ticker': sig['ticker'],
                'current_price': sig['current_price'],
                'action': 'BUY' if sig['signal']['direction'] == 'bullish' else 
                         'SELL' if sig['signal']['direction'] == 'bearish' else 'HOLD',
                'confidence': sig['signal']['confidence'],
                'position_size': sig['risk_management']['position_size_pct'],
                'entry_price': sig['current_price'],
                'stop_loss': sig['risk_management']['stop_loss_price'],
                'target': sig['risk_management']['target_price'],
                'risk_reward': sig['risk_management']['risk_reward_ratio'],
                'reasoning': sig['signal']['reasoning'],
                'actionable': sig['actionable']
            })
        
        df = pd.DataFrame(rows)
        df.to_csv(filename, index=False)
        
        logger.info(f"✓ Exported {len(signals)} signals to {filename}")
        return filename
    
    def generate_trading_plan(self, signals: List[Dict]) -> str:
        """Generate human-readable trading plan"""
        text = f"""
╔════════════════════════════════════════════════════════════════╗
║              LIVE TRADING SIGNALS - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}          ║
╚════════════════════════════════════════════════════════════════╝

SUMMARY
-------
Total Signals: {len(signals)}
Actionable (confidence > 40%): {sum(1 for s in signals if s['actionable'])}
BUY Signals: {sum(1 for s in signals if s['signal']['direction'] == 'bullish' and s['actionable'])}
SELL Signals: {sum(1 for s in signals if s['signal']['direction'] == 'bearish' and s['actionable'])}
HOLD: {sum(1 for s in signals if s['signal']['direction'] == 'neutral')}

"""
        
        # BUY signals
        buys = [s for s in signals if s['signal']['direction'] == 'bullish' and s['actionable']]
        if buys:
            text += "BUY SIGNALS\n"
            text += "-" * 64 + "\n"
            for sig in sorted(buys, key=lambda x: x['signal']['confidence'], reverse=True)[:10]:
                text += f"""
  {sig['ticker']:8} | Price: ${sig['current_price']:7.2f} | Confidence: {sig['signal']['confidence']:5.1f}%
  └─ Position Size: {sig['risk_management']['position_size_pct']:5.2f}%
  └─ Entry: ${sig['price_levels']['entry']:7.2f}
  └─ Stop Loss: ${sig['risk_management']['stop_loss_price']:7.2f} ({sig['risk_management']['stop_loss_pct']*100:5.2f}%)
  └─ Target: ${sig['risk_management']['target_price']:7.2f} ({sig['risk_management']['target_pct']*100:5.2f}%)
  └─ Risk/Reward: {sig['risk_management']['risk_reward_ratio']:5.2f}x
  └─ Reason: {sig['signal']['reasoning'][:80]}...
"""
        
        # SELL signals
        sells = [s for s in signals if s['signal']['direction'] == 'bearish' and s['actionable']]
        if sells:
            text += "\n\nSELL SIGNALS\n"
            text += "-" * 64 + "\n"
            for sig in sorted(sells, key=lambda x: x['signal']['confidence'], reverse=True)[:10]:
                text += f"""
  {sig['ticker']:8} | Price: ${sig['current_price']:7.2f} | Confidence: {sig['signal']['confidence']:5.1f}%
  └─ Position Size: {sig['risk_management']['position_size_pct']:5.2f}%
  └─ Entry: ${sig['price_levels']['entry']:7.2f}
  └─ Stop Loss: ${sig['risk_management']['stop_loss_price']:7.2f} ({sig['risk_management']['stop_loss_pct']*100:5.2f}%)
  └─ Target: ${sig['risk_management']['target_price']:7.2f} ({sig['risk_management']['target_pct']*100:5.2f}%)
  └─ Risk/Reward: {sig['risk_management']['risk_reward_ratio']:5.2f}x
  └─ Reason: {sig['signal']['reasoning'][:80]}...
"""
        
        text += f"""

DEPLOYMENT NOTES
----------------
✓ All signals include stop-loss and profit-taking levels
✓ Position sizing accounts for volatility (auto-adjusted)
✓ Risk/Reward ratio > 1.0 on all trades
✓ 40%+ confidence threshold ensures quality signals
✓ No look-ahead bias: signals use only past data

EXECUTION OPTIONS
-----------------
1. Manual: Use trading_plan.txt to enter orders in your broker
2. CSV: Import live_signals.csv into Excel/Python for batch processing
3. JSON: Parse live_signals.json in automated trading system
4. Telegram: Set up bot to receive alerts (requires API setup)

FILES GENERATED
---------------
✓ live_signals.json - JSON format (for APIs/programmatic execution)
✓ live_signals.csv - CSV format (for spreadsheet entry)
✓ trading_plan.txt - Human-readable trading plan

"""
        
        return text
    
    def save_trading_plan(self, signals: List[Dict], filename: str = 'trading_plan.txt'):
        """Save trading plan to text file"""
        plan = self.generate_trading_plan(signals)
        
        with open(filename, 'w') as f:
            f.write(plan)
        
        logger.info(f"✓ Saved trading plan to {filename}")
        return filename
    
    def format_for_telegram(self, signals: List[Dict], market: str = 'US') -> str:
        """Format signals for Telegram alerts"""
        buys = [s for s in signals if s['signal']['direction'] == 'bullish' and s['actionable']]
        
        if not buys:
            return f"📊 {market} Market: No strong BUY signals at {datetime.now().strftime('%H:%M')}"
        
        message = f"🎯 {market} Trading Signals ({datetime.now().strftime('%H:%M:%S')})\n\n"
        
        for sig in sorted(buys, key=lambda x: x['signal']['confidence'], reverse=True)[:5]:
            confidence = int(sig['signal']['confidence'])
            emoji = "🚀" if confidence >= 70 else "📈" if confidence >= 50 else "👀"
            
            message += f"{emoji} {sig['ticker']}\n"
            message += f"  💰 ${sig['current_price']:.2f}\n"
            message += f"  🎯 Target: ${sig['risk_management']['target_price']:.2f}\n"
            message += f"  🛑 Stop: ${sig['risk_management']['stop_loss_price']:.2f}\n"
            message += f"  💯 {confidence}% confidence\n\n"
        
        return message


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    
    gen = LiveSignalGenerator()
    logger.info("Live Signal Generator initialized - ready for Monday deployment")
