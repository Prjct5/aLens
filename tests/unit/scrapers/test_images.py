"""pHash tests (handbook 6.7): robustness to recompression/resize and specificity."""

import numpy as np
import pytest

from autolens.scrapers.images import image_id_from_bytes, phash

PIL = pytest.importorskip("PIL")
import io  # noqa: E402

from PIL import Image  # noqa: E402


def _sample():
    img = np.zeros((96, 96, 3), dtype=np.uint8)
    img[18:52, 18:52] = 255
    img[60:75, 10:40] = 180
    return img


def test_phash_stable_for_recompression_and_resize():
    img = _sample()
    h1 = phash(img)
    # Simulate recompression + watermark-like small noise.
    buf = io.BytesIO()
    Image.fromarray(img).save(buf, format="JPEG", quality=70)
    reloaded = np.asarray(Image.open(io.BytesIO(buf.getvalue())).convert("RGB"))
    h2 = phash(reloaded)
    assert len(h1) == 16
    assert h1 == h2, "pHash must survive JPEG recompression"


def test_phash_distinguishes_different_images():
    a = _sample()
    b = np.roll(a, 40, axis=1)
    ha, hb = phash(a), phash(b)
    assert ha != hb, "visually different images must not collide"


def test_phash_of_scaled_image_is_similar():
    a = _sample()
    b = np.asarray(Image.fromarray(a).resize((64, 64), Image.LANCZOS))
    assert phash(a) == phash(b)


def test_sha256_id():
    assert image_id_from_bytes(b"abc") == (
        "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
    )
