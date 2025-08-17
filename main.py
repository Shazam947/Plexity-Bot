import os
import logging
from flask import Flask, request
from pyrogram import Client
from pytgcalls import PyTgCalls
from pytgcalls.types import AudioPiped
import yt_dlp
import asyncio
from threading import Thread

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Bot configuration
API_ID = int(os.environ.get("API_ID", "12345"))
API_HASH = os.environ.get("API_HASH", "your_api_hash")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "your_bot_token")
SESSION_STRING = os.environ.get("SESSION_STRING", "your_session_string")
WEBHOOK_URL = os.environ.get("WEBHOOK_URL", "https://your-app.onrender.com")

# Initialize Flask app for webhook
app = Flask(__name__)

# Initialize Pyrogram client (User account for voice chat access)
user_client = Client("music_bot_user", session_string=SESSION_STRING)

# Initialize PyTgCalls for voice chat streaming
pytgcalls = PyTgCalls(user_client)

# Store for managing playing queues
playing_chats = {}

asyncio_loop = None  # Global event loop reference

class MusicBot:
    def __init__(self):
        self.yt_opts = {
            'format': 'bestaudio/best',
            'extractaudio': True,
            'audioformat': 'mp3',
            'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
            'restrictfilenames': True,
            'noplaylist': True,
            'nocheckcertificate': True,
            'ignoreerrors': False,
            'logtostderr': False,
            'quiet': True,
            'no_warnings': True,
        }

    async def download_youtube_audio(self, url):
        """Download and extract YouTube audio stream"""
        try:
            with yt_dlp.YoutubeDL(self.yt_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                audio_url = info['url']
                title = info.get('title', 'Unknown')
                duration = info.get('duration', 0)
                return {
                    'url': audio_url,
                    'title': title,
                    'duration': duration
                }
        except Exception as e:
            logger.error(f"Error extracting audio: {e}")
            return None

    async def play_music(self, chat_id, youtube_url):
        """Start playing music in voice chat"""
        try:
            audio_info = await self.download_youtube_audio(youtube_url)
            if not audio_info:
                return False

            await pytgcalls.join_group_call(
                chat_id,
                AudioPiped(audio_info['url'])
            )

            playing_chats[chat_id] = {
                'title': audio_info['title'],
                'duration': audio_info['duration'],
                'url': youtube_url
            }

            return True

        except Exception as e:
            logger.error(f"Error playing music: {e}")
            return False

    async def stop_music(self, chat_id):
        """Stop music and leave voice chat"""
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
    """Process incoming Telegram updates"""
    try:
        if 'message' in update:
            message = update['message']
            chat_id = message['chat']['id']
            text = message.get('text', '')

            if text.startswith('/play'):
                query = text[5:].strip()
                if query:
                    if 'youtube.com' in query or 'youtu.be' in query:
                        url = query
                    else:
                        url = await search_youtube(query)

                    if url:
                        success = await music_bot.play_music(chat_id, url)
                        if success:
                            await send_message(chat_id, f"🎵 Now playing: {playing_chats[chat_id]['title']}")
                        else:
                            await send_message(chat_id, "❌ Failed to play music")
                    else:
                        await send_message(chat_id, "❌ Could not find the song")

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

async def search_youtube(query):
    """Search YouTube for a song"""
    try:
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            search_results = ydl.extract_info(
                f"ytsearch1:{query}",
                download=False,
                ie_key='YoutubeSearch'
            )
            if search_results and 'entries' in search_results and search_results['entries']:
                video = search_results['entries'][0]
                return f"https://youtube.com/watch?v={video['id']}"
        return None
    except Exception as e:
        logger.error(f"Error searching YouTube: {e}")
        return None

async def send_message(chat_id, text):
    """Send message via Telegram Bot API"""
    try:
        import requests
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
        import requests
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
    return "Telegram Music Bot is running!"

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
