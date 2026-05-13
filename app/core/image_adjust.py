"""Non-destructive source image adjustments."""

from __future__ import annotations

from math import sqrt

from PIL import Image, ImageStat

from .convert_common import resize_rgb


DEFAULT_NORMALIZE_SLIDER_MAX = 1000
MAX_ADJUSTMENT_SLIDER_MAX = 10000
MIN_ADJUSTMENT_SLIDER_MAX = 100


def rescale_adjustment_percent(value: int, old_max: int, new_max: int) -> int:
    """Scale a slider percentage when the slider maximum changes."""
    if old_max <= 0 or new_max <= 0:
        return max(0, min(new_max, value))
    scaled = int(round(value * new_max / old_max))
    return max(0, min(new_max, scaled))


def apply_rgb_adjustment(
    image: Image.Image,
    brightness_percent: int = 100,
    red_percent: int = 100,
    green_percent: int = 100,
    blue_percent: int = 100,
) -> Image.Image:
    """Apply brightness and per-channel RGB multipliers to an RGB image."""
    rgb = image.convert("RGB")
    factors = (
        max(0, brightness_percent) * max(0, red_percent) / 10000.0,
        max(0, brightness_percent) * max(0, green_percent) / 10000.0,
        max(0, brightness_percent) * max(0, blue_percent) / 10000.0,
    )
    channels = rgb.split()
    adjusted = [
        channel.point(_lut_for_factor(factor))
        for channel, factor in zip(channels, factors)
    ]
    return Image.merge("RGB", adjusted)


def apply_rgb_express(image: Image.Image) -> Image.Image:
    """Square each RGB channel value and divide by 255."""
    rgb = image.convert("RGB")
    lut = [int(round((value * value) / 255.0)) for value in range(256)]
    return Image.merge("RGB", [channel.point(lut) for channel in rgb.split()])


def apply_rgb_depress(image: Image.Image) -> Image.Image:
    """Take the square root of each RGB channel value and multiply by sqrt(255)."""
    rgb = image.convert("RGB")
    lut = [min(255, int(round(sqrt(value * 255.0)))) for value in range(256)]
    return Image.merge("RGB", [channel.point(lut) for channel in rgb.split()])


def average_raster_image(image: Image.Image, size: tuple[int, int]) -> Image.Image:
    """Create the average-color C64 source raster for the requested size."""
    return resize_rgb(image, size)


def average_raster_preview(
    image: Image.Image,
    size: tuple[int, int],
    upscale_factor: int = 4,
    stretch_horizontal: bool = False,
) -> Image.Image:
    raster = average_raster_image(image, size)
    if stretch_horizontal:
        raster = raster.resize((raster.width * 2, raster.height), Image.Resampling.NEAREST)
    return raster.resize(
        (raster.width * upscale_factor, raster.height * upscale_factor),
        Image.Resampling.NEAREST,
    )


def rgb_channel_maxima_for_c64_pixels(image: Image.Image, size: tuple[int, int] = (320, 200)) -> tuple[int, int, int]:
    """Return max R/G/B values from the average C64 source-pixel raster."""
    raster = average_raster_image(image, size)
    px = raster.load()
    max_r = max_g = max_b = 0
    for y in range(raster.height):
        for x in range(raster.width):
            r, g, b = px[x, y]
            max_r = max(max_r, r)
            max_g = max(max_g, g)
            max_b = max(max_b, b)
    return max_r, max_g, max_b


def rgb_normalize_slider_values(
    image: Image.Image,
    slider_max: int = DEFAULT_NORMALIZE_SLIDER_MAX,
    size: tuple[int, int] = (320, 200),
) -> tuple[int, int, int]:
    """Calculate RGB slider percentages so each channel maximum reaches 255."""
    return tuple(
        _gain_percent_for_channel(max_value, slider_max)
        for max_value in rgb_channel_maxima_for_c64_pixels(image, size)
    )


def rgb_average_slider_values(
    image: Image.Image,
    slider_max: int = DEFAULT_NORMALIZE_SLIDER_MAX,
    size: tuple[int, int] = (320, 200),
) -> tuple[int, int, int]:
    """Calculate RGB slider percentages so each channel average reaches 50%."""
    raster = average_raster_image(image, size)
    return tuple(
        _gain_percent_for_average_channel(mean_value, slider_max)
        for mean_value in ImageStat.Stat(raster).mean
    )


def _gain_percent_for_channel(max_value: int, slider_max: int) -> int:
    if max_value <= 0:
        return max(100, slider_max)
    value = int(round(25500 / max_value))
    return max(0, min(slider_max, value))


def _gain_percent_for_average_channel(mean_value: float, slider_max: int) -> int:
    if mean_value <= 0:
        return max(100, slider_max)
    value = int(round(12750 / mean_value))
    return max(0, min(slider_max, value))


def _lut_for_factor(factor: float) -> list[int]:
    return [min(255, int(round(value * factor))) for value in range(256)]
