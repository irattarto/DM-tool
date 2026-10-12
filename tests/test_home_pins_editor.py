"""Home page, pinned entries ("Tonight") and the redesigned editor window."""
import pytest

pytest.importorskip("PyQt6")
from PyQt6.QtCore import QStandardPaths
from PyQt6.QtWidgets import QApplication, QLabel, QPushButton

from gui.components.entity_list import ROLE_ROW
from gui.components.sidebar import ROLE_ENTRY


@pytest.fixture(scope="module")
def app():
    QStandardPaths.setTestModeEnabled(True)  # keep config/data out of the real profile
    return QApplication.instance() or QApplication([])


DOCS = [
    ("faction", "Silver Guild", "Race: Human"),
    ("faction", "Iron Pact", "Race: Dwarf"),
    ("npc", "Aria", "Name: Aria\nRace: Elf\nFaction: Silver Guild\nA wanderer."),
    ("npc", "Borin", "Name: Borin\nRace: Dwarf\nFaction: Iron Pact"),
    ("npc", "Cora", "Name: Cora\nRace: Human\nFaction: Silver Guild"),
    ("location", "Aria's Tower", "A tall tower"),
]


def _window(db=None, module_id=None):
    from config.settings import Settings
    from gui.main_window import MainWindow
    from models.database import DatabaseManager

    if db is None:
        db = DatabaseManager(":memory:")
        db.initialize_database()
        module_id = db.create_module("Greywood", "d")
        for entity_type, title, content in DOCS:
            db.create_document(module_id, entity_type, title, content)
        db.create_session(module_id, "2026-10-12", "Session 12", "notes")
    settings = Settings()
    settings.set_last_module_id(module_id)
    return MainWindow(settings, db), db, module_id


def _doc(db, module_id, title):
    return next(d for d in db.get_documents(module_id) if d['title'] == title)


def _labels(widget):
    return [label.text() for label in widget.findChildren(QLabel)]


def test_window_starts_on_home_with_the_campaign_overview(app):
    window, _db, _module = _window()
    try:
        assert window.tab_widget.currentWidget() is window.home_tab
        assert window.sidebar.currentItem().data(ROLE_ENTRY)['key'] == 'home'
        texts = _labels(window.home_tab)
        assert "Greywood" in texts and "1 session · 6 entries" in texts
        assert {"NPCs", "Factions", "Locations"} <= set(texts)       # one tile per entity type
        assert "Aria's Tower" in texts and "Silver Guild" in texts    # recent activity
        assert "2 NPCs" in texts and "1 NPCs" in texts                # factions with their members
        assert "Session 12" in texts                                  # recent sessions
    finally:
        window.deleteLater()


def test_home_tiles_and_rows_navigate(app):
    window, db, module_id = _window()
    try:
        window.home_tab.go_to.emit('faction')
        assert window.tab_widget.currentWidget() is window.entity_tabs['faction']
        opened = []
        window._open_document_window = lambda document: opened.append(document.title)
        window.home_tab.open_entry.emit(_doc(db, module_id, "Aria"))
        assert opened == ["Aria"]
        assert window.tab_widget.currentWidget() is window.entity_tabs['npc']
        assert window.entity_lists['npc'].currentItem().text(0) == "Aria"
    finally:
        window.deleteLater()


def test_pins_are_stored_per_campaign_and_shown_in_the_tray(app):
    window, db, module_id = _window()
    try:
        aria = _doc(db, module_id, "Aria")
        tree = window.entity_lists['npc']
        item = window._find_entity_item(tree, aria['id'])
        assert not item.data(0, ROLE_ROW)['pinned']

        window._on_pin_item(item)                                   # the star was clicked
        assert window._pins == [aria['id']]
        assert item.data(0, ROLE_ROW)['pinned']
        assert "Aria" in [b.text() for b in window.pin_tray.chips_area.findChildren(QPushButton)]   # a chip in the tray
        assert db.get_app_meta(f"pins_{module_id}") == f"[{aria['id']}]"

        # a second window on the same database sees the same pins
        other, _, _ = _window(db, module_id)
        try:
            assert other._pins == [aria['id']]
            assert other._find_entity_item(other.entity_lists['npc'], aria['id']).data(0, ROLE_ROW)['pinned']
        finally:
            other.deleteLater()

        # another campaign has its own pins
        second = db.create_module("Winter Siege", "d")
        window._switch_campaign(second)
        assert window._pins == []
        window._switch_campaign(module_id)
        assert window._pins == [aria['id']]

        window._toggle_pin(aria['id'])                              # unpin
        assert window._pins == [] and not window._find_entity_item(tree, aria['id']).data(0, ROLE_ROW)['pinned']
    finally:
        window.deleteLater()


def test_pins_of_deleted_entries_disappear(app):
    window, db, module_id = _window()
    try:
        borin = _doc(db, module_id, "Borin")
        window._toggle_pin(borin['id'])
        db.delete_document(borin['id'])
        window._refresh_pin_tray()
        assert window._pins == []
        assert db.get_app_meta(f"pins_{module_id}") == "[]"
    finally:
        window.deleteLater()


def test_pin_from_the_preview_button_and_menu_text(app):
    window, db, module_id = _window()
    try:
        tree = window.entity_lists['npc']
        tree.setCurrentItem(window._find_entity_item(tree, _doc(db, module_id, "Cora")['id']))
        preview = window.entity_previews['npc']
        assert preview.pin_button.text() == "Pin for tonight"
        preview.pin_button.click()
        assert preview.pin_button.text() == "Unpin"
        assert window._is_pinned(_doc(db, module_id, "Cora")['id'])
    finally:
        window.deleteLater()


def test_editor_window_layout(app):
    from gui.dialogs.document_viewer import DocumentViewerWindow
    from models.document import Document

    window, db, module_id = _window()
    try:
        viewer = DocumentViewerWindow(Document.from_dict(_doc(db, module_id, "Aria")), db, window)
        try:
            tabs = [viewer.tab_widget.tabText(i) for i in range(viewer.tab_widget.count())]
            assert tabs[:2] == ["Description", "Images"] and "Metadata" not in tabs
            assert viewer.faction_combo.parentWidget().objectName() == "editorInfo"     # next to the picture
            assert viewer.primary_image_widget.parentWidget().objectName() == "editorInfo"
            assert viewer.unsaved_label.isHidden()
            viewer.title_edit.setText("Aria the Bold")
            assert viewer._is_dirty and not viewer.unsaved_label.isHidden()           # the marker follows unsaved changes
            viewer._on_save()
            assert not viewer._is_dirty and viewer.unsaved_label.isHidden()
            assert db.get_document(viewer.document.id)['title'] == "Aria the Bold"
        finally:
            viewer._is_dirty = False
            viewer.deleteLater()
    finally:
        window.deleteLater()
