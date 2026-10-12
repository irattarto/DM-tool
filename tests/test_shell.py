"""Window shell: sidebar navigation, campaign switcher and the Ctrl+K palette."""
import pytest

pytest.importorskip("PyQt6")
from PyQt6.QtCore import QStandardPaths
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import QApplication

from gui.components.sidebar import ROLE_ENTRY
from gui.dialogs.command_palette import CommandPalette


@pytest.fixture(scope="module")
def app():
    QStandardPaths.setTestModeEnabled(True)  # keep config/data out of the real profile
    return QApplication.instance() or QApplication([])


def _window(docs=(), sessions=0):
    from config.settings import Settings
    from gui.main_window import MainWindow
    from models.database import DatabaseManager

    db = DatabaseManager(":memory:")
    db.initialize_database()
    module_id = db.create_module("Greywood", "d")
    for entity_type, title, content in docs:
        db.create_document(module_id, entity_type, title, content)
    for number in range(sessions):
        db.create_session(module_id, "2026-10-1%d" % number, f"Session {number}", "notes")
    settings = Settings()
    settings.set_last_module_id(module_id)
    return MainWindow(settings, db), db, module_id


DOCS = [
    ("npc", "Aria", "Race: Elf"),
    ("npc", "Borin", "Race: Dwarf, a friend of Aria"),
    ("faction", "Silver Guild", "Race: Human"),
    ("location", "Aria's Tower", "A tall tower"),
]


def _entries(sidebar):
    return [sidebar.item(i).data(ROLE_ENTRY) for i in range(sidebar.count())]


def test_database_counts(temp_db, sample_module):
    temp_db.create_document(sample_module, "npc", "A", "x")
    temp_db.create_document(sample_module, "npc", "B", "x")
    temp_db.create_document(sample_module, "quest", "Q", "x")
    temp_db.create_session(sample_module, "2026-10-01", "S", "x")
    assert temp_db.get_module_counts(sample_module) == {'documents': {'npc': 2, 'quest': 1}, 'sessions': 1}
    assert temp_db.get_module_counts(9999) == {'documents': {}, 'sessions': 0}


def test_sidebar_replaces_the_tab_bar(app):
    window, _db, _module = _window(DOCS, sessions=2)
    try:
        assert window.tab_widget.tabBar().isHidden()
        entries = _entries(window.sidebar)
        groups = [e['label'] for e in entries if e['kind'] == 'group']
        assert groups == ['Play', 'World', 'Library']
        keys = [e['key'] for e in entries if e['kind'] == 'view']
        assert keys[:2] == ['home', 'sessions'] and keys[-1] == 'templates'
        assert keys[2:-1] == list(window.entity_tabs)          # one entry per visible entity type, in tab order
        counts = {e['key']: e['count'] for e in entries if e['kind'] == 'view'}
        assert counts['npc'] == 2 and counts['faction'] == 1 and counts['location'] == 1
        assert counts['sessions'] == 2 and counts['templates'] is None
        assert "2 sessions" in window.campaign_button.text() and "4 entries" in window.campaign_button.text()
    finally:
        window.deleteLater()


def test_sidebar_and_pages_stay_in_step(app):
    window, _db, _module = _window(DOCS)
    try:
        window._on_sidebar_selected('faction')
        assert window.tab_widget.currentWidget() is window.entity_tabs['faction']
        window.tab_widget.setCurrentWidget(window.templates_tab)           # changed from code, e.g. by the palette
        assert window.sidebar.currentItem().data(ROLE_ENTRY)['key'] == 'templates'
        window.sidebar.setCurrentItem(window.sidebar._items['sessions'])    # the user clicks "Sessions"
        assert window.tab_widget.currentWidget() is window.sessions_tab
    finally:
        window.deleteLater()


def test_custom_types_and_deletes_update_the_sidebar(app):
    from gui.dialogs.entity_types_editor import EntityTypesEditor

    window, db, _module = _window(DOCS)
    try:
        editor = EntityTypesEditor(db)
        editor.types_changed.connect(window._on_entity_types_changed)
        editor.add_type("Monster")
        assert editor.apply() is True
        assert 'monster' in [e['key'] for e in _entries(window.sidebar) if e['kind'] == 'view']

        aria = next(d for d in db.get_documents(window.current_module_id, 'npc') if d['title'] == "Aria")
        window._schedule_entity_delete('npc', aria)                          # hidden at once, so not counted
        assert window.sidebar._items['npc'].data(ROLE_ENTRY)['count'] == 1
        window._undo_pending_delete()
        assert window.sidebar._items['npc'].data(ROLE_ENTRY)['count'] == 2
    finally:
        window.deleteLater()


def test_switching_campaign(app):
    window, db, first = _window(DOCS)
    try:
        second = db.create_module("Winter Siege", "d")
        db.create_document(second, "npc", "Ursa", "Race: Goliath")
        window._switch_campaign(second)
        assert window.current_module_id == second
        assert window.settings.get_last_module_id() == second
        assert "Winter Siege" in window.campaign_button.text() and "1 entries" in window.campaign_button.text()
        tree = window.entity_lists['npc']
        assert [tree.topLevelItem(i).text(0) for i in range(tree.topLevelItemCount())] == ["Ursa"]

        window._fill_campaign_menu()
        actions = [a for a in window.campaign_menu.actions() if a.isCheckable()]
        assert [a.text() for a in actions] == [m['name'] for m in db.get_modules()]   # same order as Manage Campaigns
        assert {a.text(): a.isChecked() for a in actions} == {"Greywood": False, "Winter Siege": True}
        window._switch_campaign(first)
        assert [tree.topLevelItem(i).text(0) for i in range(tree.topLevelItemCount())] == ["Aria", "Borin"]
    finally:
        window.deleteLater()


def test_menus_show_the_shortcuts(app):
    window, _db, _module = _window()
    try:
        edit_actions = {a.text(): a for a in window.menuBar().actions()[1].menu().actions() if isinstance(a, QAction)}
        assert edit_actions["&Search Everything..."].shortcut().toString() == "Ctrl+K"
        help_texts = [a.text() for a in window.menuBar().actions()[-1].menu().actions()]
        assert "&Keyboard Shortcuts" in help_texts
    finally:
        window.deleteLater()


def _palette(app, calls):
    docs = [{'id': i, 'entity_type': t, 'title': title, 'content': content, 'modified_date': f"2026-10-0{i}"}
            for i, (t, title, content) in enumerate(DOCS, start=1)]
    from gui.components.entity_list import ThumbnailLoader
    from services.image_service import ImageService

    actions = [("Open Settings", "", lambda: calls.append("settings")), ("Go to NPCs", "", lambda: calls.append("npcs"))]
    return CommandPalette(None, docs, {'npc': 'NPC', 'faction': 'Faction', 'location': 'Location'},
                          ThumbnailLoader(ImageService()), lambda ids: {}, actions)


def test_palette_ranks_and_filters(app):
    palette = _palette(app, [])
    # empty query: recently edited entries (newest first), then every action
    assert palette.result_titles() == ["Aria's Tower", "Silver Guild", "Borin", "Aria", "Open Settings", "Go to NPCs"]
    palette.search_edit.setText("aria")
    # title starts with it, then title contains, then only the text mentions it
    assert palette.result_titles() == ["Aria", "Aria's Tower", "Borin"]
    palette.search_edit.setText("settings")
    assert palette.result_titles() == ["Open Settings"]
    palette.search_edit.setText("zzz")
    assert palette.result_titles() == []


def test_palette_opens_entries_and_runs_actions(app):
    calls = []
    palette = _palette(app, calls)
    chosen = []
    palette.entity_chosen.connect(chosen.append)
    palette.search_edit.setText("silver")
    palette._activate(palette.results.currentItem())
    assert [d['title'] for d in chosen] == ["Silver Guild"]

    palette = _palette(app, calls)
    palette.search_edit.setText("go to")
    palette._activate(palette.results.currentItem())
    app.processEvents()
    assert calls == ["npcs"]
