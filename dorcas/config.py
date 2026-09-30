"""Configuration for Agent Dorcas 1. Everything comes from environment variables
(GitHub Actions secrets in production) so no key ever lives in the repo."""
from __future__ import annotations

import json
import os
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
BRAND = json.loads((ROOT / "brand" / "brand.json").read_text())
TOPICS = json.loads((ROOT / "data" / "topics.json").read_text())
HISTORY_FILE = ROOT / "data" / "history.json"
FONT_BOLD = ROOT / "assets" / "fonts" / "Poppins-Bold.ttf"
MASCOT_PNG = ROOT / "brand" / "nia_ref.png"
PROFILE_PNG = ROOT / "brand" / "profile.png"
OUT_DIR = pathlib.Path(os.getenv("DORCAS_OUT", ROOT / "out"))


def env(name: str, default: str | None = None) -> str | None:
    v = os.getenv(name)
    return v if v not in (None, "") else default


# Mock every paid API and skip the upload. Used for tests and first-time checks.
DRY_RUN = env("DORCAS_DRY_RUN", "0") == "1"

# --- Claude (planning, lyrics, SEO, quality review) ---
ANTHROPIC_API_KEY = env("ANTHROPIC_API_KEY")
CLAUDE_MODEL = env("CLAUDE_MODEL", "claude-sonnet-5-5")

# --- Songs ---
ELEVENLABS_API_KEY = env("ELEVENLABS_API_KEY")
ELEVENLABS_MUSIC_MODEL = env("ELEVENLABS_MUSIC_MODEL", "music_v1")
SONG_SECONDS = int(env("SONG_SECONDS", "120"))

# --- Visuals (Google Veo = the model behind Google Flow) ---
GEMINI_API_KEY = env("GEMINI_API_KEY")
GEMINI_IMAGE_MODEL = env("GEMINI_IMAGE_MODEL", "gemini-3.1-flash-image")
VEO_MODEL = env("VEO_MODEL", "veo-3.1-generate-preview")
VEO_CLIPS = int(env("VEO_CLIPS", "4"))          # animated 8s clips per video (cost control)
VEO_RESOLUTION = env("VEO_RESOLUTION", "1080p")

# --- YouTube ---
YT_CLIENT_ID = env("YT_CLIENT_ID")
YT_CLIENT_SECRET = env("YT_CLIENT_SECRET")
YT_REFRESH_TOKEN = env("YT_REFRESH_TOKEN")
YT_PLAYLIST_ID = env("YT_PLAYLIST_ID")          # optional: add every upload to this playlist
# By default each video is scheduled to go public at brand publish_time_et (16:00 ET).
# Set PUBLISH_IMMEDIATELY=1 to go public the moment the upload finishes.
PUBLISH_IMMEDIATELY = env("PUBLISH_IMMEDIATELY", "0") == "1"

WIDTH, HEIGHT, FPS = 1920, 1080, 30
