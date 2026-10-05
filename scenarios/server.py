"""A tiny local API for trying Proofrun without any external service.

Endpoints
  GET  /health              -> 200
  POST /login               -> 200 + access_token (password: demo-password)
  GET  /me                  -> 200 + user id (requires Bearer token)
  GET  /users/<id>/orders   -> 200 + orders  (requires Bearer token)

Run it:
  python scenarios/server.py            # healthy
  python scenarios/server.py --break    # /me returns 500
"""

from __future__ import annotations

import argparse
import json
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

TOKEN = "demo-token-123"
PASSWORD = "demo-password"
BROKEN = False


class Handler(BaseHTTPRequestHandler):
    """HTTP request handler for the mock API server."""

    def log_message(self, format: str, *args: object) -> None:  # noqa: A002
        """Silence request logging."""

    def _send(self, code: int, body: dict | list) -> None:
        data = json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _authed(self) -> bool:
        return self.headers.get("Authorization") == f"Bearer {TOKEN}"

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/health":
            return self._send(200, {"status": "ok"})
        if self.path == "/me":
            if not self._authed():
                return self._send(401, {"error": "unauthorized"})
            if BROKEN:
                time.sleep(0.05)
                return self._send(500, {"error": "profile service unavailable"})
            return self._send(200, {"id": 42, "email": "demo@example.com"})
        if self.path.startswith("/users/42/orders"):
            if not self._authed():
                return self._send(401, {"error": "unauthorized"})
            return self._send(200, [{"id": 1, "total": 19.99}])
        self._send(404, {"error": "not found"})

    def do_POST(self) -> None:  # noqa: N802
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length) or b"{}")
        if self.path == "/login":
            if body.get("password") == PASSWORD:
                return self._send(200, {"access_token": TOKEN, "expires_in": 3600})
            return self._send(401, {"error": "bad credentials"})
        self._send(404, {"error": "not found"})


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=(__doc__ or "").split("\n")[0])
    parser.add_argument("--port", type=int, default=8099)
    parser.add_argument(
        "--break",
        dest="broken",
        action="store_true",
        help="make GET /me return 500",
    )
    args = parser.parse_args()
    BROKEN = args.broken
    print(
        f"Mock API on http://127.0.0.1:{args.port}  (broken={BROKEN})  Ctrl+C to stop"
    )
    HTTPServer(("127.0.0.1", args.port), Handler).serve_forever()
