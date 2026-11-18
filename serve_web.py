"""
Buronix Digital Twin Web Application Server
Serves the cleanroom & MAU interactive web app locally.
Usage: python serve_web.py [--port 8080]
"""

import http.server
import socketserver
import webbrowser
import sys
from pathlib import Path

PORT = 8080
if len(sys.argv) > 1 and sys.argv[1].isdigit():
    PORT = int(sys.argv[1])

DIRECTORY = Path(__file__).resolve().parent

class CustomHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(DIRECTORY), **kwargs)

    def end_headers(self):
        # Enable caching-friendly and cross-origin access
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        super().end_headers()

def main():
    with socketserver.TCPServer(("", PORT), CustomHandler) as httpd:
        url = f"http://localhost:{PORT}"
        print("=" * 70)
        print("  BURONIX // SEMICONDUCTOR CLEANROOM DIGITAL TWIN")
        print("  AI-CDCV HVAC Optimization (Phuoc Branch - SAC Engine)")
        print(f"  Live Server listening at: {url}")
        print("=" * 70)
        print("Press Ctrl+C to stop the server.\n")
        try:
            webbrowser.open(url)
        except Exception:
            pass
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nShutting down server. Goodbye!")

if __name__ == "__main__":
    main()
