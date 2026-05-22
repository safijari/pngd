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

## Releasing

Releases are cut by publishing a GitHub Release; the
[`Release`](.github/workflows/release.yml) workflow builds an sdist
and wheel and publishes them to PyPI via trusted publishing (OIDC),
so no API tokens are stored in the repo.

To cut a release:

1. Bump `version` in `pyproject.toml` (and `__version__` in
   `src/pngd/__init__.py`) and commit.
2. Create a GitHub Release whose **tag** is `vX.Y.Z` (matching the
   `pyproject.toml` version exactly). The release workflow refuses to
   publish if the two disagree.
3. The workflow builds, runs `twine check`, and uploads to PyPI.

### One-time PyPI setup

Before the first release, configure the PyPI project as a Trusted
Publisher (no API token needed):

- Go to <https://pypi.org/manage/account/publishing/> and add a
  **pending** trusted publisher with:
  - PyPI Project Name: `pngd`
  - Owner: `safijari`
  - Repository name: `pngd`
  - Workflow name: `release.yml`
  - Environment name: `pypi`
- In the GitHub repo, create an Environment named `pypi`
  (Settings → Environments → New environment). Optionally add
  required reviewers so a human has to approve each publish.

After the first successful publish PyPI converts the pending publisher
to a normal one automatically.

## License

MIT
