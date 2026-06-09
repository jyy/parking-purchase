#!/usr/bin/env python3
"""
Reusable utility to send Telegram notifications using environment variables.
Supports direct execution from CLI/Bash or import as a module in Python.
"""
import os
import sys
import urllib.request
import urllib.parse

def send_message(text: str) -> bool:
    """Send a text message via Telegram Bot API using env vars TB_TOKEN and S2T_CHATID."""
    token = os.environ.get("TB_TOKEN")
    chat_id = os.environ.get("S2T_CHATID")
    if not token or not chat_id:
        # Silently pass if not run under a Telegram environment to prevent CLI crashes
        return False
    
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    data = urllib.parse.urlencode({
        "chat_id": chat_id,
        "text": text
    }).encode("utf-8")
    
    try:
        urllib.request.urlopen(urllib.request.Request(url, data=data), timeout=5)
        return True
    except Exception as e:
        print(f"[Telegram Notify Error] Failed to send message: {e}", file=sys.stderr)
        return False

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 telegram_notify.py <message_text>", file=sys.stderr)
        sys.exit(1)
        
    message = sys.argv[1]
    send_message(message)

if __name__ == "__main__":
    main()
