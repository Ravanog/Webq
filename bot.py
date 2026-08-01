import os
import re
import json
import logging
import sys
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from github import Github

# Force stdout logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    stream=sys.stdout
)

# Dummy HTTP Server for Koyeb Health Checks
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()
        self.wfile.write(b"OK")
    def log_message(self, format, *args):
        return

def run_health_check_server():
    port = int(os.getenv("PORT", 8000))
    server = HTTPServer(('0.0.0.0', port), HealthCheckHandler)
    server.serve_forever()

# Fetch Environment Variables
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHANNEL_ID_RAW = os.getenv("CHANNEL_ID", "0")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
REPO_NAME = os.getenv("REPO_NAME")
JSON_FILE_PATH = os.getenv("JSON_FILE_PATH", "movies.json")

def update_github_json(new_movie_data: dict) -> tuple[bool, str]:
    """Updates GitHub JSON file and returns status."""
    try:
        g = Github(GITHUB_TOKEN)
        repo = g.get_repo(REPO_NAME)
        
        contents = repo.get_contents(JSON_FILE_PATH)
        current_data = json.loads(contents.decoded_content.decode('utf-8'))
        
        if "popular" not in current_data:
            current_data["popular"] = []
            
        existing_titles = [m.get("title", "").strip().lower() for m in current_data["popular"]]
        if new_movie_data.get("title", "").strip().lower() in existing_titles:
            return False, f"Movie '{new_movie_data.get('title')}' is already in movies.json!"

        current_data["popular"].insert(0, new_movie_data)
        
        updated_json_str = json.dumps(current_data, indent=2)
        repo.update_file(
            path=contents.path,
            message=f"Bot: Added '{new_movie_data.get('title')}'",
            content=updated_json_str,
            sha=contents.sha
        )
        return True, f"Successfully added '{new_movie_data.get('title')}' to website!"
    except Exception as e:
        logging.error(f"GitHub Error: {str(e)}")
        return False, f"GitHub Error: {str(e)}"

def parse_custom_movie_format(text: str) -> dict:
    """Parses your specific post format with emojis and links."""
    movie = {}
    lines = [line.strip() for line in text.strip().split('\n') if line.strip()]
    
    if len(lines) < 3:
        return {}

    # Line 0: Category/Tag (e.g., Popular)
    # Line 1: Title (e.g., The Social Network)
    # Line 2: Year (e.g., 2010)
    movie["title"] = lines[1]
    movie["year"] = lines[2]

    # Links extraction (Stream vs Telegram)
    urls = re.findall(r'https?://[^\s]+', text)
    if urls:
        movie["poster"] = urls[0]  # First URL is poster image
        if len(urls) > 1:
            movie["streamLink"] = urls[1]  # Second URL is streaming link
        if len(urls) > 2:
            movie["telegramLink"] = urls[2] # Third URL is batch/Telegram link
        elif len(urls) > 1:
            movie["telegramLink"] = urls[1]

    # Extract Rating: 🌟 7.374 / 10
    rating_match = re.search(r'🌟\s*([\d.]+)', text)
    if rating_match:
        movie["rating"] = rating_match.group(1)

    # Extract Genres: 🎭 #Drama or #Action #SciFi
    genres = re.findall(r'#(\w+)', text)
    if genres:
        movie["genres"] = genres

    # Extract Languages (Look for line with languages like Tamil, Telugu, Hindi , English)
    for line in lines:
        if any(lang in line for lang in ["English", "Hindi", "Tamil", "Telugu", "Malayalam", "Kannada"]):
            movie["language"] = [l.strip() for l in line.split(',')]
            break

    # Extract Quality (HD, 1080p, 4K, etc.)
    quality_match = re.search(r'\b(HD|1080p|720p|4K|4K UHD|BluRay|CAM)\b', text, re.IGNORECASE)
    if quality_match:
        movie["quality"] = quality_match.group(1).upper()

    # Extract Plot (Line with 📖 or multi-line text)
    plot_match = re.search(r'📖\s*(.*?)(?=\n[A-Z0-9]|\nhttps?://|\Z)', text, re.DOTALL)
    if plot_match:
        movie["plot"] = plot_match.group(1).strip()

    return movie

# --- START COMMAND ---
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome_text = (
        "🎬 *Welcome to Movie Ingestion Bot!*\n\n"
        "I automatically sync your channel movie posts directly to your website.\n\n"
        "📌 *How to use:*\n"
        "1. Simply post a movie in your channel using your formatted layout.\n"
        "2. Or send the movie text directly to me here in private chat!\n\n"
        "✨ *Supported Format Example:*\n"
        "```\n"
        "Popular\n"
        "The Social Network\n"
        "2010\n"
        "🖼 [https://image.tmdb.org/](https://image.tmdb.org/)...\n"
        "🌟 7.3 / 10\n"
        "⏱ 121 min\n"
        "🎬 David Fincher\n"
        "🎭 #Drama\n"
        "📖 In 2003, Harvard undergrad...\n"
        "HD\n"
        "Tamil, Telugu, Hindi, English\n"
        "[https://stream-url.com](https://stream-url.com)\n"
        "[https://telegram-batch-url.com](https://telegram-batch-url.com)\n"
        "```"
    )
    await update.message.reply_text(welcome_text, parse_mode="Markdown")

# --- PRIVATE CHAT MESSAGE HANDLER ---
async def handle_private_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if not text or "http" not in text:
        return

    movie_dict = parse_custom_movie_format(text)
    if movie_dict.get("title"):
        await update.message.reply_text("⏳ Extracting details and updating website...")
        success, msg = update_github_json(movie_dict)
        if success:
            await update.message.reply_text(f"✅ {msg}")
        else:
            await update.message.reply_text(f"❌ {msg}")
    else:
        await update.message.reply_text("⚠️ Could not extract movie details. Please check the post structure.")

# --- CHANNEL POST HANDLER ---
async def handle_channel_post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    post = update.channel_post
    if not post: return

    content = post.text or post.caption
    if not content: return

    movie_dict = parse_custom_movie_format(content)
    if movie_dict.get("title"):
        update_github_json(movie_dict)

if __name__ == '__main__':
    # Start health check server on background thread
    threading.Thread(target=run_health_check_server, daemon=True).start()

    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    
    # Handlers
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(MessageHandler(filters.ChatType.PRIVATE & ~filters.COMMAND, handle_private_message))
    
    # Listen to channel posts
    try:
        channel_id = int(CHANNEL_ID_RAW.strip())
        if channel_id != 0:
            channel_filter = filters.Chat(chat_id=channel_id) & filters.UpdateType.CHANNEL_POST
            app.add_handler(MessageHandler(channel_filter, handle_channel_post))
    except ValueError:
        pass

    logging.info("Bot starting polling...")
    app.run_polling()
    
