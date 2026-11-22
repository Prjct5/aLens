"""Download openly-licensed car photos from Wikimedia Commons (handbook R7, 8.4).

This replaces the synthetic placeholders with REAL car photographs that carry a
free licence (CC0 / Public domain / CC BY / CC BY-SA). Every image is:
  - fetched politely (identifiable User-Agent, >=1 request/second),
  - stored once in quarantine keyed by SHA-256 of the original bytes,
  - pHash-computed with the same 64-bit DCT routine,
  - recorded with full attribution in `outputs/open_images_attribution.csv`.

IMPORTANT honesty note: these are generic car photos from an open source, NOT
photographs of the specific listings in the supplied archives. They exercise the
image pipeline and the `photo_match` feature with real imagery; they are not
evidence that a listing had a photo, and they are not scraped from a target site.
See docs/REMAINING_REQUIREMENTS.md.

Usage:
    python scripts/fetch_open_images.py [--n 400]

Requires network access + the `httpx` extra (already in the environment).
"""

from __future__ import annotations

import argparse
import hashlib
import time
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path

import httpx
import numpy as np
import pandas as pd
from PIL import Image

from autolens.common.local_backend import Warehouse
from autolens.scrapers.images import image_id_from_bytes, phash
from autolens.scrapers.settings import M1Settings as Settings
from autolens.scrapers.synthetic_images import image_seed

ROOT = Path(__file__).resolve().parents[1]
COMMONS_API = "https://commons.wikimedia.org/w/api.php"
HEADERS = {"User-Agent": "AutoLens-Egypt/0.1 (academic research; contact: team@autolens.example)"}
# Only licences that permit academic use + redistribution with attribution.
ALLOWED_LICENCES = ("CC0", "Public domain", "CC BY", "CC BY-SA")
SEARCHES = (
    "filetype:bitmap sedan car",
    "filetype:bitmap hatchback car",
    "filetype:bitmap SUV car",
    "filetype:bitmap Toyota Camry",
    "filetype:bitmap Honda Civic",
    "filetype:bitmap Mercedes car",
    "filetype:bitmap BMW sedan",
    "filetype:bitmap Nissan car",
    "filetype:bitmap Mitsubishi car",
    "filetype:bitmap Hyundai car",
    "filetype:bitmap Chevrolet car",
    "filetype:bitmap Kia car",
)
MIN_REQUEST_INTERVAL = 1.0  # R5: never exceed 1 req/s
# Titles that indicate the photo is not a clean exterior car shot.
BAD_TITLE_WORDS = (
    "plaque",
    "information",
    "badge",
    "logo",
    "interior",
    "steering",
    "engine",
    "license",
    "plate",
    "diagram",
    "drawing",
    "poster",
    "sign",
)


def _licence_ok(meta: dict) -> bool:
    name = meta.get("LicenseShortName", {}).get("value", "")
    return any(name.startswith(prefix) for prefix in ALLOWED_LICENCES)


def _search(client: httpx.Client, query: str, limit: int = 50) -> list[dict]:
    params = {
        "action": "query",
        "format": "json",
        "generator": "search",
        "gsrsearch": query,
        "gsrnamespace": 6,
        "gsrlimit": limit,
        "prop": "imageinfo",
        "iiprop": "url|extmetadata|size",
        "iiurlwidth": 400,
    }
    r = client.get(COMMONS_API, params=params, timeout=30)
    r.raise_for_status()
    out = []
    for p in r.json().get("query", {}).get("pages", {}).values():
        ii = p.get("imageinfo", [{}])[0]
        meta = ii.get("extmetadata", {})
        title_lower = p["title"].lower()
        if not _licence_ok(meta) or "thumburl" not in ii:
            continue
        if any(word in title_lower for word in BAD_TITLE_WORDS):
            continue
        out.append(
            {
                "title": p["title"],
                "thumburl": ii["thumburl"],
                "source_url": ii.get("descriptionurl", ""),
                "licence": meta.get("LicenseShortName", {}).get("value", ""),
                "artist": meta.get("Artist", {}).get("value", ""),
                "credit": meta.get("Credit", {}).get("value", ""),
            }
        )
    return out


def _download(client: httpx.Client, url: str) -> bytes | None:
    r = client.get(url, timeout=30)
    if r.status_code != 200 or not r.content:
        return None
    try:
        img = Image.open(BytesIO(r.content))
        img.verify()  # reject corrupt payloads
        if img.size[0] < 80 or img.size[1] < 60:
            return None
    except Exception:
        return None
    return r.content


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, default=400, help="number of distinct photos to fetch")
    args = parser.parse_args()

    settings = Settings.from_env()
    qdir = Path(settings.quarantine_dir)
    qdir.mkdir(parents=True, exist_ok=True)
    outdir = Path(settings.output_dir)
    outdir.mkdir(parents=True, exist_ok=True)

    client = httpx.Client(headers=HEADERS, timeout=30)
    last_request = 0.0
    candidates: list[dict] = []
    for q in SEARCHES:
        wait = MIN_REQUEST_INTERVAL - (time.monotonic() - last_request)
        if wait > 0:
            time.sleep(wait)
        found = _search(client, q)
        last_request = time.monotonic()
        print(f"search {q!r}: {len(found)} usable licence hits")
        candidates.extend(found)
        if len(candidates) >= args.n * 2:
            break
    # De-duplicate by source page.
    seen_titles: set[str] = set()
    unique = []
    for c in candidates:
        if c["title"] not in seen_titles:
            seen_titles.add(c["title"])
            unique.append(c)
    unique = unique[: args.n]
    print(f"fetching {len(unique)} distinct openly-licensed photos")

    photos: list[dict] = []
    attribution: list[dict] = []
    for i, c in enumerate(unique, 1):
        wait = MIN_REQUEST_INTERVAL - (time.monotonic() - last_request)
        if wait > 0:
            time.sleep(wait)
        data = _download(client, c["thumburl"])
        last_request = time.monotonic()
        if data is None:
            continue
        image_id = image_id_from_bytes(data)
        path = qdir / f"{image_id}.jpg"
        path.write_bytes(data)
        ph = phash(np.asarray(Image.open(BytesIO(data)).convert("RGB")))
        photos.append({"image_id": image_id, "phash": ph})
        attribution.append(
            {
                "image_id": image_id,
                "title": c["title"],
                "licence": c["licence"],
                "artist": c["artist"][:300],
                "source_url": c["source_url"],
                "cache_path": (
                    str(path.relative_to(settings.root))
                    if path.is_relative_to(settings.root)
                    else str(path)
                ),
                "fetched_at": datetime.now(UTC).isoformat(),
            }
        )
        if i % 25 == 0:
            print(f"  {i}/{len(unique)} downloaded")
    client.close()

    if not photos:
        raise SystemExit("no photos downloaded; check network / licence filters")

    # Assign each distinct car seed to one photo deterministically.
    db = Warehouse(settings.db_path)
    rows = db.query(
        "SELECT * FROM staging_normalized_listing WHERE scrape_date=?",
        (settings.run_date,),
    )
    now = datetime.now(UTC).isoformat()
    fetch_rows = []
    for r in rows:
        listing = dict(r)
        key = f"{listing['source']}:{listing['source_listing_id']}"
        seed = image_seed(listing)
        pick = int(hashlib.sha256(seed.encode()).hexdigest(), 16) % len(photos)
        photo = photos[pick]
        fetch_rows.append(
            {
                "listing_key": key,
                "position": 0,
                "image_id": photo["image_id"],
                "source_url": None,
                "fetched_at": now,
                "width": 400,
                "height": 300,
                "phash": photo["phash"],
                "status": "open_source_commons",
                "quarantine_key": f"quarantine/{photo['image_id']}.jpg",
            }
        )
    db.insert_many("staging_image_fetch", fetch_rows)
    db.close()

    pd.DataFrame(attribution).to_csv(outdir / "open_images_attribution.csv", index=False)
    print(
        f"wrote {len(photos)} photos to quarantine, {len(fetch_rows)} image_fetch rows, "
        f"and {outdir / 'open_images_attribution.csv'}"
    )


if __name__ == "__main__":
    main()
