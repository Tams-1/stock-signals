#!/usr/bin/env python3
"""
Real-time market monitor V2 - With intelligent exits and news
Runs every 3 minutes, fetches news every 10 minutes
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import json
from datetime import datetime, timedelta
from production_v2 import ProductionRunnerV2, TICKERS

STATE_FILE = "monitor_state_v2.json"
ALERT_FILE = "monitor_alerts.txt"
NEWS_CACHE_FILE = "monitor_news_cache.json"
NEWS_REFRESH_MINUTES = 10


def load_previous_state():
    """Load previous signals state"""
    if not os.path.exists(STATE_FILE):
        return {
            "timestamp": None,
            "trends": {},
            "positions": {},
            "last_news_fetch": None,
        }
    
    try:
        with open(STATE_FILE, 'r') as f:
            return json.load(f)
    except:
        return {
            "timestamp": None,
            "trends": {},
            "positions": {},
            "last_news_fetch": None,
        }


def save_current_state(results, runner):
    """Save current state"""
    trends = {r['ticker']: r['trend'] for r in results}
    positions = {
        ticker: {
            'entry_price': pos.entry_price,
            'entry_date': pos.entry_date,
            'size': pos.size,
        }
        for ticker, pos in runner.active_positions.items()
    }
    
    state = {
        "timestamp": datetime.now().isoformat(),
        "trends": trends,
        "positions": positions,
        "last_news_fetch": datetime.now().isoformat(),
    }
    
    with open(STATE_FILE, 'w') as f:
        json.dump(state, f, indent=2)


def should_fetch_news(prev_state):
    """Check if we should fetch news (every 10 minutes)"""
    last_fetch = prev_state.get("last_news_fetch")
    
    if not last_fetch:
        return True
    
    last_fetch_time = datetime.fromisoformat(last_fetch)
    elapsed = (datetime.now() - last_fetch_time).total_seconds() / 60
    
    return elapsed >= NEWS_REFRESH_MINUTES


def detect_changes(prev_state, curr_results, runner):
    """Detect signal changes and position updates"""
    alerts = []
    
    prev_trends = prev_state.get("trends", {})
    prev_positions = prev_state.get("positions", {})
    
    # Check for new positions (BUY signals)
    for ticker, pos in runner.active_positions.items():
        if ticker not in prev_positions:
            # Find the result to get full details
            result = next((r for r in curr_results if r['ticker'] == ticker), None)
            
            # Build detailed alert
            alert_lines = [
                f"🟢 SIGNAL: BUY - {ticker}",
                f"💰 Entrada: R$ {pos.entry_price:.2f} | Tamanho: {pos.size*100:.0f}%",
                f"📊 Trend: {result.get('trend', 'N/A')} | Confidence: {result.get('confidence', 0)*100:.1f}%",
                f"🛡️ Stop Loss: R$ {pos.stop_loss:.2f}",
            ]
            
            # Add reasoning if available
            if result and 'reasoning' in result:
                reasoning = result['reasoning']
                # Truncate if too long
                if len(reasoning) > 100:
                    reasoning = reasoning[:97] + "..."
                alert_lines.append(f"💡 Reasoning: {reasoning}")
            
            alerts.append("\n".join(alert_lines))
    
    # Check for closed positions (SELL signals - 100%)
    for ticker in prev_positions:
        if ticker not in runner.active_positions:
            # Find the result to get exit info
            result = next((r for r in curr_results if r['ticker'] == ticker), None)
            if result and result.get('action') == 'EXIT':
                gain = result.get('gain', 0) * 100
                reason = result.get('exit_reason', 'unknown')
                entry_price = prev_positions[ticker].get('entry_price', 0)
                exit_price = result.get('price', 0)
                gain_emoji = "📈" if gain > 0 else "📉"
                
                alert_lines = [
                    f"🔴 SIGNAL: SELL (100%) - {ticker}",
                    f"💰 Entry: R$ {entry_price:.2f} → Exit: R$ {exit_price:.2f}",
                    f"{gain_emoji} Gain: {gain:+.2f}%",
                    f"📝 Razão: {reason}"
                ]
                alerts.append("\n".join(alert_lines))
    
    # Check for partial exits (partial SELL signals)
    for result in curr_results:
        ticker = result['ticker']
        if result.get('action') == 'EXIT' and ticker in runner.active_positions:
            exit_pct = result.get('exit_percentage', 0) * 100
            gain = result.get('gain', 0) * 100
            reason = result.get('exit_reason', 'unknown')
            entry_price = result.get('entry_price', 0)
            exit_price = result.get('price', 0)
            gain_emoji = "📈" if gain > 0 else "📉"
            
            alert_lines = [
                f"⚠️ SIGNAL: SELL ({exit_pct:.0f}%) - {ticker}",
                f"💰 Entry: R$ {entry_price:.2f} → Exit: R$ {exit_price:.2f}",
                f"{gain_emoji} Gain: {gain:+.2f}%",
                f"📝 Razão: {reason}"
            ]
            alerts.append("\n".join(alert_lines))
    
    # Check for trend changes
    for result in curr_results:
        ticker = result['ticker']
        curr_trend = result['trend']
        prev_trend = prev_trends.get(ticker)
        
        if prev_trend and prev_trend != curr_trend:
            # Only alert if position is active or significant change
            if ticker in runner.active_positions or (prev_trend == "bullish" and curr_trend == "bearish"):
                alert_lines = [
                    f"🔄 MUDANÇA DE TENDÊNCIA - {ticker}",
                    f"📊 {prev_trend} → {curr_trend}",
                    f"⚠️ {'Atenção! Revisar posição ativa' if ticker in runner.active_positions else 'Sem posição ativa'}"
                ]
                alerts.append("\n".join(alert_lines))
    
    return alerts


def write_alert(alert_text):
    """Write alert to file"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    with open(ALERT_FILE, 'a') as f:
        f.write(f"[{timestamp}] {alert_text}\n")


def main():
    try:
        print(f"🔍 Market Monitor V2 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Load previous state
        prev_state = load_previous_state()
        
        # Check if we should fetch news
        use_news = should_fetch_news(prev_state)
        
        if use_news:
            print("📰 Fetching news (10min refresh)...")
        
        # Run analysis (with reasoning for decision logging)
        runner = ProductionRunnerV2(use_news=use_news, use_reasoning=True)
        
        # Get previous trends for regime detection
        previous_trends = prev_state.get("trends", {})
        
        results = runner.run(tickers=TICKERS, previous_trends=previous_trends)
        
        if not results:
            print("❌ No results")
            return
        
        # Detect changes
        alerts = detect_changes(prev_state, results, runner)
        
        # Print and save alerts
        if alerts:
            print(f"\n🚨 {len(alerts)} ALERTAS:")
            for alert in alerts:
                print(f"   {alert}")
                write_alert(alert)
        else:
            print("✅ No changes - market stable")
        
        # Save current state
        save_current_state(results, runner)
        
        # Print current summary
        active_count = len(runner.active_positions)
        buy_signals = len([r for r in results if r.get('action') == 'ENTER'])
        exit_signals = len([r for r in results if r.get('action') == 'EXIT'])
        
        print(f"\n📊 Current: 🟢 {buy_signals} BUY | 🔴 {exit_signals} SELL | 💼 {active_count} Active Positions")
        
        # Show active positions with P&L
        if runner.active_positions:
            print(f"\n💼 POSIÇÕES ATIVAS ({active_count}):")
            for ticker, pos in runner.active_positions.items():
                gain = (pos.current_price - pos.entry_price) / pos.entry_price * 100
                gain_emoji = "📈" if gain > 0 else "📉"
                trailing = "(Trailing)" if pos.trailing_stop_active else ""
                print(f"   {ticker:<10} {gain_emoji} {gain:+6.2f}% | Stop: R${pos.stop_loss:.2f} {trailing}")
    
    except Exception as e:
        error_msg = f"🚨 ERRO CRÍTICO NO MONITOR: {str(e)}"
        print(error_msg)
        write_alert(error_msg)
        raise  # Re-raise for cron job to know it failed


if __name__ == "__main__":
    main()
