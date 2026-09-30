"""Tiny JSON log of past uploads so Dorcas never repeats itself."""
from __future__ import annotations

import datetime as dt
import json

from . import config


def load() -> list[dict]:
    if config.HISTORY_FILE.exists():
        return json.loads(config.HISTORY_FILE.read_text())
    return []


def recent_topics(n: int) -> set[str]:
    return {h["topic"] for h in load()[-n:]}


def recent_titles(n: int) -> list[str]:
    return [h["title"] for h in load()[-n:]]


def add(entry: dict) -> None:
    items = load()
    entry = {"date": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), **entry}
    items.append(entry)
    config.HISTORY_FILE.write_text(json.dumps(items, indent=2))
