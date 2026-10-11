"""Leftovers of the removed AI features are deleted, other data is not."""
from utils.legacy_cleanup import remove_legacy_ai_data


def test_old_ai_configuration_files_are_removed(tmp_path):
    (tmp_path / "ai_providers.json").write_text("{}", encoding="utf-8")
    (tmp_path / "ai_providers.json.corrupt-20260101").write_text("x", encoding="utf-8")
    (tmp_path / ".secure_key").write_text("key", encoding="utf-8")  # shared with the Discord token
    (tmp_path / "rpg.db").write_text("db", encoding="utf-8")

    assert remove_legacy_ai_data(tmp_path) == 2
    assert sorted(p.name for p in tmp_path.iterdir()) == [".secure_key", "rpg.db"]
    assert remove_legacy_ai_data(tmp_path) == 0  # nothing left, no error


def test_recording_limit_is_kept_within_30_and_480_seconds(tmp_path):
    from PyQt6.QtCore import QSettings
    from config.settings import Settings
    s = Settings()
    assert s.speech_to_text.phrase_limit == 120
    for stored, expected in ((10, 30), (30, 30), (200, 200), (9999, 480)):
        s._settings.setValue("SpeechToText/phrase_limit", stored)
        s.load_settings()
        assert s.speech_to_text.phrase_limit == expected
