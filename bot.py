import os
import json
import logging
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes
from github import Github

# Setup Logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Load Environment Variables (Passed by Koyeb)
TELEGRAM_BOT_TOKEN = os.getenv("8675260165:AAHaMWq6b5-nVy_42Szt_FQqT04kwZifPMM")
CHANNEL_ID = int(os.getenv("CHANNEL_ID", "-1003224239956"))
GITHUB_TOKEN = os.getenv("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")
REPO_NAME = os.getenv("Ravanog/Webq")  # e.g., "username/moviez-app"
JSON_FILE_PATH = os.getenv("JSON_FILE_PATH", "movies.json")

def update_github_json(new_movie_data: dict) -> bool:
    """Fetches movies.json, appends new movie, and commits back to GitHub."""
    try:
        g = Github(GITHUB_TOKEN)
        repo = g.get_repo(REPO_NAME)
        
        # Get existing file content
        contents = repo.get_contents(JSON_FILE_PATH)
        current_data = json.loads(contents.decoded_content.decode('utf-8'))
        
        if "popular" not in current_data:
            current_data["popular"] = []
            
        # Prevent duplicate entries by title
        existing_titles = [m.get("title", "").strip().lower() for m in current_data["popular"]]
        if new_movie_data.get("title", "").strip().lower() in existing_titles:
            logging.info(f"Skipping duplicate movie: {new_movie_data.get('title')}")
            return False

        # Add new movie at the beginning of the array
        current_data["popular"].insert(0, new_movie_data)
        
        # Write back to GitHub
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

    # Extract text from standard text post or photo caption
    content = post.text or post.caption
    if not content:
        return

    # Filter out posts that don't match our key format
    if "title:" not in content.lower():
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
        logging.error(f"Error processing post: {str(e)}")

if __name__ == '__main__':
    if not all([TELEGRAM_BOT_TOKEN, CHANNEL_ID, GITHUB_TOKEN, REPO_NAME]):
        raise ValueError("Missing critical Environment Variables. Check your Koyeb settings.")

    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    
    # Filter messages coming ONLY from your targeted Telegram Channel
    channel_filter = filters.Chat(chat_id=CHANNEL_ID) & filters.UpdateType.CHANNEL_POST
    app.add_handler(MessageHandler(channel_filter, handle_channel_post))
    
    logging.info("Starting Koyeb Bot listener...")
    app.run_polling()
