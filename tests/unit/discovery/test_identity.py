from hunter.domain.discovery.identity import company_key, title_key


def test_company_keys_drop_legal_forms_accents_and_punctuation() -> None:
    assert company_key("Redcare Pharmacy GmbH") == "redcarepharmacy"
    assert company_key("Bartko & Reher GmbH & Co. KG") == "bartkoandreher"
    assert company_key("Zürich Versicherung AG") == "zurichversicherung"
    assert company_key("kleinanzeigen.de GmbH") == "kleinanzeigende"


def test_company_keys_keep_words_that_only_contain_a_legal_form() -> None:
    assert company_key("Agile Labs") == "agile"
    assert company_key("Seco") == "seco"


def test_title_keys_drop_gender_markers() -> None:
    assert title_key("Senior Backend Engineer (m/w/d)") == "senior backend engineer"
    assert title_key("Software Engineer Full-Stack (all genders)") == "software engineer full stack"
    assert title_key("PHP-Entwickler (w/m/div)") == "php entwickler"
    assert title_key("Data Engineer (f/m/x) – Berlin") == "data engineer berlin"
