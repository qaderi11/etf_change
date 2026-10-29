"""生成 PWA 图标：深红底 + 白色净值折线 + ETF 字样。"""
from __future__ import annotations

import os
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "app" / "public" / "icons"
OUT.mkdir(parents=True, exist_ok=True)

RED = (178, 58, 47)
RED_DARK = (150, 44, 35)
WHITE = (255, 252, 246)


def font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for name in ["arialbd.ttf", "Arial Bold.ttf", "segoeuib.ttf"]:
        path = os.path.join(os.environ.get("WINDIR", "C:\\Windows"), "Fonts", name)
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def make(size: int) -> Image.Image:
    scale = size / 512
    img = Image.new("RGB", (size, size), RED)
    d = ImageDraw.Draw(img)

    # 底部略深，增加层次
    for y in range(size):
        t = y / max(1, size - 1)
        col = tuple(int(RED[i] * (1 - 0.25 * t) + RED_DARK[i] * 0.25 * t) for i in range(3))
        d.line([(0, y), (size, y)], fill=col)

    pts = [(90, 350), (170, 270), (250, 300), (340, 190), (420, 150)]
    pts = [(x * scale, y * scale) for x, y in pts]
    d.line(pts, fill=WHITE, width=max(2, int(24 * scale)), joint="curve")

    r = 20 * scale
    x, y = pts[-1]
    d.ellipse([x - r, y - r, x + r, y + r], fill=WHITE)

    f = font(int(62 * scale))
    d.text((88 * scale, 386 * scale), "ETF", font=f, fill=WHITE)

    f2 = font(int(22 * scale))
    d.text((92 * scale, 456 * scale), "WEEKLY ROTATION", font=f2, fill=(255, 255, 255, 180))

    return img


if __name__ == "__main__":
    for s in [512, 192, 180, 32]:
        name = {512: "icon-512.png", 192: "icon-192.png", 180: "apple-touch-icon.png", 32: "favicon.png"}[s]
        make(s).save(OUT / name)
        print("saved", name)
