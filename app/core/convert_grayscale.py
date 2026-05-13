"""Five-level grayscale conversion for C64 multicolor (160x200)."""

from __future__ import annotations

from dataclasses import dataclass

from PIL import Image

from .convert_multicolor import MulticolorFrame, MulticolorResult, convert_to_multicolor

# Schwarz, Dunkelgrau, Mittelgrau, Hellgrau, Weiß (C64 palette indices).
GRAYSCALE_COLOR_INDICES = (0, 11, 12, 15, 1)


@dataclass
class GrayscaleResult:
    preview: Image.Image
    preview_upscaled: Image.Image
    frame: MulticolorFrame
    width: int = 160
    height: int = 200


def convert_to_grayscale(
    image: Image.Image,
    upscale_factor: int = 4,
) -> GrayscaleResult:
    result: MulticolorResult = convert_to_multicolor(
        image,
        upscale_factor=upscale_factor,
        fixed_palette=GRAYSCALE_COLOR_INDICES,
    )
    return GrayscaleResult(
        preview=result.preview,
        preview_upscaled=result.preview_upscaled,
        frame=result.frame,
    )
