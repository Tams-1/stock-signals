# Phase 5: Deployment Guide

Quick start guide for running the real-time execution framework in production.

---

## Prerequisites

### Required Libraries
```bash
pip install yfinance pandas numpy scikit-learn textblob requests
```

### Optional but Recommended
```bash
pip install python-telegram-bot  # For Telegram alerts
```

### Configuration Files
- Telegram bot token (from BotFather)
- Telegram chat ID
- NewsAPI key (optional, system works without it)

---

## Quick Start (5 Minutes)

### 1. Basic Setup

```python
from src.execution.main_executor import MainExecutor

# Create executor
executor = MainExecutor(
    tickers=['VALE3.SA', 'PETR4.SA', 'ITUB4.SA'],
    initial_capital=100000.0,
    cycle_interval=60,  # 1-minute updates
    paper_trading_enabled=True,
    live_trading_enabled=False  # Safe!
)

# Run for 1 hour
executor.run(duration_minutes=60)
```

### 2. With Telegram Alerts

```python
executor = MainExecutor(
    tickers=['VALE3.SA', 'PETR4.SA'],
    initial_capital=100000.0,
    cycle_interval=60,
    paper_trading_enabled=True,
    telegram_token='YOUR_BOT_TOKEN',
    telegram_chat_id='YOUR_CHAT_ID'
)

executor.run(duration_minutes=480)  # 8-hour run
```

### 3. Check Results

```python
# Get performance summary
summary = executor.get_performance_summary()

print(f"Cycles: {summary['cycles_completed']}")
print(f"Total Signals: {summary['total_signals_generated']}")
print(f"Total Alerts: {summary['total_alerts_triggered']}")

if 'trading' in summary:
    print(f"Win Rate: {summary['trading']['win_rate_pct']:.1f}%")
    print(f"Total Return: {summary['trading']['total_return_pct']:.2f}%")
    print(f"Current Equity: ${summary['trading']['equity']:.2f}")
```

---

## Advanced Configuration

### Customizing Tickers

```python
# Brazilian stocks
tickers_br = ['VALE3.SA', 'PETR4.SA', 'ITUB4.SA', 'WEGE3.SA', 'ASAI3.SA']

# US stocks (if desired)
tickers_us = ['AAPL', 'MSFT', 'GOOGL']

executor = MainExecutor(
    tickers=tickers_br,
    initial_capital=100000.0
)
```

### Adjusting Cycle Interval

```python
# 1-minute updates (fast, more signals, more alerts)
executor = MainExecutor(..., cycle_interval=60)

# 5-minute updates (balanced)
executor = MainExecutor(..., cycle_interval=300)

# 15-minute updates (slower, fewer false alarms)
executor = MainExecutor(..., cycle_interval=900)
```

### Different Capital Levels

```python
# Conservative (small)
executor = MainExecutor(..., initial_capital=10000.0)

# Standard
executor = MainExecutor(..., initial_capital=100000.0)

# Aggressive (large)
executor = MainExecutor(..., initial_capital=500000.0)
```

---

## Monitoring

### Real-Time Status

```python
# During execution (in separate terminal)
import time
from src.execution.main_executor import MainExecutor

executor = MainExecutor(...)
executor.run(duration_minutes=480)  # In one terminal

# In another terminal - check status
while True:
    status = executor.get_status()
    print(f"Cycles: {status['cycles']}")
    print(f"Uptime: {status['uptime_sec']:.0f}s")
    if 'trading_metrics' in status:
        print(f"Equity: ${status['trading_metrics']['equity']:.2f}")
    time.sleep(60)
```

### Viewing Logs

```bash
# tail -f executor.log
tail -f executor.log

# grep for alerts
grep "Alert" executor.log

# grep for errors
grep "ERROR" executor.log
```

### Database Queries

```python
import sqlite3

# View recent alerts
conn = sqlite3.connect('executor.db')
cursor = conn.cursor()

cursor.execute('SELECT * FROM alerts ORDER BY timestamp DESC LIMIT 10')
for row in cursor.fetchall():
    print(row)

conn.close()
```

---

## Safety Checks

### Before Running Live

1. **Verify paper trading enabled**:
   ```python
   assert executor.paper_trading_enabled == True
   assert executor.live_trading_enabled == False  # CRITICAL!
   ```

2. **Test Telegram integration** (if using):
   ```python
   # Send test message
   monitor = executor.monitor
   monitor._send_telegram_alert("Test alert from executor")
   ```

3. **Check database connectivity**:
   ```python
   import sqlite3
   conn = sqlite3.connect(executor.db_path)
   cursor = conn.cursor()
   cursor.execute("SELECT COUNT(*) FROM alerts")
   print(f"Database OK: {cursor.fetchone()[0]} alerts")
   conn.close()
   ```

4. **Verify capital settings**:
   ```python
   print(f"Initial Capital: ${executor.initial_capital:.2f}")
   print(f"Paper Trader Capital: ${executor.trader.current_capital:.2f}")
   ```

---

## Common Scenarios

### Scenario 1: Monitor Single Ticker

```python
executor = MainExecutor(
    tickers=['VALE3.SA'],
    initial_capital=50000.0,
    cycle_interval=60
)

executor.run(duration_minutes=120)  # 2 hours
```

### Scenario 2: Multi-Ticker Diversified

```python
# 10 highly liquid Brazilian stocks
tickers = [
    'VALE3.SA', 'PETR4.SA', 'ITUB4.SA', 'BBDC4.SA',
    'ABEV3.SA', 'ASAI3.SA', 'WEGE3.SA', 'LREN3.SA',
    'JBSS3.SA', 'EQTL3.SA'
]

executor = MainExecutor(
    tickers=tickers,
    initial_capital=100000.0,
    cycle_interval=60
)

executor.run(duration_minutes=480)  # 8-hour test
```

### Scenario 3: Stress Test (Many Cycles)

```python
# Run for 24 hours to see performance over extended period
executor = MainExecutor(
    tickers=['VALE3.SA', 'PETR4.SA'],
    initial_capital=100000.0,
    cycle_interval=300  # 5-minute updates (manageable)
)

# 24 hours = 1440 minutes
executor.run(duration_minutes=1440)
```

### Scenario 4: High-Frequency Testing

```python
# Rapid cycles for development/testing
executor = MainExecutor(
    tickers=['TEST1', 'TEST2'],
    initial_capital=100000.0,
    cycle_interval=10  # 10 seconds (testing only!)
)

executor.run(duration_minutes=10)
```

---

## Handling Errors

### Network Error Recovery

```python
try:
    executor.run(duration_minutes=480)
except KeyboardInterrupt:
    print("User interrupted execution")
except Exception as e:
    print(f"Error: {e}")
    # System logs to file automatically
    print("Check executor.log for details")
```

### Data Availability Issues

```python
# If yfinance rate limited, executor waits and retries:
# - Automatic 5-second delay on error
# - Continues with next cycle

# If news API unavailable:
# - System continues with technical signals only
# - News sentiment optional, not critical
```

### Database Issues

```python
# If SQLite locked, executor waits for unlock
# Timeout after 30 seconds, skips logging for that cycle

# If disk full:
# - Stop executor
# - Clean old data: sqlite3 executor.db "DELETE FROM alerts WHERE timestamp < datetime('now', '-7 days')"
# - Resume
```

---

## Performance Tuning

### Reduce CPU Usage
```python
# Use longer cycle interval
executor = MainExecutor(..., cycle_interval=600)  # 10 minutes

# Use fewer tickers
executor = MainExecutor(tickers=['VALE3.SA', 'PETR4.SA'])
```

### Reduce Memory Usage
```python
# Clear old data periodically:
import sqlite3
conn = sqlite3.connect('executor.db')
cursor = conn.cursor()

# Keep only 1 week of data
cursor.execute("DELETE FROM alerts WHERE timestamp < datetime('now', '-7 days')")
cursor.execute("DELETE FROM signals WHERE timestamp < datetime('now', '-7 days')")

conn.commit()
conn.close()
```

### Faster Execution
```python
# Use shorter cycle interval
executor = MainExecutor(..., cycle_interval=30)  # 30 seconds

# Reduce number of checks
# (No simple config, would require code changes)
```

---

## Production Checklist

- [ ] Live trading disabled (`live_trading_enabled=False`)
- [ ] Paper trading enabled (`paper_trading_enabled=True`)
- [ ] Telegram token valid (test with alert)
- [ ] Sufficient disk space (SQLite logging)
- [ ] Network connectivity (yfinance, Telegram)
- [ ] Database file writable
- [ ] Log file created (`executor.log`)
- [ ] Initial capital reasonable
- [ ] Cycle interval chosen
- [ ] Tickers validated
- [ ] Test run completed (30 minutes)
- [ ] No errors in test run
- [ ] Final report reviewed

---

## Transitioning to Live Trading (Future)

### When Ready (Phase 6+):

1. **Complete backtesting across multiple periods**
   - 6+ months of historical data
   - Different market regimes validated
   - Win rate >50%, Sharpe ratio >1.0

2. **Extended paper trading**
   - 100+ hours with real market data
   - All regime types encountered
   - System stability proven

3. **Start with micro positions**
   ```python
   # Only after all above criteria met
   executor = MainExecutor(
       ...
       live_trading_enabled=True,  # ONLY AFTER VALIDATION
       initial_capital=5000.0  # START SMALL
   )
   ```

4. **Daily monitoring**
   - Compare live P&L to paper trading
   - Check for slippage differences
   - Verify alerts timely

5. **Scale gradually**
   - 1-2 weeks: 5% of intended capital
   - 1-2 weeks: 25%
   - 1-2 weeks: 50%
   - Then 100%

---

## Cleanup

### After Successful Run

```python
# Get final summary
summary = executor.get_performance_summary()

# Save to file
import json
with open(f'results_{summary["timestamp"]}.json', 'w') as f:
    json.dump(summary, f, indent=2)

# Archive database
import shutil
shutil.copy('executor.db', f'executor_archive_{summary["timestamp"]}.db')
```

### Clean Old Data

```python
import sqlite3
import os

# Clear alerts older than 30 days
conn = sqlite3.connect('executor.db')
cursor = conn.cursor()

cursor.execute(
    "DELETE FROM alerts WHERE timestamp < datetime('now', '-30 days')"
)

cursor.execute(
    "DELETE FROM signals WHERE timestamp < datetime('now', '-30 days')"
)

conn.commit()
conn.close()

# Vacuum to reclaim space
cursor.execute("VACUUM")
conn.commit()
conn.close()
```

---

## Troubleshooting

### Issue: No alerts generated
1. Check tickers are valid: `yfinance.download(ticker, period='1d')`
2. Check conviction threshold (0.8): See `LiveMonitor.trigger_alert()`
3. Check regime detection: Must be non-empty
4. Enable debug logging: Add `logging.basicConfig(level=logging.DEBUG)`

### Issue: Low win rate in paper trading
1. Normal for new strategy: Expect 45-55% initially
2. Check signal quality: Might need tuning
3. Review alerts generated: Are they actionable?
4. Backtest for comparison: See if signals match backtest

### Issue: Telegram alerts not sending
1. Check token valid: `curl https://api.telegram.org/bot<TOKEN>/getMe`
2. Check chat ID correct: `curl https://api.telegram.org/bot<TOKEN>/getUpdates`
3. Check network connectivity: `ping api.telegram.org`
4. Check token has permission: Run `/start` in Telegram chat

### Issue: Database locked
1. Close other connections: Check other terminals
2. Verify disk not full: `df -h`
3. Try WAL mode: 
   ```python
   import sqlite3
   conn = sqlite3.connect('executor.db')
   conn.execute('PRAGMA journal_mode=WAL')
   ```

### Issue: High CPU/Memory usage
1. Reduce cycle interval: Use 5-10 minute cycles
2. Reduce ticker count: Monitor fewer stocks
3. Clear old data: Archive and delete signals older than 7 days
4. Restart executor: Memory leaks are rare but possible

---

## Support Resources

1. **Check Logs**: `executor.log`
2. **Database Analysis**: `sqlite3 executor.db ".schema"`
3. **Code Examples**: See `tests/test_*.py`
4. **Module Docstrings**: Run `python -c "from src.execution import MainExecutor; help(MainExecutor)"`

---

## Key Takeaways

✅ **Safe by Default**: Paper trading only, no real trades
✅ **Automatic Logging**: All signals and alerts stored
✅ **Manual Control**: Alerts require confirmation
✅ **Scalable**: Handles 10+ tickers easily
✅ **Flexible**: Configurable cycle times and capital
✅ **Monitored**: Status and metrics available in real-time

---

**Last Updated**: 2026-02-14 21:51 GMT-3
**Version**: Phase 5 Production Ready
**Status**: ✅ Ready for 8+ hour paper trading test
