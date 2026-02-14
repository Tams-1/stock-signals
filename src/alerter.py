"""
Alert delivery: send signals to Telegram.
"""

class TelegramAlerter:
    """Send alerts to Telegram via OpenClaw."""
    
    def __init__(self, chat_id='208292712'):
        self.chat_id = chat_id
    
    def format_alert(self, alert):
        """Format alert for Telegram."""
        ticker = alert['ticker']
        confidence = alert['confidence']
        status = alert['status']
        signals = alert['signals']
        news = alert['news_sentiment']
        
        message = f"🚨 *{ticker}* | Confidence: {confidence:.0%}\n\n"
        message += f"Status: {status}\n\n"
        
        message += "*Technical Signals:*\n"
        for sig in signals:
            message += f"• [{sig['type']}] {sig['strength']:.2f}\n"
            message += f"  _{sig['explanation']}_\n"
        
        if news:
            _, direction, news_exp = news
            message += f"\n*📰 News Sentiment:*\n"
            message += f"_{news_exp}_\n"
        
        return message
    
    def send_alert(self, alert):
        """Send alert to Telegram (via OpenClaw)."""
        try:
            # This will be called by the OpenClaw messaging system
            # Format: use the message tool with Telegram channel
            message = self.format_alert(alert)
            return message
        except Exception as e:
            print(f"Error sending alert: {e}")
            return None
