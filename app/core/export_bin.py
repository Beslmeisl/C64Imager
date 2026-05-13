"""Binary export helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Iterable, Mapping


def save_binary(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def export_named_blobs(output_dir: Path, base_name: str, blobs: Mapping[str, bytes]) -> Dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    written: Dict[str, Path] = {}
    for suffix, data in blobs.items():
        target = output_dir / f"{base_name}_{suffix}.bin"
        target.write_bytes(data)
        written[suffix] = target
    return written


def c64_prg_wrap(load_address: int, payload: bytes) -> bytes:
    if not (0 <= load_address <= 0xFFFF):
        raise ValueError("Invalid C64 load address.")
    return bytes((load_address & 0xFF, (load_address >> 8) & 0xFF)) + payload
