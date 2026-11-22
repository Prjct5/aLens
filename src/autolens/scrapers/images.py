"""Image quarantine + 64-bit pHash (handbook 6.7, 8.4).

The supplied archives carry no image URLs. To exercise the full image pipeline
(callers, quarantine, SHA-256 ids, pHash, `photo_match` comparison and ablation)
we optionally generate clearly-labelled SYNTHETIC placeholder images. They are
never presented as real observations; see synthetic_images.py.
"""

from __future__ import annotations

import hashlib
import os
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path

import numpy as np
import pandas as pd
from PIL import Image
from scipy.fftpack import dct

from autolens.common.stage import RunContext, StageResult
from autolens.scrapers.synthetic_images import (
    MANIFEST_NOTE,
    SYNTHETIC_STATUS,
    image_seed,
    synthetic_image_bytes,
)


def phash(image_array: np.ndarray, hash_size: int = 8, highfreq_factor: int = 4) -> str:
    """64-bit perceptual hash as 16 lower-case hex chars.

    downsize to (hash_size*highfreq_factor)^2 greyscale, DCT, keep the lowest
    hash_size^2 low-frequency coefficients, threshold at their median (6.7).
    """
    from PIL import Image  # optional dependency

    img = Image.fromarray(image_array).convert("L")
    size = hash_size * highfreq_factor
    pixels = np.asarray(img.resize((size, size), Image.LANCZOS), dtype=float)
    d = dct(dct(pixels, axis=0, norm="ortho"), axis=1, norm="ortho")[:hash_size, :hash_size]
    bits = d > np.median(d[1:, :])
    value = 0
    for bit in bits.flatten():
        value = (value << 1) | int(bit)
    return f"{value:016x}"


def image_id_from_bytes(data: bytes) -> str:
    """image_id = lower-case SHA-256 of original bytes (16.1)."""
    return hashlib.sha256(data).hexdigest()


def _synthetic_enabled() -> bool:
    """Synthetic placeholders are DISABLED by default now that real open-licensed
    photos are available via ``scripts/fetch_open_images.py``. Set to 1 only for
    offline demos; never as evidence of real image acquisition.
    """
    return os.getenv("AUTOLENS_SYNTHETIC_IMAGES", "0").strip() not in {"0", "false", "False", "no"}


def run_fetch_images(run_date, ctx: RunContext) -> StageResult:
    """Populate ``staging_image_fetch`` from synthetic placeholders.

    Real lawful images (M3) would replace the generator call with an HTTP fetch
    into quarantine; the storage, hashing and downstream contract are identical.
    """
    ctx.settings.ensure_dirs()
    qdir = Path(ctx.settings.quarantine_dir)
    qdir.mkdir(parents=True, exist_ok=True)

    rows = ctx.db.query(
        "SELECT * FROM staging_normalized_listing WHERE scrape_date=?", (str(run_date),)
    )
    if not _synthetic_enabled():
        # Keep existing open-source image assignments when the synthetic fallback
        # is off and the archive has no URLs (do not wipe them on re-runs).
        existing = ctx.db.query(
            "SELECT COUNT(*) AS n FROM staging_image_fetch WHERE listing_key IN "
            "(SELECT source || ':' || source_listing_id FROM staging_normalized_listing "
            " WHERE scrape_date=?)",
            (str(run_date),),
        )[0]["n"]
        if existing:
            ctx.log.info("image fetch: keeping %d existing open-source image rows", existing)
            return StageResult(
                "fetch_images",
                run_date,
                len(rows),
                existing,
                ["using_open_source_commons_images"],
                {"n_images": existing, "provenance": "open_source_commons"},
            )
        ctx.log.info("image fetch: synthetic images disabled; archive has no URLs")
        return StageResult("fetch_images", run_date, 0, 0, ["no_image_urls_in_archive"])

    if not rows:
        return StageResult("fetch_images", run_date, 0, 0, ["no_normalized_listings"])

    now = datetime.now(UTC).isoformat()
    cache: dict[str, tuple[str, bytes, str]] = {}  # seed -> (image_id, bytes, phash)
    seen_hashes: set[str] = set()
    fetch_rows: list[dict] = []
    manifest: list[dict] = []

    for r in rows:
        listing = dict(r)
        listing_key = f"{listing['source']}:{listing['source_listing_id']}"
        seed = image_seed(listing)
        if seed not in cache:
            data = synthetic_image_bytes(seed)
            image_id = image_id_from_bytes(data)
            ph = phash(np.asarray(Image.open(BytesIO(data)).convert("RGB")))
            cache[seed] = (image_id, data, ph)
            if image_id not in seen_hashes:
                seen_hashes.add(image_id)
                (qdir / f"{image_id}.png").write_bytes(data)
        image_id, _data, ph = cache[seed]
        fetch_rows.append(
            {
                "listing_key": listing_key,
                "position": 0,
                "image_id": image_id,
                "source_url": None,
                "fetched_at": now,
                "width": 320,
                "height": 200,
                "phash": ph,
                "status": SYNTHETIC_STATUS,
                "quarantine_key": f"quarantine/{image_id}.png",
            }
        )
        manifest.append(
            {
                "listing_key": listing_key,
                "image_id": image_id,
                "phash": ph,
                "status": SYNTHETIC_STATUS,
                "note": MANIFEST_NOTE,
            }
        )

    ctx.db.execute(
        "DELETE FROM staging_image_fetch WHERE listing_key IN "
        "(SELECT source || ':' || source_listing_id FROM staging_normalized_listing "
        " WHERE scrape_date=?)",
        (str(run_date),),
    )
    ctx.db.insert_many("staging_image_fetch", fetch_rows)
    pd.DataFrame(manifest).to_csv(
        Path(ctx.settings.output_dir) / "synthetic_images_manifest.csv", index=False
    )
    ctx.log.info(
        "image fetch: %d synthetic placeholders (%d unique) written to quarantine; %s",
        len(fetch_rows),
        len(seen_hashes),
        MANIFEST_NOTE,
    )
    return StageResult(
        "fetch_images",
        run_date,
        len(rows),
        len(fetch_rows),
        ["synthetic_placeholders_not_real_image_observations"],
        {
            "n_images": len(fetch_rows),
            "n_unique_hashes": len(seen_hashes),
            "provenance": "synthetic_placeholder",
        },
    )
