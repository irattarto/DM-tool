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
        db.create_document(module_id, "session", "Session 12", "notes", metadata='{"session_date": "2026-10-12"}')
        db.create_document(module_id, "session", "Session 11", "notes", metadata='{"session_date": "2026-09-28"}')
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
        assert "Greywood" in texts and "2 sessions · 6 entries" in texts      # the sessions are counted as the Sessions page lists them
        assert {"NPCs", "Factions", "Locations"} <= set(texts)       # one tile per entity type
        assert "Aria's Tower" in texts and "Silver Guild" in texts    # recent activity
        assert "2 NPCs" in texts and "1 NPCs" in texts                # factions with their members
        assert texts.index("Session 12") < texts.index("Session 11")  # recent sessions, newest game date first
        assert "2026-10-12" in texts
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


def test_pin_tray_follows_delete_undo_and_final_delete(app):
    window, db, module_id = _window()
    try:
        borin = _doc(db, module_id, "Borin")
        window._toggle_pin(borin['id'])
        chips = lambda: [b.text() for b in window.pin_tray.chips_area.findChildren(QPushButton)]
        assert "Borin" in chips()
        window._schedule_entity_delete('npc', borin)
        assert "Borin" not in chips() and window._pins == [borin['id']]      # hidden at once, still pinned for Undo
        window._undo_pending_delete()
        assert "Borin" in chips()
        window._schedule_entity_delete('npc', borin)
        window._flush_pending_deletes()                                       # really gone: the pin goes too
        assert "Borin" not in chips() and window._pins == []
    finally:
        window.deleteLater()


def test_pending_deletes_do_not_follow_a_switch_to_another_campaign(app):
    window, db, module_id = _window()
    try:
        second = db.create_module("Winter Siege", "d")
        aria = _doc(db, module_id, "Aria")
        window._schedule_entity_delete('npc', aria)
        window.current_module_id = second                                    # e.g. File > New Campaign
        window._load_documents()
        assert db.get_document(aria['id']) is None and not window._pending_deletes
        assert window.sidebar._items['npc'].data(ROLE_ENTRY)['count'] == 0   # not "minus one"
    finally:
        window.deleteLater()


def test_home_faction_counts_come_from_the_database_not_from_the_lists(app):
    window, db, module_id = _window()
    try:
        window.entity_search_widgets['npc'].setText("cora")                 # the NPC list shows a single row now
        window._refresh_home()
        texts = _labels(window.home_tab)
        assert "2 NPCs" in texts and "1 NPCs" in texts                      # Silver Guild has Aria and Cora, Iron Pact has Borin
        window._schedule_entity_delete('npc', _doc(db, module_id, "Cora"))
        window._refresh_home()
        assert "2 NPCs" not in _labels(window.home_tab)                     # a delete waiting for Undo is not counted
    finally:
        window.deleteLater()


def test_sidebar_icons_are_all_known_shapes(app):
    from gui.components.sidebar import ICON_FOR_TYPE
    window, _db, _module = _window()
    try:
        icons = {e['key']: e['icon'] for e in (window.sidebar.item(i).data(ROLE_ENTRY) for i in range(window.sidebar.count()))
                 if e['kind'] == 'view'}
        assert icons['home'] == 'house' and icons['sessions'] == 'play' and icons['templates'] == 'page'
        assert set(ICON_FOR_TYPE.values()) >= {'house', 'play', 'page', 'circle', 'shield', 'diamond'}
    finally:
        window.deleteLater()


def test_a_double_click_on_the_pin_star_pins_once_and_opens_nothing(app):
    from PyQt6.QtCore import QEvent, QPointF, Qt
    from PyQt6.QtGui import QMouseEvent
    from gui.components.entity_list import PinClickFilter, pin_rect

    window, db, module_id = _window()
    try:
        tree = window.entity_lists['npc']
        window.resize(1000, 600)
        window.tab_widget.setCurrentWidget(window.entity_tabs['npc'])
        window.show()
        app.processEvents()
        item = window._find_entity_item(tree, _doc(db, module_id, "Aria")['id'])
        point = QPointF(pin_rect(tree.visualItemRect(item)).center())
        pin_filter = PinClickFilter(tree)
        clicks = []
        pin_filter.pin_clicked.connect(clicks.append)

        def mouse(kind):
            return QMouseEvent(kind, point, point, Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
        assert pin_filter.eventFilter(tree.viewport(), mouse(QEvent.Type.MouseButtonPress)) is True
        assert pin_filter.eventFilter(tree.viewport(), mouse(QEvent.Type.MouseButtonDblClick)) is True   # swallowed, no second pin
        assert len(clicks) == 1
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
            # a save refreshes the main window: the NPC list shows the new title
            tree = window.entity_lists['npc']
            assert "Aria the Bold" in [tree.topLevelItem(i).text(0) for i in range(tree.topLevelItemCount())]

            # changing the faction is an unsaved change too
            viewer.faction_combo.setCurrentIndex(1)
            assert viewer._is_dirty and not viewer.unsaved_label.isHidden()
            viewer._is_dirty = False
        finally:
            viewer._is_dirty = False
            viewer.deleteLater()
    finally:
        window.deleteLater()
