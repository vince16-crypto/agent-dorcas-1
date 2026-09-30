"""Agent Dorcas 1 — one full run: plan -> song -> visuals -> video -> thumbnail -> QA -> upload.

    python -m dorcas.main                # normal run (used by the scheduler)
    DORCAS_DRY_RUN=1 python -m dorcas.main   # no paid APIs, no upload; renders a sample video
    python -m dorcas.main --branding     # push banner/description/keywords to the channel
"""
from __future__ import annotations

import datetime as dt
import json
import sys

from . import assemble, config, history, music, planner, review, thumbnail, visuals, youtube


def run() -> dict:
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    work = config.OUT_DIR / stamp
    work.mkdir(parents=True, exist_ok=True)
    log = lambda m: print(f"[dorcas1 {dt.datetime.now():%H:%M:%S}] {m}", flush=True)  # noqa: E731

    plan = planner.plan_song()
    (work / "plan.json").write_text(json.dumps(plan, indent=2))
    log(f"planned '{plan['title']}' ({plan['topic']}), {len(plan['sections'])} sections")

    song = music.make_song(plan, work / "song.mp3")
    log(f"song ready ({assemble.probe_duration(song):.1f}s)")

    stills = visuals.make_scene_images(plan, work / "scenes")
    log(f"{len(stills)} scene images ready")

    clips = {}
    for i, s in enumerate(plan["sections"]):
        if s.get("animate"):
            c = visuals.animate(stills[i], s["scene"], work / "scenes" / f"clip_{i:02d}.mp4")
            if c:
                clips[i] = c
    log(f"{len(clips)} animated clips ready")

    video = assemble.assemble(plan, song, stills, clips, work / "build", work / "video.mp4")
    log(f"video rendered ({assemble.probe_duration(video):.1f}s)")

    art = visuals.make_thumbnail_art(plan, work / "thumb_art.png", stills[0] if stills else None)
    thumb = thumbnail.make_thumbnail(art, plan["thumbnail_text"], work / "thumbnail.jpg")

    qa = review.check_video(video, thumb, plan, work)
    log(f"QA: {'pass' if qa.get('ok') else 'FAIL ' + str(qa.get('issues'))}")

    result = {"topic": plan["topic"], "title": plan["title"], "qa": qa, "workdir": str(work)}
    if config.DRY_RUN:
        log("dry run: skipping upload")
        return result

    meta = youtube.build_metadata(plan, hold_private=not qa.get("ok"))
    vid = youtube.upload(video, thumb, meta)
    result.update(video_id=vid, url=f"https://youtu.be/{vid}",
                  privacy=meta["status"]["privacyStatus"], publish_at=meta["status"].get("publishAt"))
    history.add({k: result[k] for k in ("topic", "title", "video_id", "url", "privacy", "publish_at")} |
                {"qa_ok": bool(qa.get("ok"))})
    log(f"uploaded {result['url']} ({result['privacy']}, publishAt={result['publish_at']})")
    return result


if __name__ == "__main__":
    if "--branding" in sys.argv:
        youtube.apply_branding(config.ROOT / "brand" / "banner.png")
    else:
        print(json.dumps(run(), indent=2))
