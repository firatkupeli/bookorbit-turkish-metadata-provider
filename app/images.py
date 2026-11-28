"""Decode bounded JPEG/PNG covers for truthful dimensions and safe upload."""

import io
import math
import warnings

from PIL import Image, UnidentifiedImageError

from app.epub import MAX_COVER, EpubError

MAX_PIXELS = 20_000_000


def image_info(data):
    if not data or len(data) > MAX_COVER:
        raise EpubError("Kapak en fazla 5 MiB olabilir.")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(data), formats=("JPEG", "PNG")) as image:
                width, height = image.size
                if width * height > MAX_PIXELS or min(width, height) < 1:
                    raise EpubError("Kapak en fazla 20 milyon piksel olabilir.")
                if getattr(image, "n_frames", 1) != 1:
                    raise EpubError("Hareketli görseller kapak olarak kullanılamaz.")
                orientation = image.getexif().get(274, 1)
                kind = image.format
                image.load()
            if orientation in (5, 6, 7, 8):
                width, height = height, width
            ratio = math.gcd(width, height)
            return {
                "width": width,
                "height": height,
                "bytes": len(data),
                "format": kind,
                "ratio": f"{width // ratio}:{height // ratio}",
            }
    except EpubError:
        raise
    except (
        UnidentifiedImageError,
        OSError,
        ValueError,
        SyntaxError,
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
    ):
        raise EpubError("Görsel okunamadı. Geçerli bir JPG veya PNG seçin.") from None
