"""Create simple C64 PRG files from conversion output."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Sequence

from .convert_multicolor import MulticolorFrame, build_multicolor_frame
from .export_bin import c64_prg_wrap

_LOAD_ADDR = 0x0801
_BITMAP_ADDR = 0xE000
_SCREEN_ADDR = 0xCC00
_COLOR_RAM_ADDR = 0xD800
_TEXT_SCREEN_ADDR = 0x0400
_VIC_BANK_BITS = 0
_VIC_D018 = 56  # bank-relative screen $0c00, bitmap $2000 => $38
_NORMAL_VIC_BANK_BITS = 3
_NORMAL_VIC_D018 = 21
_NORMAL_BORDER_COLOR = 14
_NORMAL_BACKGROUND_COLOR = 6
_NORMAL_TEXT_COLOR = 14
_NORMAL_SCREEN_CODE = 32
_BASIC_TEXT_COLOR_ADDR = 0x0286
_DATA_HEX_BYTES_PER_LINE = 32
_MACHINE_START_ADDR = 0x0810


@dataclass
class HiresFrame:
    bitmap: bytes
    screen_ram: bytes
    background_color: int
    border_color: int | None = None


@dataclass
class HiresSlideshowFrame:
    bitmap: bytes
    screen_ram: bytes


@dataclass(frozen=True)
class AsmExportFrame:
    bitmap: bytes
    screen_ram: bytes
    background_color: int
    border_color: int | None = None
    multicolor: bool = False
    color_ram: bytes | None = None


def export_basic_hires_prg(output_path: Path, frame: HiresFrame) -> Path:
    """
    Generates a compact tokenized BASIC PRG: raw bitmap + screen bytes are appended
    after the BASIC program in the PRG file and copied into video RAM with backward
    PEEK/POKE loops (avoids huge DATA blocks that overlap $2000 and corrupt the loader).
    """
    if len(frame.bitmap) != 8000:
        raise ValueError("HIRES bitmap must be exactly 8000 bytes.")
    if len(frame.screen_ram) != 1000:
        raise ValueError("Screen RAM must be exactly 1000 bytes.")

    basic_payload, _ = _build_hires_basic_payload(
        background_color=frame.background_color,
        border_color=_frame_border_color(frame),
        slideshow_frames=1,
    )
    prg = c64_prg_wrap(_LOAD_ADDR, basic_payload + frame.bitmap + frame.screen_ram)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(prg)
    return output_path


def export_hires_data_program(output_base: Path, frame: HiresFrame) -> tuple[Path, Path]:
    """Export one HIRES image as tokenized PRG and ASCII .bas with DATA lines."""
    if len(frame.bitmap) != 8000:
        raise ValueError("HIRES bitmap must be exactly 8000 bytes.")
    if len(frame.screen_ram) != 1000:
        raise ValueError("Screen RAM must be exactly 1000 bytes.")

    lines = _build_hires_data_source_lines(
        bitmap=frame.bitmap,
        screen_ram=frame.screen_ram,
        background_color=frame.background_color,
        border_color=_frame_border_color(frame),
    )
    return _write_basic_pair(output_base, lines)


def export_multicolor_data_program(output_base: Path, frame: MulticolorFrame) -> tuple[Path, Path]:
    """Export one multicolor bitmap image as tokenized PRG and ASCII .bas with DATA lines."""
    if len(frame.bitmap) != 8000:
        raise ValueError("Multicolor bitmap must be exactly 8000 bytes.")
    if len(frame.screen_ram) != 1000:
        raise ValueError("Screen RAM must be exactly 1000 bytes.")
    if len(frame.color_ram) != 1000:
        raise ValueError("Color RAM must be exactly 1000 bytes.")

    lines = _build_multicolor_data_source_lines(frame)
    return _write_basic_pair(output_base, lines)


def export_hires_asm_program(output_base: Path, frame: HiresFrame) -> tuple[Path, Path]:
    """Export one HIRES image as ASM-based PRG and 64 Studio .asm source."""
    if len(frame.bitmap) != 8000:
        raise ValueError("HIRES bitmap must be exactly 8000 bytes.")
    if len(frame.screen_ram) != 1000:
        raise ValueError("Screen RAM must be exactly 1000 bytes.")
    return _write_asm_pair(
        output_base,
        AsmExportFrame(
            bitmap=frame.bitmap,
            screen_ram=frame.screen_ram,
            background_color=frame.background_color,
            border_color=_frame_border_color(frame),
            multicolor=False,
        ),
    )


def export_hires_prg_program(output_base: Path, frame: HiresFrame) -> Path:
    """Export one HIRES image as executable C64 PRG only."""
    if len(frame.bitmap) != 8000:
        raise ValueError("HIRES bitmap must be exactly 8000 bytes.")
    if len(frame.screen_ram) != 1000:
        raise ValueError("Screen RAM must be exactly 1000 bytes.")
    return _write_prg(
        output_base,
        AsmExportFrame(
            bitmap=frame.bitmap,
            screen_ram=frame.screen_ram,
            background_color=frame.background_color,
            border_color=_frame_border_color(frame),
            multicolor=False,
        ),
    )


def export_multicolor_asm_program(output_base: Path, frame: MulticolorFrame) -> tuple[Path, Path]:
    """Export one multicolor bitmap image as ASM-based PRG and 64 Studio .asm source."""
    if len(frame.bitmap) != 8000:
        raise ValueError("Multicolor bitmap must be exactly 8000 bytes.")
    if len(frame.screen_ram) != 1000:
        raise ValueError("Screen RAM must be exactly 1000 bytes.")
    if len(frame.color_ram) != 1000:
        raise ValueError("Color RAM must be exactly 1000 bytes.")
    return _write_asm_pair(
        output_base,
        AsmExportFrame(
            bitmap=frame.bitmap,
            screen_ram=frame.screen_ram,
            color_ram=frame.color_ram,
            background_color=frame.background_color,
            border_color=_frame_border_color(frame),
            multicolor=True,
        ),
    )


def export_multicolor_prg_program(output_base: Path, frame: MulticolorFrame) -> Path:
    """Export one multicolor bitmap image as executable C64 PRG only."""
    if len(frame.bitmap) != 8000:
        raise ValueError("Multicolor bitmap must be exactly 8000 bytes.")
    if len(frame.screen_ram) != 1000:
        raise ValueError("Screen RAM must be exactly 1000 bytes.")
    if len(frame.color_ram) != 1000:
        raise ValueError("Color RAM must be exactly 1000 bytes.")
    return _write_prg(
        output_base,
        AsmExportFrame(
            bitmap=frame.bitmap,
            screen_ram=frame.screen_ram,
            color_ram=frame.color_ram,
            background_color=frame.background_color,
            border_color=_frame_border_color(frame),
            multicolor=True,
        ),
    )


def _write_prg(output_base: Path, frame: AsmExportFrame) -> Path:
    output_base.parent.mkdir(parents=True, exist_ok=True)
    prg_path = output_base.with_suffix(".prg")
    prg_path.write_bytes(_build_asm_prg(frame))
    return prg_path


def _write_asm_pair(output_base: Path, frame: AsmExportFrame) -> tuple[Path, Path]:
    output_base.parent.mkdir(parents=True, exist_ok=True)
    prg_path = output_base.with_suffix(".prg")
    asm_path = output_base.with_suffix(".asm")
    program = _build_asm_prg(frame)
    prg_path.write_bytes(program)
    asm_path.write_text(_build_asm_source(frame), encoding="ascii", newline="\r\n")
    return prg_path, asm_path


def _build_asm_prg(frame: AsmExportFrame) -> bytes:
    stub = _basic_sys_stub(_MACHINE_START_ADDR)
    pad_len = _MACHINE_START_ADDR - (_LOAD_ADDR + len(stub))
    if pad_len < 0:
        raise ValueError("BASIC SYS stub overlaps machine code start.")
    payload = stub + bytes([0] * pad_len)
    machine_code = _build_machine_code(frame)
    data = _asm_frame_data(frame)
    return c64_prg_wrap(_LOAD_ADDR, payload + machine_code + data)


def _basic_sys_stub(sys_address: int) -> bytes:
    return _build_basic_program([(10, _tok_line(f"SYS {sys_address}"))])


def _asm_frame_data(frame: AsmExportFrame) -> bytes:
    data = bytearray(frame.bitmap)
    data += frame.screen_ram
    if frame.multicolor:
        if frame.color_ram is None:
            raise ValueError("Multicolor frame requires color RAM.")
        data += frame.color_ram
    return bytes(data)


def _frame_border_color(frame: HiresFrame | MulticolorFrame | AsmExportFrame) -> int:
    return (
        frame.background_color
        if frame.border_color is None
        else frame.border_color
    ) & 0x0F


def _build_machine_code(frame: AsmExportFrame) -> bytes:
    preliminary = _build_machine_code_at(frame, data_start=0)
    data_start = _MACHINE_START_ADDR + len(preliminary)
    return _build_machine_code_at(frame, data_start=data_start)


def _build_machine_code_at(frame: AsmExportFrame, data_start: int) -> bytes:
    code = bytearray()
    src = data_start
    _emit_copy(code, src, _BITMAP_ADDR, 8000)
    src += 8000
    _emit_copy(code, src, _SCREEN_ADDR, 1000)
    src += 1000
    if frame.multicolor:
        _emit_copy(code, src, _COLOR_RAM_ADDR, 1000)
    _emit_setup(code, frame.background_color, _frame_border_color(frame), frame.multicolor)
    _emit_wait_and_restore_text_mode(code)
    return bytes(code)


def _emit_setup(
    code: bytearray,
    background_color: int,
    border_color: int,
    multicolor: bool,
) -> None:
    code.extend([0xAD, 0x02, 0xDD])  # LDA $DD02
    code.extend([0x09, 0x03])  # ORA #$03
    code.extend([0x8D, 0x02, 0xDD])  # STA $DD02
    code.extend([0xAD, 0x00, 0xDD])  # LDA $DD00
    code.extend([0x29, 0xFC])  # AND #$FC
    code.extend([0x09, _VIC_BANK_BITS])  # ORA #bank
    code.extend([0x8D, 0x00, 0xDD])  # STA $DD00
    code.extend([0xA9, border_color & 0x0F])
    code.extend([0x8D, 0x20, 0xD0])  # STA $D020
    code.extend([0xA9, background_color & 0x0F])
    code.extend([0x8D, 0x21, 0xD0])  # STA $D021
    code.extend([0xA9, _VIC_D018])
    code.extend([0x8D, 0x18, 0xD0])  # STA $D018
    code.extend([0xAD, 0x16, 0xD0])  # LDA $D016
    code.extend([0x29, 0xEF])  # AND #$EF
    if multicolor:
        code.extend([0x09, 0x10])  # ORA #$10
    code.extend([0x8D, 0x16, 0xD0])  # STA $D016
    code.extend([0xAD, 0x11, 0xD0])  # LDA $D011
    code.extend([0x09, 0x20])  # ORA #$20
    code.extend([0x8D, 0x11, 0xD0])  # STA $D011


def _emit_copy(code: bytearray, src: int, dest: int, length: int) -> None:
    full_pages, remainder = divmod(length, 256)
    offset = 0
    for _ in range(full_pages):
        _emit_copy_page(code, src + offset, dest + offset)
        offset += 256
    if remainder:
        _emit_copy_remainder(code, src + offset, dest + offset, remainder)


def _emit_copy_page(code: bytearray, src: int, dest: int) -> None:
    code.extend([0xA2, 0x00])  # LDX #0
    loop_start = _MACHINE_START_ADDR + len(code)
    code.extend([0xBD, src & 0xFF, (src >> 8) & 0xFF])  # LDA src,X
    code.extend([0x9D, dest & 0xFF, (dest >> 8) & 0xFF])  # STA dest,X
    code.append(0xE8)  # INX
    branch_from = _MACHINE_START_ADDR + len(code)
    rel = (loop_start - (branch_from + 2)) & 0xFF
    code.extend([0xD0, rel])  # BNE loop


def _emit_copy_remainder(code: bytearray, src: int, dest: int, length: int) -> None:
    code.extend([0xA2, 0x00])  # LDX #0
    loop_start = _MACHINE_START_ADDR + len(code)
    code.extend([0xBD, src & 0xFF, (src >> 8) & 0xFF])  # LDA src,X
    code.extend([0x9D, dest & 0xFF, (dest >> 8) & 0xFF])  # STA dest,X
    code.append(0xE8)  # INX
    code.extend([0xE0, length & 0xFF])  # CPX #length
    branch_from = _MACHINE_START_ADDR + len(code)
    rel = (loop_start - (branch_from + 2)) & 0xFF
    code.extend([0xD0, rel])  # BNE loop


def _emit_wait_and_restore_text_mode(code: bytearray) -> None:
    loop_start = _MACHINE_START_ADDR + len(code)
    code.extend([0x20, 0xE4, 0xFF])  # JSR $FFE4 GETIN
    branch_from = _MACHINE_START_ADDR + len(code)
    rel = (loop_start - (branch_from + 2)) & 0xFF
    code.extend([0xF0, rel])  # BEQ wait
    code.extend([0xAD, 0x02, 0xDD])  # LDA $DD02
    code.extend([0x09, 0x03])  # ORA #$03
    code.extend([0x8D, 0x02, 0xDD])  # STA $DD02
    code.extend([0xAD, 0x00, 0xDD])  # LDA $DD00
    code.extend([0x29, 0xFC])  # AND #$FC
    code.extend([0x09, _NORMAL_VIC_BANK_BITS])  # ORA #normal bank
    code.extend([0x8D, 0x00, 0xDD])  # STA $DD00
    code.extend([0xA9, _NORMAL_BORDER_COLOR])
    code.extend([0x8D, 0x20, 0xD0])  # STA $D020
    code.extend([0xA9, _NORMAL_BACKGROUND_COLOR])
    code.extend([0x8D, 0x21, 0xD0])  # STA $D021
    code.extend([0xA9, _NORMAL_VIC_D018])
    code.extend([0x8D, 0x18, 0xD0])  # STA $D018
    code.extend([0xAD, 0x16, 0xD0])  # LDA $D016
    code.extend([0x29, 0xEF])  # AND #$EF
    code.extend([0x8D, 0x16, 0xD0])  # STA $D016
    code.extend([0xAD, 0x11, 0xD0])  # LDA $D011
    code.extend([0x29, 0xDF])  # AND #$DF
    code.extend([0x8D, 0x11, 0xD0])  # STA $D011
    code.extend([0xA9, _NORMAL_TEXT_COLOR])
    code.extend([0x8D, _BASIC_TEXT_COLOR_ADDR & 0xFF, (_BASIC_TEXT_COLOR_ADDR >> 8) & 0xFF])
    _emit_fill(code, _TEXT_SCREEN_ADDR, 1000, _NORMAL_SCREEN_CODE)
    _emit_fill(code, _COLOR_RAM_ADDR, 1000, _NORMAL_TEXT_COLOR)
    code.append(0x60)  # RTS back to BASIC, which prints READY.


def _emit_fill(code: bytearray, dest: int, length: int, value: int) -> None:
    full_pages, remainder = divmod(length, 256)
    offset = 0
    for _ in range(full_pages):
        _emit_fill_page(code, dest + offset, value)
        offset += 256
    if remainder:
        _emit_fill_remainder(code, dest + offset, remainder, value)


def _emit_fill_page(code: bytearray, dest: int, value: int) -> None:
    code.extend([0xA9, value & 0xFF])  # LDA #value
    code.extend([0xA2, 0x00])  # LDX #0
    loop_start = _MACHINE_START_ADDR + len(code)
    code.extend([0x9D, dest & 0xFF, (dest >> 8) & 0xFF])  # STA dest,X
    code.append(0xE8)  # INX
    branch_from = _MACHINE_START_ADDR + len(code)
    rel = (loop_start - (branch_from + 2)) & 0xFF
    code.extend([0xD0, rel])  # BNE loop


def _emit_fill_remainder(code: bytearray, dest: int, length: int, value: int) -> None:
    code.extend([0xA9, value & 0xFF])  # LDA #value
    code.extend([0xA2, 0x00])  # LDX #0
    loop_start = _MACHINE_START_ADDR + len(code)
    code.extend([0x9D, dest & 0xFF, (dest >> 8) & 0xFF])  # STA dest,X
    code.append(0xE8)  # INX
    code.extend([0xE0, length & 0xFF])  # CPX #length
    branch_from = _MACHINE_START_ADDR + len(code)
    rel = (loop_start - (branch_from + 2)) & 0xFF
    code.extend([0xD0, rel])  # BNE loop


def _build_asm_source(frame: AsmExportFrame) -> str:
    lines = [
        "; Generated by C64 Imager",
        "; Assemble in C64 Studio, then run the resulting PRG on C64/VICE/CCS64.",
        "",
        "ORG $0801",
        *_byte_lines(_basic_sys_stub(_MACHINE_START_ADDR)),
        "",
        "ORG $0810",
        "start:",
    ]
    lines.extend(_copy_asm_lines("bitmap", "bitmap_data", _BITMAP_ADDR, 8000))
    lines.extend(_copy_asm_lines("screen", "screen_data", _SCREEN_ADDR, 1000))
    if frame.multicolor:
        lines.extend(_copy_asm_lines("color", "color_data", _COLOR_RAM_ADDR, 1000))
    lines.extend(
        [
            "    lda $dd02",
            "    ora #$03",
            "    sta $dd02",
            "    lda $dd00",
            "    and #$fc",
            f"    ora #${_VIC_BANK_BITS:02x}",
            "    sta $dd00",
            f"    lda #${_frame_border_color(frame):02x}",
            "    sta $d020",
            f"    lda #${frame.background_color & 0x0F:02x}",
            "    sta $d021",
            f"    lda #${_VIC_D018:02x}",
            "    sta $d018",
            "    lda $d016",
            "    and #$ef",
        ]
    )
    if frame.multicolor:
        lines.append("    ora #$10")
    lines.extend(
        [
            "    sta $d016",
            "    lda $d011",
            "    ora #$20",
            "    sta $d011",
            "",
        ]
    )
    lines.extend(
        [
            "wait_key:",
            "    jsr $ffe4",
            "    beq wait_key",
            "    lda $dd02",
            "    ora #$03",
            "    sta $dd02",
            "    lda $dd00",
            "    and #$fc",
            f"    ora #${_NORMAL_VIC_BANK_BITS:02x}",
            "    sta $dd00",
            f"    lda #${_NORMAL_BORDER_COLOR:02x}",
            "    sta $d020",
            f"    lda #${_NORMAL_BACKGROUND_COLOR:02x}",
            "    sta $d021",
            f"    lda #${_NORMAL_VIC_D018:02x}",
            "    sta $d018",
            "    lda $d016",
            "    and #$ef",
            "    sta $d016",
            "    lda $d011",
            "    and #$df",
            "    sta $d011",
            f"    lda #${_NORMAL_TEXT_COLOR:02x}",
            f"    sta ${_BASIC_TEXT_COLOR_ADDR:04x}",
            "",
            "clear_text_screen:",
            f"    lda #${_NORMAL_SCREEN_CODE:02x}",
            "    ldx #$00",
            "clear_text_screen_loop:",
            f"    sta ${_TEXT_SCREEN_ADDR:04x},x",
            f"    sta ${_TEXT_SCREEN_ADDR + 0x0100:04x},x",
            f"    sta ${_TEXT_SCREEN_ADDR + 0x0200:04x},x",
            "    inx",
            "    bne clear_text_screen_loop",
            "    ldx #$00",
            "clear_text_screen_tail:",
            f"    sta ${_TEXT_SCREEN_ADDR + 0x0300:04x},x",
            "    inx",
            "    cpx #$e8",
            "    bne clear_text_screen_tail",
            "",
            "clear_color_ram:",
            f"    lda #${_NORMAL_TEXT_COLOR:02x}",
            "    ldx #$00",
            "clear_color_ram_loop:",
            f"    sta ${_COLOR_RAM_ADDR:04x},x",
            f"    sta ${_COLOR_RAM_ADDR + 0x0100:04x},x",
            f"    sta ${_COLOR_RAM_ADDR + 0x0200:04x},x",
            "    inx",
            "    bne clear_color_ram_loop",
            "    ldx #$00",
            "clear_color_ram_tail:",
            f"    sta ${_COLOR_RAM_ADDR + 0x0300:04x},x",
            "    inx",
            "    cpx #$e8",
            "    bne clear_color_ram_tail",
            "    rts",
            "",
            "bitmap_data:",
            *_byte_lines(frame.bitmap),
            "",
            "screen_data:",
            *_byte_lines(frame.screen_ram),
        ]
    )
    if frame.multicolor and frame.color_ram is not None:
        lines.extend(["", "color_data:", *_byte_lines(frame.color_ram)])
    return "\n".join(lines) + "\n"


def _basic_restore_source_lines(start_line: int) -> List[tuple[int, str]]:
    return [
        (start_line, f"POKE 56576, ( PEEK(56576) AND 252 ) OR {_NORMAL_VIC_BANK_BITS}"),
        (start_line + 10, f"POKE 53272, {_NORMAL_VIC_D018}"),
        (start_line + 20, "POKE 53270, PEEK(53270) AND 239"),
        (start_line + 30, "POKE 53265, PEEK(53265) AND 223"),
        (
            start_line + 40,
            f"POKE 53280, {_NORMAL_BORDER_COLOR} : POKE 53281, {_NORMAL_BACKGROUND_COLOR}",
        ),
        (start_line + 50, f"POKE {_BASIC_TEXT_COLOR_ADDR}, {_NORMAL_TEXT_COLOR}"),
        (
            start_line + 60,
            f"FOR I = 0 TO 999 : POKE {_TEXT_SCREEN_ADDR} + I, {_NORMAL_SCREEN_CODE} : "
            f"POKE {_COLOR_RAM_ADDR} + I, {_NORMAL_TEXT_COLOR} : NEXT",
        ),
        (start_line + 70, 'PRINT "READY."'),
        (start_line + 80, "END"),
    ]


def _copy_asm_lines(name: str, source_label: str, dest: int, length: int) -> List[str]:
    lines: List[str] = []
    full_pages, remainder = divmod(length, 256)
    offset = 0
    for page in range(full_pages):
        suffix = f"{name}_{page:02d}"
        lines.extend(
            [
                f"copy_{suffix}:",
                "    ldx #$00",
                f"copy_{suffix}_loop:",
                f"    lda {source_label} + ${offset:04x},x",
                f"    sta ${dest + offset:04x},x",
                "    inx",
                f"    bne copy_{suffix}_loop",
                "",
            ]
        )
        offset += 256
    if remainder:
        suffix = f"{name}_tail"
        lines.extend(
            [
                f"copy_{suffix}:",
                "    ldx #$00",
                f"copy_{suffix}_loop:",
                f"    lda {source_label} + ${offset:04x},x",
                f"    sta ${dest + offset:04x},x",
                "    inx",
                f"    cpx #${remainder:02x}",
                f"    bne copy_{suffix}_loop",
                "",
            ]
        )
    return lines


def _byte_lines(data: bytes, values_per_line: int = 16) -> List[str]:
    return [
        "DC.B " + ",".join(f"${value:02x}" for value in data[i : i + values_per_line])
        for i in range(0, len(data), values_per_line)
    ]


def _build_hires_data_source_lines(
    *,
    bitmap: bytes,
    screen_ram: bytes,
    background_color: int,
    border_color: int,
) -> List[tuple[int, str]]:
    lines: List[tuple[int, str]] = [
        (10, f"POKE 53280, {border_color} : POKE 53281, {background_color}"),
        (12, f"POKE 56576, ( PEEK(56576) AND 252 ) OR {_VIC_BANK_BITS}"),
        (14, f"POKE 53272, {_VIC_D018}"),
        (16, "POKE 53270, PEEK(53270) AND 239"),
        (18, "POKE 53265, PEEK(53265) OR 32"),
        (20, f"B = {_BITMAP_ADDR} : C = 8000 : GOSUB 500"),
        (30, f"B = {_SCREEN_ADDR} : C = 1000 : GOSUB 500"),
        (40, 'PRINT "PRESS ANY KEY..."'),
        (50, 'GET K$ : IF K$ = "" THEN 50'),
        *_basic_restore_source_lines(60),
        (500, "P = B : E = B + C - 1"),
        (510, "IF P > E THEN RETURN"),
        (520, "READ A$"),
        (530, "FOR J = 1 TO LEN(A$) STEP 2"),
        (540, "H = ASC(MID$(A$, J, 1)) : GOSUB 600 : V = H * 16"),
        (550, "H = ASC(MID$(A$, J + 1, 1)) : GOSUB 600 : POKE P, V + H : P = P + 1"),
        (560, "NEXT J : GOTO 510"),
        (600, "IF H > 64 THEN H = H - 55 : RETURN"),
        (610, "H = H - 48 : RETURN"),
    ]
    data_lines = _data_hex_source_lines(100, bitmap)
    data_lines.extend(_data_hex_source_lines(data_lines[-1][0] + 1, screen_ram))
    return _insert_data_before_subroutines(lines, data_lines)


def _build_multicolor_data_source_lines(frame: MulticolorFrame) -> List[tuple[int, str]]:
    lines: List[tuple[int, str]] = [
        (
            10,
            f"POKE 53280, {_frame_border_color(frame)} : "
            f"POKE 53281, {frame.background_color}",
        ),
        (12, f"POKE 56576, ( PEEK(56576) AND 252 ) OR {_VIC_BANK_BITS}"),
        (14, f"POKE 53272, {_VIC_D018}"),
        (16, "POKE 53270, ( PEEK(53270) AND 239 ) OR 16"),
        (18, "POKE 53265, PEEK(53265) OR 32"),
        (20, f"B = {_BITMAP_ADDR} : C = 8000 : GOSUB 500"),
        (30, f"B = {_SCREEN_ADDR} : C = 1000 : GOSUB 500"),
        (35, f"B = {_COLOR_RAM_ADDR} : C = 1000 : GOSUB 500"),
        (40, 'PRINT "PRESS ANY KEY..."'),
        (50, 'GET K$ : IF K$ = "" THEN 50'),
        *_basic_restore_source_lines(60),
        (500, "P = B : E = B + C - 1"),
        (510, "IF P > E THEN RETURN"),
        (520, "READ A$"),
        (530, "FOR J = 1 TO LEN(A$) STEP 2"),
        (540, "H = ASC(MID$(A$, J, 1)) : GOSUB 600 : V = H * 16"),
        (550, "H = ASC(MID$(A$, J + 1, 1)) : GOSUB 600 : POKE P, V + H : P = P + 1"),
        (560, "NEXT J : GOTO 510"),
        (600, "IF H > 64 THEN H = H - 55 : RETURN"),
        (610, "H = H - 48 : RETURN"),
    ]
    data_lines = _data_hex_source_lines(100, frame.bitmap)
    data_lines.extend(_data_hex_source_lines(data_lines[-1][0] + 1, frame.screen_ram))
    data_lines.extend(_data_hex_source_lines(data_lines[-1][0] + 1, frame.color_ram))
    return _insert_data_before_subroutines(lines, data_lines)


def _insert_data_before_subroutines(
    control_lines: Sequence[tuple[int, str]],
    data_lines: Sequence[tuple[int, str]],
) -> List[tuple[int, str]]:
    return sorted([*control_lines, *data_lines], key=lambda line: line[0])


def _data_hex_source_lines(start_line: int, data: bytes) -> List[tuple[int, str]]:
    """Store binary data as compact hex strings in DATA lines."""
    lines: List[tuple[int, str]] = []
    line_number = start_line
    for offset in range(0, len(data), _DATA_HEX_BYTES_PER_LINE):
        chunk = data[offset : offset + _DATA_HEX_BYTES_PER_LINE]
        lines.append((line_number, 'DATA "' + chunk.hex().upper() + '"'))
        line_number += 1
    return lines


def _write_basic_pair(output_base: Path, lines: Sequence[tuple[int, str]]) -> tuple[Path, Path]:
    output_base.parent.mkdir(parents=True, exist_ok=True)
    prg_path = output_base.with_suffix(".prg")
    bas_path = output_base.with_suffix(".bas")
    bas_path.write_text(_basic_ascii(lines), encoding="ascii", newline="\r\n")
    prg_path.write_bytes(c64_prg_wrap(_LOAD_ADDR, _build_basic_source_program(lines)))
    return prg_path, bas_path


def _basic_ascii(lines: Sequence[tuple[int, str]]) -> str:
    return "\n".join(f"{line_number} {source}" for line_number, source in lines) + "\n"


def _build_basic_source_program(lines: Sequence[tuple[int, str]]) -> bytes:
    return _build_basic_program([(line_number, _tok_line(source)) for line_number, source in lines])


def export_basic_hires_slideshow_prg(
    output_path: Path,
    frames: Sequence[HiresSlideshowFrame],
    background_color: int = 0,
    border_color: int | None = None,
) -> Path:
    """Generate a key-advance slideshow PRG (multiple frames, embedded binary blobs)."""
    if not frames:
        raise ValueError("At least one frame is required for slideshow export.")

    for frame in frames:
        if len(frame.bitmap) != 8000:
            raise ValueError("Each slideshow bitmap must be exactly 8000 bytes.")
        if len(frame.screen_ram) != 1000:
            raise ValueError("Each slideshow screen RAM must be exactly 1000 bytes.")

    frame_count = len(frames)
    basic_payload, _ = _build_hires_basic_payload(
        background_color=background_color,
        border_color=background_color if border_color is None else border_color,
        slideshow_frames=frame_count,
    )
    blob = bytearray()
    for frame in frames:
        blob += frame.bitmap
        blob += frame.screen_ram
    prg = c64_prg_wrap(_LOAD_ADDR, basic_payload + bytes(blob))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(prg)
    return output_path


def _build_hires_basic_payload(
    *,
    background_color: int,
    border_color: int,
    slideshow_frames: int,
) -> tuple[bytes, int]:
    """
    Build BASIC program bytes and return (payload, bitmap_base_address).
    bitmap_base_address is where the first embedded bitmap byte appears in C64 RAM
    ($0801 + length of this BASIC program).
    """
    guess_base = _LOAD_ADDR + 128
    basic_payload = b""

    for _ in range(48):
        lines: List[tuple[int, bytes]] = []
        lines.append(
            (
                10,
                _tok_line(
                    f"POKE 53280, {border_color & 0x0F} : "
                    f"POKE 53281, {background_color & 0x0F}"
                ),
            )
        )
        # VIC-II hires bitmap @ $2000, screen @ $0400: bank $0000-$3FFF, pointers, bitmap mode, hires (not MCM).
        lines.append(
            (
                12,
                _tok_line(
                    "POKE 56576, ( PEEK(56576) AND 252 ) OR 3"
                ),
            )
        )
        lines.append((14, _tok_line("POKE 53272, 24")))
        lines.append((16, _tok_line("POKE 53270, PEEK(53270) AND 239")))
        lines.append((18, _tok_line("POKE 53265, PEEK(53265) OR 32")))
        if slideshow_frames <= 1:
            b0 = guess_base
            lines.append((20, _tok_line(_copy_loop(8192, b0, 8000))))
            lines.append((30, _tok_line(_copy_loop(1024, b0 + 8000, 1000))))
            lines.append((40, _tok_line('PRINT "PRESS ANY KEY..."')))
            lines.append((50, _tok_line('GET K$ : IF K$ = "" THEN 50')))
            lines.extend(_tokenized_basic_restore_lines(60))
        else:
            line_no = 20
            for frame_index in range(slideshow_frames):
                frame_no = frame_index + 1
                bitmap_src = guess_base + frame_index * 9000
                screen_src = bitmap_src + 8000
                lines.append((line_no, _tok_line(_copy_loop(8192, bitmap_src, 8000))))
                line_no += 10
                lines.append((line_no, _tok_line(_copy_loop(1024, screen_src, 1000))))
                line_no += 10
                lines.append(
                    (
                        line_no,
                        _tok_line(f'PRINT "FRAME {frame_no} / {slideshow_frames}  KEY..."'),
                    )
                )
                line_no += 10
                lines.append((line_no, _tok_line(f'GET K$ : IF K$ = "" THEN {line_no}')))
                line_no += 10
            lines.extend(_tokenized_basic_restore_lines(line_no))

        basic_payload = _build_basic_program(lines)
        actual_base = _LOAD_ADDR + len(basic_payload)
        if actual_base == guess_base:
            return basic_payload, actual_base
        guess_base = actual_base

    raise RuntimeError("Could not converge BASIC loader base address.")


def _tokenized_basic_restore_lines(start_line: int) -> List[tuple[int, bytes]]:
    return [
        (line_number, _tok_line(source))
        for line_number, source in _basic_restore_source_lines(start_line)
    ]


def _copy_loop(dest: int, src: int, length: int) -> str:
    """Return a BASIC PEEK/POKE loop with a safe direction for overlapping ranges."""
    if length <= 0:
        raise ValueError("Copy length must be positive.")
    dest_end = dest + length
    src_end = src + length
    overlaps = src < dest_end and dest < src_end
    if overlaps and dest > src:
        return f"FOR I = {length - 1} TO 0 STEP -1 : POKE {dest} + I, PEEK({src} + I) : NEXT"
    return f"FOR I = 0 TO {length - 1} : POKE {dest} + I, PEEK({src} + I) : NEXT"


def _build_basic_program(lines: Sequence[tuple[int, bytes]]) -> bytes:
    parts = bytearray()
    current_addr = 0x0801
    for line_number, tokenized in lines:
        next_addr = current_addr + 2 + 2 + len(tokenized) + 1
        parts += bytes((next_addr & 0xFF, (next_addr >> 8) & 0xFF))
        parts += bytes((line_number & 0xFF, (line_number >> 8) & 0xFF))
        parts += tokenized
        parts.append(0x00)
        current_addr = next_addr
    parts += b"\x00\x00"
    return bytes(parts)


def _tok_line(source: str) -> bytes:
    # Commodore BASIC V2 — see e.g. https://www.c64-wiki.com/wiki/BASIC_token
    # AND=$AF, OR=$B0, relational > is $B1 (do not swap OR and >).
    tokens = {
        "END": 0x80,
        "FOR": 0x81,
        "NEXT": 0x82,
        "DATA": 0x83,
        "GOSUB": 0x8D,
        "RETURN": 0x8E,
        "GOTO": 0x89,
        "IF": 0x8B,
        "THEN": 0xA7,
        "STEP": 0xA9,
        "TO": 0xA4,
        "GET": 0xA1,
        "POKE": 0x97,
        "PRINT": 0x99,
        "READ": 0x87,
        "SYS": 0x9E,
        "LEN": 0xC3,
        "PEEK": 0xC2,
        "ASC": 0xC6,
        "MID$": 0xCA,
        "INT": 0xB5,
        "AND": 0xAF,
        "OR": 0xB0,
        "+": 0xAA,
        "-": 0xAB,
        "*": 0xAC,
        "/": 0xAD,
        ">": 0xB1,
        "=": 0xB2,
        "<": 0xB3,
    }

    out = bytearray()
    i = 0
    while i < len(source):
        ch = source[i]
        if ch == '"':
            out.append(ord(ch))
            i += 1
            while i < len(source):
                out.append(ord(source[i]))
                if source[i] == '"':
                    i += 1
                    break
                i += 1
            continue

        matched_kw: str | None = None
        for kw in sorted(tokens.keys(), key=len, reverse=True):
            if source.startswith(kw, i):
                matched_kw = kw
                break
        if matched_kw is not None:
            out.append(tokens[matched_kw])
            i += len(matched_kw)
            continue

        out.append(ord(ch))
        i += 1
    return bytes(out)
