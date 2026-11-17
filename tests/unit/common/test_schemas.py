from __future__ import annotations

import pytest
from pydantic import ValidationError

from autolens.common.schemas import listing_key
from autolens.common.schemas.core import ImageAsset
from autolens.common.schemas.staging import ImageFetch


def test_listing_key() -> None:
    assert listing_key("hatla2ee", "42") == "hatla2ee:42"
    with pytest.raises(ValueError):
        listing_key("unknown", "42")


def test_image_id_must_be_sha256_hex() -> None:
    with pytest.raises(ValidationError):
        ImageFetch(
            listing_key="hatla2ee:1",
            position=0,
            image_id="not-a-hash",
            source_url="x",
            fetched_at="2026-01-15T00:00:00Z",
            status="fetched",
        )


def test_extra_fields_forbidden() -> None:
    with pytest.raises(ValidationError):
        ImageAsset(  # type: ignore[call-arg]
            image_id="a" * 64,
            width=1,
            height=1,
            object_key="aa/a.jpg",
            n_faces_blurred=0,
            n_plates_blurred=0,
            blur_model_version="v",
            promoted_at="2026-01-15T00:00:00Z",
            seller_phone="000",
        )
