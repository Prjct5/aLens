"""Contract tests: Pydantic models are the source of truth (15.2, Part IV)."""

import pytest
from pydantic import ValidationError

from autolens.common.schemas import (
    SOURCES,
    ImageRef,
    NormalizedListing,
    ParsedListing,
    listing_key,
)


def test_listing_key_contract():
    assert listing_key("hatla2ee", "123") == "hatla2ee:123"
    assert SOURCES == ("hatla2ee", "contactcars", "dubizzle")


def test_parsed_listing_validation():
    base = dict(
        source="hatla2ee",
        source_listing_id="1",
        url="u",
        scrape_date="2026-01-15",
        scraped_at="2026-01-15T01:00:00+00:00",
        run_id="r",
    )
    obj = ParsedListing(**base)
    assert obj.key == "hatla2ee:1"
    with pytest.raises(ValidationError):
        ParsedListing(**{**base, "source": "unknown"})
    with pytest.raises(ValidationError):
        ParsedListing(**{**base, "seller_phone": "010..."})  # extra forbidden


def test_normalized_and_image_contracts():
    n = NormalizedListing(source="dubizzle", source_listing_id="2", scrape_date="2026-01-15")
    assert n.dq_flags == {}
    assert n.model_id is None
    with pytest.raises(ValidationError):
        ImageRef(listing_key="k", position=1, image_id="xyz")
