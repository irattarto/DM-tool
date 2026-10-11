"""Generate data/icons/app_icon.png (a gold d20 on a dark tile). Run: python tools/make_icon.py"""
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

SIZE = 512
BG = (30, 32, 44, 255)
GOLD = (212, 175, 55, 255)
GOLD_DARK = (150, 120, 30, 255)
FACE = (46, 50, 70, 255)


def hexagon(cx, cy, r, rotate=-90):
    return [(cx + r * math.cos(math.radians(rotate + 60 * i)),
             cy + r * math.sin(math.radians(rotate + 60 * i))) for i in range(6)]


def main():
    img = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((16, 16, SIZE - 16, SIZE - 16), radius=96, fill=BG)

    c = SIZE / 2
    outer = hexagon(c, c, 190)
    d.polygon(outer, fill=FACE, outline=GOLD)
    d.line(outer + [outer[0]], fill=GOLD, width=10, joint="curve")

    inner = hexagon(c, c, 95, rotate=-60)  # d20 face: inner hexagon turned 30 degrees
    d.line(inner + [inner[0]], fill=GOLD_DARK, width=6, joint="curve")
    for i, point in enumerate(outer):
        d.line([point, inner[(i + 1) % 6]], fill=GOLD_DARK, width=6)
        d.line([point, inner[i % 6]], fill=GOLD_DARK, width=6)

    font = None
    for candidate in ("DejaVuSans-Bold.ttf", "arialbd.ttf", "Arial Bold.ttf"):
        try:
            font = ImageFont.truetype(candidate, 120)
            break
        except OSError:
            continue
    if font is None:
        font = ImageFont.load_default(size=120)
    d.text((c, c + 4), "DM", font=font, fill=GOLD, anchor="mm", stroke_width=3, stroke_fill=BG)

    out = Path(__file__).resolve().parent.parent / "data" / "icons" / "app_icon.png"
    img.save(out)
    print(f"wrote {out} ({out.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
