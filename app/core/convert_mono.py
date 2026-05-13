"""Monochrome conversion for 320x200 with configurable threshold."""

from __future__ import annotations

from bisect import bisect_left
from dataclasses import dataclass
from math import sqrt
from typing import List, Sequence

from PIL import Image

from .c64_palette import C64_PALETTE
from .convert_common import resize_rgb, upscale_nearest


@dataclass
class MonoResult:
    preview: Image.Image
    preview_upscaled: Image.Image
    bitmap: bytes
    width: int = 320
    height: int = 200


def convert_to_mono(
    image: Image.Image,
    threshold: float,
    fg_color: int,
    bg_color: int,
    upscale_factor: int = 4,
) -> MonoResult:
    src = resize_rgb(image, (320, 200))
    px = src.load()

    preview_indexes: List[int] = [0] * (320 * 200)
    bitmap = bytearray(8000)

    for cell_y in range(25):
        for cell_x in range(40):
            x0 = cell_x * 8
            y0 = cell_y * 8
            for row in range(8):
                bits = 0
                y = y0 + row
                for col in range(8):
                    x = x0 + col
                    r, g, b = px[x, y]
                    l = sqrt(r * r + g * g + b * b)
                    bit = 1 if l >= threshold else 0
                    bits = (bits << 1) | bit
                    preview_indexes[y * 320 + x] = fg_color if bit else bg_color
                bitmap[cell_y * 320 + cell_x * 8 + row] = bits

    preview = Image.new("RGB", (320, 200))
    preview.putdata([C64_PALETTE[i] for i in preview_indexes])
    preview_upscaled = upscale_nearest(preview, upscale_factor)
    return MonoResult(preview=preview, preview_upscaled=preview_upscaled, bitmap=bytes(bitmap))


def compute_mono_luminances(image: Image.Image) -> List[float]:
    """RGB vector length per pixel after resize to 320x200 (same formula as convert_to_mono)."""
    src = resize_rgb(image, (320, 200))
    px = src.load()
    out: List[float] = []
    for y in range(200):
        for x in range(320):
            r, g, b = px[x, y]
            out.append(sqrt(r * r + g * g + b * b))
    return out


def foreground_percent_for_threshold(luminances: Sequence[float], threshold: float) -> float:
    if not luminances:
        return 0.0
    fg = sum(1 for L in luminances if L >= threshold)
    return 100.0 * fg / len(luminances)


def threshold_for_foreground_percent(
    luminances: Sequence[float],
    percent: float,
    slider_min: int = 0,
    slider_max: int = 442,
) -> int:
    """
    Integer slider threshold in [slider_min, slider_max] that best matches
    the desired foreground percentage (pixels with L >= threshold).
    """
    n = len(luminances)
    if n == 0:
        return slider_min
    p = max(0.0, min(100.0, percent))
    k = int(round(n * p / 100.0))
    k = max(0, min(n, k))

    lum_sorted = sorted(luminances)
    if k == 0:
        return slider_max
    if k == n:
        return slider_min

    def count_ge(t: float) -> int:
        return n - bisect_left(lum_sorted, t)

    best_t = slider_min
    best_err = 10**9
    for t in range(slider_min, slider_max + 1):
        c = count_ge(float(t))
        err = abs(c - k)
        if err < best_err:
            best_err = err
            best_t = t
    return best_t
