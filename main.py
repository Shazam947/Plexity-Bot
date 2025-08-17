import os
import logging
from flask import Flask, request
from pyrogram import Client
from pytgcalls import PyTgCalls
from pytgcalls.types import AudioPiped
import requests
from jiosaavn import JioSaavn
import asyncio
from threading import Thread

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

API_ID = int(os.environ.get("API_ID", "12345"))
API_HASH = os.environ.get("API_HASH", "your_api_hash")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "your_bot_token")
SESSION_STRING = os.environ.get("SESSION_STRING", "your_session_string")
WEBHOOK_URL = os.environ.get("WEBHOOK_URL", "https://your-app.onrender.com")

app = Flask(__name__)
user_client = Client("music_bot_user", session_string=SESSION_STRING)
pytgcalls = PyTgCalls(user_client)
playing_chats = {}
asyncio_loop = None

js = JioSaavn()

class MusicBot:
    async def download_jiosaavn_audio(self, query):
        try:
            results = js.search(query)
            if not results or not results['songs']:
                return None
            song = results['songs'][0]
            audio_url = song['downloadUrl'][1]
            title = song['song']
            duration = song['duration']
            return {
                'url': audio_url,
                'title': title,
                'duration': duration
            }
        except Exception as e:
            logger.error(f"Error extracting JioSaavn audio: {e}")
            return None

    async def play_music(self, chat_id, query):
        try:
            audio_info = await self.download_jiosaavn_audio(query)
            if not audio_info:
                return False

            await pytgcalls.join_group_call(
                chat_id,
                AudioPiped(audio_info['url'])
            )

            playing_chats[chat_id] = {
                'title': audio_info['title'],
                'duration': audio_info['duration'],
                'url': audio_info['url']
            }
            return True
        except Exception as e:
            logger.error(f"Error playing music: {e}")
            return False

    async def stop_music(self, chat_id):
        try:
            await pytgcalls.leave_group_call(chat_id)
            if chat_id in playing_chats:
                del playing_chats[chat_id]
            return True
        except Exception as e:
            logger.error(f"Error stopping music: {e}")
            return False

music_bot = MusicBot()

async def process_update(update):
    try:
        if 'message' in update:
            message = update['message']
            chat_id = message['chat']['id']
            text = message.get('text', '').strip()

            if text.startswith('/play'):
                query = text[5:].strip()
                if query:
                    success = await music_bot.play_music(chat_id, query)
                    if success:
                        await send_message(chat_id, f"🎵 Now playing: {playing_chats[chat_id]['title']}")
                    else:
                        await send_message(chat_id, "❌ Song Not Found or Can't Play")
                else:
                    await send_message(chat_id, "❌ Please provide song name!")
            elif text.startswith('/stop'):
                success = await music_bot.stop_music(chat_id)
                if success:
                    await send_message(chat_id, "⏹️ Music stopped")
                else:
                    await send_message(chat_id, "❌ No music playing")
            elif text.startswith('/current'):
                if chat_id in playing_chats:
                    info = playing_chats[chat_id]
                    await send_message(chat_id, f"🎵 Currently playing: {info['title']}")
                else:
                    await send_message(chat_id, "❌ No music playing")
    except Exception as e:
        logger.error(f"Error processing update: {e}")

async def send_message(chat_id, text):
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        payload = {
            'chat_id': chat_id,
            'text': text
        }
        requests.post(url, json=payload)
    except Exception as e:
        logger.error(f"Error sending message: {e}")

@app.route(f'/{BOT_TOKEN}', methods=['POST'])
def webhook():
    try:
        update = request.get_json()
        future = asyncio.run_coroutine_threadsafe(process_update(update), asyncio_loop)
        return 'OK', 200
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return 'Error', 500

@app.route('/setwebhook')
def set_webhook():
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/setWebhook"
        payload = {
            'url': f"{WEBHOOK_URL}/{BOT_TOKEN}",
            'drop_pending_updates': True
        }
        response = requests.post(url, json=payload)
        return response.json()
    except Exception as e:
        return {'error': str(e)}

@app.route('/')
def home():
    return "Telegram JioSaavn Music Bot is running!"

async def start_bot():
    try:
        await user_client.start()
        await pytgcalls.start()
        logger.info("Bot started successfully")
    except Exception as e:
        logger.error(f"Error starting bot: {e}")

def run_async_loop():
    global asyncio_loop
    loop = asyncio.new_event_loop()
    asyncio_loop = loop
    asyncio.set_event_loop(loop)
    loop.run_until_complete(start_bot())
    loop.run_forever()

if __name__ == '__main__':
    thread = Thread(target=run_async_loop)
    thread.daemon = True
    thread.start()

    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
