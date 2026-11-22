from __future__ import annotations

import re

_ARABIC_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")

_MOBILE = re.compile(r"(?<!\d)(?:\+?\s?20[\s\-.]?)?0?1[0125](?:[\s\-.]?\d){8}(?!\d)")
_LANDLINE = re.compile(r"(?<!\d)0[2-9]\d?[\s\-.]?\d{7,8}(?!\d)")
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")


def _mask(text: str, probe: str, pattern: re.Pattern[str], token: str) -> tuple[str, str]:
    out: list[str] = []
    out_probe: list[str] = []
    last = 0
    for m in pattern.finditer(probe):
        out.append(text[last : m.start()])
        out.append(token)
        out_probe.append(probe[last : m.start()])
        out_probe.append(token)
        last = m.end()
    out.append(text[last:])
    out_probe.append(probe[last:])
    return "".join(out), "".join(out_probe)


def scrub_contact_info(text: str | None) -> str | None:
    """Replace phone numbers (ASCII or Arabic-Indic digits) and e-mails with tokens.

    Seller contact details must never be stored (Part IV, privacy rules).
    """
    if not text:
        return text
    probe = text.translate(_ARABIC_DIGITS)
    text, probe = _mask(text, probe, _EMAIL, "[email]")
    text, probe = _mask(text, probe, _MOBILE, "[phone]")
    text, _ = _mask(text, probe, _LANDLINE, "[phone]")
    return text


def contains_contact_info(text: str | None) -> bool:
    if not text:
        return False
    probe = text.translate(_ARABIC_DIGITS)
    return bool(_EMAIL.search(probe) or _MOBILE.search(probe) or _LANDLINE.search(probe))
