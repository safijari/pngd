"""Pillow plugin for the ``.pngd`` format.

Importing :mod:`pngd` (or this module) registers ``PNGD`` with Pillow so
``Image.open("frame.pngd")`` and ``img.save("frame.pngd")`` work transparently.
"""
from __future__ import annotations

import io

import numpy as np
from PIL import Image, ImageFile

from ._format import HEADER_SIZE, Header, accept
from .core import encode

_FORMAT = "PNGD"


class PngdImageFile(ImageFile.ImageFile):
    format = _FORMAT
    format_description = "Byte-split depth PNG (uint16)"

    def _open(self) -> None:
        header_bytes = self.fp.read(HEADER_SIZE)
        try:
            header = Header.unpack(header_bytes)
        except ValueError as exc:
            raise SyntaxError(str(exc)) from exc

        hi_bytes = self.fp.read(header.hi_len)
        lo_bytes = self.fp.read(header.lo_len)
        if len(hi_bytes) != header.hi_len or len(lo_bytes) != header.lo_len:
            raise SyntaxError("pngd payload truncated")

        hi_img = Image.open(io.BytesIO(hi_bytes))
        lo_img = Image.open(io.BytesIO(lo_bytes))
        if hi_img.size != lo_img.size:
            raise SyntaxError(
                f"pngd hi/lo size mismatch: {hi_img.size} vs {lo_img.size}"
            )
        if hi_img.mode != "L" or lo_img.mode != "L":
            raise SyntaxError(
                f"pngd planes must be mode 'L', got {hi_img.mode!r}/{lo_img.mode!r}"
            )

        hi_arr = np.asarray(hi_img, dtype=np.uint16)
        lo_arr = np.asarray(lo_img, dtype=np.uint16)
        combined = ((hi_arr << 8) | lo_arr).astype("<u2", copy=False)

        self._size = hi_img.size  # (W, H)
        self._mode = "I;16"

        # Hand the raw little-endian uint16 bytes to Pillow's "raw" decoder so
        # the normal load() machinery (lazy decode, cropping, etc.) just works.
        original_fp = self.fp
        self.fp = io.BytesIO(combined.tobytes())
        if getattr(self, "_exclusive_fp", False):
            try:
                original_fp.close()
            except Exception:
                pass
        self.tile = [("raw", (0, 0) + self._size, 0, ("I;16", 0, 1))]

    def load(self):
        # Pillow's default load() tries to mmap the original file for "raw"
        # tiles when the mode is in _MAPMODES. For .pngd the file holds
        # compressed PNGs, not raw uint16 pixels, so mmap reads the wrong
        # bytes and raises. Hide the filename across the super call to
        # force the read-from-fp path; restore it afterwards so img.filename
        # still works for callers.
        saved = self.filename
        self.filename = ""
        try:
            return super().load()
        finally:
            self.filename = saved


def _coerce_uint16(im: Image.Image) -> np.ndarray:
    mode = im.mode
    if mode in ("I;16", "I;16L"):
        arr = np.frombuffer(im.tobytes(), dtype="<u2")
        return arr.reshape(im.size[1], im.size[0]).astype(np.uint16, copy=False)
    if mode == "I;16B":
        arr = np.frombuffer(im.tobytes(), dtype=">u2")
        return arr.reshape(im.size[1], im.size[0]).astype(np.uint16, copy=False)
    if mode == "I":
        arr = np.asarray(im)
        lo, hi = int(arr.min()), int(arr.max())
        if lo < 0 or hi > 0xFFFF:
            raise ValueError(
                f"mode 'I' values out of uint16 range: [{lo}, {hi}]"
            )
        return arr.astype(np.uint16)
    if mode == "L":
        return np.asarray(im, dtype=np.uint16)
    raise OSError(f"cannot write mode {mode!r} as PNGD; need a 16-bit integer image")


def _save(im: Image.Image, fp, filename) -> None:  # noqa: ANN001 — Pillow signature
    optimize = bool(im.encoderinfo.get("optimize", True))
    arr = _coerce_uint16(im)
    fp.write(encode(arr, optimize=optimize))


def register() -> None:
    """Idempotently register the PNGD plugin with Pillow."""
    if _FORMAT in Image.OPEN:
        return
    Image.register_open(_FORMAT, PngdImageFile, accept)
    Image.register_save(_FORMAT, _save)
    Image.register_extension(_FORMAT, ".pngd")
    Image.register_mime(_FORMAT, "image/x-pngd")


register()
