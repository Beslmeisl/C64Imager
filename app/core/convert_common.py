"""Shared helpers for image conversion."""

from __future__ import annotations

from math import sqrt
from typing import List, Sequence, Tuple

from PIL import Image

from .c64_palette import C64_PALETTE

RGB = Tuple[int, int, int]


def resize_rgb(image: Image.Image, size: Tuple[int, int]) -> Image.Image:
    """Resize and force RGB."""
    return image.convert("RGB").resize(size, Image.Resampling.LANCZOS)


def squared_distance(a: RGB, b: RGB) -> int:
    dr = a[0] - b[0]
    dg = a[1] - b[1]
    db = a[2] - b[2]
    return dr * dr + dg * dg + db * db


def euclidean_distance(a: RGB, b: RGB) -> float:
    return sqrt(squared_distance(a, b))


def nearest_c64_color_index(rgb: RGB, palette: Sequence[RGB] = C64_PALETTE) -> int:
    best_idx = 0
    best_dist = 2**31 - 1
    for idx, pal_rgb in enumerate(palette):
        dist = squared_distance(rgb, pal_rgb)
        if dist < best_dist:
            best_dist = dist
            best_idx = idx
    return best_idx


def rgb_vector_length(rgb: RGB) -> float:
    return sqrt(rgb[0] * rgb[0] + rgb[1] * rgb[1] + rgb[2] * rgb[2])


def upscale_nearest(image: Image.Image, factor: int = 4) -> Image.Image:
    if factor <= 1:
        return image.copy()
    return image.resize((image.width * factor, image.height * factor), Image.Resampling.NEAREST)


def indexed_to_rgb(indexes: Sequence[int], width: int, height: int) -> Image.Image:
    """Create RGB image from palette indexes."""
    if len(indexes) != width * height:
        raise ValueError("Palette index buffer length does not match width*height.")
    out = Image.new("RGB", (width, height))
    out.putdata([C64_PALETTE[i] for i in indexes])
    return out


def block_average(image: Image.Image, x0: int, y0: int, w: int, h: int) -> RGB:
    px = image.load()
    total_r = total_g = total_b = 0
    count = 0
    for y in range(y0, y0 + h):
        for x in range(x0, x0 + w):
            r, g, b = px[x, y]
            total_r += r
            total_g += g
            total_b += b
            count += 1
    return (total_r // count, total_g // count, total_b // count)


def map_image_to_palette(image: Image.Image) -> List[int]:
    """Map each pixel to nearest C64 palette entry."""
    px = image.convert("RGB").getdata()
    return [nearest_c64_color_index(cast_rgb(rgb)) for rgb in px]


def cast_rgb(rgb: Tuple[int, ...]) -> RGB:
    return (int(rgb[0]), int(rgb[1]), int(rgb[2]))
