"""Natural sorting: numbers inside names are ordered by value ("2" before "10") everywhere lists are sorted."""
import pytest

pytest.importorskip("PyQt6")
from PyQt6.QtCore import Qt, QStandardPaths
from PyQt6.QtWidgets import QApplication

from gui.components.entity_list import ROLE_ROW
from utils.natural_sort import natural_key


@pytest.fixture(scope="module")
def app():
    QStandardPaths.setTestModeEnabled(True)  # keep config/data out of the real profile
    return QApplication.instance() or QApplication([])


def _sorted(names):
    return sorted(names, key=natural_key)


def test_numbers_are_compared_by_value():
    assert _sorted(["10", "2", "1", "9", "3", "20", "11"]) == ["1", "2", "3", "9", "10", "11", "20"]
    assert _sorted(["Room 10", "Room 2", "room 1"]) == ["room 1", "Room 2", "Room 10"]    # case is ignored
    assert _sorted(["Goblin 2b", "Goblin 2a", "Goblin 10"]) == ["Goblin 2a", "Goblin 2b", "Goblin 10"]
    assert _sorted(["Level 1.10", "Level 1.2"]) == ["Level 1.2", "Level 1.10"]


def test_text_numbers_and_empty_values_never_clash():
    # numbers before letters, text without numbers still works, empty and None are fine
    assert _sorted(["b", "10", "a", "", "2"]) == ["", "2", "10", "a", "b"]
    assert natural_key(None) == [""]
    assert _sorted(["Zed", "Åsa 10", "Åsa 2"]) == ["Åsa 2", "Åsa 10", "Zed"]                    # accents do not push names to the end
    assert _sorted(["Zoltán", "Ödön", "Ágnes", "Béla", "Éva", "Árpád"]) == ["Ágnes", "Árpád", "Béla", "Éva", "Ödön", "Zoltán"]
    assert _sorted(["²", "3"]) is not None                       # superscript digits are text, not numbers: no crash
    assert _sorted(["٣", "٢", "١٠"]) == ["٢", "٣", "١٠"]         # other scripts' digits are numbers too


def _titles(tree):
    items = []
    for i in range(tree.topLevelItemCount()):
        item = tree.topLevelItem(i)
        if item.data(0, ROLE_ROW) and item.data(0, ROLE_ROW).get('is_group'):
            items.append(item.data(0, ROLE_ROW)['title'])
        else:
            items.append(item.text(0))
    return items


def _window(titles):
    from config.settings import Settings
    from gui.main_window import MainWindow
    from models.database import DatabaseManager

    db = DatabaseManager(":memory:")
    db.initialize_database()
    module_id = db.create_module("Numbers", "d")
    for title in titles:
        db.create_document(module_id, "npc", title, "Race: Elf")
    settings = Settings()
    settings.set_last_module_id(module_id)
    settings.set_entity_sort_preference('npc', 0, 'asc')
    settings.set_entity_group_preference('npc', '')
    return MainWindow(settings, db), db, module_id


NAMES = ["10", "1", "2", "NPC 10", "NPC 2", "npc 1", "3", "9"]


def test_entity_lists_sort_numbers_by_value_in_both_directions(app):
    window, _db, _module = _window(NAMES)
    try:
        tree = window.entity_lists['npc']
        assert _titles(tree) == ["1", "2", "3", "9", "10", "npc 1", "NPC 2", "NPC 10"]
        window.entity_order_buttons['npc'].click()                       # descending
        assert _titles(tree) == ["NPC 10", "NPC 2", "npc 1", "10", "9", "3", "2", "1"]
    finally:
        window.deleteLater()


def test_group_headers_and_other_text_columns_sort_naturally(app):
    window, db, module_id = _window([])
    try:
        for faction in ("Clan 10", "Clan 2", "Clan 1"):
            db.create_document(module_id, "faction", faction, "Race: Human")
        for index, faction in enumerate(("Clan 10", "Clan 2", "Clan 1")):
            db.create_document(module_id, "npc", f"N{index}", f"Race: Elf\nFaction: {faction}")
        window._load_documents()
        tree = window.entity_lists['npc']
        window.entity_group_combos['npc'].setCurrentIndex(window.entity_group_combos['npc'].findData('faction'))
        assert _titles(tree) == ["Clan 1", "Clan 2", "Clan 10"]          # not Clan 1, Clan 10, Clan 2
        window.entity_group_combos['npc'].setCurrentIndex(0)
        window.entity_sort_combos['npc'].setCurrentIndex(2)              # by faction
        assert [tree.topLevelItem(i).text(2) for i in range(3)] == ["Clan 1", "Clan 2", "Clan 10"]
    finally:
        window.deleteLater()


def test_the_sessions_page_sorts_numbers_by_value(app):
    from services.session_service import SessionService
    from gui.session_widget import SessionWidget

    window, db, module_id = _window([])
    try:
        for number in (10, 2, 1, 9):
            db.create_document(module_id, "session", f"Session {number}", "notes",
                               metadata='{"session_date": "2026-10-01"}')
        widget = SessionWidget(SessionService(db), module_id, window.template_service, window.settings)
        widget.refresh_data()
        tree = widget.sessions_tree
        tree.sortByColumn(0, Qt.SortOrder.AscendingOrder)
        assert [tree.topLevelItem(i).text(0) for i in range(4)] == ["Session 1", "Session 2", "Session 9", "Session 10"]
        tree.sortByColumn(0, Qt.SortOrder.DescendingOrder)
        assert [tree.topLevelItem(i).text(0) for i in range(4)] == ["Session 10", "Session 9", "Session 2", "Session 1"]
        widget.deleteLater()
    finally:
        window.deleteLater()


def test_the_search_palette_ranks_equal_matches_in_natural_order(app):
    from gui.components.entity_list import ThumbnailLoader
    from gui.dialogs.command_palette import CommandPalette
    from services.image_service import ImageService

    docs = [{'id': i, 'entity_type': 'npc', 'title': title, 'content': '', 'modified_date': '2026-10-01'}
            for i, title in enumerate(["Guard 10", "Guard 2", "Guard 1"], start=1)]
    palette = CommandPalette(None, docs, {'npc': 'NPC'}, ThumbnailLoader(ImageService()), lambda ids: {}, [])
    try:
        palette.search_edit.setText("guard")
        assert palette.result_titles() == ["Guard 1", "Guard 2", "Guard 10"]
    finally:
        palette.deleteLater()


def test_the_discord_picker_lists_numbers_by_value(app):
    from gui.dialogs.discord_entity_picker import DiscordEntityPickerDialog, EntityChoice

    dialog = DiscordEntityPickerDialog([EntityChoice(1, "Orc 10"), EntityChoice(2, "Orc 2"), EntityChoice(3, "Orc 1")])
    try:
        assert [c.name for c in dialog._choices] == ["Orc 1", "Orc 2", "Orc 10"]
    finally:
        dialog.deleteLater()
