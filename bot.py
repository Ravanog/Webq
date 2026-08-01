import os
import re
import sys
import logging
import threading
from bson import json_util
from http.server import HTTPServer, BaseHTTPRequestHandler
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from pymongo import MongoClient

# Logging setup
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    stream=sys.stdout
)

# Dummy HTTP Server for Koyeb Health Checks


class WebAndHealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        # CORS Headers so your website can access the data
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()

        if self.path == '/api/movies' or self.path == '/movies':
            try:
                # Fetch all movies from MongoDB, sorted by latest
                movies = list(movies_collection.find({}, {'_id': 0}))
                response_data = json.dumps({"popular": movies})
                self.wfile.write(response_data.encode('utf-8'))
            except Exception as e:
                self.wfile.write(json.dumps({"error": str(e)}).encode('utf-8'))
        else:
            # Koyeb Health Check Route
            self.wfile.write(b'{"status": "OK"}')

def run_health_check_server():
    port = int(os.getenv("PORT", 8000))
    server = HTTPServer(('0.0.0.0', port), WebAndHealthHandler)
    server.serve_forever()


# Environment Variables
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHANNEL_ID_RAW = os.getenv("CHANNEL_ID", "0")
MONGO_URI = os.getenv("MONGO_URI")  # MongoDB Connection String

# Setup MongoDB Connection
client = MongoClient(MONGO_URI)
db = client["movie_database"]
movies_collection = db["movies"]

def insert_movie_to_mongodb(movie_data: dict) -> tuple[bool, str]:
    """Inserts movie object into MongoDB collection."""
    try:
        title = movie_data.get("title", "").strip()
        if not title:
            return False, "Invalid title."

        # Check if movie already exists (case-insensitive)
        existing = movies_collection.find_one({"title": re.compile(f"^{re.escape(title)}$", re.IGNORECASE)})
        if existing:
            return False, f"Movie '{title}' is already in database!"

        # Insert new movie
        movies_collection.insert_one(movie_data)
        return True, f"Successfully added '{title}' to MongoDB!"
    except Exception as e:
        logging.error(f"MongoDB Error: {str(e)}")
        return False, f"Database Error: {str(e)}"

def parse_custom_movie_format(text: str) -> dict:
    """Parses custom post format into JSON/dict object."""
    movie = {}
    lines = [line.strip() for line in text.strip().split('\n') if line.strip()]
    
    if len(lines) < 3:
        return {}

    movie["title"] = lines[1]
    movie["year"] = lines[2]

    # Links extraction
    urls = re.findall(r'https?://[^\s]+', text)
    if urls:
        movie["poster"] = urls[0]
        if len(urls) > 1:
            movie["streamLink"] = urls[1]
        if len(urls) > 2:
            movie["telegramLink"] = urls[2]
        elif len(urls) > 1:
            movie["telegramLink"] = urls[1]

    # Rating
    rating_match = re.search(r'🌟\s*([\d.]+)', text)
    if rating_match:
        movie["rating"] = rating_match.group(1)

    # Genres
    genres = re.findall(r'#(\w+)', text)
    if genres:
        movie["genres"] = genres

    # Languages
    for line in lines:
        if any(lang in line for lang in ["English", "Hindi", "Tamil", "Telugu", "Malayalam", "Kannada"]):
            movie["language"] = [l.strip() for l in line.split(',')]
            break

    # Quality
    quality_match = re.search(r'\b(HD|1080p|720p|4K|4K UHD|BluRay|CAM)\b', text, re.IGNORECASE)
    if quality_match:
        movie["quality"] = quality_match.group(1).upper()

    # Plot
    plot_match = re.search(r'📖\s*(.*?)(?=\n[A-Z0-9]|\nhttps?://|\Z)', text, re.DOTALL)
    if plot_match:
        movie["plot"] = plot_match.group(1).strip()

    return movie

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🎬 Bot is active and connected to MongoDB!")

async def handle_private_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if not text or "http" not in text:
        return

    movie_dict = parse_custom_movie_format(text)
    if movie_dict.get("title"):
        await update.message.reply_text("⏳ Saving movie to MongoDB...")
        success, msg = insert_movie_to_mongodb(movie_dict)
        if success:
            await update.message.reply_text(f"✅ {msg}")
        else:
            await update.message.reply_text(f"❌ {msg}")

async def handle_channel_post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    post = update.channel_post
    if not post: return

    content = post.text or post.caption
    if not content: return

    movie_dict = parse_custom_movie_format(content)
    if movie_dict.get("title"):
        insert_movie_to_mongodb(movie_dict)

if __name__ == '__main__':
    threading.Thread(target=run_health_check_server, daemon=True).start()

    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(MessageHandler(filters.ChatType.PRIVATE & ~filters.COMMAND, handle_private_message))
    
    try:
        channel_id = int(CHANNEL_ID_RAW.strip())
        if channel_id != 0:
            channel_filter = filters.Chat(chat_id=channel_id) & filters.UpdateType.CHANNEL_POST
            app.add_handler(MessageHandler(channel_filter, handle_channel_post))
    except ValueError:
        pass

    logging.info("Bot starting polling...")
    app.run_polling()
    
