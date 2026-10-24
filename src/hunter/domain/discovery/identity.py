"""Normalised names, so one company or one job seen in different sources gets one key."""

import re
import unicodedata

AND_COMPANY = re.compile(r"&\s*co\b\.?")
LEGAL_FORMS = re.compile(
    r"\b(gmbh|ag|se|kg|kgaa|ug|ohg|gbr|ev|co|ltd|limited|inc|llc|plc|bv|nv|sa|sas|sarl|spa|srl|"
    r"corp|corporation|labs|group|holding|technologies)\b"
)
GENDER_MARKER = re.compile(r"\((?:m|w|f|d|x|div|all|gn|mwd)\b[^)]*\)", re.IGNORECASE)
NOT_ALPHANUMERIC = re.compile(r"[^a-z0-9]+")


def folded(text: str) -> str:
    """Lower case, accents dropped: 'Zürich' -> 'zurich'."""
    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()


def text_key(text: str) -> str:
    """Words only, single spaces: 'Full-Stack' -> 'full stack'."""
    return NOT_ALPHANUMERIC.sub(" ", folded(text)).strip()


def company_key(name: str) -> str:
    """'Bartko & Reher GmbH & Co. KG' -> 'bartkoandreher'."""
    plain = AND_COMPANY.sub(" ", folded(name)).replace("&", " and ")
    return NOT_ALPHANUMERIC.sub("", LEGAL_FORMS.sub(" ", plain))


def title_key(title: str) -> str:
    """'Senior Backend Engineer (m/w/d)' -> 'senior backend engineer'."""
    return text_key(GENDER_MARKER.sub(" ", title))
