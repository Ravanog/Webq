import json
import re
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes
from github import Github

# --- CONFIGURATION ---
TELEGRAM_BOT_TOKEN = "YOUR_TELEGRAM_BOT_TOKEN"
CHANNEL_ID = -1001234567890  # Replace with your Telegram Channel ID (include the -100 prefix)

GITHUB_TOKEN = "YOUR_GITHUB_PERSONAL_ACCESS_TOKEN"
REPO_NAME = "your-username/your-repo-name"  # e.g., "hari/moviez-site"
JSON_FILE_PATH = "movies.json" # Path to movies.json in repo

# --- GITHUB HELPER FUNCTION ---
def update_github_json(new_movie_data):
    g = Github(GITHUB_TOKEN)
    repo = g.get_repo(REPO_NAME)
    
    # Fetch current movies.json from GitHub
    contents = repo.get_contents(JSON_FILE_PATH)
    current_data = json.loads(contents.decoded_content.decode('utf-8'))
    
    if "popular" not in current_data:
        current_data["popular"] = []
    
    # Check if movie already exists to prevent duplicates
    existing_titles = [m.get("title", "").lower() for m in current_data["popular"]]
    if new_movie_data.get("title", "").lower() in existing_titles:
        print(f"Skipped duplicate: {new_movie_data.get('title')}")
        return False

    # Insert new movie at the top
    current_data["popular"].insert(0, new_movie_data)
    
    # Update GitHub
    updated_json_str = json.dumps(current_data, indent=2)
    repo.update_file(
        path=contents.path,
        message=f"Bot: Added {new_movie_data['title']} from Channel",
        content=updated_json_str,
        sha=contents.sha
    )
    return True

# --- CHANNEL POST PARSER ---
async def handle_channel_post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    post = update.channel_post
    if not post or not (post.text or post.caption):
        return

    # Extract text from standard message or image caption
    content = post.text if post.text else post.caption
    
    # Simple check to ensure it's a movie post
    if "#movie" not in content.lower() and "title:" not in content.lower():
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

        # If poster isn't provided as a link, but an image was uploaded with caption
        if "poster" not in movie_dict and post.photo:
            # Gets the high-res photo link via Telegram File ID (Optional extension)
            photo_file = await context.bot.get_file(post.photo[-1].file_id)
            movie_dict["poster"] = photo_file.file_path

        if "title" in movie_dict:
            success = update_github_json(movie_dict)
            if success:
                print(f"Successfully published {movie_dict['title']} to website!")

    except Exception as e:
        print(f"Error parsing channel post: {str(e)}")

# --- MAIN RUNNER ---
if __name__ == '__main__':
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    
    # Listen only to channel posts from the specified channel
    channel_filter = filters.Chat(chat_id=CHANNEL_ID) & filters.UpdateType.CHANNEL_POST
    app.add_handler(MessageHandler(channel_filter, handle_channel_post))
    
    print("Bot is listening for channel posts...")
    app.run_polling()
