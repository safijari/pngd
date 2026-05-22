"""Save and load uint16 depth images as single-file ``.pngd`` containers."""
from __future__ import annotations

import io
import os
from typing import BinaryIO, Union

import numpy as np
from PIL import Image

from ._format import Header, VERSION

PathLike = Union[str, "os.PathLike[str]"]


def _encode_plane(plane: np.ndarray, optimize: bool) -> bytes:
    buf = io.BytesIO()
    Image.fromarray(plane, mode="L").save(buf, format="PNG", optimize=optimize)
    return buf.getvalue()


def encode(depth: np.ndarray, *, optimize: bool = True) -> bytes:
    """Encode a uint16 depth array to .pngd bytes.

    Args:
        depth: ``uint16`` array of shape ``(H, W)``.
        optimize: pass ``optimize=True`` to the underlying PNG encoder.
            Slower but smaller; recommended for batch saves.
    """
    if not isinstance(depth, np.ndarray):
        raise TypeError(f"expected numpy.ndarray, got {type(depth).__name__}")
    if depth.dtype != np.uint16:
        raise TypeError(f"expected uint16, got {depth.dtype}")
    if depth.ndim != 2:
        raise ValueError(f"expected 2D array, got shape {depth.shape}")

    hi = (depth >> 8).astype(np.uint8)
    lo = (depth & 0xFF).astype(np.uint8)

    hi_bytes = _encode_plane(hi, optimize)
    lo_bytes = _encode_plane(lo, optimize)

    header = Header(version=VERSION, flags=0, hi_len=len(hi_bytes), lo_len=len(lo_bytes))
    return header.pack() + hi_bytes + lo_bytes


def decode(data: bytes) -> np.ndarray:
    """Decode .pngd bytes back into a uint16 ``(H, W)`` array."""
    header = Header.unpack(data[: _format_header_size()])
    off = _format_header_size()
    hi_bytes = data[off : off + header.hi_len]
    off += header.hi_len
    lo_bytes = data[off : off + header.lo_len]
    if len(hi_bytes) != header.hi_len or len(lo_bytes) != header.lo_len:
        raise ValueError("pngd payload truncated")

    hi = np.asarray(Image.open(io.BytesIO(hi_bytes)), dtype=np.uint16)
    lo = np.asarray(Image.open(io.BytesIO(lo_bytes)), dtype=np.uint16)
    if hi.shape != lo.shape:
        raise ValueError(f"hi/lo shape mismatch: {hi.shape} vs {lo.shape}")
    return (hi << 8) | lo


def save_depth(depth: np.ndarray, path: PathLike, *, optimize: bool = True) -> str:
    """Save a uint16 depth image to a single .pngd file.

    Returns the path that was written.
    """
    payload = encode(depth, optimize=optimize)
    path_str = os.fspath(path)
    with open(path_str, "wb") as fp:
        fp.write(payload)
    return path_str


def load_depth(path: PathLike) -> np.ndarray:
    """Load a .pngd file back into a uint16 ``(H, W)`` array."""
    with open(os.fspath(path), "rb") as fp:
        return decode(fp.read())


def save_depth_stream(depth: np.ndarray, fp: BinaryIO, *, optimize: bool = True) -> None:
    """Write a uint16 depth image to an open binary stream."""
    fp.write(encode(depth, optimize=optimize))


def load_depth_stream(fp: BinaryIO) -> np.ndarray:
    """Read a uint16 depth image from an open binary stream."""
    return decode(fp.read())


def _format_header_size() -> int:
    # Indirection keeps the public API independent of the constant import path.
    from ._format import HEADER_SIZE

    return HEADER_SIZE
