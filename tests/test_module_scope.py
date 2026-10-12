"""Adventure modules: links, the scope selector, per-list filters and bulk actions."""
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
    campaign = db.create_module("Campaign", "d")
    return db, campaign


def test_database_links_are_many_to_many_and_idempotent():
    db, campaign = _db()
    a = db.create_document(campaign, "module", "A", "x")
    b = db.create_document(campaign, "module", "B", "x")
    npc = db.create_document(campaign, "npc", "Mira", "Race: Elf")
    assert db.set_module_membership([npc], a, True) == 1
    assert db.set_module_membership([npc], a, True) == 0          # twice is harmless
    db.set_module_membership([npc], b, True)
    assert sorted(db.get_module_links(campaign)[npc]) == sorted([a, b])
    db.set_module_membership([npc], a, False)
    assert db.get_module_links(campaign)[npc] == [b]
    db.set_document_modules(npc, [])
    assert npc not in db.get_module_links(campaign)
    db.set_module_membership([a], a, True)                         # a module is never its own member
    assert a not in db.get_module_links(campaign)


def test_bulk_faction_keeps_other_metadata():
    db, campaign = _db()
    faction = db.create_document(campaign, "faction", "Guild", "x")
    npc = db.create_document(campaign, "npc", "Mira", "x", metadata='{"source_id": "c-1"}')
    db.set_documents_faction([npc], faction)
    import json
    assert json.loads(db.get_document(npc)['metadata']) == {"source_id": "c-1", "faction_id": faction}
    db.set_documents_faction([npc], None)
    assert json.loads(db.get_document(npc)['metadata']) == {"source_id": "c-1"}


def _window():
    from config.settings import Settings
    from gui.main_window import MainWindow

    db, campaign = _db()
    mod_a = db.create_document(campaign, "module", "Raton Pass", "x")
    mod_b = db.create_document(campaign, "module", "Docks", "x")
    ids = {name: db.create_document(campaign, "npc", name, "Race: Elf") for name in ("Mira", "Kaz", "Nyx", "Barnaby")}
    db.set_module_membership([ids["Mira"], ids["Nyx"]], mod_a, True)
    db.set_module_membership([ids["Kaz"], ids["Nyx"]], mod_b, True)
    session = db.create_document(campaign, "session", "Session 1", "n", metadata='{"session_date": "2026-10-01"}')
    db.set_module_membership([session], mod_a, True)
    settings = Settings()
    settings.set_last_module_id(campaign)
    return MainWindow(settings, db), db, campaign, mod_a, mod_b, ids


def _names(tree):
    return sorted(tree.topLevelItem(i).text(0) for i in range(tree.topLevelItemCount()))


def test_scope_filters_lists_sessions_and_counts(app):
    window, db, campaign, mod_a, mod_b, ids = _window()
    try:
        tree = window.entity_lists['npc']
        assert _names(tree) == ["Barnaby", "Kaz", "Mira", "Nyx"]
        window._set_scope(False, {mod_a}, False)
        assert _names(tree) == ["Mira", "Nyx"]
        window._set_scope(False, {mod_a, mod_b}, False)
        assert _names(tree) == ["Kaz", "Mira", "Nyx"]                # an entry in two modules shows once
        window._set_scope(False, set(), True)
        assert _names(tree) == ["Barnaby"]
        window._set_scope(False, {mod_b}, True)
        assert _names(tree) == ["Barnaby", "Kaz", "Nyx"]
        window._set_scope(False, {mod_a}, False)
        assert window.session_widget.sessions_tree.topLevelItemCount() == 1
        window._set_scope(False, {mod_b}, False)
        assert window.session_widget.sessions_tree.topLevelItemCount() == 0
        window._set_scope(True, set(), False)
        assert window.session_widget.sessions_tree.topLevelItemCount() == 1
        assert window.scope_button.text().startswith("Scope: Whole campaign")
    finally:
        window.deleteLater()


def test_list_filter_and_module_column(app):
    window, db, campaign, mod_a, mod_b, ids = _window()
    try:
        tree = window.entity_lists['npc']
        combo = window.entity_module_filters['npc']
        combo.setCurrentIndex(combo.findData(mod_b))
        assert _names(tree) == ["Kaz", "Nyx"]
        combo.setCurrentIndex(combo.findData('none'))
        assert _names(tree) == ["Barnaby"]
        combo.setCurrentIndex(0)
        nyx = next(tree.topLevelItem(i) for i in range(tree.topLevelItemCount()) if tree.topLevelItem(i).text(0) == "Nyx")
        labels = [tree.headerItem().text(i) for i in range(tree.columnCount())]
        assert nyx.text(labels.index("Module")) == "Docks, Raton Pass"
    finally:
        window.deleteLater()


def test_bulk_add_and_remove_on_selected_rows(app):
    window, db, campaign, mod_a, mod_b, ids = _window()
    try:
        window._bulk_set_module('npc', [ids["Barnaby"], ids["Kaz"]], mod_a, True)
        assert mod_a in window._module_links[ids["Barnaby"]]
        window._bulk_set_module('npc', [ids["Barnaby"]], mod_a, False)
        assert ids["Barnaby"] not in window._module_links
        faction = db.create_document(campaign, "faction", "Guild", "x")
        window._bulk_set_faction('npc', [ids["Mira"], ids["Kaz"]], faction)
        tree = window.entity_lists['npc']
        factions = {tree.topLevelItem(i).text(0): tree.topLevelItem(i).text(2) for i in range(tree.topLevelItemCount())}
        assert factions["Mira"] == "Guild" and factions["Kaz"] == "Guild" and factions["Nyx"] == ""
    finally:
        window.deleteLater()


def test_editor_saves_modules(app):
    from gui.dialogs.document_viewer import DocumentViewerWindow
    from models.document import Document

    window, db, campaign, mod_a, mod_b, ids = _window()
    try:
        viewer = DocumentViewerWindow(Document.from_dict(db.get_document(ids["Kaz"])), db, window)
        assert viewer.module_picker.selected_ids() == [mod_b]
        viewer.module_picker.set_selected([mod_a, mod_b])
        viewer._on_save()
        assert sorted(db.get_module_links(campaign)[ids["Kaz"]]) == sorted([mod_a, mod_b])
        assert sorted(window._module_links[ids["Kaz"]]) == sorted([mod_a, mod_b])
        viewer._is_dirty = False
        viewer.close()
    finally:
        window.deleteLater()
