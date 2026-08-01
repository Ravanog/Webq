import sys
import os

# Add parent directory to sys.path so Python can find bot.py
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bot import app

# Vercel entrypoint handler
handler = app
