#!/usr/bin/env python3
"""
Send monitor alerts to Telegram via OpenClaw
Checks if monitor_alerts.txt was modified recently and sends content
"""

import os
import sys
import time
from datetime import datetime

ALERT_FILE = "/home/ulluboz/.openclaw/workspace/stock-signals/monitor_alerts.txt"
STATE_FILE = "/home/ulluboz/.openclaw/workspace/stock-signals/alert_sent_state.txt"

def get_last_sent_timestamp():
    """Get timestamp of last sent alert"""
    if not os.path.exists(STATE_FILE):
        return 0
    try:
        with open(STATE_FILE, 'r') as f:
            return float(f.read().strip())
    except:
        return 0

def save_sent_timestamp(timestamp):
    """Save timestamp of sent alert"""
    with open(STATE_FILE, 'w') as f:
        f.write(str(timestamp))

def main():
    if not os.path.exists(ALERT_FILE):
        sys.exit(0)
    
    # Check if alert file was modified recently (last 3 minutes)
    now = time.time()
    mod_time = os.path.getmtime(ALERT_FILE)
    age = now - mod_time
    
    # Get last sent timestamp
    last_sent = get_last_sent_timestamp()
    
    # Only send if:
    # 1. File was modified in last 180 seconds (3 minutes)
    # 2. We haven't sent this alert yet (mod_time > last_sent)
    if age < 180 and mod_time > last_sent:
        # Read last alert
        with open(ALERT_FILE, 'r') as f:
            lines = f.readlines()
            if lines:
                alert = lines[-1].strip()
                
                # Print alert (will be captured by OpenClaw system event)
                print(f"[ALERTA MERCADO V2] {alert}")
                
                # Save that we sent this alert
                save_sent_timestamp(mod_time)

if __name__ == "__main__":
    main()
