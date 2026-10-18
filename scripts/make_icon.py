"""Render assets/plumpick.png into src/plumpick/assets/plumpick.ico.

Each size is downsampled straight from the full-size source rather than
from the next size up. The .ico is committed, so building the app doesn't
need this script (or Pillow).

Usage: uv run python scripts/make_icon.py
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "assets" / "plumpick.png"
TARGET = ROOT / "src" / "plumpick" / "assets" / "plumpick.ico"
SIZES = [16, 20, 24, 32, 40, 48, 64, 128, 256]
MARGIN = 1 / 32  # of the icon size, on each side


def squared(art: Image.Image) -> Image.Image:
    """Crop to the drawing, then center it on a transparent square with a margin.

    Stray dots away from the drawing are left out of the crop (the source has
    one right of the fruit that would push it off center).
    """
    alpha = art.getchannel("A")
    visible = alpha.point(lambda a: 255 if a > 0 else 0)
    # The drawing's solid parts: opening (shrink, then grow) removes anything
    # thinner than `speck`, including the stray dot. Then keep every visible
    # pixel within `speck` of those, so thin outlines on the drawing stay.
    speck = 2 * max(1, max(art.size) // 256) + 1
    solid = alpha.point(lambda a: 255 if a > 128 else 0)
    solid = solid.filter(ImageFilter.MinFilter(speck)).filter(ImageFilter.MaxFilter(speck))
    near = solid.filter(ImageFilter.MaxFilter(2 * speck + 1))
    art = art.crop(ImageChops.multiply(visible, near).getbbox())

    side = round(max(art.size) / (1 - 2 * MARGIN))
    square = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    square.paste(art, ((side - art.width) // 2, (side - art.height) // 2))
    return square


def on_white(art: Image.Image) -> Image.Image:
    """Put white behind the drawing, reaching just past its outline.

    The drawing's "white" parts are holes, so on a dark taskbar or a
    dark-mode Explorer they would show the dark background and the icon
    would almost disappear.
    """
    # Flood the transparent area from outside; whatever the flood can't reach
    # is inside the outline. A 1 px empty border lets the flood get all the
    # way around even where small sizes' anti-aliasing touches the edge.
    w, h = art.size
    mask = Image.new("L", (w + 2, h + 2), 0)
    # Only clearly opaque pixels count as outline; the faint halo resampling
    # leaves around the edge would otherwise put white outside the drawing.
    mask.paste(art.getchannel("A").point(lambda a: 255 if a > 128 else 0), (1, 1))
    ImageDraw.floodfill(mask, (0, 0), 128)
    inside = mask.crop((1, 1, w + 1, h + 1)).point(lambda v: 0 if v == 128 else 255)
    # Grow it into a thin white outline: the fruit is mostly black, and on
    # a dark background it would blend in. On a light one it doesn't show.
    outline = max(1, round(w / 64))
    inside = inside.filter(ImageFilter.MaxFilter(2 * outline + 1))

    result = Image.new("RGBA", art.size, (255, 255, 255, 0))
    result.putalpha(inside)
    result.alpha_composite(art)
    return result


def main() -> None:
    source = squared(Image.open(SOURCE).convert("RGBA"))
    images = [on_white(source.resize((s, s), Image.Resampling.LANCZOS)) for s in SIZES]
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    # Pillow takes each size from the image of exactly that size.
    images[-1].save(TARGET, sizes=[(s, s) for s in SIZES], append_images=images[:-1])
    print(f"Wrote {TARGET.relative_to(ROOT)} ({', '.join(map(str, SIZES))} px)")


if __name__ == "__main__":
    main()
