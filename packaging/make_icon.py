#!/usr/bin/env python
"""Generate the application icon.

    python packaging/make_icon.py

Writes ``packaging/icon.ico`` (for the executables) and
``moondrop/ui/assets/icon.png`` (for the window and taskbar). Requires Pillow,
which is only needed to regenerate the artwork -- not to run the app.

The mark is a level meter: four bars on the same violet-to-cyan gradient the UI
uses. Deliberately simple, because the device itself is unreadable at 16 px.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
SIZE = 1024
ICO_SIZES = [(s, s) for s in (16, 24, 32, 48, 64, 128, 256)]

ACCENT_A = (124, 92, 255)    # violet
ACCENT_B = (34, 211, 238)    # cyan
BACKDROP = (11, 13, 16)

# Bar heights as a fraction of the artboard, left to right. The tallest must
# clear the tile's top edge: baseline (0.78) minus height stays above ~0.14.
BARS = (0.26, 0.46, 0.62, 0.37)


def diagonal_gradient(size: int, start, end) -> Image.Image:
    gradient = Image.new("RGB", (size, size))
    pixels = gradient.load()
    for y in range(size):
        for x in range(size):
            t = (x + y) / (2 * (size - 1))
            pixels[x, y] = (
                round(start[0] + (end[0] - start[0]) * t),
                round(start[1] + (end[1] - start[1]) * t),
                round(start[2] + (end[2] - start[2]) * t),
            )
    return gradient


def rounded_mask(size: int, radius: int) -> Image.Image:
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, size - 1, size - 1], radius, fill=255)
    return mask


def build() -> Image.Image:
    # Dark rounded tile, so the mark keeps its shape on light and dark taskbars.
    tile = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    plate = Image.new("RGBA", (SIZE, SIZE), BACKDROP + (255,))
    tile.paste(plate, (0, 0), rounded_mask(SIZE, round(SIZE * 0.22)))

    # Gradient-filled bars, drawn as a mask over the gradient.
    bars = Image.new("L", (SIZE, SIZE), 0)
    draw = ImageDraw.Draw(bars)

    count = len(BARS)
    span = SIZE * 0.56
    bar_w = span / (count * 2 - 1)
    left = (SIZE - span) / 2
    baseline = SIZE * 0.78

    for index, fraction in enumerate(BARS):
        x0 = left + index * bar_w * 2
        height = SIZE * fraction
        draw.rounded_rectangle(
            [x0, baseline - height, x0 + bar_w, baseline],
            radius=bar_w / 2,
            fill=255,
        )

    gradient = diagonal_gradient(SIZE, ACCENT_A, ACCENT_B).convert("RGBA")
    gradient.putalpha(bars)
    tile.alpha_composite(gradient)
    return tile


def main() -> int:
    icon = build()

    ico_path = ROOT / "packaging" / "icon.ico"
    icon.save(ico_path, format="ICO", sizes=ICO_SIZES)

    assets = ROOT / "moondrop" / "ui" / "assets"
    assets.mkdir(parents=True, exist_ok=True)
    png_path = assets / "icon.png"
    icon.resize((256, 256), Image.LANCZOS).save(png_path)

    print(f"wrote {ico_path}")
    print(f"wrote {png_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
