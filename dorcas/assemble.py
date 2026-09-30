"""Step 4: cut the song, clips and stills into a finished 1080p sing-along video with ffmpeg."""
from __future__ import annotations

import pathlib
import subprocess

from . import config

W, H, FPS = config.WIDTH, config.HEIGHT, config.FPS
ENC = ["-c:v", "libx264", "-preset", "medium", "-crf", "19", "-pix_fmt", "yuv420p", "-r", str(FPS)]
END_CARD_SECONDS = 6


def run(cmd: list[str]) -> None:
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *cmd], check=True)


def probe_duration(path: pathlib.Path) -> float:
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of",
                          "default=nw=1:nk=1", str(path)], capture_output=True, text=True, check=True)
    return float(out.stdout.strip())


def ken_burns(image: pathlib.Path, seconds: float, out: pathlib.Path, variant: int) -> None:
    frames = max(1, int(round(seconds * FPS)))
    moves = [
        ("1+0.12*on/{f}", "iw/2-(iw/zoom/2)", "ih/2-(ih/zoom/2)"),            # slow zoom in, centre
        ("1.12-0.12*on/{f}", "iw/2-(iw/zoom/2)", "ih/2-(ih/zoom/2)"),         # slow zoom out
        ("1.1", "(iw-iw/zoom)*on/{f}", "ih/2-(ih/zoom/2)"),                   # pan left->right
        ("1.1", "(iw-iw/zoom)*(1-on/{f})", "ih/2-(ih/zoom/2)"),               # pan right->left
    ]
    z, x, y = (m.format(f=frames) for m in moves[variant % len(moves)])
    vf = (f"scale={W * 2}:{H * 2}:force_original_aspect_ratio=increase,crop={W * 2}:{H * 2},"
          f"zoompan=z='{z}':x='{x}':y='{y}':d={frames}:s={W}x{H}:fps={FPS},setsar=1")
    run(["-loop", "1", "-i", str(image), "-vf", vf, "-frames:v", str(frames), "-an", *ENC, str(out)])


def clip_segment(clip: pathlib.Path, seconds: float, out: pathlib.Path) -> None:
    vf = f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},fps={FPS},setsar=1"
    run(["-i", str(clip), "-t", f"{seconds:.3f}", "-vf", vf, "-an", *ENC, str(out)])


def build_segments(plan: dict, stills: list[pathlib.Path], clips: dict[int, pathlib.Path],
                   work: pathlib.Path) -> list[pathlib.Path]:
    segs: list[pathlib.Path] = []
    for i, (s, still) in enumerate(zip(plan["sections"], stills)):
        dur = s["duration_ms"] / 1000
        clip = clips.get(i)
        if clip:
            clen = min(probe_duration(clip), dur)
            a = work / f"seg_{i:02d}a.mp4"
            clip_segment(clip, clen, a)
            segs.append(a)
            if dur - clen > 0.05:
                b = work / f"seg_{i:02d}b.mp4"
                ken_burns(still, dur - clen, b, i)
                segs.append(b)
        else:
            p = work / f"seg_{i:02d}.mp4"
            ken_burns(still, dur, p, i)
            segs.append(p)
    return segs


def end_card(work: pathlib.Path) -> pathlib.Path:
    """Branded outro: mascot + 'new songs every Mon, Wed & Fri'."""
    from PIL import Image, ImageDraw, ImageFont
    img = Image.new("RGB", (W, H), config.BRAND["palette"]["purple"])
    face = Image.open(config.PROFILE_PNG).convert("RGB").resize((620, 620))
    mask = Image.new("L", face.size, 0)
    ImageDraw.Draw(mask).ellipse((0, 0, *face.size), fill=255)
    img.paste(face, (160, 230), mask)
    d = ImageDraw.Draw(img)
    big = ImageFont.truetype(str(config.FONT_BOLD), 110)
    mid = ImageFont.truetype(str(config.FONT_BOLD), 60)
    d.text((880, 330), "Thanks for", font=big, fill="#FFFFFF")
    d.text((880, 450), "singing!", font=big, fill=config.BRAND["palette"]["yellow"])
    d.text((880, 620), "New songs every", font=mid, fill="#FFFFFF")
    d.text((880, 695), "Mon • Wed • Fri", font=mid, fill=config.BRAND["palette"]["teal"])
    still = work / "endcard.png"
    img.save(still)
    out = work / "seg_zz_end.mp4"
    ken_burns(still, END_CARD_SECONDS, out, 0)
    return out


def _round_logo(out: pathlib.Path, size: int = 150) -> pathlib.Path:
    from PIL import Image, ImageDraw
    face = Image.open(config.PROFILE_PNG).convert("RGBA").resize((size, size))
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, size - 1, size - 1), fill=235)
    face.putalpha(mask)
    face.save(out)
    return out


def _ts(sec: float) -> str:
    h, rem = divmod(sec, 3600)
    m, s = divmod(rem, 60)
    return f"{int(h)}:{int(m):02d}:{s:05.2f}"


def write_lyrics_ass(plan: dict, path: pathlib.Path) -> None:
    head = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Lyric,Poppins,74,&H00FFFFFF,&H003FD2FF,&H00731F4A,&H96000000,-1,0,0,0,100,100,0,0,1,6,3,2,80,80,70,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    events, t = [], 0.0
    for s in plan["sections"]:
        dur = s["duration_ms"] / 1000
        lines = [ln for ln in s["lines"] if ln.strip()]
        if lines:
            step = dur / len(lines)
            for k, ln in enumerate(lines):
                start, end = t + k * step + 0.15, t + (k + 1) * step - 0.1
                text = ln.replace("{", "(").replace("}", ")")
                events.append(f"Dialogue: 0,{_ts(start)},{_ts(end)},Lyric,,0,0,0,,{{\\fad(150,150)}}{text}")
        t += dur
    path.write_text(head + "\n".join(events) + "\n")


def assemble(plan: dict, song: pathlib.Path, stills: list[pathlib.Path], clips: dict[int, pathlib.Path],
             work: pathlib.Path, out: pathlib.Path) -> pathlib.Path:
    work.mkdir(parents=True, exist_ok=True)
    segs = build_segments(plan, stills, clips, work) + [end_card(work)]
    concat = work / "concat.txt"
    concat.write_text("".join(f"file '{p.resolve()}'\n" for p in segs))
    body = work / "body.mp4"
    run(["-f", "concat", "-safe", "0", "-i", str(concat), "-c", "copy", str(body)])

    ass = work / "lyrics.ass"
    write_lyrics_ass(plan, ass)
    logo = _round_logo(work / "logo.png")
    fonts = config.FONT_BOLD.parent
    vf = (f"[0:v]subtitles='{ass}':fontsdir='{fonts}'[sub];"
          f"[2:v]format=rgba[lg];"
          f"[sub][lg]overlay=W-w-40:40:enable='lt(t,{probe_duration(body) - END_CARD_SECONDS})'[v]")
    run(["-i", str(body), "-i", str(song), "-i", str(logo),
         "-filter_complex", vf, "-map", "[v]", "-map", "1:a",
         "-af", "apad,afade=t=out:st={:.2f}:d=3".format(probe_duration(body) - 3),
         "-t", f"{probe_duration(body):.3f}", *ENC, "-c:a", "aac", "-b:a", "192k",
         "-movflags", "+faststart", str(out)])
    return out
