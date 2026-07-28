# pngd

Lossless single-file container for 16-bit depth images, stored as two
byte-split 8-bit PNGs.

For depth maps from RealSense-style cameras, `.pngd` is consistently
smaller than a single uint16 PNG of the same image — ~1.2–1.5× on
typical frames, more on scenes with large flat regions — while
remaining bit-exact and decoder-friendly.

See [`docs/format.md`](docs/format.md) for the normative format spec.

## Install

```sh
pip install pngd
```

## Use

### As a function

```python
import numpy as np
import pngd

depth = np.load("frame.npy").astype(np.uint16)  # (H, W) uint16

pngd.save_depth(depth, "frame.pngd")
roundtrip = pngd.load_depth("frame.pngd")
assert np.array_equal(depth, roundtrip)
```

### Through Pillow

Importing `pngd` registers the format with Pillow, so the usual
`Image.open` / `img.save` flow works:

```python
import pngd  # registers the PNGD plugin
from PIL import Image

img = Image.open("frame.pngd")   # mode "I;16"
img.save("copy.pngd")            # round-trips losslessly
```

You can also save any 16-bit Pillow image to `.pngd`:

```python
from PIL import Image
import pngd  # noqa: F401

Image.open("frame_16bit.png").save("frame.pngd")
```

### Streams

```python
import io, pngd

buf = io.BytesIO()
pngd.save_depth_stream(depth, buf)
buf.seek(0)
restored = pngd.load_depth_stream(buf)
```

## When to use this

- You have many uint16 depth frames and storage matters.
- You need a single file per frame (e.g. for indexing, archival, S3 keys).
- You don't want to invent your own naming scheme to keep the hi/lo
  PNG pair from getting separated.

If you only need the in-memory split, the existing
`save_depth_bytesplit` / `load_depth_bytesplit` helpers that write two
side-by-side files remain fine.

## Compatibility

- Python 3.9+
- NumPy 1.20+
- Pillow 9.0+

## License

MIT
