"""On-disk layout of the .pngd container.

See ``docs/format.md`` for the normative spec; this module is its
machine-readable mirror.
"""
from __future__ import annotations

import struct
from dataclasses import dataclass

MAGIC: bytes = b"\x89PNGD\r\n\x1a\n"
assert len(MAGIC) == 9, "MAGIC length is part of the on-disk layout"
MAGIC_LEN: int = len(MAGIC)

VERSION: int = 1

# Header (after magic):
#   uint8   version
#   uint8   flags         (reserved, must be 0 in v1)
#   uint16  reserved      (must be 0 in v1)
#   uint32  hi_len        big-endian
#   uint32  lo_len        big-endian
_HEADER_STRUCT = struct.Struct(">BBHII")
HEADER_SIZE: int = MAGIC_LEN + _HEADER_STRUCT.size  # 9 + 12 = 21


@dataclass(frozen=True)
class Header:
    version: int
    flags: int
    hi_len: int
    lo_len: int

    def pack(self) -> bytes:
        return MAGIC + _HEADER_STRUCT.pack(
            self.version, self.flags, 0, self.hi_len, self.lo_len
        )

    @classmethod
    def unpack(cls, buf: bytes) -> "Header":
        if len(buf) < HEADER_SIZE:
            raise ValueError(
                f"pngd header truncated: need {HEADER_SIZE} bytes, got {len(buf)}"
            )
        if buf[:MAGIC_LEN] != MAGIC:
            raise ValueError("not a pngd file: magic bytes mismatch")
        version, flags, reserved, hi_len, lo_len = _HEADER_STRUCT.unpack(
            buf[MAGIC_LEN:HEADER_SIZE]
        )
        if version != VERSION:
            raise ValueError(f"unsupported pngd version: {version}")
        if reserved != 0:
            raise ValueError(f"pngd reserved field must be 0, got {reserved}")
        if flags != 0:
            raise ValueError(f"pngd flags must be 0 in v1, got {flags:#x}")
        return cls(version=version, flags=flags, hi_len=hi_len, lo_len=lo_len)


def accept(prefix: bytes) -> bool:
    """Magic-bytes sniffer for PIL's open dispatch."""
    return prefix[:MAGIC_LEN] == MAGIC
