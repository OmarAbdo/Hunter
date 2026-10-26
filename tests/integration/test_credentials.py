from pathlib import Path

from hunter.adapters.credentials import keys_from

KEYS = """
[[mailbox]]
address = "jobs@example.com"
app_password = "secret"

[keys.adzuna]
app_id = "id"
app_key = "key"

[keys.jooble]
api_key = "another"
"""


def test_api_keys_come_from_the_credentials_file(tmp_path: Path) -> None:
    (tmp_path / "accounts.toml").write_text(KEYS, encoding="utf-8")
    keys = keys_from(tmp_path / "accounts.toml")
    assert keys["adzuna"] == {"app_id": "id", "app_key": "key"}
    assert keys["jooble"] == {"api_key": "another"}


def test_no_credentials_file_means_no_keys(tmp_path: Path) -> None:
    assert keys_from(tmp_path / "accounts.toml") == {}


def test_a_file_without_keys_has_none(tmp_path: Path) -> None:
    (tmp_path / "accounts.toml").write_text(KEYS.split("[keys", 1)[0], encoding="utf-8")
    assert keys_from(tmp_path / "accounts.toml") == {}
