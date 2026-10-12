"""Headless smoke test: the main window builds its entity tabs from the registry."""
import pytest

pytest.importorskip("PyQt6")
from PyQt6.QtCore import QStandardPaths
from PyQt6.QtWidgets import QApplication, QPushButton


@pytest.fixture(scope="module")
def app():
    QStandardPaths.setTestModeEnabled(True)  # keep config/data out of the real profile
    return QApplication.instance() or QApplication([])


def test_main_window_builds_entity_tabs(app):
    from config.settings import Settings
    from gui.main_window import MainWindow
    from models.database import DatabaseManager

    db = DatabaseManager(":memory:")
    db.initialize_database()
    module_id = db.create_module("Smoke", "d")
    db.create_document(module_id, "faction", "Silver Guild", "Race: Human")
    db.create_document(module_id, "npc", "Aria", "Name: Aria\nRace: Elf\nFaction: Silver Guild")
    settings = Settings()
    settings.set_last_module_id(module_id)  # skips the modal module-choice dialog
    window = MainWindow(settings, db)
    try:
        assert list(window.entity_lists) == ['character', 'npc', 'faction', 'location', 'item', 'event',
                                             'quest', 'setting', 'module']
        npc_tree = window.entity_lists['npc']
        assert [npc_tree.headerItem().text(i) for i in range(npc_tree.columnCount())] == \
            ['Name', 'Race', 'Faction', 'Created Date', 'Modified Date', 'Module', 'Last seen']
        assert window.entity_lists['faction'].columnCount() == 6
        assert window.entity_lists['quest'].columnCount() == 5
        assert window.entity_lists['module'].columnCount() == 3   # a module has no parent module
        # rows are filled according to capabilities
        npc_item = window.entity_lists['npc'].topLevelItem(0)
        assert [npc_item.text(i) for i in range(3)] == ['Aria', 'Elf', 'Silver Guild']
        faction_item = window.entity_lists['faction'].topLevelItem(0)
        assert [faction_item.text(i) for i in range(2)] == ['Silver Guild', 'Human']
    finally:
        window.deleteLater()  # close() would raise a modal confirmation dialog


def _window(app, extra_docs=()):
    from config.settings import Settings
    from gui.main_window import MainWindow
    from models.database import DatabaseManager

    db = DatabaseManager(":memory:")
    db.initialize_database()
    module_id = db.create_module("Smoke", "d")
    for entity_type, title in extra_docs:
        db.create_document(module_id, entity_type, title, "body")
    settings = Settings()
    settings.set_last_module_id(module_id)
    return MainWindow(settings, db), db, module_id


def test_custom_types_rebuild_tabs_live(app):
    window, db, module_id = _window(app)
    try:
        tab_widget = window.tab_widget
        npc_tab = window.entity_tabs['npc']
        tab_widget.setCurrentWidget(npc_tab)

        from gui.dialogs.entity_types_editor import EntityTypesEditor
        editor = EntityTypesEditor(db)
        editor.types_changed.connect(window._on_entity_types_changed)
        key = editor.add_type("Monster")
        assert key == "monster"
        editor.move_selected(0)  # no selection: no-op
        editor.table.selectRow(len(editor.rows()) - 1)
        for _ in range(len(editor.rows())):
            editor.move_selected(-1)  # move the new type to the front
        editor.rows()[0]  # sanity
        assert editor.apply() is True

        labels = [tab_widget.tabText(i) for i in range(tab_widget.count())]
        assert labels[0] == "Sessions" and labels[1] == "Monsters"
        assert list(window.entity_lists)[0] == "monster"
        assert window.entity_lists['monster'].columnCount() == 5
        # the selected tab survived the rebuild
        assert tab_widget.currentWidget() is window.entity_tabs['npc']

        # hide and rename
        editor2 = EntityTypesEditor(db)
        editor2.types_changed.connect(window._on_entity_types_changed)
        rows = editor2.rows()
        for r in rows:
            if r['key'] == 'event':
                r['hidden'] = True
            if r['key'] == 'npc':
                r['label_plural'] = 'People'
        editor2._rows = rows
        editor2._dirty = True
        editor2.apply()
        assert 'event' not in window.entity_lists
        assert window.tab_widget.tabText(window.tab_widget.indexOf(window.entity_tabs['npc'])) == 'People'
        assert window.entity_lists['npc'].columnCount() == 7  # capabilities (not the label) drive columns
    finally:
        window.deleteLater()


def test_editor_rules(app):
    from gui.dialogs.entity_types_editor import EntityTypesEditor, slugify
    from models.database import DatabaseManager

    db = DatabaseManager(":memory:")
    db.initialize_database()
    module_id = db.create_module("M", "d")
    editor = EntityTypesEditor(db)

    assert slugify("  Dragon Lair! ") == "dragon_lair"
    first = editor.add_type("Deity")
    second = editor.add_type("Deity")  # same label twice gets a distinct, immutable key
    assert (first, second) == ("deity", "deity_2")
    assert editor.add_type("NPC") == "npc_2"  # never collides with a built-in key
    with pytest.raises(ValueError):
        editor.add_type("   ")

    keys = [r['key'] for r in editor.rows()]
    npc_index = keys.index('npc')
    allowed, reason = editor.can_delete(npc_index)
    assert not allowed and "Built-in" in reason

    editor.apply()
    db.create_document(module_id, "deity", "Thor", "body")
    allowed, reason = editor.can_delete([r['key'] for r in editor.rows()].index('deity'))
    assert not allowed and "1 document" in reason
    assert editor.delete_row([r['key'] for r in editor.rows()].index('deity_2')) is True
    editor.apply()
    assert [t['key'] for t in db.get_entity_types() if not t['builtin']] == ['deity', 'npc_2']


def test_settings_dialog_has_entity_types_tab_and_saves(app):
    from config.settings import Settings
    from gui.settings_dialog import SettingsDialog
    from models.database import DatabaseManager

    db = DatabaseManager(":memory:")
    db.initialize_database()
    settings = Settings()
    dialog = SettingsDialog(settings, db, None)
    try:
        tabs = [dialog.tab_widget.tabText(i) for i in range(dialog.tab_widget.count())]
        assert "Entity Types" in tabs
        dialog.entity_types_editor.add_type("Deity")
        assert dialog._apply_entity_types() is True
        assert dialog.entity_types_modified is True
        assert [t['key'] for t in db.get_entity_types()][-1] == 'deity'
    finally:
        dialog.deleteLater()


def test_discord_button_only_on_npc_and_location_tabs(app):
    window, _db, _module_id = _window(app)
    try:
        assert sorted(window.entity_discord_buttons) == ['location', 'npc']
        assert window.entity_discord_buttons['npc'].text() == "Send to Discord..."
        # every list has a right-click menu (Open, Delete; plus Discord on npc/location)
        assert window.entity_lists['npc'].contextMenuPolicy().name == 'CustomContextMenu'
        assert window.entity_lists['faction'].contextMenuPolicy().name == 'CustomContextMenu'
        # Delete is in that menu and on the Delete key, no longer a toolbar button
        assert not [b for b in window.entity_tabs['npc'].findChildren(QPushButton) if b.text() == "Delete"]
    finally:
        window.deleteLater()
