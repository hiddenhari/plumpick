"""Image decoding: Qt first, Pillow for formats Qt can't read (HEIF/HEIC, AVIF)."""

from pathlib import Path

from PIL import Image, ImageOps
from pillow_heif import register_heif_opener
from PySide6.QtGui import QImage, QImageReader

register_heif_opener()  # teaches Pillow .heic/.heif (and AVIF via libheif)


def load_image(path: Path) -> QImage:
    """Decode `path` with EXIF rotation applied. Returns a null QImage on failure."""
    reader = QImageReader(str(path))
    reader.setAutoTransform(True)  # respect EXIF rotation
    image = reader.read()
    if not image.isNull():
        return image
    try:
        with Image.open(path) as pil:
            pil = ImageOps.exif_transpose(pil).convert("RGBA")
            data = pil.tobytes()
            # QImage borrows the buffer, so copy() before `data` goes away.
            return QImage(data, pil.width, pil.height, QImage.Format.Format_RGBA8888).copy()
    except Exception:
        return QImage()
