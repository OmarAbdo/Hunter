from pathlib import Path

import pytest

from hunter.adapters.campaign_files import CampaignFileError, load_campaign, load_campaigns
from hunter.domain.discovery.campaign import Campaign
from hunter.domain.discovery.location import Workplace
from hunter.domain.discovery.posting import Employment

CAMPAIGNS = Path(__file__).resolve().parents[2] / "campaigns"
DUBAI = """
title = "Onsite software jobs in Dubai"
home = "AE"
countries = ["AE"]
cities = ["Dubai"]
workplaces = ["onsite", "hybrid"]
employment = ["full-time"]
roles = ["engineer"]
excluded_roles = ["intern"]
"""


def test_a_campaign_file_becomes_a_campaign(tmp_path: Path) -> None:
    (tmp_path / "ae-dubai.toml").write_text(DUBAI, encoding="utf-8")
    assert load_campaign(tmp_path / "ae-dubai.toml") == Campaign(
        id="ae-dubai",
        title="Onsite software jobs in Dubai",
        home="AE",
        countries=frozenset({"AE"}),
        cities=frozenset({"Dubai"}),
        workplaces=frozenset({Workplace.ONSITE, Workplace.HYBRID}),
        employment=frozenset({Employment.FULL_TIME}),
        roles=("engineer",),
        excluded_roles=("intern",),
    )


def test_only_what_a_campaign_needs_must_be_written(tmp_path: Path) -> None:
    (tmp_path / "anywhere.toml").write_text('title = "Any"\nhome = "DE"\ncountries = ["DE"]\n')
    campaign = load_campaign(tmp_path / "anywhere.toml")
    assert campaign.workplaces == frozenset(Workplace)
    assert (campaign.roles, campaign.employment) == ((), frozenset())


def test_an_unknown_setting_is_refused_by_name(tmp_path: Path) -> None:
    (tmp_path / "typo.toml").write_text(DUBAI + 'citys = ["Abu Dhabi"]\n', encoding="utf-8")
    with pytest.raises(CampaignFileError, match="typo.toml: unknown setting citys"):
        load_campaign(tmp_path / "typo.toml")


def test_an_unknown_workplace_is_refused(tmp_path: Path) -> None:
    (tmp_path / "bad.toml").write_text(DUBAI.replace('"hybrid"', '"office"'), encoding="utf-8")
    with pytest.raises(CampaignFileError, match="bad.toml: 'office'"):
        load_campaign(tmp_path / "bad.toml")


def test_a_missing_setting_is_refused(tmp_path: Path) -> None:
    (tmp_path / "short.toml").write_text('title = "Short"\n', encoding="utf-8")
    with pytest.raises(CampaignFileError, match="short.toml: missing home"):
        load_campaign(tmp_path / "short.toml")


def test_every_campaign_in_a_folder_in_name_order(tmp_path: Path) -> None:
    (tmp_path / "b.toml").write_text(DUBAI, encoding="utf-8")
    (tmp_path / "a.toml").write_text(DUBAI, encoding="utf-8")
    assert [campaign.id for campaign in load_campaigns(tmp_path)] == ["a", "b"]


def test_the_pilot_campaign_loads() -> None:
    pilot = load_campaign(CAMPAIGNS / "de-swe-berlin.toml")
    assert (pilot.id, pilot.home, pilot.cities) == ("de-swe-berlin", "DE", frozenset({"Berlin"}))
