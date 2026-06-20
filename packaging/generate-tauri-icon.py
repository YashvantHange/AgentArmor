"""Generate a minimal app icon for Tauri Windows builds (stdlib only)."""
from __future__ import annotations

import struct
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ICON_DIR = ROOT / "gui" / "src-tauri" / "icons"
PNG_PATH = ICON_DIR / "icon.png"


def _chunk(tag: bytes, data: bytes) -> bytes:
    return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)


def write_png(path: Path, size: int = 256) -> None:
  """Simple solid-color PNG with a lighter shield-like diamond."""
  rows = []
  cx, cy = (size - 1) / 2, (size - 1) / 2
  for y in range(size):
    row = bytearray([0])  # filter byte
    for x in range(size):
      nx, ny = (x - cx) / size, (y - cy) / size
      inside = abs(nx) + abs(ny) * 1.2 < 0.42 and ny < 0.15
      if inside:
        row.extend((37, 99, 235, 255))  # blue
      else:
        row.extend((15, 23, 42, 255))  # slate background
    rows.append(bytes(row))
  raw = b"".join(rows)
  ihdr = struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0)
  png = b"\x89PNG\r\n\x1a\n" + _chunk(b"IHDR", ihdr) + _chunk(b"IDAT", zlib.compress(raw, 9)) + _chunk(b"IEND", b"")
  path.parent.mkdir(parents=True, exist_ok=True)
  path.write_bytes(png)


def main() -> None:
  write_png(PNG_PATH)
  print(f"Wrote {PNG_PATH}")


if __name__ == "__main__":
  main()
