#!/usr/bin/env python3
"""Regenerate images/og/nodecontrol-share.png (1200×630).

From the repo root:

    python3 images/og/render_share.py

The card is the official logo, centred on its own dark background with
padding. It is not the old share card (that one used images/logo-simple.svg
plus a blurred product screenshot).
"""

from __future__ import annotations

from pathlib import Path
from statistics import median

from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "images" / "logo-official.png"
OUTPUT = ROOT / "images" / "og" / "nodecontrol-share.png"

WIDTH = 1200
HEIGHT = 630
PAD = 52


def main() -> None:
    logo = Image.open(SOURCE).convert("RGB")
    pixels = logo.load()
    width, height = logo.size
    border = []
    for x in range(width):
        border.append(pixels[x, 0])
        border.append(pixels[x, height - 1])
    for y in range(height):
        border.append(pixels[0, y])
        border.append(pixels[width - 1, y])
    background = tuple(int(median(channel)) for channel in zip(*border))
    scale = min((WIDTH - PAD * 2) / logo.width, (HEIGHT - PAD * 2) / logo.height)
    size = (round(logo.width * scale), round(logo.height * scale))
    card = Image.new("RGB", (WIDTH, HEIGHT), background)
    card.paste(
        logo.resize(size, Image.Resampling.LANCZOS),
        ((WIDTH - size[0]) // 2, (HEIGHT - size[1]) // 2),
    )
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    card.save(OUTPUT, "PNG", optimize=True, compress_level=9)


if __name__ == "__main__":
    main()
