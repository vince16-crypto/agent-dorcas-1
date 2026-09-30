"""Step 1: pick a fresh topic and have Claude write an original song + shot list + SEO."""
from __future__ import annotations

import json
import random

from . import claude, config, history

PLANNER_SYSTEM = """You are Agent Dorcas 1, head writer and producer for the YouTube Kids music channel
"{name}". Mascot: {mascot}. Friends: {friends}.
Audience: {audience}. Music style: {style}.

The niche you compete in is culturally rich preschool music (think modern learning songs with hip-hop, R&B,
gospel and bounce grooves, joyful Black family representation). Rules you never break:
- Every lyric is 100% ORIGINAL. Never quote or closely paraphrase any copyrighted song. Public-domain nursery
  rhymes may be remixed, with new verses. Never use the traditional "Happy Birthday to You" melody or words.
- Never mention, imitate or reference any other channel, brand, show, or real person/celebrity.
- Age-appropriate for 1-6 year olds: simple words, lots of repetition, call-and-response, clear learning goal,
  positive, nothing scary, no brand names, no violence, no romance, no unsafe behaviour.
- Characters are only Nia, Kofi, Grandma Dot and Beau the puppy (plus generic background kids/grown-ups).
"""

PLANNER_TASK = """Write the next video.
Topic: {topic}  (learning goal: {goal})
Target song length: {seconds} seconds. Recently used song titles (avoid similar hooks): {recent}
Pick one visual theme (or invent a fitting one): {themes}

Return JSON with exactly these keys:
{{
 "title": "catchy song title, max 45 chars, starts with the topic keyword parents search for",
 "hook": "the 1-line chorus hook",
 "genre": "one of the channel grooves",
 "bpm": 90-130,
 "positive_styles": ["6-10 short music style descriptors incl. genre, tempo, 'bright child lead vocal', 'warm adult backing vocals', instruments"],
 "negative_styles": ["explicit", "dark", "sad", "distorted", "..."],
 "sections": [
   {{"name": "Intro|Verse 1|Chorus|Verse 2|Chorus|Bridge|Chorus|Outro...",
     "duration_ms": 8000-16000,
     "lines": ["sung lyric lines for this section (can be [] for instrumental intro)"],
     "scene": "one vivid visual description for this section: setting, which characters, what they do, camera move. Flat 2D children's cartoon style.",
     "animate": true/false}}
 ],
 "thumbnail_text": "2-4 BIG words for the thumbnail",
 "thumbnail_scene": "what the thumbnail image shows (Nia front and centre, big expression, topic props)",
 "description": "YouTube description, 700-1200 chars: first 150 chars hook with main keywords, what kids learn, sing-along invite, 'Lyrics:' section with full lyrics, 3-5 hashtags at end. No links.",
 "tags": ["12-18 search tags mixing broad (kids songs) and specific (e.g. abc phonics song for toddlers)"]
}}
Constraints: sum of duration_ms must be {seconds}000 +/- 4000; 8-12 sections; the Chorus repeats at least 3 times;
mark exactly {veo} of the most exciting sections "animate": true (these get full animation), the rest false."""


def pick_topic() -> dict:
    used = history.recent_topics(len(config.TOPICS) // 2)
    fresh = [t for t in config.TOPICS if t["topic"] not in used] or config.TOPICS
    return random.choice(fresh)


def plan_song(topic: dict | None = None) -> dict:
    topic = topic or pick_topic()
    if config.DRY_RUN:
        return _mock_plan(topic)
    b = config.BRAND
    system = PLANNER_SYSTEM.format(
        name=b["channel_name"], mascot=b["mascot"]["description"], friends="; ".join(b["mascot"]["friends"]),
        audience=b["audience"], style=b["music_style"],
    )
    task = PLANNER_TASK.format(
        topic=topic["topic"], goal=topic["goal"], seconds=config.SONG_SECONDS,
        recent=json.dumps(history.recent_titles(15)), themes="; ".join(b["visual_themes"]), veo=config.VEO_CLIPS,
    )
    for _ in range(3):
        plan = claude.ask_json(system, task)
        plan["topic"] = topic["topic"]
        review = review_plan(plan)
        if review.get("ok"):
            return _normalise(plan)
        task += f"\n\nA reviewer rejected the previous draft for: {review.get('issues')}. Fix these."
    raise RuntimeError("Could not produce a plan that passed review")


def review_plan(plan: dict) -> dict:
    return claude.ask_json(
        "You are a strict YouTube Kids content-safety and copyright reviewer.",
        "Review this planned kids' song video. Fail it if lyrics copy or closely paraphrase any existing "
        "copyrighted song, reference another channel/brand/celebrity, are not suitable for ages 1-6, have "
        "unclear learning value, or if section durations do not add up to about the target. "
        'Return {"ok": true|false, "issues": ["..."]}.\n\n' + json.dumps(plan),
        max_tokens=1500,
    )


def _normalise(plan: dict) -> dict:
    target = config.SONG_SECONDS * 1000
    total = sum(s["duration_ms"] for s in plan["sections"])
    scale = target / total if total else 1
    for s in plan["sections"]:
        s["duration_ms"] = max(3000, min(120000, int(round(s["duration_ms"] * scale / 100) * 100)))
    # enforce the Veo budget regardless of what the model marked
    budget = config.VEO_CLIPS
    for s in plan["sections"]:
        s["animate"] = bool(s.get("animate")) and budget > 0
        budget -= int(s["animate"])
    plan["title"] = plan["title"][:60]
    return plan


def _mock_plan(topic: dict) -> dict:
    lines = {
        "Intro": [],
        "Chorus": ["Clap your hands and count with me", "One, two, three, it's easy as can be"],
        "Verse 1": ["Nia's got one bright yellow ball", "Kofi's got two, he stacks them tall"],
        "Verse 2": ["Grandma Dot has three red shoes", "Beau the puppy's got four to lose"],
        "Outro": ["Now you can count, yes you can!"],
    }
    order = ["Intro", "Chorus", "Verse 1", "Chorus", "Verse 2", "Chorus", "Outro"]
    per = config.SONG_SECONDS * 1000 // len(order)
    plan = {
        "topic": topic["topic"], "title": f"{topic['topic']} Song", "hook": "Clap your hands and count with me",
        "genre": "kid-friendly hip-hop", "bpm": 100,
        "positive_styles": ["kids hip-hop", "100 bpm", "bright child lead vocal", "handclaps"],
        "negative_styles": ["dark", "explicit"],
        "sections": [
            {"name": n, "duration_ms": per, "lines": lines[n],
             "scene": f"Nia and Kofi dance at a block party ({n})", "animate": i in (1, 3)}
            for i, n in enumerate(order)
        ],
        "thumbnail_text": topic["topic"].upper()[:18], "thumbnail_scene": "Nia smiling with numbers",
        "description": f"Sing and learn {topic['topic']} with Nia! (dry run)",
        "tags": ["kids songs", "dry run"],
    }
    return _normalise(plan)
