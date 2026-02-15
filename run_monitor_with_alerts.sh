#!/bin/bash
# Monitor V2 com News + Telegram Alerts
# Roda a cada 3 minutos, news a cada 10 min

cd /home/ulluboz/.openclaw/workspace/stock-signals

# Run monitor
python3 monitor_market_v2.py > /tmp/monitor_v2_output.txt 2>&1

# Check if monitor_alerts.txt was updated in last 3 minutes
ALERT_FILE="monitor_alerts.txt"
if [ -f "$ALERT_FILE" ]; then
    NOW=$(date +%s)
    MOD=$(stat -c '%Y' "$ALERT_FILE")
    AGE=$((NOW - MOD))
    
    # If modified in last 180 seconds (3 minutes)
    if [ $AGE -lt 180 ]; then
        # Read last alert
        ALERT=$(tail -n 1 "$ALERT_FILE")
        
        # Send via OpenClaw messaging
        echo "[ALERTA MERCADO V2] $ALERT"
    fi
fi
