"""Thin Claude Messages API client (plain HTTP, no SDK pin)."""
from __future__ import annotations

import base64
import json
import pathlib
import re
import time

import requests

from . import config

API = "https://api.anthropic.com/v1/messages"


def ask(system: str, content, max_tokens: int = 8000) -> str:
    if not config.ANTHROPIC_API_KEY:
        raise RuntimeError("ANTHROPIC_API_KEY is not set")
    body = {
        "model": config.CLAUDE_MODEL,
        "max_tokens": max_tokens,
        "system": system,
        "messages": [{"role": "user", "content": content}],
    }
    for attempt in range(5):
        r = requests.post(
            API,
            headers={
                "x-api-key": config.ANTHROPIC_API_KEY,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json=body,
            timeout=600,
        )
        if r.status_code in (429, 500, 502, 503, 529):
            time.sleep(10 * (attempt + 1))
            continue
        r.raise_for_status()
        return "".join(b.get("text", "") for b in r.json()["content"] if b.get("type") == "text")
    r.raise_for_status()
    return ""


def ask_json(system: str, content, max_tokens: int = 8000) -> dict:
    text = ask(system + "\n\nRespond with a single JSON object only, no prose, no code fences.", content, max_tokens)
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        raise ValueError(f"Claude did not return JSON: {text[:300]}")
    return json.loads(m.group(0))


def image_block(path: pathlib.Path) -> dict:
    media = "image/png" if path.suffix.lower() == ".png" else "image/jpeg"
    return {
        "type": "image",
        "source": {"type": "base64", "media_type": media, "data": base64.b64encode(path.read_bytes()).decode()},
    }
