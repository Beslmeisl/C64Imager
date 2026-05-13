"""HIRES 320x200 conversion with C64 block constraints."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import List, Tuple

from PIL import Image

from .c64_palette import C64_PALETTE
from .convert_common import nearest_c64_color_index, resize_rgb, squared_distance, upscale_nearest


@dataclass
class HiresResult:
    preview: Image.Image
    preview_upscaled: Image.Image
    bitmap: bytes
    screen_ram: bytes
    background_color: int
    width: int = 320
    height: int = 200


def convert_to_hires(image: Image.Image, background_color: int = 0, upscale_factor: int = 4) -> HiresResult:
    src = resize_rgb(image, (320, 200))
    src_px = src.load()

    bitmap = bytearray(8000)
    screen_ram = bytearray(1000)
    preview_indexes: List[int] = [background_color] * (320 * 200)

    for cell_y in range(25):
        for cell_x in range(40):
            x0 = cell_x * 8
            y0 = cell_y * 8

            block_colors: List[int] = []
            for y in range(y0, y0 + 8):
                for x in range(x0, x0 + 8):
                    block_colors.append(nearest_c64_color_index(src_px[x, y]))

            counts = Counter(block_colors)
            top = [idx for idx, _ in counts.most_common(3)]
            if background_color in top:
                top.remove(background_color)
            fg = top[0] if top else background_color

            # Validate choice by aggregate distance on block.
            if len(top) > 1:
                alt = top[1]
                fg_dist = _pair_distance(src_px, x0, y0, fg, background_color)
                alt_dist = _pair_distance(src_px, x0, y0, alt, background_color)
                if alt_dist < fg_dist:
                    fg = alt

            screen_ram[cell_y * 40 + cell_x] = ((fg & 0x0F) << 4) | (background_color & 0x0F)

            for row in range(8):
                bits = 0
                y = y0 + row
                for col in range(8):
                    x = x0 + col
                    rgb = src_px[x, y]
                    dist_fg = squared_distance(rgb, C64_PALETTE[fg])
                    dist_bg = squared_distance(rgb, C64_PALETTE[background_color])
                    bit = 1 if dist_fg <= dist_bg else 0
                    bits = (bits << 1) | bit
                    preview_indexes[y * 320 + x] = fg if bit else background_color

                bitmap[cell_y * 320 + cell_x * 8 + row] = bits

    preview = Image.new("RGB", (320, 200))
    preview.putdata([C64_PALETTE[i] for i in preview_indexes])
    preview_upscaled = upscale_nearest(preview, upscale_factor)

    return HiresResult(
        preview=preview,
        preview_upscaled=preview_upscaled,
        bitmap=bytes(bitmap),
        screen_ram=bytes(screen_ram),
        background_color=background_color,
    )


def _pair_distance(src_px, x0: int, y0: int, c1: int, c2: int) -> int:
    total = 0
    c1_rgb = C64_PALETTE[c1]
    c2_rgb = C64_PALETTE[c2]
    for y in range(y0, y0 + 8):
        for x in range(x0, x0 + 8):
            rgb = src_px[x, y]
            d1 = squared_distance(rgb, c1_rgb)
            d2 = squared_distance(rgb, c2_rgb)
            total += d1 if d1 < d2 else d2
    return total
