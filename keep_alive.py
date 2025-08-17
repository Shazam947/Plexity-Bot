from flask import Flask
from threading import Thread
import time
import requests
import os

app = Flask(__name__)

@app.route('/')
def home():
    return "Keep-alive service is running!"

def run():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run)
    t.daemon = True
    t.start()

def ping_self():
    """Ping the app every 5 minutes to keep it alive"""
    webhook_url = os.environ.get('WEBHOOK_URL', '')
    if webhook_url:
        while True:
            try:
                time.sleep(300)  # Wait 5 minutes
                requests.get(webhook_url)
                print("âœ… Keep-alive ping sent")
            except Exception as e:
                print(f"âŒ Keep-alive ping failed: {e}")

if __name__ == "__main__":
    keep_alive()
    # Start background pinging
    Thread(target=ping_self, daemon=True).start()
