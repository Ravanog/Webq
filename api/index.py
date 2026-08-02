import json
import os
from http.server import BaseHTTPRequestHandler

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        # Locate movies.json in root directory
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        movies_path = os.path.join(base_dir, 'movies.json')

        try:
            with open(movies_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception:
            data = {"popular": [], "bannerSlides": []}

        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode('utf-8'))

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
        
