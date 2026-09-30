"""Step 3: scene art (Gemini image model) and animated clips (Veo, the model behind Google Flow)."""
from __future__ import annotations

import pathlib
import subprocess
import time

from . import config

STYLE = ("Flat 2D children's cartoon, bold clean outlines, soft shading, bright saturated colours "
         "(purple, orange, sunny yellow, teal), joyful, preschool TV quality, 16:9 widescreen, "
         "no text, no letters, no logos, no watermarks.")


def _client():
    from google import genai
    if not config.GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY is not set")
    return genai.Client(api_key=config.GEMINI_API_KEY)


def make_scene_images(plan: dict, workdir: pathlib.Path) -> list[pathlib.Path]:
    workdir.mkdir(parents=True, exist_ok=True)
    paths = []
    anchor = None  # first finished scene is reused as a style/character anchor
    for i, s in enumerate(plan["sections"]):
        p = workdir / f"scene_{i:02d}.png"
        if config.DRY_RUN:
            _mock_image(p, f"{i}: {s['name']}")
        else:
            _gen_image(_scene_prompt(s["scene"]), p, anchor)
            anchor = anchor or p
        paths.append(p)
    return paths


def make_thumbnail_art(plan: dict, out: pathlib.Path, anchor: pathlib.Path | None) -> pathlib.Path:
    if config.DRY_RUN:
        return _mock_image(out, "thumbnail")
    prompt = (f"YouTube thumbnail art. {plan['thumbnail_scene']}. Nia is large in the right half, huge happy "
              f"expression, simple uncluttered background, strong contrast, leave the left 45% fairly plain for "
              f"a title. {STYLE}")
    return _gen_image(prompt, out, anchor)


def _scene_prompt(scene: str) -> str:
    b = config.BRAND["mascot"]
    return (f"{scene}\nMain character Nia must match the reference image exactly: {b['description']} "
            f"Other characters if present: {'; '.join(b['friends'])}. {STYLE}")


def _gen_image(prompt: str, out: pathlib.Path, anchor: pathlib.Path | None) -> pathlib.Path:
    from google.genai import types
    client = _client()
    parts = [prompt, types.Part.from_bytes(data=config.MASCOT_PNG.read_bytes(), mime_type="image/png")]
    if anchor:
        parts.append("Match the art style and character designs of this earlier frame:")
        parts.append(types.Part.from_bytes(data=anchor.read_bytes(), mime_type="image/png"))
    for attempt in range(4):
        try:
            resp = client.models.generate_content(
                model=config.GEMINI_IMAGE_MODEL, contents=parts,
                config=types.GenerateContentConfig(
                    response_modalities=["IMAGE"], image_config=types.ImageConfig(aspect_ratio="16:9")),
            )
            for part in resp.candidates[0].content.parts:
                if getattr(part, "inline_data", None) and part.inline_data.data:
                    out.write_bytes(part.inline_data.data)
                    return out
            raise RuntimeError("image model returned no image")
        except Exception as e:  # noqa: BLE001 - retry any transient API failure
            print(f"[image] attempt {attempt + 1} failed: {e}")
            time.sleep(15 * (attempt + 1))
    raise RuntimeError(f"image generation failed for {out.name}")


def animate(image: pathlib.Path, scene: str, out: pathlib.Path) -> pathlib.Path | None:
    """Image-to-video with Veo. Returns None on failure so the video falls back to a Ken Burns still."""
    if config.DRY_RUN:
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-loop", "1", "-i", str(image), "-t", "8",
                        "-vf", f"scale={config.WIDTH}:{config.HEIGHT},zoompan=z='1+0.002*on':d=1:s={config.WIDTH}x{config.HEIGHT}:fps={config.FPS}",
                        "-pix_fmt", "yuv420p", str(out)], check=True)
        return out
    from google.genai import types
    client = _client()
    prompt = (f"Animate this cartoon scene: {scene}. Characters dance and move joyfully to an upbeat kids' song, "
              f"smooth gentle camera motion, keep the exact same flat 2D cartoon style and character designs. "
              f"No text, no dialogue.")
    cfg = dict(aspect_ratio="16:9", duration_seconds=8, resolution=config.VEO_RESOLUTION,
               negative_prompt="realistic, photographic, scary, text, watermark, distorted faces, extra limbs")
    for attempt in range(3):
        try:
            try:
                op = client.models.generate_videos(
                    model=config.VEO_MODEL, prompt=prompt,
                    image=types.Image(image_bytes=image.read_bytes(), mime_type="image/png"),
                    config=types.GenerateVideosConfig(person_generation="allow_all", **cfg))
            except Exception:  # some regions/accounts reject allow_all; retry with defaults
                op = client.models.generate_videos(
                    model=config.VEO_MODEL, prompt=prompt,
                    image=types.Image(image_bytes=image.read_bytes(), mime_type="image/png"),
                    config=types.GenerateVideosConfig(**cfg))
            deadline = time.time() + 900
            while not op.done and time.time() < deadline:
                time.sleep(15)
                op = client.operations.get(op)
            if not op.done or not op.response or not op.response.generated_videos:
                raise RuntimeError(f"Veo returned nothing: {getattr(op, 'error', None)}")
            vid = op.response.generated_videos[0]
            client.files.download(file=vid.video)
            vid.video.save(str(out))
            return out
        except Exception as e:  # noqa: BLE001
            print(f"[veo] attempt {attempt + 1} failed: {e}")
            time.sleep(30)
    return None


def _mock_image(out: pathlib.Path, label: str) -> pathlib.Path:
    from PIL import Image, ImageDraw, ImageFont
    im = Image.open(config.MASCOT_PNG).convert("RGB").resize((720, 720))
    bg = Image.new("RGB", (config.WIDTH, config.HEIGHT), "#7B3FB0")
    bg.paste(im, (1100, 300))
    d = ImageDraw.Draw(bg)
    d.text((120, 480), label, fill="#FFD23F", font=ImageFont.truetype(str(config.FONT_BOLD), 90))
    out.parent.mkdir(parents=True, exist_ok=True)
    bg.save(out)
    return out
