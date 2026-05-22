"""Byte-split depth PNG (``.pngd``).

A single-file lossless container for uint16 depth images.  Internally the
high and low bytes are stored as two independent 8-bit PNG streams, which
typically compresses several times smaller than a single uint16 PNG for the
slowly-varying depth maps produced by RealSense-style cameras.

Public API::

    from pngd import save_depth, load_depth, encode, decode

Importing the package also registers the PNGD format with Pillow::

    from PIL import Image
    Image.open("frame.pngd")          # -> mode "I;16"
    img.save("frame.pngd")            # writes a .pngd container
"""
from __future__ import annotations

from ._format import HEADER_SIZE, MAGIC, VERSION, Header
from .core import (
    decode,
    encode,
    load_depth,
    load_depth_stream,
    save_depth,
    save_depth_stream,
)
from .pil_plugin import PngdImageFile, register as _register_pil

_register_pil()

__all__ = [
    "HEADER_SIZE",
    "Header",
    "MAGIC",
    "PngdImageFile",
    "VERSION",
    "decode",
    "encode",
    "load_depth",
    "load_depth_stream",
    "save_depth",
    "save_depth_stream",
]

__version__ = "0.1.0"
