"""Careerjet's job search API (docs/sources.md), a keyed aggregator over many job boards: `GET
search.api.careerjet.net/v4/query`, with Omar's key (`[keys.careerjet]` in var/accounts.toml) as
Basic auth and his registered site as the referer. A search needs a country, which picks
Careerjet's site for it (`de_DE`, `en_GB`), and reads 50 jobs a page. A place
Careerjet can't tell apart ("Springfield") runs no search. Jobs come without an id, and their
links to Careerjet's click tracker (`jobviewtrack.com`) change with every answer, so a job is known
by its company, title and place; the description is a snippet."""

from base64 import b64encode
from dataclasses import replace
from email.utils import parsedate_to_datetime
from typing import Any

from hunter.adapters.html_text import plain_text
from hunter.adapters.places import places_from_text
from hunter.adapters.sources.reading import read_json
from hunter.adapters.sources.searches.keyed import keeping_keys_out, without_tracking
from hunter.adapters.web_client import USER_AGENT, WebClient
from hunter.application.ports import SourceUnavailableError
from hunter.domain.discovery.campaign import Search
from hunter.domain.discovery.posting import Posting, SourceRef

API = "https://search.api.careerjet.net/v4/query"
PAGE_SIZE = 50  # Careerjet gives 50; asked for 100, it gives its default of 20
MOST_PAGES = 6  # 300 jobs
USER_IP = "127.0.0.1"  # the API asks for the user's address; Hunter's user is on this machine
# Careerjet's sites by country, one language each where a country has several.
SITES = """
    cs_CZ da_DK de_AT de_CH de_DE en_AE en_AU en_BD en_CA en_CN en_HK en_IE en_IN en_KW en_MY
    en_NZ en_OM en_PH en_PK en_QA en_SG en_GB en_US en_ZA en_SA en_TW es_AR es_BO es_CL es_CO
    es_CR es_DO es_EC es_ES es_GT es_MX es_PA es_PE es_PR es_PY es_UY es_VE fi_FI fr_FR fr_LU
    fr_MA hu_HU it_IT ja_JP ko_KR nl_BE nl_NL no_NO pl_PL pt_PT pt_BR ru_RU sv_SE sk_SK tr_TR
    uk_UA vi_VN
"""
LOCALES = {code[-2:]: code for code in SITES.split()}


class CareerjetSearch:
    def __init__(self, web: WebClient, search: Search, key: dict[str, Any], api: str = API) -> None:
        self.web = web
        self.search = search
        self.key = key
        self.api = api

    @property
    def name(self) -> str:
        place = f"@{self.search.place}" if self.search.place else ""
        country = f",{self.search.country}" if self.search.country else ""
        return f"careerjet:{self.search.query}{place}{country}"

    def fetch(self) -> list[Posting]:
        """Page after page, until one isn't full or brings no job not already read."""
        locale = self._locale()
        postings: dict[str, Posting] = {}
        for page in range(1, MOST_PAGES + 1):
            jobs = self._jobs(locale, page)
            before = len(postings)
            for posting in map(self._posting, jobs):
                postings.setdefault(posting.source.native_id, posting)  # the first one read stays
            if len(postings) == before or len(jobs) < PAGE_SIZE:
                break
        return list(postings.values())

    def _locale(self) -> str:
        country = self.search.country.upper()
        if not country:
            raise SourceUnavailableError(f"{self.name}: Careerjet needs a country for each search")
        if country not in LOCALES:
            raise SourceUnavailableError(f"{self.name}: Careerjet has no site for {country}")
        return LOCALES[country]

    def _jobs(self, locale: str, page: int) -> list[dict[str, Any]]:
        params = {
            "locale_code": locale,
            "keywords": self.search.query,
            **({"location": self.search.place} if self.search.place else {}),
            "user_ip": USER_IP,
            "user_agent": USER_AGENT,
            "pagesize": str(PAGE_SIZE),  # the documented `page_size` is ignored
            "page": str(page),
        }
        headers = sent_headers(self.key)
        secrets = [*self.key.values(), headers["Authorization"]]
        answer = keeping_keys_out(lambda: read_json(self.web, self.api, params, headers), secrets)
        if isinstance(answer, dict) and answer.get("type") == "LOCATIONS":
            places = "; ".join(place.get("name", "") for place in answer.get("locations") or [])
            message = f"{self.name}: Careerjet can't tell the place ({answer.get('message')})"
            raise SourceUnavailableError(f"{message}: {places}" if places else message)
        jobs: list[dict[str, Any]] = answer.get("jobs") or [] if isinstance(answer, dict) else []
        return jobs

    def _posting(self, job: dict[str, Any]) -> Posting:
        link = without_tracking(job.get("url") or "")
        place, *other_places = places_from_text(job.get("locations") or "", self.search.country)
        published = job.get("date")
        posting = Posting(
            title=(job.get("title") or "").strip(),
            company=(job.get("company") or "").strip(),
            location=place,
            other_locations=tuple(other_places),
            source=SourceRef(source="careerjet", native_id=""),
            url=link,
            apply_url=link,
            description=plain_text(job.get("description")),
            posted_at=parsedate_to_datetime(published) if published else None,
        )
        return replace(posting, source=SourceRef(source="careerjet", native_id=posting.fuzzy_key))


def sent_headers(key: dict[str, Any]) -> dict[str, str]:
    """Careerjet takes the key as a Basic auth user without a password, and checks the referer
    against the site the key was issued for."""
    login = b64encode(f"{key['api_key']}:".encode()).decode()
    return {"Authorization": f"Basic {login}", "Referer": key["referer"]}
