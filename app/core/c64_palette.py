"""C64 palette definitions and helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Sequence, Tuple

RGB = Tuple[int, int, int]

# Pepto-like palette commonly used in emulators/tools.
C64_PALETTE: List[RGB] = [
    (0, 0, 0),  # 0 black
    (255, 255, 255),  # 1 white
    (136, 57, 50),  # 2 red
    (103, 182, 189),  # 3 cyan
    (139, 63, 150),  # 4 purple
    (85, 160, 73),  # 5 green
    (64, 49, 141),  # 6 blue
    (191, 206, 114),  # 7 yellow
    (139, 84, 41),  # 8 orange
    (87, 66, 0),  # 9 brown
    (184, 105, 98),  # 10 light red
    (80, 80, 80),  # 11 dark gray
    (120, 120, 120),  # 12 gray
    (148, 224, 137),  # 13 light green
    (120, 105, 196),  # 14 light blue
    (159, 159, 159),  # 15 light gray
]


@dataclass(frozen=True)
class PaletteColor:
    index: int
    rgb: RGB


def iter_palette() -> Iterable[PaletteColor]:
    for i, rgb in enumerate(C64_PALETTE):
        yield PaletteColor(index=i, rgb=rgb)


def color_name(index: int) -> str:
    names: Sequence[str] = (
        "Black",
        "White",
        "Red",
        "Cyan",
        "Purple",
        "Green",
        "Blue",
        "Yellow",
        "Orange",
        "Brown",
        "Light Red",
        "Dark Gray",
        "Gray",
        "Light Green",
        "Light Blue",
        "Light Gray",
    )
    return names[index]
