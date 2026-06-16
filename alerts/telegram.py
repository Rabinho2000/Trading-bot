import requests
import config

def send_telegram_message(message):
    """
    Send a message to Telegram.
    """
    if not config.TELEGRAM_BOT_TOKEN or not config.TELEGRAM_CHAT_ID:
        print("Telegram not configured. Skipping alert.")
        return
    
    url = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": config.TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown"
    }
    
    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()
    except Exception as e:
        print(f"Telegram error: {e}")

def format_daily_summary(regime, signals):
    """
    Format the daily summary for Telegram.
    """
    top_signals = [s for s in signals if s['action'] in ['BUY', 'WATCH']]
    top_signals = sorted(top_signals, key=lambda x: x['final_score'], reverse=True)[:5]
    
    message = f"*Market Regime: {regime}*\n\n"
    message += "*Top Signals:*\n"
    
    for i, s in enumerate(top_signals, 1):
        message += f"{i}. {s['ticker']} - {s['action']} - Score {s['final_score']} - Risk {s['risk_rating']}\n"
    
    message += "\n_Nota: Isto é research automatizado, não aconselhamento financeiro personalizado._"
    return message
