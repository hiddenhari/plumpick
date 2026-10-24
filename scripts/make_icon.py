"""Render assets/plum.png into src/plumpick/assets/plumpick.ico.

The source is pixel art, so every size is scaled with nearest-neighbour
(no blur), straight from the full-size source. Sizes that are a whole
multiple or fraction of the source (16, 32, 64, 128, 256 for a 64 px source)
keep every pixel crisp. The .ico is committed, so building the app doesn't
need this script (or Pillow).

Usage: uv run python scripts/make_icon.py
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "assets" / "plum.png"
TARGET = ROOT / "src" / "plumpick" / "assets" / "plumpick.ico"
SIZES = [16, 20, 24, 32, 40, 48, 64, 128, 256]
MARGIN = 0  # transparent source pixels on each side; keeps the scale a whole number


def squared(art: Image.Image) -> Image.Image:
    """Crop to the drawing, then center it on a transparent square with a margin.

    Stray dots away from the drawing are left out of the crop.
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

    side = -(-(max(art.size) + 2 * MARGIN) // 16) * 16  # round up to a multiple of 16
    square = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    square.paste(art, ((side - art.width) // 2, (side - art.height) // 2))
    return square


def keyed(art: Image.Image) -> Image.Image:
    """Make the flat background colour transparent.

    The source is drawn on solid orange. Flood in from every edge pixel so
    only background connected to the edge goes, never orange inside the
    drawing. Starting from every edge pixel matters because the stem touches
    the top edge and splits the background in two.
    """
    art = art.copy()
    background = art.getpixel((0, 0))
    w, h = art.size
    edge = [(x, y) for x in range(w) for y in (0, h - 1)] + [(x, y) for y in range(h) for x in (0, w - 1)]
    for xy in edge:
        # thresh also catches the odd off-orange pixel the art has in the background
        if art.getpixel(xy) != (0, 0, 0, 0) and max(abs(a - b) for a, b in zip(art.getpixel(xy), background)) <= 45:
            ImageDraw.floodfill(art, xy, (0, 0, 0, 0), thresh=45)
    return art


def main() -> None:
    source = squared(keyed(Image.open(SOURCE).convert("RGBA")))
    images = [source.resize((s, s), Image.Resampling.NEAREST) for s in SIZES]
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    # Pillow takes each size from the image of exactly that size.
    images[-1].save(TARGET, sizes=[(s, s) for s in SIZES], append_images=images[:-1])
    print(f"Wrote {TARGET.relative_to(ROOT)} ({', '.join(map(str, SIZES))} px)")


if __name__ == "__main__":
    main()
