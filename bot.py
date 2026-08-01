import os
import json
import logging
import sys
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes
from github import Github

# Force stdout logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    stream=sys.stdout
)

# Fetch Environment Variables
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHANNEL_ID_RAW = os.getenv("CHANNEL_ID")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
REPO_NAME = os.getenv("REPO_NAME")
JSON_FILE_PATH = os.getenv("JSON_FILE_PATH", "movies.json")

# Variable Verification
missing_vars = []
if not TELEGRAM_BOT_TOKEN: missing_vars.append("TELEGRAM_BOT_TOKEN")
if not CHANNEL_ID_RAW: missing_vars.append("CHANNEL_ID")
if not GITHUB_TOKEN: missing_vars.append("GITHUB_TOKEN")
if not REPO_NAME: missing_vars.append("REPO_NAME")

if missing_vars:
    logging.error(f"CRITICAL ERROR: Missing Environment Variables in Koyeb: {', '.join(missing_vars)}")
    sys.exit(1)

try:
    CHANNEL_ID = int(CHANNEL_ID_RAW.strip())
except ValueError:
    logging.error(f"CRITICAL ERROR: CHANNEL_ID must be a valid integer! Got: '{CHANNEL_ID_RAW}'")
    sys.exit(1)

def update_github_json(new_movie_data: dict) -> bool:
    try:
        g = Github(GITHUB_TOKEN)
        repo = g.get_repo(REPO_NAME)
        
        contents = repo.get_contents(JSON_FILE_PATH)
        current_data = json.loads(contents.decoded_content.decode('utf-8'))
        
        if "popular" not in current_data:
            current_data["popular"] = []
            
        existing_titles = [m.get("title", "").strip().lower() for m in current_data["popular"]]
        if new_movie_data.get("title", "").strip().lower() in existing_titles:
            logging.info(f"Skipping duplicate movie: {new_movie_data.get('title')}")
            return False

        current_data["popular"].insert(0, new_movie_data)
        
        updated_json_str = json.dumps(current_data, indent=2)
        repo.update_file(
            path=contents.path,
            message=f"Bot: Added '{new_movie_data.get('title')}'",
            content=updated_json_str,
            sha=contents.sha
        )
        logging.info(f"Successfully added '{new_movie_data.get('title')}' to GitHub!")
        return True
    except Exception as e:
        logging.error(f"Error updating GitHub repository: {str(e)}")
        return False

async def handle_channel_post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    post = update.channel_post
    if not post:
        return

    content = post.text or post.caption
    if not content or "title:" not in content.lower():
        return

    try:
        lines = content.split('\n')
        movie_dict = {}
        
        for line in lines:
            if ":" in line:
                key, value = line.split(":", 1)
                key = key.strip().lower()
                value = value.strip()
                
                if key == "title": movie_dict["title"] = value
                elif key == "year": movie_dict["year"] = value
                elif key == "quality": movie_dict["quality"] = value
                elif key == "rating": movie_dict["rating"] = value
                elif key == "language": 
                    movie_dict["language"] = [l.strip() for l in value.split(",")]
                elif key == "poster": movie_dict["poster"] = value
                elif key == "genres": 
                    movie_dict["genres"] = [g.strip() for g in value.split(",")]
                elif key == "plot": movie_dict["plot"] = value
                elif key == "stream": movie_dict["streamLink"] = value
                elif key == "telegram": movie_dict["telegramLink"] = value

        if "title" in movie_dict:
            update_github_json(movie_dict)

    except Exception as e:
        logging.error(f"Error parsing channel post: {str(e)}")

if __name__ == '__main__':
    logging.info("Starting Telegram Bot listener on Koyeb...")
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    
    channel_filter = filters.Chat(chat_id=CHANNEL_ID) & filters.UpdateType.CHANNEL_POST
    app.add_handler(MessageHandler(channel_filter, handle_channel_post))
    
    app.run_polling()
    
