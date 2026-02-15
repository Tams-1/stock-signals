#!/usr/bin/env python3
"""
Monitor Market V3 - Actionable Alert Format
Delivers top trading opportunities with drivers every 30 minutes.
Format: BEST STOCKS TO ACT ON + DRIVERS (trend, news, volume, patterns)
"""

import sys
sys.path.insert(0, '/home/ulluboz/.openclaw/workspace/stock-signals')

import yfinance as yf
from datetime import datetime, timedelta
from production_simple import SimpleProductionRunner

def detect_technical_patterns(data):
    """Detect golden crosses, double bottoms, etc."""
    patterns = []
    
    if len(data) < 200:
        return patterns
    
    close = data['Close']
    ma50 = close.rolling(50).mean()
    ma200 = close.rolling(200).mean()
    
    # Golden Cross detection
    if ma50.iloc[-2] <= ma200.iloc[-2] and ma50.iloc[-1] > ma200.iloc[-1]:
        patterns.append("🟡 Golden Cross (bullish reversal)")
    
    # Death Cross detection
    if ma50.iloc[-2] >= ma200.iloc[-2] and ma50.iloc[-1] < ma200.iloc[-1]:
        patterns.append("⚫ Death Cross (bearish reversal)")
    
    # Double Bottom detection
    if len(close) >= 40:
        lows = close.rolling(10).min()
        if lows.iloc[-20] == lows.iloc[-10] and close.iloc[-1] > lows.iloc[-10] * 1.02:
            patterns.append("💎 Double Bottom (support breakout)")
    
    return patterns

def format_alert_output(results):
    """Format results into actionable alerts for trading"""
    
    if not results:
        return "❌ No signals detected.\n"
    
    # Sort by conviction (absolute value)
    sorted_results = sorted(results, key=lambda x: abs(x.get('conviction', 0)), reverse=True)
    
    # Filter for only BUY/SELL signals (conviction > 0.5 threshold)
    signals = [r for r in sorted_results if r.get('signal') in ['BUY', 'SELL']]
    
    if not signals:
        return "⚪ No strong signals above 50% confidence threshold.\n"
    
    # Take top 5-10 opportunities
    top_signals = signals[:10]
    
    output = []
    output.append("\n" + "="*70)
    output.append(f"🚨 TOP TRADING OPPORTUNITIES")
    output.append(f"Generated: {datetime.now().strftime('%H:%M:%S')}")
    output.append("="*70 + "\n")
    
    for i, result in enumerate(top_signals, 1):
        ticker = result['ticker']
        signal = result['signal']
        price = result['price']
        trend = result['trend']
        confidence = result.get('confidence', 0.0)
        news_sentiment = result.get('news_sentiment', 0.0)
        position_size = result.get('position_size', 0.0)
        conviction = result.get('conviction', 0.0)
        
        # Signal emoji
        if signal == "BUY":
            emoji = "🟢"
        elif signal == "SELL":
            emoji = "🔴"
        else:
            emoji = "⚪"
        
        # Conviction level
        if abs(conviction) >= 0.8:
            conviction_label = "VERY HIGH"
        elif abs(conviction) >= 0.7:
            conviction_label = "HIGH"
        elif abs(conviction) >= 0.6:
            conviction_label = "MEDIUM-HIGH"
        else:
            conviction_label = "MEDIUM"
        
        output.append(f"{i}️⃣  {ticker} - {signal} {emoji}")
        output.append(f"    Price: R${price:.2f}")
        output.append(f"    └─ Drivers:")
        output.append(f"       • Trend: {trend.upper()} ({confidence:.0%} confidence)")
        output.append(f"       • News: {news_sentiment:+.2f} sentiment")
        
        # News interpretation
        if news_sentiment > 0.15:
            output.append(f"         ✅ Positive news boost (+{news_sentiment*0.20:.0%} position)")
        elif news_sentiment < -0.15:
            output.append(f"         ⚠️  Negative news headwind ({news_sentiment*0.15:.0%} position)")
        else:
            output.append(f"         😐 Neutral news (no impact)")
        
        output.append(f"       • Position: {position_size:.0%} ({conviction_label} conviction)")
        
        # Try to get technical patterns
        try:
            ticker_with_sa = f"{ticker}.SA" if not ticker.endswith('.SA') else ticker
            data = yf.download(ticker_with_sa, period='1y', progress=False)
            patterns = detect_technical_patterns(data)
            
            if patterns:
                for pattern in patterns:
                    output.append(f"       • Pattern: {pattern}")
        except:
            pass
        
        output.append("")
    
    # Summary stats
    buy_count = sum(1 for r in top_signals if r['signal'] == 'BUY')
    sell_count = sum(1 for r in top_signals if r['signal'] == 'SELL')
    
    output.append("="*70)
    output.append(f"📊 Summary: {buy_count} BUY signals | {sell_count} SELL signals")
    output.append("="*70 + "\n")
    
    return "\n".join(output)

def main():
    print("\n" + "="*70)
    print(f"📈 MARKET MONITOR V3 (Smart News) - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*70 + "\n")
    
    # Run analysis with CACHED news (fast, uses 0 API credits)
    runner = SimpleProductionRunner(use_news=True)
    
    print("📊 Analyzing 150 stocks with CACHED news sentiment...\n")
    results = runner.run()
    
    # Identify top movers for fresh news refresh
    top_movers = runner.get_top_movers(results, top_n=10)
    
    # Smart news refresh: ONLY fetch fresh news for top movers
    if top_movers:
        print(f"\n🔄 Smart News Refresh: Fetching fresh sentiment for {len(top_movers)} top movers...")
        fresh_sentiments = runner.news_client.refresh_sentiment_batch(top_movers)
        
        # Update results with fresh news sentiment
        for result in results:
            if result['ticker'] in fresh_sentiments:
                old_sentiment = result['news_sentiment']
                new_sentiment = fresh_sentiments[result['ticker']]
                result['news_sentiment'] = new_sentiment
                
                if abs(new_sentiment - old_sentiment) > 0.05:
                    print(f"   {result['ticker']}: sentiment updated {old_sentiment:+.2f} → {new_sentiment:+.2f}")
        
        # Log API usage
        cache_stats = runner.news_client.get_cache_stats()
        print(f"\n💾 News Cache Stats:")
        print(f"   Total cached: {cache_stats['total_entries']}")
        print(f"   Fresh: {cache_stats['fresh']}")
        print(f"   API calls this run: ~{len(top_movers)} credits")
    
    # Format and output actionable alerts
    alert_text = format_alert_output(results)
    print(alert_text)
    
    # Save for cron delivery
    with open('monitor_alerts.txt', 'w') as f:
        f.write(alert_text)
    
    print("✅ Alert saved to monitor_alerts.txt")

if __name__ == "__main__":
    main()
