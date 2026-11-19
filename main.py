#!/usr/bin/env python3
"""Entry for make.fun bounty "Sum up 19 November's world news in one image".

The repository holds one front-page style image, ``entry.png``, that sums up
the world news of Thursday 19 November 2026. This program is the entry: it
validates the image against the competition's gate rules and then writes it
to ``/output/entry.png`` (or to a path given as the first argument, which is
handy for local testing).

Only the Python standard library is used, and nothing here touches the
network, so the program runs exactly the same in the grader's sandbox as it
does on a laptop.

Gate rules enforced before anything is written:
  * the file is a PNG or a JPEG, told apart by its first bytes;
  * it is at most 1 MiB (1048576 bytes);
  * it is at most 1024 by 1024 pixels;
  * a PNG carries a complete IHDR and IEND, a JPEG ends with its EOI marker.
"""

import struct
import sys
import zlib
from pathlib import Path

MAX_BYTES = 1_048_576
MAX_SIDE = 1024

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
JPEG_SOI = b"\xff\xd8"
JPEG_EOI = b"\xff\xd9"

HERE = Path(__file__).resolve().parent
SOURCE = HERE / "entry.png"
DEFAULT_OUTPUT = Path("/output/entry.png")


def png_dimensions(data: bytes) -> tuple[int, int]:
    """Read width and height from a PNG's IHDR chunk."""
    if not data.startswith(PNG_SIGNATURE):
        raise ValueError("not a PNG: bad signature")
    if data[12:16] != b"IHDR":
        raise ValueError("not a PNG: first chunk is not IHDR")
    width, height = struct.unpack(">II", data[16:24])
    check_png_chunks(data)
    return width, height


def check_png_chunks(data: bytes) -> None:
    """Walk every PNG chunk: lengths must tile the file exactly, each
    chunk's CRC must match its contents, and IEND must come last — the
    gate asks for a whole image, not a header with good intentions."""
    pos = len(PNG_SIGNATURE)
    seen_iend = False
    while pos < len(data):
        if pos + 8 > len(data):
            raise ValueError("truncated PNG: chunk header runs past the end")
        length = struct.unpack(">I", data[pos : pos + 4])[0]
        ctype = data[pos + 4 : pos + 8]
        end = pos + 8 + length + 4
        if end > len(data):
            raise ValueError(f"truncated PNG: chunk {ctype!r} runs past the end")
        stored_crc = struct.unpack(">I", data[pos + 8 + length : end])[0]
        actual_crc = zlib.crc32(data[pos + 4 : pos + 8 + length]) & 0xFFFFFFFF
        if stored_crc != actual_crc:
            raise ValueError(f"corrupt PNG: CRC mismatch in chunk {ctype!r}")
        pos = end
        if ctype == b"IEND":
            seen_iend = True
            break
    if not seen_iend:
        raise ValueError("truncated PNG: IEND chunk missing")
    if pos != len(data):
        raise ValueError("corrupt PNG: trailing bytes after IEND")


def jpeg_dimensions(data: bytes) -> tuple[int, int]:
    """Walk JPEG segments until a start-of-frame marker gives the size."""
    if not data.startswith(JPEG_SOI):
        raise ValueError("not a JPEG: bad start-of-image marker")
    if not data.rstrip().endswith(JPEG_EOI):
        raise ValueError("truncated JPEG: end-of-image marker missing")
    pos = 2
    while pos + 4 <= len(data):
        if data[pos] != 0xFF:
            raise ValueError(f"corrupt JPEG: expected marker at byte {pos}")
        marker = data[pos + 1]
        # Standalone markers (SOI, EOI, RSTn, TEM) carry no length field.
        if marker in (0xD8, 0xD9, 0x01) or 0xD0 <= marker <= 0xD7:
            pos += 2
            continue
        length = struct.unpack(">H", data[pos + 2 : pos + 4])[0]
        # SOF0, SOF1 and SOF2 hold precision, height and width.
        if marker in (0xC0, 0xC1, 0xC2):
            height, width = struct.unpack(">HH", data[pos + 5 : pos + 9])
            return width, height
        pos += 2 + length
    raise ValueError("no start-of-frame marker found in JPEG")


def validate(data: bytes) -> tuple[str, int, int]:
    """Check the gate rules and return (kind, width, height)."""
    if len(data) > MAX_BYTES:
        raise ValueError(f"image is {len(data)} bytes, over the 1 MiB limit")
    if data.startswith(PNG_SIGNATURE):
        kind, (width, height) = "PNG", png_dimensions(data)
    elif data.startswith(JPEG_SOI):
        kind, (width, height) = "JPEG", jpeg_dimensions(data)
    else:
        raise ValueError("image is neither PNG nor JPEG")
    if width > MAX_SIDE or height > MAX_SIDE:
        raise ValueError(f"image is {width}x{height}, over the 1024px limit")
    if width == 0 or height == 0:
        raise ValueError("image has a zero side")
    return kind, width, height


def main(argv: list[str]) -> int:
    output = Path(argv[1]) if len(argv) > 1 else DEFAULT_OUTPUT
    data = SOURCE.read_bytes()
    kind, width, height = validate(data)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(data)
    print(f"wrote {output} ({kind}, {width}x{height}, {len(data)} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
