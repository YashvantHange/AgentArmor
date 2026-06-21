"""Generate AgentArmor app icon for Tauri Windows builds (stdlib only)."""
from __future__ import annotations

import struct
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ICON_DIR = ROOT / "gui" / "src-tauri" / "icons"
PNG_PATH = ICON_DIR / "icon.png"

# Brand emerald + slate palette
BG = (15, 23, 42, 255)
SHIELD = (5, 150, 105, 255)
SHIELD_HIGHLIGHT = (52, 211, 153, 255)


def _chunk(tag: bytes, data: bytes) -> bytes:
    return (
        struct.pack(">I", len(data))
        + tag
        + data
        + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
    )


def _in_shield(nx: float, ny: float) -> bool:
    """Diamond shield silhouette."""
    return abs(nx) + abs(ny) * 1.15 < 0.4 and ny < 0.12


def _in_highlight(nx: float, ny: float) -> bool:
    return _in_shield(nx, ny) and ny < -0.05 and nx > -0.08


def write_png(path: Path, size: int = 1024) -> None:
    rows = []
    cx, cy = (size - 1) / 2, (size - 1) / 2
    for y in range(size):
        row = bytearray([0])
        for x in range(size):
            nx, ny = (x - cx) / size, (y - cy) / size
            if _in_highlight(nx, ny):
                row.extend(SHIELD_HIGHLIGHT)
            elif _in_shield(nx, ny):
                row.extend(SHIELD)
            else:
                row.extend(BG)
        rows.append(bytes(row))
    raw = b"".join(rows)
    ihdr = struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0)
    png = (
        b"\x89PNG\r\n\x1a\n"
        + _chunk(b"IHDR", ihdr)
        + _chunk(b"IDAT", zlib.compress(raw, 9))
        + _chunk(b"IEND", b"")
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(png)


def main() -> None:
    write_png(PNG_PATH)
    print(f"Wrote {PNG_PATH}")


if __name__ == "__main__":
    main()
