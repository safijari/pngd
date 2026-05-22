"""Tests for the pngd package and PIL plugin."""
from __future__ import annotations

import io
import struct
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

import pngd
from pngd._format import HEADER_SIZE, MAGIC


def _depth_fixture(seed: int = 0) -> np.ndarray:
    """A realsense-flavored depth map: smooth foreground + noisy background."""
    rng = np.random.default_rng(seed)
    h, w = 64, 80
    # smooth ramp for the high byte
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    smooth = (xx * 50 + yy * 30 + 1500).astype(np.uint16)
    # plus per-pixel jitter for the low byte
    jitter = rng.integers(0, 256, size=(h, w), dtype=np.uint16)
    return (smooth + jitter).astype(np.uint16)


# ---------- round-trip ----------


def test_roundtrip_file(tmp_path: Path) -> None:
    depth = _depth_fixture()
    out = tmp_path / "frame.pngd"
    pngd.save_depth(depth, out)
    restored = pngd.load_depth(out)
    assert restored.dtype == np.uint16
    assert np.array_equal(restored, depth)


def test_roundtrip_bytes() -> None:
    depth = _depth_fixture(seed=1)
    blob = pngd.encode(depth)
    assert blob.startswith(MAGIC)
    restored = pngd.decode(blob)
    assert np.array_equal(restored, depth)


def test_roundtrip_stream() -> None:
    depth = _depth_fixture(seed=2)
    buf = io.BytesIO()
    pngd.save_depth_stream(depth, buf)
    buf.seek(0)
    restored = pngd.load_depth_stream(buf)
    assert np.array_equal(restored, depth)


def test_full_uint16_range() -> None:
    # 0 and 65535 must survive.
    depth = np.array(
        [[0, 1, 255, 256], [0xFFFF, 0xFF00, 0x00FF, 0x1234]], dtype=np.uint16
    )
    restored = pngd.decode(pngd.encode(depth))
    assert np.array_equal(restored, depth)


# ---------- input validation ----------


def test_rejects_non_uint16() -> None:
    bad = np.zeros((4, 4), dtype=np.uint8)
    with pytest.raises(TypeError):
        pngd.encode(bad)


def test_rejects_non_2d() -> None:
    bad = np.zeros((4, 4, 3), dtype=np.uint16)
    with pytest.raises(ValueError):
        pngd.encode(bad)


# ---------- header parsing ----------


def test_rejects_bad_magic() -> None:
    blob = pngd.encode(_depth_fixture())
    corrupted = b"X" * 9 + blob[9:]
    with pytest.raises(ValueError, match="magic"):
        pngd.decode(corrupted)


def test_rejects_bad_version() -> None:
    blob = pngd.encode(_depth_fixture())
    corrupted = bytearray(blob)
    corrupted[9] = 99  # version byte (after 9-byte magic)
    with pytest.raises(ValueError, match="version"):
        pngd.decode(bytes(corrupted))


def test_rejects_nonzero_reserved() -> None:
    blob = pngd.encode(_depth_fixture())
    corrupted = bytearray(blob)
    corrupted[11:13] = b"\x01\x00"  # reserved (offset 11..13)
    with pytest.raises(ValueError, match="reserved"):
        pngd.decode(bytes(corrupted))


def test_rejects_truncated() -> None:
    blob = pngd.encode(_depth_fixture())
    with pytest.raises(ValueError, match="truncated"):
        pngd.decode(blob[:-10])


# ---------- PIL plugin ----------


def test_pil_open_roundtrip(tmp_path: Path) -> None:
    depth = _depth_fixture(seed=3)
    out = tmp_path / "frame.pngd"
    pngd.save_depth(depth, out)

    img = Image.open(out)
    assert img.format == "PNGD"
    assert img.mode == "I;16"
    assert img.size == (depth.shape[1], depth.shape[0])
    assert np.array_equal(np.asarray(img, dtype=np.uint16), depth)


def test_pil_save_roundtrip(tmp_path: Path) -> None:
    depth = _depth_fixture(seed=4)
    src = Image.fromarray(depth)
    out = tmp_path / "frame.pngd"
    src.save(out)

    restored = pngd.load_depth(out)
    assert np.array_equal(restored, depth)


def test_pil_save_format_arg(tmp_path: Path) -> None:
    """``img.save(path, format="PNGD")`` must work for a non-.pngd suffix."""
    depth = _depth_fixture(seed=5)
    src = Image.fromarray(depth)
    out = tmp_path / "frame.bin"
    src.save(out, format="PNGD")
    restored = pngd.load_depth(out)
    assert np.array_equal(restored, depth)


def test_pil_save_from_8bit_mode_l(tmp_path: Path) -> None:
    # An 8-bit image should also be losslessly storable.
    arr = np.arange(256 * 256, dtype=np.uint16).reshape(256, 256) % 256
    src = Image.fromarray(arr.astype(np.uint8), mode="L")
    out = tmp_path / "gray.pngd"
    src.save(out)
    restored = pngd.load_depth(out)
    assert np.array_equal(restored, arr.astype(np.uint16))


def test_pil_rejects_unwritable_mode(tmp_path: Path) -> None:
    # RGB has no obvious uint16 mapping.
    src = Image.new("RGB", (4, 4))
    out = tmp_path / "bad.pngd"
    with pytest.raises(OSError):
        src.save(out)


# ---------- format integrity ----------


def test_header_size_constant() -> None:
    # Spec says 21 bytes (9-byte magic + 12-byte fixed header).
    assert HEADER_SIZE == 21


def test_planes_are_valid_pngs() -> None:
    """The interior planes must be standalone valid PNGs (per the spec)."""
    blob = pngd.encode(_depth_fixture(seed=6))
    _v, _f, _r, hi_len, lo_len = struct.unpack(">BBHII", blob[9:21])
    hi_bytes = blob[21 : 21 + hi_len]
    lo_bytes = blob[21 + hi_len : 21 + hi_len + lo_len]

    PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
    assert hi_bytes.startswith(PNG_MAGIC)
    assert lo_bytes.startswith(PNG_MAGIC)

    hi_img = Image.open(io.BytesIO(hi_bytes))
    lo_img = Image.open(io.BytesIO(lo_bytes))
    assert hi_img.mode == "L" and lo_img.mode == "L"
    assert hi_img.size == lo_img.size


def test_compression_beats_uint16_png(tmp_path: Path) -> None:
    """Sanity check: byte-split should beat a plain 16-bit PNG on depth-like data."""
    depth = _depth_fixture(seed=7)

    plain = tmp_path / "plain.png"
    Image.fromarray(depth).save(plain, optimize=True)

    split = tmp_path / "frame.pngd"
    pngd.save_depth(depth, split)

    assert split.stat().st_size < plain.stat().st_size
