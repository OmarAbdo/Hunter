"""The employer's own ad for a job only job boards showed (Careerjet, Indeed, LinkedIn), found by a
web search: an ad found is the job's only when it names the same title and the same company, as
Hunter's keys see them. A near miss is no ad: the wrong ad is worse than none."""

import re

from hunter.domain.discovery.boards import Board
from hunter.domain.discovery.identity import (
    GENDER_MARKER,
    company_key,
    company_words,
    text_key,
    title_key,
)
from hunter.domain.discovery.posting import Posting

SPACES = re.compile(r"\s+")
SHORTEST_NAME_WORD = 4  # a shorter word of a company's name names too many boards


def fits(job: Posting, title: str, company: str) -> bool:
    """Whether an ad with this title, from this company, is the job's."""
    same_title = bool(title_key(title)) and title_key(title) == title_key(job.title)
    return (
        same_title
        and bool(company_key(company))
        and company_key(company) == company_key(job.company)
    )


def search_query(job: Posting) -> str:
    """The company by its name, then the title without its gender marker."""
    title = SPACES.sub(" ", GENDER_MARKER.sub(" ", job.title)).strip()
    return f'"{job.company}" {title}'


def names_company(board: Board, company: str) -> bool:
    """Whether a board seen in a search for the company's job is the company's own: its name holds
    one of the company's words of four letters or more ("careers.nexus-ag.de" for Nexus)."""
    words = set(text_key(board.slug).split())
    return any(word in words for word in company_words(company) if len(word) >= SHORTEST_NAME_WORD)
