import pytest

from core import i18n
from core.settings import Settings


@pytest.fixture(autouse=True)
def isolated_settings(tmp_path, monkeypatch):
    monkeypatch.setattr("core.settings.CONFIG_FILE", tmp_path / "settings.json")
    yield


def test_de_and_en_have_the_same_keys():
    de_keys = set(i18n._TRANSLATIONS["de"])
    en_keys = set(i18n._TRANSLATIONS["en"])
    assert de_keys == en_keys


def test_t_returns_german_by_default():
    Settings.set_language("de")
    assert i18n.t("home.sync_button") == "Jetzt synchronisieren"


def test_t_returns_english_when_selected():
    Settings.set_language("en")
    assert i18n.t("home.sync_button") == "Sync now"


def test_t_formats_placeholders():
    Settings.set_language("de")
    text = i18n.t("import.done_text", groups=2, bookmarks=10, skipped=1)
    assert text == "2 Ordner und 10 Lesezeichen importiert, 1 Duplikate übersprungen."


def test_t_falls_back_to_key_for_unknown_key():
    Settings.set_language("de")
    assert i18n.t("does.not.exist") == "does.not.exist"
