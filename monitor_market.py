#!/usr/bin/env python3
"""
Real-time market monitor - runs every 3 minutes
Detects signal changes and notifies via file
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import json
from datetime import datetime
from production_simple import SimpleProductionRunner, TICKERS

STATE_FILE = "monitor_state.json"
ALERT_FILE = "monitor_alerts.txt"

def load_previous_state():
    """Load previous signals state"""
    if not os.path.exists(STATE_FILE):
        return {}
    
    try:
        with open(STATE_FILE, 'r') as f:
            return json.load(f)
    except:
        return {}

def save_current_state(signals):
    """Save current signals state"""
    state = {
        "timestamp": datetime.now().isoformat(),
        "signals": signals
    }
    
    with open(STATE_FILE, 'w') as f:
        json.dump(state, f, indent=2)

def detect_changes(prev_state, curr_signals):
    """Detect signal changes"""
    changes = []
    
    prev_signals = prev_state.get("signals", {})
    
    for ticker, curr in curr_signals.items():
        prev = prev_signals.get(ticker, {})
        
        prev_signal = prev.get("signal", "HOLD")
        curr_signal = curr["signal"]
        
        # Detect change
        if curr_signal != prev_signal:
            changes.append({
                "ticker": ticker,
                "prev_signal": prev_signal,
                "curr_signal": curr_signal,
                "price": curr["price"],
                "trend": curr["trend"],
                "conviction": curr.get("conviction", 0.0),
                "position_size": curr.get("position_size", 0.0)
            })
    
    return changes

def format_alert(changes):
    """Format alert message"""
    if not changes:
        return None
    
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    lines = [
        f"🚨 MUDANÇA DE SINAIS - {timestamp}",
        ""
    ]
    
    for change in changes:
        emoji_curr = {
            "BUY": "🟢",
            "SELL": "🔴",
            "HOLD": "⚪"
        }[change["curr_signal"]]
        
        emoji_prev = {
            "BUY": "🟢",
            "SELL": "🔴",
            "HOLD": "⚪"
        }[change["prev_signal"]]
        
        lines.append(f"{emoji_prev} → {emoji_curr} {change['ticker']}")
        lines.append(f"   Preço: R$ {change['price']:.2f}")
        lines.append(f"   Trend: {change['trend']}")
        lines.append(f"   Conviction: {change['conviction']:.2f}")
        
        if change['curr_signal'] == "BUY":
            lines.append(f"   📍 Alocar: {change['position_size']*100:.0f}% do capital")
        elif change['curr_signal'] == "SELL":
            lines.append(f"   📍 Fechar posição")
        
        lines.append("")
    
    return "\n".join(lines)

def main():
    print(f"🔍 Market Monitor - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Load previous state
    prev_state = load_previous_state()
    
    # Run analysis
    runner = SimpleProductionRunner(use_news=False)  # Fast mode for real-time
    results = runner.run()
    
    if not results:
        print("❌ No results")
        return
    
    # Convert to dict
    curr_signals = {
        r["ticker"]: r
        for r in results
    }
    
    # Detect changes
    changes = detect_changes(prev_state, curr_signals)
    
    if changes:
        print(f"\n🚨 {len(changes)} CHANGES DETECTED!")
        
        # Format and save alert
        alert_msg = format_alert(changes)
        
        with open(ALERT_FILE, 'a') as f:
            f.write(alert_msg + "\n" + "="*70 + "\n\n")
        
        print(alert_msg)
    else:
        print("✅ No changes - market stable")
    
    # Save current state
    save_current_state(curr_signals)
    
    # Summary
    buy_count = sum(1 for s in curr_signals.values() if s["signal"] == "BUY")
    sell_count = sum(1 for s in curr_signals.values() if s["signal"] == "SELL")
    hold_count = sum(1 for s in curr_signals.values() if s["signal"] == "HOLD")
    
    print(f"\n📊 Current: 🟢 {buy_count} BUY | 🔴 {sell_count} SELL | ⚪ {hold_count} HOLD")

if __name__ == "__main__":
    main()
