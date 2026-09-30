"""Automatic quality gate: Claude looks at sampled frames + thumbnail before anything goes public.
A failed check still uploads the video, but as PRIVATE, so nothing broken reaches kids."""
from __future__ import annotations

import pathlib
import subprocess

from . import assemble, claude, config


def sample_frames(video: pathlib.Path, work: pathlib.Path, n: int = 6) -> list[pathlib.Path]:
    dur = assemble.probe_duration(video)
    frames = []
    for i in range(n):
        t = dur * (i + 0.5) / n
        p = work / f"qa_{i}.jpg"
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{t:.2f}", "-i", str(video),
                        "-frames:v", "1", "-vf", "scale=768:-2", str(p)], check=True)
        frames.append(p)
    return frames


def check_video(video: pathlib.Path, thumb: pathlib.Path, plan: dict, work: pathlib.Path) -> dict:
    if config.DRY_RUN:
        return {"ok": True, "issues": [], "note": "dry run"}
    frames = sample_frames(video, work)
    content = [claude.image_block(p) for p in frames + [thumb]]
    content.append({"type": "text", "text": (
        "These are 6 frames from a children's music video (ages 1-6) and its thumbnail (last image), "
        f"titled '{plan['title']}'. Fail the video if you see ANY of: scary or inappropriate imagery, "
        "disturbing/distorted faces or bodies, garbled on-screen text inside the artwork, realistic photos of "
        "real children, logos or characters from other brands/shows, or a thumbnail that misrepresents the "
        "video. Minor art-style inconsistency is fine. "
        'Return {"ok": true|false, "issues": ["..."]}.')})
    return claude.ask_json("You are a meticulous YouTube Kids visual QA reviewer.", content, max_tokens=1200)
