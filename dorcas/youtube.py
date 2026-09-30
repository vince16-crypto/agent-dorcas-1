"""Step 6: upload to YouTube with the Data API v3 (plain HTTP, resumable upload)."""
from __future__ import annotations

import datetime as dt
import json
import pathlib
import time
from zoneinfo import ZoneInfo

import requests

from . import config

TOKEN_URL = "https://oauth2.googleapis.com/token"
API = "https://www.googleapis.com/youtube/v3"
UPLOAD = "https://www.googleapis.com/upload/youtube/v3"


def access_token() -> str:
    for name in ("YT_CLIENT_ID", "YT_CLIENT_SECRET", "YT_REFRESH_TOKEN"):
        if not getattr(config, name):
            raise RuntimeError(f"{name} is not set")
    r = requests.post(TOKEN_URL, data={
        "client_id": config.YT_CLIENT_ID, "client_secret": config.YT_CLIENT_SECRET,
        "refresh_token": config.YT_REFRESH_TOKEN, "grant_type": "refresh_token"}, timeout=60)
    r.raise_for_status()
    return r.json()["access_token"]


def _auth(tok: str) -> dict:
    return {"Authorization": f"Bearer {tok}"}


def publish_at(now: dt.datetime | None = None) -> str | None:
    """Next brand publish slot (default 16:00 America/New_York), at least 30 min from now."""
    if config.PUBLISH_IMMEDIATELY:
        return None
    et = ZoneInfo("America/New_York")
    now = (now or dt.datetime.now(dt.timezone.utc)).astimezone(et)
    hh, mm = map(int, config.BRAND["publish_schedule"]["publish_time_et"].split(":"))
    slot = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
    if slot < now + dt.timedelta(minutes=30):
        slot = now + dt.timedelta(minutes=45)
    return slot.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")


def build_metadata(plan: dict, hold_private: bool = False) -> dict:
    b = config.BRAND
    title = b["title_pattern"].format(title=plan["title"])
    if len(title) > 100:
        title = f"{plan['title']} | {b['channel_name']}"[:100]
    tags, total = [], 0
    for t in list(dict.fromkeys(plan.get("tags", []) + b["default_tags"])):
        t = t.replace("<", "").replace(">", "").strip()
        if t and total + len(t) + 3 <= 480:
            tags.append(t)
            total += len(t) + 3
    desc = (plan["description"].replace("<", "").replace(">", "") +
            f"\n\n🎶 New songs from {b['channel_name']} every Monday, Wednesday & Friday!")
    status = {"selfDeclaredMadeForKids": b["made_for_kids"], "containsSyntheticMedia": b["contains_synthetic_media"],
              "license": "youtube", "embeddable": True}
    when = publish_at()
    if hold_private:
        status["privacyStatus"] = "private"
    elif when:
        status.update(privacyStatus="private", publishAt=when)
    else:
        status["privacyStatus"] = "public"
    return {
        "snippet": {"title": title, "description": desc.encode("utf-8")[:4900].decode("utf-8", "ignore"),
                    "tags": tags, "categoryId": b["category_id"], "defaultLanguage": "en",
                    "defaultAudioLanguage": "en"},
        "status": status,
    }


def upload(video: pathlib.Path, thumb: pathlib.Path, meta: dict) -> str:
    tok = access_token()
    size = video.stat().st_size
    init = requests.post(
        f"{UPLOAD}/videos", params={"uploadType": "resumable", "part": "snippet,status"},
        headers={**_auth(tok), "Content-Type": "application/json; charset=UTF-8",
                 "X-Upload-Content-Type": "video/mp4", "X-Upload-Content-Length": str(size)},
        data=json.dumps(meta), timeout=60)
    init.raise_for_status()
    url = init.headers["Location"]

    offset, chunk = 0, 16 * 1024 * 1024
    with video.open("rb") as f:
        while True:
            f.seek(offset)
            data = f.read(chunk)
            end = offset + len(data) - 1
            r = None
            for attempt in range(6):
                try:
                    r = requests.put(url, data=data, timeout=600, headers={
                        **_auth(tok), "Content-Length": str(len(data)),
                        "Content-Range": f"bytes {offset}-{end}/{size}"})
                except requests.RequestException:
                    time.sleep(5 * 2 ** attempt)
                    continue
                if r.status_code in (500, 502, 503, 504):
                    time.sleep(5 * 2 ** attempt)
                    continue
                break
            if r is None:
                raise RuntimeError("upload failed: network errors on every retry")
            if r.status_code in (200, 201):
                video_id = r.json()["id"]
                break
            if r.status_code == 308:
                rng = r.headers.get("Range")
                offset = int(rng.split("-")[1]) + 1 if rng else 0
                continue
            r.raise_for_status()

    t = requests.post(f"{UPLOAD}/thumbnails/set", params={"videoId": video_id},
                      headers={**_auth(tok), "Content-Type": "image/jpeg"}, data=thumb.read_bytes(), timeout=120)
    if not t.ok:  # custom thumbnails need a phone-verified channel; don't fail the run over it
        print(f"[youtube] thumbnail not set ({t.status_code}): {t.text[:200]}")

    if config.YT_PLAYLIST_ID:
        requests.post(f"{API}/playlistItems", params={"part": "snippet"}, headers=_auth(tok), json={
            "snippet": {"playlistId": config.YT_PLAYLIST_ID,
                        "resourceId": {"kind": "youtube#video", "videoId": video_id}}}, timeout=60)
    return video_id


def apply_branding(banner: pathlib.Path) -> None:
    """Channel description, keywords, country and banner. (Name + profile photo must be set in Studio.)"""
    b = config.BRAND
    tok = access_token()
    me = requests.get(f"{API}/channels", params={"part": "brandingSettings", "mine": "true"},
                      headers=_auth(tok), timeout=60)
    me.raise_for_status()
    ch = me.json()["items"][0]
    up = requests.post(f"{UPLOAD}/channelBanners/insert", headers={**_auth(tok), "Content-Type": "image/png"},
                       data=banner.read_bytes(), timeout=300)
    up.raise_for_status()
    keywords = " ".join(f'"{k}"' if " " in k else k for k in b["channel_keywords"])
    branding = ch.get("brandingSettings", {})
    branding.setdefault("channel", {}).update(
        {"description": b["channel_description"], "keywords": keywords, "defaultLanguage": "en", "country": "US"})
    branding.setdefault("image", {})["bannerExternalUrl"] = up.json()["url"]
    r = requests.put(f"{API}/channels", params={"part": "brandingSettings"}, headers=_auth(tok),
                     json={"id": ch["id"], "brandingSettings": branding}, timeout=60)
    r.raise_for_status()
    print(f"[youtube] branding applied to channel {ch['id']}")
