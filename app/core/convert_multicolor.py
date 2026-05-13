"""Multicolor 160x200 conversion."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Sequence

from PIL import Image

from .c64_palette import C64_PALETTE
from .convert_common import resize_rgb, squared_distance, upscale_nearest


@dataclass
class MulticolorFrame:
    bitmap: bytes
    screen_ram: bytes
    color_ram: bytes
    background_color: int
    border_color: int | None = None

    def with_border_color(self, border_color: int) -> "MulticolorFrame":
        return MulticolorFrame(
            bitmap=self.bitmap,
            screen_ram=self.screen_ram,
            color_ram=self.color_ram,
            background_color=self.background_color,
            border_color=border_color & 0x0F,
        )


@dataclass
class MulticolorResult:
    preview: Image.Image
    preview_upscaled: Image.Image
    color_indexes: List[int]
    frame: MulticolorFrame
    width: int = 160
    height: int = 200


def convert_to_multicolor(
    image: Image.Image,
    upscale_factor: int = 4,
    fixed_palette: Sequence[int] | None = None,
) -> MulticolorResult:
    src = resize_rgb(image, (160, 200))
    px = src.load()

    if fixed_palette:
        valid = list(fixed_palette)
    else:
        valid = list(range(16))

    indexes: List[int] = []
    for y in range(200):
        for x in range(160):
            rgb = px[x, y]
            nearest = min(valid, key=lambda i: _squared_dist(rgb, C64_PALETTE[i]))
            indexes.append(nearest)

    frame = build_multicolor_frame(indexes)
    constrained_indexes = render_multicolor_frame_indexes(frame)
    preview = Image.new("RGB", (160, 200))
    preview.putdata([C64_PALETTE[i] for i in constrained_indexes])
    # C64 multicolor pixels are effectively double-width.
    stretched = preview.resize((320, 200), Image.Resampling.NEAREST)
    preview_upscaled = upscale_nearest(stretched, upscale_factor)
    return MulticolorResult(
        preview=preview,
        preview_upscaled=preview_upscaled,
        color_indexes=indexes,
        frame=frame,
    )


def build_multicolor_frame(color_indexes: Sequence[int]) -> MulticolorFrame:
    """Convert 160x200 C64 palette indexes into a legal C64 multicolor bitmap frame."""
    if len(color_indexes) != 160 * 200:
        raise ValueError("Multicolor index buffer must be exactly 160*200 entries.")

    background = _most_common_color(color_indexes)
    bitmap = bytearray(8000)
    screen_ram = bytearray(1000)
    color_ram = bytearray(1000)

    for cell_y in range(25):
        for cell_x in range(40):
            cell_colors: List[int] = []
            for row in range(8):
                y = cell_y * 8 + row
                for col in range(4):
                    x = cell_x * 4 + col
                    cell_colors.append(color_indexes[y * 160 + x] & 0x0F)

            palette = _choose_multicolor_cell_palette(cell_colors, background)
            c1, c2, c3 = palette[1], palette[2], palette[3]
            cell_index = cell_y * 40 + cell_x
            screen_ram[cell_index] = ((c1 & 0x0F) << 4) | (c2 & 0x0F)
            color_ram[cell_index] = c3 & 0x0F

            for row in range(8):
                byte_value = 0
                y = cell_y * 8 + row
                for col in range(4):
                    x = cell_x * 4 + col
                    src_color = color_indexes[y * 160 + x] & 0x0F
                    code = _nearest_multicolor_code(src_color, palette)
                    byte_value = (byte_value << 2) | code
                bitmap[cell_y * 320 + cell_x * 8 + row] = byte_value

    return MulticolorFrame(
        bitmap=bytes(bitmap),
        screen_ram=bytes(screen_ram),
        color_ram=bytes(color_ram),
        background_color=background,
    )


def render_multicolor_frame_indexes(frame: MulticolorFrame) -> List[int]:
    """Render a C64 multicolor frame back to 160x200 palette indexes."""
    if len(frame.bitmap) != 8000:
        raise ValueError("Multicolor bitmap must be exactly 8000 bytes.")
    if len(frame.screen_ram) != 1000 or len(frame.color_ram) != 1000:
        raise ValueError("Screen/color RAM must be exactly 1000 bytes.")

    indexes = [frame.background_color] * (160 * 200)
    for cell_y in range(25):
        for cell_x in range(40):
            cell_index = cell_y * 40 + cell_x
            screen = frame.screen_ram[cell_index]
            palette = [
                frame.background_color & 0x0F,
                (screen >> 4) & 0x0F,
                screen & 0x0F,
                frame.color_ram[cell_index] & 0x0F,
            ]
            for row in range(8):
                value = frame.bitmap[cell_y * 320 + cell_x * 8 + row]
                y = cell_y * 8 + row
                for col in range(4):
                    shift = 6 - col * 2
                    code = (value >> shift) & 0x03
                    x = cell_x * 4 + col
                    indexes[y * 160 + x] = palette[code]
    return indexes


def _most_common_color(indexes: Sequence[int]) -> int:
    counts = [0] * 16
    for index in indexes:
        counts[index & 0x0F] += 1
    return max(range(16), key=lambda i: counts[i])


def _choose_multicolor_cell_palette(cell_colors: Sequence[int], background: int) -> List[int]:
    counts = [0] * 16
    for color in cell_colors:
        counts[color & 0x0F] += 1

    colors = [background]
    for color in sorted(range(16), key=lambda i: counts[i], reverse=True):
        if color != background and counts[color] > 0:
            colors.append(color)
        if len(colors) == 4:
            break
    while len(colors) < 4:
        colors.append(background)
    return colors


def _nearest_multicolor_code(color: int, palette: Sequence[int]) -> int:
    rgb = C64_PALETTE[color & 0x0F]
    return min(
        range(4),
        key=lambda i: squared_distance(rgb, C64_PALETTE[palette[i] & 0x0F]),
    )


def _squared_dist(a, b) -> int:
    dr = a[0] - b[0]
    dg = a[1] - b[1]
    db = a[2] - b[2]
    return dr * dr + dg * dg + db * db
