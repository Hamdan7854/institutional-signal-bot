"""Chhota HTTP health server. Render ke 'Web Service' ko ek khula PORT chahiye hota hai, warna deploy 'No open ports detected' par fail/restart hota hai. PORT env na ho to kuch nahi karta."""
import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer


class _H(BaseHTTPRequestHandler):
    def do_GET(self):
        body = b"MICP bot alive"
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    do_HEAD = do_GET

    def log_message(self, *a):
        pass


def start():
    port = os.getenv("PORT")
    if not port:
        return None
    srv = HTTPServer(("0.0.0.0", int(port)), _H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    print(f"[health] listening on :{port}")
    return srv
