"""Likely boards for a company Hunter knows only by its name. Most systems name a company's board
after the company, so the board is guessed from the name's words, most likely first. Workday's
`tenant/wdN/site` can't be guessed. Nothing is guessed from one word of a longer name: "delivery"
for Delivery Hero would find some other company's board."""

import re
import unicodedata

from hunter.domain.discovery.boards import Board
from hunter.domain.discovery.identity import LEGAL_FORMS, company_words

# Workable isn't guessed: it allows few requests a day, and its boards come in through links.
GUESSABLE = ("greenhouse", "ashby", "lever", "recruitee", "teamtailor")
PERSONIO_DOMAINS = ("de", "com")
WORDS = re.compile(r"[A-Za-z0-9]+")
# The longest name a web address can have in one part, and so the longest slug any board can have.
LONGEST_SLUG = 63


def slugs(name: str) -> list[str]:
    """'Bartko & Reher GmbH & Co. KG' -> bartkoandreher, bartko-and-reher, bartkoreher."""
    words = company_words(name)
    if not words:
        return []
    forms = ["".join(words), "-".join(words), "".join(word for word in words if word != "and")]
    return [form for form in dict.fromkeys(forms) if len(form) <= LONGEST_SLUG]


def capitalised(name: str) -> list[str]:
    """SmartRecruiters keeps the name's capitals: 'Redcare Pharmacy' -> Redcare-Pharmacy."""
    plain = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    words = [word for word in WORDS.findall(plain) if not LEGAL_FORMS.fullmatch(word.lower())]
    forms = ("-".join(words), "".join(words))
    return [form for form in dict.fromkeys(forms) if form and len(form) <= LONGEST_SLUG]


def board_candidates(name: str) -> list[Board]:
    found = slugs(name)
    guessed = [Board(ats=ats, slug=slug) for slug in found for ats in GUESSABLE]
    personio = [
        Board(ats="personio", slug=f"{slug}.{tld}") for slug in found for tld in PERSONIO_DOMAINS
    ]
    smartrecruiters = [Board(ats="smartrecruiters", slug=slug) for slug in capitalised(name)]
    return guessed + personio + smartrecruiters
