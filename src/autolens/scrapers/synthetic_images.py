"""Deterministic SYNTHETIC car images for exercising the image pipeline.

IMPORTANT — honesty contract (handbook 8.4 / 15.9 / REMAINING_REQUIREMENTS #3):
These images are *generated locally*, not downloaded from any source. They are
placeholders used only to prove that quarantine storage, SHA-256 image ids,
perceptual hashing and the `photo_match` comparison feature work end to end.
Every generated row is labelled `synthetic_placeholder` in
`staging_image_fetch.status` and recorded in `outputs/synthetic_images_manifest.csv`.
They MUST NOT be reported as real image observations or used as evidence of
lawful image acquisition. Replace them with images obtained with permission
before any production claim.

The same seed always yields the same bytes, so a car listed on two platforms
(canonical make/model/year/trim) receives the *same* synthetic photo and the
pHash-based `photo_match` feature behaves like the real pipeline would.
"""

from __future__ import annotations

import hashlib
from io import BytesIO

from PIL import Image, ImageDraw

IMAGE_WIDTH = 320
IMAGE_HEIGHT = 200
SYNTHETIC_STATUS = "synthetic_placeholder"
MANIFEST_NOTE = "SYNTHETIC_PLACEHOLDER_NOT_A_REAL_OBSERVATION"


def image_seed(listing: dict) -> str:
    """Stable seed shared by the same car across sources.

    Deliberately excludes price/mileage (which change over time) and source
    (which differs across platforms) so near-duplicate listings collide on the
    same synthetic image.
    """
    parts = [
        str(listing.get("make_canon") or ""),
        str(listing.get("model_canon") or ""),
        str(listing.get("year") or ""),
        str(listing.get("transmission") or ""),
        str(listing.get("fuel_type") or ""),
        str(listing.get("body_type") or ""),
    ]
    return "|".join(parts)


def synthetic_image_bytes(seed: str, width: int = IMAGE_WIDTH, height: int = IMAGE_HEIGHT) -> bytes:
    """Return deterministic PNG bytes for ``seed`` (simple stylised car)."""
    digest = hashlib.sha256(seed.encode("utf-8")).digest()
    body_rgb = (60 + digest[0] % 150, 60 + digest[1] % 150, 60 + digest[2] % 150)
    bg_rgb = (200 + digest[3] % 50, 210 + digest[4] % 45, 220 + digest[5] % 35)
    # A couple of seed-driven details so different cars have different pHashes.
    roof_shift = digest[6] % 20
    wheel_gap = 8 + digest[7] % 10

    img = Image.new("RGB", (width, height), bg_rgb)
    d = ImageDraw.Draw(img)
    d.rectangle(
        [18, height - 42, width - 18, height - 12], fill=body_rgb, outline=(30, 30, 30), width=2
    )
    d.polygon(
        [
            (60 + roof_shift, height - 42),
            (100 + roof_shift, height - 80),
            (width - 100, height - 80),
            (width - 50, height - 42),
        ],
        fill=body_rgb,
        outline=(30, 30, 30),
    )
    d.rectangle([105 + roof_shift, height - 76, width - 105, height - 48], fill=(180, 215, 235))
    for cx in (18 + wheel_gap + 30, width - 18 - wheel_gap - 30):
        d.ellipse([cx - 18, height - 20, cx + 18, height + 12], fill=(25, 25, 25))
        d.ellipse([cx - 7, height - 9, cx + 7, height + 5], fill=(190, 190, 190))
    d.text((12, 10), "SYNTHETIC", fill=(120, 40, 40))

    buf = BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()
