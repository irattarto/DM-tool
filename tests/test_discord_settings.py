"""Discord settings storage, module channel link and the v9 migration."""
import sqlite3

import pytest

from models.database import DatabaseManager
from services.discord_settings import DiscordSettings, META_TOKEN

TOKEN = "MTIzNDU2Nzg5MDEyMzQ1Njc4.Gabcde.abcdefghijklmnopqrstuvwxyz0123456789"


class FakeSecure:
    """Reversible stand-in for SecureStorage that makes plain text easy to spot."""
    def encrypt(self, text):
        return "enc:" + text[::-1]

    def decrypt(self, text):
        if not text.startswith("enc:"):
            raise RuntimeError("bad data")
        return text[4:][::-1]


def test_token_is_stored_encrypted_and_round_trips(temp_db):
    settings = DiscordSettings(temp_db, FakeSecure())
    assert not settings.has_token() and settings.get_token() is None
    settings.set_token("Bot " + TOKEN)
    stored = temp_db.get_app_meta(META_TOKEN)
    assert stored and TOKEN not in stored and stored.startswith("enc:")
    assert settings.get_token() == TOKEN and settings.has_token()
    settings.clear_token()
    assert settings.get_token() is None


def test_invalid_token_is_rejected_before_storing(temp_db):
    settings = DiscordSettings(temp_db, FakeSecure())
    with pytest.raises(ValueError):
        settings.set_token("too short")
    assert temp_db.get_app_meta(META_TOKEN) is None


def test_undecryptable_token_behaves_as_not_configured(temp_db):
    temp_db.set_app_meta(META_TOKEN, "garbage")
    assert DiscordSettings(temp_db, FakeSecure()).get_token() is None


def test_guild_and_configured_flag(temp_db):
    settings = DiscordSettings(temp_db, FakeSecure())
    assert not settings.is_configured()
    settings.set_token(TOKEN)
    settings.set_guild("100000000000000010", "My Campaign")
    assert settings.get_guild() == ("100000000000000010", "My Campaign") and settings.is_configured()
    settings.set_guild(None)
    assert settings.get_guild() == (None, None)


def test_module_channel_link_set_and_clear(temp_db):
    mod = temp_db.create_module("M", "d")
    assert temp_db.get_module(mod)['discord_channel_id'] is None
    assert temp_db.set_module_discord_channel(mod, "123456789012345678", "handouts")
    module = temp_db.get_module(mod)
    assert (module['discord_channel_id'], module['discord_channel_name']) == ("123456789012345678", "handouts")
    temp_db.set_module_discord_channel(mod, None)
    module = temp_db.get_module(mod)
    assert module['discord_channel_id'] is None and module['discord_channel_name'] is None
    with pytest.raises(ValueError):
        temp_db.set_module_discord_channel(mod, "not-a-number")


def test_v9_migration_adds_columns_and_keeps_data(tmp_path):
    path = str(tmp_path / "v8.db")
    db = DatabaseManager(path)
    db.initialize_database()
    mod = db.create_module("Keep", "d")
    db.connection.disconnect()

    conn = sqlite3.connect(path)  # simulate a v8 database
    conn.execute("ALTER TABLE modules DROP COLUMN discord_channel_id")
    conn.execute("ALTER TABLE modules DROP COLUMN discord_channel_name")
    conn.execute("DELETE FROM schema_version")
    conn.execute("INSERT INTO schema_version (version) VALUES (8)")
    conn.commit()
    conn.close()

    db2 = DatabaseManager(path)
    db2.initialize_database()
    module = db2.get_module(mod)
    assert module['name'] == "Keep" and 'discord_channel_id' in module
    assert db2.set_module_discord_channel(mod, "100000000000000042", "x")


def test_v10_migration_gives_existing_links_the_stored_server(tmp_path):
    path = str(tmp_path / "v9.db")
    db = DatabaseManager(path)
    db.initialize_database()
    linked = db.create_module("Linked", "d")
    unlinked = db.create_module("Unlinked", "d")
    db.set_module_discord_channel(linked, "100000000000000042", "x")
    db.set_app_meta('discord_guild_id', "100000000000000010")
    db.set_app_meta('discord_guild_name', "Old server")
    db.connection.disconnect()

    conn = sqlite3.connect(path)  # simulate a v9 database
    conn.execute("ALTER TABLE modules DROP COLUMN discord_guild_id")
    conn.execute("ALTER TABLE modules DROP COLUMN discord_guild_name")
    conn.execute("DELETE FROM schema_version")
    conn.execute("INSERT INTO schema_version (version) VALUES (9)")
    conn.commit()
    conn.close()

    db2 = DatabaseManager(path)
    db2.initialize_database()
    assert db2.get_module(linked)['discord_guild_id'] == "100000000000000010"
    assert db2.get_module(linked)['discord_guild_name'] == "Old server"
    assert db2.get_module(unlinked)['discord_guild_id'] is None


def test_backup_never_contains_the_token(temp_db, tmp_path):
    from services.backup_service import BackupService

    class Img:
        def regenerate_thumbnails_for_module(self, module_id):
            return 0

    DiscordSettings(temp_db, FakeSecure()).set_token(TOKEN)
    mod = temp_db.create_module("M", "d")
    data = BackupService(temp_db, Img())._export_module_data(mod)
    assert TOKEN not in repr(data) and 'discord_bot_token' not in repr(data)
