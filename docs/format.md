# PNGD — Byte-Split Depth PNG, v1

`.pngd` is a single-file lossless container for 16-bit depth images.
It stores the high and low bytes of a `uint16` depth map as two
independent 8-bit PNG streams concatenated behind a small fixed header.

## Motivation

RealSense-style depth cameras emit slowly-varying `uint16` images.
Encoded as a single 16-bit PNG, the filter/predictor inside libpng has
to operate on 2-byte samples, which is a poor fit for depth data where
the high byte changes slowly (mostly a few unique values across the
frame) and the low byte is approximately uniform noise.

Splitting the image into two 8-bit planes lets libpng compress each
plane with the predictor that suits it:

- **hi plane:** large flat regions → predictor + DEFLATE shrink it dramatically.
- **lo plane:** near-random → barely compresses, but is no worse than
  the bottom byte of a 16-bit PNG would have been.

In practice this is consistently smaller than the equivalent
single-file 16-bit PNG, while remaining bit-exact and entirely
implementable in terms of standard PNG tooling. The exact win depends
on the scene: typical RealSense frames see ~1.2–1.5× smaller files,
and scenes with large flat regions (or large invalid/zero regions) do
considerably better.

The `.pngd` container exists so this representation can live in a
single file instead of two side-by-side files that downstream tools
might forget to keep paired.

## File layout

All multi-byte integers are **big-endian** (network byte order),
matching PNG itself.

```
Offset  Size  Field         Notes
------  ----  -----------   ----------------------------------------
 0      9    magic         0x89 'P' 'N' 'G' 'D' 0x0D 0x0A 0x1A 0x0A
 9      1    version       0x01
10      1    flags         0x00 in v1 (reserved)
11      2    reserved      0x0000 in v1
13      4    hi_len        length of the hi-plane PNG, in bytes
17      4    lo_len        length of the lo-plane PNG, in bytes
21      hi_len   hi PNG    a standalone 8-bit grayscale PNG stream
21+hi_len lo_len lo PNG    a standalone 8-bit grayscale PNG stream
```

Total fixed header size: **21 bytes**.

### Magic

The 9-byte magic mirrors PNG's own (`\x89PNG\r\n\x1a\n`) with `D`
inserted to make `\x89PNGD\r\n\x1a\n`. This keeps PNG-style
robustness against text-mode corruption (the high-bit byte detects
7-bit transports, the CR/LF pair detects newline translation, the EOF
byte stops naive `cat`/`type` output, etc.) and is unambiguously
distinct from a plain PNG.

### Planes

Both planes are valid standalone PNG streams. A v1 reader MUST reject
the file if either plane:

- is not a standard 8-bit grayscale PNG (Pillow mode `"L"`), or
- has dimensions that differ from the other plane.

Both planes SHOULD be encoded with `optimize=True` (or equivalent),
since the dominant cost is encoding time, not decoding.

### Reconstruction

Given decoded plane arrays `hi` and `lo` (both `uint8`, shape `(H, W)`):

```python
depth = (hi.astype(uint16) << 8) | lo.astype(uint16)
```

This is exact and reversible.

## Versioning

- `version == 1`: the layout above.
- Future versions are free to redefine `flags` and the layout after
  byte 10. Readers MUST reject unknown versions rather than guess.
- The reserved fields MUST be zero in v1; readers MUST reject nonzero
  values so v2 can use them safely.

## MIME and extension

- File extension: `.pngd`
- MIME type: `image/x-pngd`

## Why not …?

- **Two side-by-side PNGs.** Works, but the pair can be split apart
  by file transfers, version control, archives, etc. `.pngd`
  guarantees the planes travel together.
- **16-bit PNG.** Noticeably larger for typical RealSense depth; the
  uint16 PNG predictor cannot exploit the very different statistics
  of the high and low bytes.
- **PNG with a private ancillary chunk holding the second plane.**
  Most PNG decoders drop unknown ancillary chunks silently on
  re-encode, so the file format becomes lossy in the hands of generic
  tooling. A distinct extension makes the "this is not a normal PNG"
  contract explicit.
- **A zip of two PNGs.** Adds central directory overhead and CRC32s
  that PNG already provides per chunk. Decoders also need a zip
  parser, which is much larger than a 20-byte header.
- **EXR / TIFF / OpenEXR.** Heavier dependencies, and `.pngd` keeps
  the option of repairing a file with nothing more than a PNG decoder.

## Recovering planes with stock tools

A `.pngd` file is just `[21-byte header][hi.png][lo.png]`. You can
extract the two PNGs with `dd` and the lengths from the header, or
with any tool that can read the header and slice the file.

For example, given a `frame.pngd`:

```sh
python -c "
import struct
buf = open('frame.pngd','rb').read()
v, f, r, hi, lo = struct.unpack('>BBHII', buf[9:21])
open('frame_hi.png','wb').write(buf[21:21+hi])
open('frame_lo.png','wb').write(buf[21+hi:21+hi+lo])
"
```

This is a deliberate design choice: the format degrades gracefully to
"two PNGs" when needed.
