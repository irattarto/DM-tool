"""Regression tests for the second review round (crash prevention and Discord safety)."""
import sys

import pytest

from services.discord_service import DiscordClient, DiscordError, clean_text, validate_token
from services.discord_settings import DiscordSettings

TOKEN = "MTIzNDU2Nzg5MDEyMzQ1Njc4.Gabcde.abcdefghijklmnopqrstuvwxyz0123456789"


def test_excepthook_logs_and_notifies_once_without_raising():
    from utils import exception_hook

    seen = []
    old = sys.excepthook
    try:
        exception_hook.install(notifier=seen.append)
        try:
            raise RuntimeError("boom in a slot")
        except RuntimeError:
            sys.excepthook(*sys.exc_info())
        assert len(seen) == 1 and "boom in a slot" in seen[0]
        assert sys.excepthook is exception_hook.handle_exception
    finally:
        sys.excepthook = old
        exception_hook._notifier = None


def test_excepthook_does_not_recurse_when_notifier_fails():
    from utils import exception_hook

    def bad(_text):
        raise ValueError("notifier broke")

    exception_hook._notifier = bad
    try:
        try:
            raise RuntimeError("x")
        except RuntimeError:
            exception_hook.handle_exception(*sys.exc_info())
        assert exception_hook._reporting is False
    finally:
        exception_hook._notifier = None


@pytest.mark.parametrize("bad_id", ["", "abc", "22", "../../x", "1234567890123456789012345678"])
def test_client_rejects_malformed_ids(bad_id):
    import asyncio
    client = DiscordClient(TOKEN)
    with pytest.raises(DiscordError):
        asyncio.run(client.send_text(bad_id, "hi"))
    with pytest.raises(DiscordError):
        asyncio.run(client.list_text_channels(bad_id))


def test_token_validation_is_strict():
    assert validate_token("Bot " + TOKEN) == TOKEN
    for bad in ("short", TOKEN + " x", "tokén" + "a" * 30):
        with pytest.raises(ValueError):
            validate_token(bad)


def test_clean_text_keeps_angle_bracket_prose():
    assert clean_text("3 < 5 and 7 > 2") == "3 < 5 and 7 > 2"
    assert clean_text("<b>bold</b> text") == "bold text"


class _Secure:
    def encrypt(self, t):
        return "enc:" + t

    def decrypt(self, t):
        return t[4:]


def test_each_campaign_keeps_its_own_discord_server(temp_db):
    first = temp_db.create_module("M1", "d")
    second = temp_db.create_module("M2", "d")
    settings = DiscordSettings(temp_db, _Secure())
    settings.set_guild("100000000000000001", "Default")
    temp_db.set_module_discord_channel(first, "200000000000000002", "rolls", "100000000000000009", "Other")
    temp_db.set_module_discord_channel(second, "200000000000000003", "maps")  # no own server
    # Changing the default server must not touch a campaign's own link
    settings.set_guild("100000000000000005", "New default")
    module = temp_db.get_module(first)
    assert module['discord_channel_id'] == "200000000000000002"
    assert settings.get_guild_for_module(module) == ("100000000000000009", "Other")
    assert settings.get_guild_for_module(temp_db.get_module(second)) == ("100000000000000005", "New default")
    # Clearing the channel clears the server link too
    temp_db.set_module_discord_channel(first, None)
    module = temp_db.get_module(first)
    assert module['discord_guild_id'] is None and module['discord_guild_name'] is None


def test_module_channel_id_must_look_like_a_snowflake(temp_db):
    module_id = temp_db.create_module("M", "d")
    with pytest.raises(ValueError):
        temp_db.set_module_discord_channel(module_id, "12", "x")
    with pytest.raises(ValueError):
        temp_db.set_module_discord_channel(module_id, "٣" * 18, "x")  # non-ASCII digits


def test_send_worker_skips_items_already_posted(tmp_path):
    from gui.dialogs.discord_send_dialog import SendItem
    from gui.workers.discord_worker import DiscordSendWorker

    posted = []

    class FakeClient:
        async def send_text(self, channel_id, text):
            posted.append(text)

    items = [SendItem(kind='text', text=t) for t in ("one", "two", "three")]
    worker = DiscordSendWorker(lambda: FakeClient(), "200000000000000002", items, skip=2)
    results = []
    worker.result_ready.connect(lambda ok, msg: results.append(ok))
    worker.run()  # synchronously, no thread needed
    assert posted == ["three"] and results == [True] and worker.sent_count == 3


def test_newer_schema_database_is_refused_and_untouched(tmp_path):
    import sqlite3
    from models.database import DatabaseManager

    path = tmp_path / "future.db"
    db = DatabaseManager(str(path))
    db.initialize_database()
    db.close()
    conn = sqlite3.connect(path)
    version = conn.execute("SELECT MAX(version) FROM schema_version").fetchone()[0]
    conn.execute("INSERT INTO schema_version (version) VALUES (?)", (version + 5,))
    conn.commit()
    conn.close()

    with pytest.raises(RuntimeError, match="newer version"):
        DatabaseManager(str(path)).initialize_database()
    conn = sqlite3.connect(path)
    assert conn.execute("SELECT MAX(version) FROM schema_version").fetchone()[0] == version + 5
    conn.close()


def test_failed_pragma_does_not_leave_a_cached_connection(tmp_path, monkeypatch):
    import sqlite3
    from models import database_connection as dc

    real_connect = sqlite3.connect

    class Boom:
        def __init__(self, conn):
            self._c = conn

        def execute(self, sql, *a):
            if "journal_mode" in sql:
                raise sqlite3.OperationalError("database is locked")
            return self._c.execute(sql, *a)

        def close(self):
            self._c.close()

    monkeypatch.setattr(dc.sqlite3, "connect", lambda *a, **k: Boom(real_connect(*a, **k)))
    connection = dc.DatabaseConnection(str(tmp_path / "x.db"))
    with pytest.raises(sqlite3.OperationalError):
        connection.connect()
    assert connection._connection is None


def test_legacy_entity_type_keys_do_not_block_saving(temp_db):
    module_id = temp_db.create_module("M", "d")
    with temp_db.connection.transaction() as conn:
        conn.execute("INSERT INTO entity_types (key, label_singular, label_plural, sort_order, hidden, builtin) "
                     "VALUES ('Old Type', 'Old', 'Olds', 50, 0, 0)")
    rows = temp_db.get_entity_types()
    temp_db.save_entity_types(rows)  # must not raise for the legacy key
    with pytest.raises(ValueError):
        temp_db.save_entity_types(rows + [{'key': 'Bad Key', 'label_singular': 'B', 'label_plural': 'Bs',
                                           'hidden': False, 'builtin': False}])


def test_entity_type_keys_are_ascii_only():
    from config.entity_types import is_valid_key
    assert is_valid_key("faction_2") and not is_valid_key("façtion") and not is_valid_key("a" * 51)
    assert not is_valid_key("٣٤")


def test_hidden_type_documents_stay_linkable(app_window=None):
    pytest.importorskip("PyQt6")
    from PyQt6.QtCore import QStandardPaths
    from PyQt6.QtWidgets import QApplication
    QStandardPaths.setTestModeEnabled(True)
    app = QApplication.instance() or QApplication([])
    from config.entity_types import get_registry
    from config.settings import Settings
    from gui.main_window import MainWindow
    from models.database import DatabaseManager

    db = DatabaseManager(":memory:")
    db.initialize_database()
    module_id = db.create_module("Hidden", "d")
    db.create_document(module_id, "quest", "Find the Gem", "Goal")
    rows = get_registry().to_rows()
    for r in rows:
        if r['key'] == 'quest':
            r['hidden'] = True
    db.save_entity_types(rows)
    get_registry().load_overrides(db.get_entity_types())
    settings = Settings()
    settings.set_last_module_id(module_id)
    window = MainWindow(settings, db)
    try:
        assert 'quest' not in window.entity_lists
        # internal links to a hidden type are still valid
        assert 'quest' in get_registry().keys_for('context')
    finally:
        window.deleteLater()
        for r in rows:
            r['hidden'] = False
        db.save_entity_types(rows)
        get_registry().load_overrides(db.get_entity_types())


@pytest.mark.parametrize("name,ok", [
    ("portrait.png", True), ("Árvíztűrő tükörfúrógép.jpg", True), ("a (1).webp", True),
    ("C:evil.png", False), ("evil.png:stream", False), ("sub\\evil.png", False), ("NUL.png", False),
    ("com1.png", False), ("trail.png.", False), ("../x.png", False), ("a.exe", False), (".hidden.png", False),
])
def test_backup_image_names_are_strictly_filtered(tmp_path, name, ok):
    import zipfile
    from services.backup_service import BackupService
    path = tmp_path / "b.zip"
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("images/" + name, b"x")
    with zipfile.ZipFile(path) as zf:
        assert bool(BackupService._image_entries(zf)) is ok


def test_swap_images_dir_keeps_old_folder_when_replace_fails(tmp_path, monkeypatch):
    import os
    from services import backup_service
    from services.backup_service import BackupService

    old = tmp_path / "images" / "1"
    old.mkdir(parents=True)
    (old / "old.png").write_bytes(b"old")
    new = tmp_path / "new"
    new.mkdir()
    (new / "new.png").write_bytes(b"new")

    real_replace = os.replace
    calls = {"n": 0}

    def flaky(src, dst):
        calls["n"] += 1
        if calls["n"] == 2:  # the staging -> target step
            raise OSError("disk error")
        return real_replace(src, dst)

    monkeypatch.setattr(backup_service.os, "replace", flaky)
    with pytest.raises(OSError):
        BackupService._swap_images_dir(new, old)
    assert (old / "old.png").read_bytes() == b"old"  # previous images are back
    monkeypatch.undo()
    BackupService._swap_images_dir(new, old)
    assert (old / "new.png").exists() and not (old / "old.png").exists()


def test_hard_delete_never_removes_the_main_database(tmp_path, monkeypatch):
    from models import database as dbmod
    from models.database import DatabaseManager

    monkeypatch.setattr(dbmod, "get_data_dir", lambda: tmp_path)
    main = tmp_path / "main.db"
    db = DatabaseManager(str(main))
    db.initialize_database()
    module_id = db.create_module("M", "d", database_path=str(main))
    db.hard_delete_module(module_id, delete_files=True)
    assert main.exists()


def test_exif_is_stripped_from_uploaded_jpeg(tmp_path):
    from PIL import Image
    from services.discord_service import prepare_image

    path = tmp_path / "photo.jpg"
    image = Image.new("RGB", (20, 20), "red")
    exif = Image.Exif()
    exif[0x010F] = "SecretCamera"
    image.save(path, exif=exif)
    _, data, _ = prepare_image(str(path))
    import io
    assert not dict(Image.open(io.BytesIO(data)).getexif())


def test_backup_zip_is_written_atomically(tmp_path):
    from services.backup_service import BackupService
    svc = BackupService.__new__(BackupService)
    import logging
    svc.logger = logging.getLogger("t")
    target = tmp_path / "b.zip"
    ok, _, _ = svc._create_zip_backup(str(target), {"a": 1}, [], {"b": 2})
    assert ok and target.exists() and not (tmp_path / "b.zip.part").exists()


def test_gitignore_blocks_local_data_and_secrets():
    from pathlib import Path
    text = (Path(__file__).resolve().parent.parent / ".gitignore").read_text(encoding="utf-8")
    for pattern in ("*.db", "*.db-wal", ".secure_key", ".secure_salt", "ai_providers.json", ".env*"):
        assert pattern in text.splitlines()


def _pump(done, timeout=3.0):
    import time
    from PyQt6.QtCore import QCoreApplication
    end = time.time() + timeout
    while not done() and time.time() < end:
        QCoreApplication.processEvents()
        time.sleep(0.01)


def test_transcription_runs_in_worker_and_reports_errors(monkeypatch):
    pytest.importorskip("PyQt6")
    from PyQt6.QtCore import QCoreApplication, QThread
    app = QCoreApplication.instance() or QCoreApplication([])  # keep a reference alive
    import speech_recognition as sr
    from gui.workers.transcription_worker import TranscriptionWorker

    seen = {}

    def fake_google(self, audio, language=None):
        seen['thread'] = QThread.currentThread()
        return "hello world"

    monkeypatch.setattr(sr.Recognizer, "recognize_google", fake_google)
    worker = TranscriptionWorker(object(), "google", "en-US")
    results, errors = [], []
    worker.result_ready.connect(results.append)
    worker.error.connect(errors.append)
    worker.start()
    assert worker.wait(5000)
    _pump(lambda: results or errors)
    assert results == ["hello world"] and not errors
    assert seen['thread'] is not QThread.currentThread()  # not on the GUI thread

    def unknown(self, audio, language=None):
        raise sr.UnknownValueError()

    monkeypatch.setattr(sr.Recognizer, "recognize_google", unknown)
    worker = TranscriptionWorker(object(), "google", "en-US")
    worker.error.connect(errors.append)
    worker.start()
    assert worker.wait(5000)
    _pump(lambda: errors)
    assert errors == ["Could not understand audio"]


def test_fullscreen_toggle_and_setting_round_trip():
    pytest.importorskip("PyQt6")
    from PyQt6.QtCore import QStandardPaths
    from PyQt6.QtWidgets import QApplication
    QStandardPaths.setTestModeEnabled(True)
    app = QApplication.instance() or QApplication([])
    from config.settings import Settings
    from gui.main_window import MainWindow
    from models.database import DatabaseManager

    db = DatabaseManager(":memory:")
    db.initialize_database()
    module_id = db.create_module("FS", "d")
    settings = Settings()
    settings.set_last_module_id(module_id)
    window = MainWindow(settings, db)
    try:
        assert window.fullscreen_action.shortcut().toString() == "F11"
        window.fullscreen_action.setChecked(True)
        assert window.isFullScreen()
        window.fullscreen_action.setChecked(False)
        assert not window.isFullScreen()
        assert hasattr(settings.window, "is_fullscreen")
    finally:
        window.deleteLater()


def test_settings_survive_one_bad_value(monkeypatch, tmp_path):
    pytest.importorskip("PyQt6")
    from PyQt6.QtCore import QSettings
    from config.settings import Settings

    s = Settings()
    s._settings.setValue("Window/width", "not-a-number")
    s._settings.setValue("UI/font_size", 17)
    s._settings.setValue("SpeechToText/device_index", "garbage")
    s.load_settings()
    assert s.ui.font_size == 17                      # other settings still load
    assert s.speech_to_text.device_index is None     # the bad one falls back
    s._settings.remove("Window/width")
    s._settings.remove("UI/font_size")
    s._settings.remove("SpeechToText/device_index")


def test_one_backup_covers_the_whole_migration_chain(tmp_path):
    import sqlite3
    from models.database import DatabaseManager
    from models.database_migrations import DatabaseMigration

    path = tmp_path / "old.db"
    db = DatabaseManager(str(path))
    db.initialize_database()
    db.close()
    conn = sqlite3.connect(path)
    conn.execute("DELETE FROM schema_version")
    conn.execute("INSERT INTO schema_version (version) VALUES (6)")
    conn.commit()
    conn.close()

    migrator = DatabaseMigration(str(path))
    calls = []
    # three steps that each ask for their own backup, as the real ones do
    migrator.migrations = {v: (lambda v=v: (migrator._backup_database(str(tmp_path / f"step{v}.db")), calls.append(v)))
                           for v in (7, 8, 9)}
    assert migrator.migrate_to_version(9)
    assert calls == [7, 8, 9] and not list(tmp_path.glob("step*.db"))
    backups = list(tmp_path.glob("old.db.pre_*"))
    assert len(backups) == 1, backups


def test_orphan_thumbnails_are_removed(tmp_path):
    pytest.importorskip("PyQt6")
    from services.image_service import ImageService
    svc = ImageService.__new__(ImageService)
    import logging
    svc.logger = logging.getLogger("t")
    svc.modules_path = tmp_path / "modules"
    svc.thumbnails_path = tmp_path / "thumbs"
    svc.supported_formats = {".png"}
    (svc.modules_path / "1").mkdir(parents=True)
    svc.thumbnails_path.mkdir()
    (svc.modules_path / "1" / "keep.png").write_bytes(b"x")
    (svc.thumbnails_path / "keep.jpg").write_bytes(b"x")
    (svc.thumbnails_path / "gone.jpg").write_bytes(b"x")
    assert svc.cleanup_orphan_thumbnails() == 1
    assert (svc.thumbnails_path / "keep.jpg").exists() and not (svc.thumbnails_path / "gone.jpg").exists()


def test_github_actions_are_pinned_to_commit_hashes():
    import re
    from pathlib import Path
    root = Path(__file__).resolve().parent.parent
    for workflow in (root / ".github" / "workflows").glob("*.yml"):
        for line in workflow.read_text(encoding="utf-8").splitlines():
            m = re.match(r"\s*-?\s*uses:\s*(\S+)", line)
            if m and not m.group(1).startswith("./"):
                assert re.search(r"@[0-9a-f]{40}$", m.group(1)), f"{workflow.name}: {m.group(1)} is not pinned"


def test_appimagetool_is_a_fixed_verified_release():
    from pathlib import Path
    script = (Path(__file__).resolve().parent.parent / "packaging" / "linux" / "build_appimage.sh").read_text()
    assert "continuous" not in script and "sha256sum -c" in script


def test_cleanup_workflow_has_only_the_permission_it_needs():
    import yaml
    from pathlib import Path
    wf = yaml.safe_load((Path(__file__).resolve().parent.parent / ".github" / "workflows" / "cleanup-runs.yml").read_text())
    assert wf["permissions"] == {"actions": "write", "contents": "read"}
    assert "uses" not in str(wf["jobs"])          # no third-party action in a job that can delete runs


def test_release_workflow_can_publish_a_marked_prerelease_from_main():
    from pathlib import Path
    text = (Path(__file__).resolve().parent.parent / ".github" / "workflows" / "build-executables.yml").read_text()
    assert "[pre-release v" in text and "--generate-notes" in text
    assert "needs.plan.outputs.prerelease" in text    # suffixed tags / marked merges are pre-releases
    assert "-split '-'" in text                        # tag check ignores the -beta.N suffix


def test_app_version_is_a_valid_release_version():
    import re
    from config.version import __version__, __version_info__
    assert re.fullmatch(r"\d+\.\d+\.\d+", __version__) and tuple(int(x) for x in __version__.split(".")) == __version_info__


def test_code_base_has_no_pyflakes_warnings():
    """Undefined names, unused imports and variables, and placeholder-less f-strings must not creep back in."""
    import subprocess
    import sys
    from pathlib import Path
    root = Path(__file__).resolve().parent.parent
    files = [str(p) for p in root.rglob("*.py")
             if not any(part in {"tests", "build", "dist", "node_modules"} or part.startswith(".")
                        for part in p.relative_to(root).parts)]  # dot-folders (.git, .kilo worktrees, ...) are not our code
    result = subprocess.run([sys.executable, "-m", "pyflakes", *files], capture_output=True, text=True)
    allowed = ("utils/audio_recording.py",)  # imports pyaudio only to test that it is installed
    problems = [line for line in result.stdout.splitlines()
                if not any(a in line.replace("\\", "/") for a in allowed)]  # Windows prints backslashes
    assert not problems, "\n".join(problems[:20])


# ---- second review: the 16 findings ---------------------------------------------------------

def test_readme_badge_matches_version():
    from pathlib import Path
    from config.version import __version__
    readme = (Path(__file__).resolve().parent.parent / "README.md").read_text(encoding="utf-8")
    assert f"badge/version-{__version__}-" in readme


def test_no_gui_module_imports_the_legacy_styles_module():
    import re
    from pathlib import Path
    root = Path(__file__).resolve().parent.parent
    bad = [str(p) for p in list((root / "gui").rglob("*.py")) + [root / "main.py"]
           if p.name != "styles.py" and re.search(r"from gui\.styles import", p.read_text(encoding="utf-8"))]
    assert not bad, bad


def test_module_data_read_is_capped(tmp_path):
    import zipfile
    from services.backup_service import BackupService
    zp = tmp_path / "b.zip"
    with zipfile.ZipFile(zp, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("module_data.json", "x" * 5000)
    with zipfile.ZipFile(zp) as zf:
        assert len(BackupService._read_capped(zf, "module_data.json", 10000)) == 5000
        with pytest.raises(ValueError):
            BackupService._read_capped(zf, "module_data.json", 100)


def test_html_import_image_cannot_escape_module_folder(tmp_path):
    from services.html_module_import_service import HtmlModuleImportService, ParsedEntity
    outside = tmp_path / "secret.png"
    outside.write_bytes(b"x")
    html_dir = tmp_path / "mod"
    (html_dir / "images" / "portraits").mkdir(parents=True)
    svc = HtmlModuleImportService.__new__(HtmlModuleImportService)
    ent = ParsedEntity.__new__(ParsedEntity)
    ent.image = ""
    ent.source_id = "../../secret"
    assert svc._find_image(html_dir, ent) is None



def test_game_session_status_round_trips():
    from models.session import GameSession
    s = GameSession(module_id=1, title="t", status="played")
    assert s.to_dict()["status"] == "played"


# ---- second review: lower-severity bugs ------------------------------------------------------

def test_validate_json_input_parses_and_accepts_unicode():
    from utils.security_utils import get_security_validator
    v = get_security_validator()
    assert v.validate_json_input('{"név": "Kovács Éva"}')['valid']
    assert not v.validate_json_input('{not json')['valid']


def test_update_image_description_reports_missing_image(temp_db):
    assert temp_db.update_image_description(99999, "x") is False


def test_entity_sort_preference_survives_garbage(monkeypatch):
    from config.settings import Settings
    s = Settings.__new__(Settings)
    monkeypatch.setattr(Settings, "get_custom_setting", lambda self, k, d=None: "abc,sideways")
    assert s.get_entity_sort_preference("npc") == (0, "asc")


def test_multi_word_interaction_indicators_match():
    from services.parsing_service import ParsingService
    found = ParsingService()._extract_npc_interactions("The party spoke with Aldric near the gate.")
    assert [f["npc_name"] for f in found] == ["Aldric"] and found[0]["interaction_type"] == "spoke with"


def test_shared_sidecar_only_applies_to_its_own_module(tmp_path):
    import json
    from services.html_module_parser import parse_file, module_to_json
    html = "<html><head><title>{t}</title></head><body><h1>{t}</h1></body></html>"
    a, b = tmp_path / "alpha.html", tmp_path / "beta.html"
    a.write_text(html.format(t="Alpha"), encoding="utf-8")
    b.write_text(html.format(t="Beta"), encoding="utf-8")
    data = module_to_json(parse_file(a))
    data["module"]["title"] = "Alpha from sidecar"
    (tmp_path / "module-export.json").write_text(json.dumps(data), encoding="utf-8")
    assert parse_file(a).title == "Alpha from sidecar"
    assert parse_file(b).title != "Alpha from sidecar"


def test_thumbnail_survives_while_another_module_has_the_same_file(tmp_path):
    from PyQt6.QtGui import QImage, QColor
    from services.image_service import ImageService
    svc = ImageService(tmp_path / "imgs")
    img = QImage(8, 8, QImage.Format.Format_RGB32)
    img.fill(QColor("red"))
    src = tmp_path / "a.png"
    img.save(str(src))
    meta = svc.save_image(str(src), 1)
    for module in (1, 2):
        (svc.modules_path / str(module)).mkdir(parents=True, exist_ok=True)
        (svc.modules_path / str(module) / meta["filename"]).write_bytes(src.read_bytes())
    thumb = svc.thumbnails_path / f"{meta['filename'].rsplit('.', 1)[0]}.jpg"
    thumb.write_bytes(b"x")
    assert svc.delete_image(1, meta["filename"])
    assert thumb.exists()                       # module 2 still uses it
    assert svc.delete_image(2, meta["filename"])
    assert not thumb.exists()


def test_backup_progress_callback_survives_nested_calls(temp_db, tmp_path):
    from services.backup_service import BackupService
    from services.image_service import ImageService
    svc = BackupService(temp_db, ImageService(tmp_path / "imgs"))
    seen = []
    svc._progress = seen.append                      # the outer operation's callback
    svc.backup_module(424242, str(tmp_path / "x.zip"))   # nested call without a callback (fails: no such module)
    assert svc._progress == seen.append


def test_whisper_works_without_the_voice_filter(monkeypatch):
    from services import local_stt

    class Seg:
        start, end, text = 0.0, 1.0, " hello "

    class Info:
        duration = 1.0

    class FakeModel:
        def transcribe(self, path, **kw):
            if kw.get("vad_filter"):
                raise RuntimeError("onnxruntime missing")
            return iter([Seg()]), Info()

    monkeypatch.setattr(local_stt, "load_model", lambda plan, status=None: FakeModel())
    segments, used = local_stt.transcribe_file("x.wav", local_stt.Plan("small", "cpu", "int8"), language="hu-HU")
    assert [s.text for s in segments] == ["hello"] and used.device == "cpu"


def test_transcription_errors_name_the_cause():
    from gui.workers.transcription_worker import _describe
    assert "downloaded" in _describe(ConnectionError("Connection refused"))
    assert "CPU" in _describe(RuntimeError("CUDA failed"))
    assert "ValueError" in _describe(ValueError("odd"))


def test_spec_bundles_whisper_runtime_dependencies():
    from pathlib import Path
    spec = (Path(__file__).resolve().parent.parent / "RPG_Database_Manager.spec").read_text(encoding="utf-8")
    for pkg in ("faster_whisper", "ctranslate2", "onnxruntime", "av"):
        assert f"'{pkg}'" in spec


def test_setup_py_reads_requirements_and_has_no_placeholder_urls():
    from pathlib import Path
    setup = (Path(__file__).resolve().parent.parent / "setup.py").read_text(encoding="utf-8")
    assert "yourusername" not in setup and "requirements.txt" in setup


def test_lock_files_pin_and_hash_every_requirement():
    import re
    from pathlib import Path
    root = Path(__file__).resolve().parent.parent
    wanted = {re.split(r"[<>=!~\[ ]", line.split("#")[0].strip())[0].lower().replace("_", "-")
              for line in (root / "requirements.txt").read_text(encoding="utf-8").splitlines()
              if line.split("#")[0].strip()}
    for name in ("requirements-windows.lock", "requirements-linux.lock"):
        text = (root / name).read_text(encoding="utf-8")
        pinned = {m.group(1).lower().replace("_", "-") for m in re.finditer(r"^([A-Za-z0-9_.\-]+)==", text, re.M)}
        assert wanted <= pinned, f"{name} misses {wanted - pinned}"
        blocks = re.split(r"\n(?=[A-Za-z0-9_.\-]+==)", text)
        assert all("--hash=sha256:" in b for b in blocks if re.match(r"[A-Za-z0-9_.\-]+==", b)), name


def test_release_builds_install_with_required_hashes():
    from pathlib import Path
    wf = (Path(__file__).resolve().parent.parent / ".github" / "workflows" / "build-executables.yml").read_text(encoding="utf-8")
    assert "pip install --require-hashes -r requirements-windows.lock" in wf
    assert "pip install --require-hashes -r requirements-linux.lock" in wf
    assert "pip install -r requirements.txt" not in wf


def test_build_workflow_does_not_leave_its_write_token_in_the_checkout():
    """The build jobs can write releases, so the checkout must not keep the token for later steps."""
    from pathlib import Path
    text = (Path(__file__).resolve().parent.parent / ".github" / "workflows" / "build-executables.yml").read_text()
    assert text.count("actions/checkout@") == text.count("persist-credentials: false")
