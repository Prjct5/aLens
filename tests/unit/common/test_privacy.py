from __future__ import annotations

import pytest

from autolens.common.privacy import contains_contact_info, scrub_contact_info


@pytest.mark.parametrize(
    "text",
    [
        "call me 01012345678 now",
        "whatsapp +20 10 1234 5678",
        "٠١٠١٢٣٤٥٦٧٨ للتواصل",
        "tel 0101-234-5678",
        "mail seller@example.com please",
        "landline 03 4567890",
    ],
)
def test_contact_details_are_removed(text: str) -> None:
    assert contains_contact_info(text)
    cleaned = scrub_contact_info(text)
    assert cleaned is not None and not contains_contact_info(cleaned)
    assert "[phone]" in cleaned or "[email]" in cleaned


@pytest.mark.parametrize(
    "text",
    ["Toyota Corolla 2018, 90000 km", "price 1,250,000 EGP negotiable", "2 owners, 4 doors", ""],
)
def test_ordinary_text_is_untouched(text: str) -> None:
    assert scrub_contact_info(text) == text
    assert not contains_contact_info(text)


def test_none_passes_through() -> None:
    assert scrub_contact_info(None) is None
