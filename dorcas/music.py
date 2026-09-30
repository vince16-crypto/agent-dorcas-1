"""Step 2: turn the plan into a finished song (ElevenLabs Music API)."""
from __future__ import annotations

import pathlib
import subprocess
import time

import requests

from . import config

API = "https://api.elevenlabs.io/v1/music"


def make_song(plan: dict, out: pathlib.Path) -> pathlib.Path:
    out.parent.mkdir(parents=True, exist_ok=True)
    if config.DRY_RUN:
        return _mock_song(plan, out)
    if not config.ELEVENLABS_API_KEY:
        raise RuntimeError("ELEVENLABS_API_KEY is not set")

    composition = {
        "positive_global_styles": plan["positive_styles"],
        "negative_global_styles": plan["negative_styles"] + ["explicit lyrics", "profanity"],
        "sections": [
            {
                "section_name": s["name"],
                "positive_local_styles": ["instrumental groove"] if not s["lines"] else [],
                "negative_local_styles": [],
                "duration_ms": s["duration_ms"],
                "lines": s["lines"],
            }
            for s in plan["sections"]
        ],
    }
    body = {"composition_plan": composition, "model_id": config.ELEVENLABS_MUSIC_MODEL,
            "respect_sections_durations": True}
    try:
        audio = _post(body)
    except requests.HTTPError as e:
        # Fallback: a single text prompt carrying the lyrics.
        print(f"[music] composition plan rejected ({e}); retrying with prompt")
        lyrics = "\n\n".join(f"[{s['name']}]\n" + "\n".join(s["lines"]) for s in plan["sections"])
        prompt = (f"{', '.join(plan['positive_styles'])}. A {plan['bpm']} BPM children's song. "
                  f"Sing exactly these lyrics:\n{lyrics}")[:4000]
        audio = _post({"prompt": prompt, "music_length_ms": config.SONG_SECONDS * 1000,
                       "model_id": config.ELEVENLABS_MUSIC_MODEL})
    out.write_bytes(audio)
    return out


def _post(body: dict) -> bytes:
    for attempt in range(4):
        r = requests.post(
            API, params={"output_format": "mp3_44100_192"},
            headers={"xi-api-key": config.ELEVENLABS_API_KEY, "Content-Type": "application/json"},
            json=body, timeout=900,
        )
        if r.status_code in (429, 500, 502, 503):
            time.sleep(20 * (attempt + 1))
            continue
        r.raise_for_status()
        return r.content
    r.raise_for_status()
    return b""


def _mock_song(plan: dict, out: pathlib.Path) -> pathlib.Path:
    secs = sum(s["duration_ms"] for s in plan["sections"]) / 1000
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i",
         f"sine=frequency=440:beep_factor=4:duration={secs}", "-ac", "2", "-b:a", "128k", str(out)],
        check=True,
    )
    return out
