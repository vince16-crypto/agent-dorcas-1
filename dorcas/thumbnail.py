"""Step 5: thumbnail = generated art + big bold title text + channel badge (1280x720, < 2 MB)."""
from __future__ import annotations

import pathlib

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from . import config


def _wrap(text: str, font: ImageFont.FreeTypeFont, width: int, draw: ImageDraw.ImageDraw) -> list[str]:
    words, lines, cur = text.split(), [], ""
    for w in words:
        test = f"{cur} {w}".strip()
        if draw.textlength(test, font=font) <= width:
            cur = test
        else:
            if cur:
                lines.append(cur)
            cur = w
    return lines + ([cur] if cur else [])


def make_thumbnail(art: pathlib.Path, text: str, out: pathlib.Path) -> pathlib.Path:
    pal = config.BRAND["palette"]
    img = Image.open(art).convert("RGB").resize((1280, 720))
    # soft dark gradient on the left so text pops
    shade = Image.new("L", (1280, 720), 0)
    d = ImageDraw.Draw(shade)
    for x in range(700):
        d.line([(x, 0), (x, 720)], fill=int(170 * (1 - x / 700)))
    img = Image.composite(Image.new("RGB", img.size, pal["purple"]), img, shade.filter(ImageFilter.GaussianBlur(8)))
    draw = ImageDraw.Draw(img)

    text = text.upper()
    size = 140
    while size > 60:
        font = ImageFont.truetype(str(config.FONT_BOLD), size)
        lines = _wrap(text, font, 600, draw)
        if len(lines) <= 3 and size * 1.05 * len(lines) <= 470:
            break
        size -= 8
    y = 360 - int(size * 1.05 * len(lines) / 2)
    colors = ["#FFFFFF", pal["yellow"], "#FFFFFF"]
    for i, ln in enumerate(lines):
        draw.text((50, y), ln, font=font, fill=colors[i % 3], stroke_width=10, stroke_fill="#2B0F45")
        y += int(size * 1.05)

    badge = Image.open(config.PROFILE_PNG).convert("RGBA").resize((120, 120))
    m = Image.new("L", (120, 120), 0)
    ImageDraw.Draw(m).ellipse((0, 0, 119, 119), fill=255)
    img.paste(badge, (40, 40), m)
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out, "JPEG", quality=90)
    return out
