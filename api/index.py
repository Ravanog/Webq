import json
import os
from http.server import BaseHTTPRequestHandler

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        # Serve movies data on /api/movies
        if self.path.startswith('/api/movies') or self.path == '/api':
            movies_path = os.path.join(os.path.dirname(__file__), '..', 'movies.json')
            
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
        else:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b'{"error": "Not found"}')

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
