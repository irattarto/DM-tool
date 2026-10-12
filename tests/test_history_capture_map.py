"""Entry history, quick capture, the relationship map and the automatic backup."""
import json

import pytest

pytest.importorskip("PyQt6")
from PyQt6.QtCore import QStandardPaths
from PyQt6.QtWidgets import QApplication

from models.database import DatabaseManager


@pytest.fixture(scope="module")
def app():
    QStandardPaths.setTestModeEnabled(True)
    return QApplication.instance() or QApplication([])


def _db():
    db = DatabaseManager(":memory:")
    db.initialize_database()
    return db, db.create_module("C", "d")


def test_each_save_keeps_the_replaced_text_up_to_twenty_versions():
    db, campaign = _db()
    doc = db.create_document(campaign, "npc", "Mira", "first")
    for number in range(2, 30):
        db.update_document(doc, "Mira", f"text {number}")
    versions = db.get_document_versions(doc)
    assert len(versions) == 20 and versions[0]['content'] == "text 28" and versions[-1]['content'] == "text 9"
    db.update_document(doc, "Mira", "text 29")                      # an identical save adds nothing
    assert len(db.get_document_versions(doc)) == 20
    db.update_document(doc, "Mira", "internal", record_history=False)
    assert db.get_document_versions(doc)[0]['content'] == "text 28"
    db.delete_document(doc)
    assert db.get_document_versions(doc) == []


def test_the_schema_is_version_11(tmp_path):
    from models.database_migrations import DatabaseMigration
    path = tmp_path / "v.db"
    db = DatabaseManager(str(path))
    db.initialize_database()
    assert DatabaseMigration(str(path)).get_current_version() == 11
    db.close()


def test_history_dialog_restores_a_version(app):
    from gui.dialogs.history_dialog import HistoryDialog
    dialog = HistoryDialog("Mira", [{'id': 2, 'title': "Mira", 'content': "newer", 'saved_date': "2026-10-02"},
                                    {'id': 1, 'title': "Mirra", 'content': "older", 'saved_date': "2026-10-01"}])
    try:
        dialog.list.setCurrentRow(1)
        assert "older" in dialog.preview.toPlainText()
        dialog._restore()
        assert dialog.restored['title'] == "Mirra"
    finally:
        dialog.deleteLater()


def _window():
    from config.settings import Settings
    from gui.main_window import MainWindow
    db, campaign = _db()
    npc = db.create_document(campaign, "npc", "Kaz the Quick", "Race: Halfling")
    place = db.create_document(campaign, "location", "The Gilded Goose", "An inn")
    session = db.create_document(campaign, "session", "Session 1", "Notes",
                                 metadata=json.dumps({"session_date": "2026-10-01", "status": "active"}))
    settings = Settings()
    settings.set_last_module_id(campaign)
    return MainWindow(settings, db), db, campaign, npc, place, session


def test_quick_capture_appends_a_linked_line_to_the_session(app, monkeypatch):
    from PyQt6.QtWidgets import QDialog
    from gui.dialogs import quick_capture

    window, db, campaign, npc, place, session = _window()
    try:
        monkeypatch.setattr(quick_capture.QuickCaptureDialog, "exec", lambda self: QDialog.DialogCode.Accepted)
        monkeypatch.setattr(quick_capture.QuickCaptureDialog, "text", lambda self: "Kaz hinted at a cellar under The Gilded Goose")
        window._on_quick_capture()
        content = db.get_document(session)['content']
        assert content.startswith("Notes\n- ") and f"[Kaz](rpg://npc/{npc})" not in content   # only the whole title is linked
        monkeypatch.setattr(quick_capture.QuickCaptureDialog, "text", lambda self: "Met Kaz the Quick at The Gilded Goose")
        window._on_quick_capture()
        content = db.get_document(session)['content']
        assert f"[Kaz the Quick](rpg://npc/{npc})" in content and f"[The Gilded Goose](rpg://location/{place})" in content
        assert [d['title'] for d in window._get_link_graph().cast_of(session)] == ["The Gilded Goose", "Kaz the Quick"] \
            or {d['title'] for d in window._get_link_graph().cast_of(session)} == {"Kaz the Quick", "The Gilded Goose"}
    finally:
        window.deleteLater()


def test_quick_capture_goes_through_an_open_editor(app, monkeypatch):
    from PyQt6.QtWidgets import QDialog
    from gui.dialogs import quick_capture
    from gui.dialogs.document_viewer import DocumentViewerWindow
    from models.document import Document

    window, db, campaign, npc, place, session = _window()
    try:
        viewer = DocumentViewerWindow(Document.from_dict(db.get_document(session)), db, window)
        viewer.show()
        viewer.content_edit.set_content("Typed but not saved yet")
        monkeypatch.setattr(quick_capture.QuickCaptureDialog, "exec", lambda self: QDialog.DialogCode.Accepted)
        monkeypatch.setattr(quick_capture.QuickCaptureDialog, "text", lambda self: "Kaz the Quick arrives")
        window._on_quick_capture()
        saved = db.get_document(session)['content']
        assert "Typed but not saved yet" in saved and f"rpg://npc/{npc}" in saved       # nothing of the editor was lost
        viewer._is_dirty = False
        viewer.close()
    finally:
        window.deleteLater()


def test_quick_capture_makes_a_session_when_there_is_none(app, monkeypatch):
    from PyQt6.QtWidgets import QDialog
    from config.settings import Settings
    from gui.dialogs import quick_capture
    from gui.main_window import MainWindow
    db, campaign = _db()
    settings = Settings()
    settings.set_last_module_id(campaign)
    window = MainWindow(settings, db)
    try:
        monkeypatch.setattr(quick_capture.QuickCaptureDialog, "exec", lambda self: QDialog.DialogCode.Accepted)
        monkeypatch.setattr(quick_capture.QuickCaptureDialog, "text", lambda self: "Something happened")
        window._on_quick_capture()
        sessions = db.get_documents(campaign, "session")
        assert len(sessions) == 1 and "Something happened" in sessions[0]['content']
    finally:
        window.deleteLater()


def test_relationship_map_places_neighbours_and_recentres(app):
    from gui.dialogs.relationship_map import RelationshipMapDialog
    from services.link_service import build_link_graph

    window, db, campaign, npc, place, session = _window()
    try:
        doc = db.get_document(session)
        db.update_document(session, doc['title'], f"[Kaz](rpg://npc/{npc}) at [Goose](rpg://location/{place})", doc['metadata'])
        graph = build_link_graph(db, campaign)
        dialog = RelationshipMapDialog(graph, session)
        assert set(dialog.nodes) == {session, npc, place}
        dialog._recentre(npc)
        assert dialog.center_id == npc and set(dialog.nodes) == {npc, session}
        dialog.second_ring.setChecked(True)
        assert set(dialog.nodes) == {npc, session, place}
        dialog.deleteLater()
    finally:
        window.deleteLater()


def test_automatic_backup_keeps_the_last_seven_and_skips_fresh_ones(app, tmp_path, monkeypatch):
    import os
    import time

    monkeypatch.setenv("RPG_DB_DATA_DIR", str(tmp_path))
    window, db, campaign, npc, place, session = _window()
    try:
        folder = tmp_path / "auto_backups"
        window._auto_backup_on_close()
        files = list(folder.glob("*.zip"))
        assert len(files) == 1
        window._auto_backup_on_close()                          # a moment later: the fresh backup is enough
        assert len(list(folder.glob("*.zip"))) == 1
        for number in range(9):                                 # old ones pile up, only seven stay
            old = folder / f"C-2026010{number}-000000.zip"
            old.write_bytes(b"x")
            os.utime(old, (time.time() - 90000 + number, time.time() - 90000 + number))
        os.utime(files[0], (time.time() - 3600, time.time() - 3600))
        window._auto_backup_on_close()
        assert len(list(folder.glob("*.zip"))) == 7
        window.automation_actions['auto_backup_on_close'].setChecked(False)
        before = sorted(p.name for p in folder.glob("*.zip"))
        os.utime(max(folder.glob("*.zip"), key=lambda p: p.stat().st_mtime), (time.time() - 7200, time.time() - 7200))
        window._auto_backup_on_close()
        assert sorted(p.name for p in folder.glob("*.zip")) == before      # switched off: nothing new
    finally:
        window.deleteLater()
