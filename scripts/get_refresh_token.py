"""One-time: connect Agent Dorcas 1 to your YouTube channel and print a refresh token.

Run on your own computer:
    python scripts/get_refresh_token.py CLIENT_ID CLIENT_SECRET
A browser opens -> pick the Google account / channel -> Allow. Copy the printed token into the
GitHub secret YT_REFRESH_TOKEN. You never need to do this again (as long as the OAuth app is
"In production", see SETUP.md).
"""
import http.server
import sys
import threading
import urllib.parse
import webbrowser

import requests

SCOPES = "https://www.googleapis.com/auth/youtube.upload https://www.googleapis.com/auth/youtube"
PORT = 8765


def main() -> None:
    cid, secret = sys.argv[1], sys.argv[2]
    redirect = f"http://127.0.0.1:{PORT}/"
    got: dict = {}

    class H(http.server.BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            got.update(urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query))
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"Agent Dorcas 1 is connected. You can close this tab.")

        def log_message(self, *a):
            pass

    srv = http.server.HTTPServer(("127.0.0.1", PORT), H)
    threading.Thread(target=srv.handle_request, daemon=True).start()
    url = "https://accounts.google.com/o/oauth2/v2/auth?" + urllib.parse.urlencode({
        "client_id": cid, "redirect_uri": redirect, "response_type": "code", "scope": SCOPES,
        "access_type": "offline", "prompt": "consent"})
    print("Opening:", url)
    webbrowser.open(url)
    while "code" not in got and "error" not in got:
        pass
    if "error" in got:
        sys.exit(f"Authorization failed: {got['error']}")
    r = requests.post("https://oauth2.googleapis.com/token", data={
        "code": got["code"][0], "client_id": cid, "client_secret": secret,
        "redirect_uri": redirect, "grant_type": "authorization_code"}, timeout=60)
    r.raise_for_status()
    print("\nYT_REFRESH_TOKEN =", r.json()["refresh_token"])


if __name__ == "__main__":
    main()
