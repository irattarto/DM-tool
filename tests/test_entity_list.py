"""Thumbnail entity lists: helpers, primary-image lookup, sorting, grouping and delete-with-undo."""
import pytest

pytest.importorskip("PyQt6")
from PyQt6.QtCore import QStandardPaths, Qt
from PyQt6.QtGui import QColor, QImage
from PyQt6.QtWidgets import QApplication

from gui.components.entity_list import ROLE_DOC, ROLE_ROW, ThumbnailLoader, excerpt, initials, name_hue


@pytest.fixture(scope="module")
def app():
    QStandardPaths.setTestModeEnabled(True)  # keep config/data out of the real profile
    return QApplication.instance() or QApplication([])


def _window(extra=()):
    from config.settings import Settings
    from gui.main_window import MainWindow
    from models.database import DatabaseManager

    db = DatabaseManager(":memory:")
    db.initialize_database()
    module_id = db.create_module("Lists", "d")
    ids = {}
    for entity_type, title, content in extra:
        ids[title] = db.create_document(module_id, entity_type, title, content)
    settings = Settings()
    settings.set_last_module_id(module_id)
    for entity_type in ('npc', 'faction'):
        settings.set_entity_sort_preference(entity_type, 0, 'asc')
        settings.set_entity_group_preference(entity_type, '')
    return MainWindow(settings, db), db, module_id, ids


NPCS = [
    ("faction", "Silver Guild", "Race: Human"),
    ("faction", "Iron Pact", "Race: Dwarf"),
    ("npc", "Aria", "Name: Aria\nRace: Elf\nFaction: Silver Guild\nA wanderer."),
    ("npc", "Borin", "Name: Borin\nRace: Dwarf\nFaction: Iron Pact"),
    ("npc", "Cora", "Name: Cora\nRace: Human"),
]


def _titles(tree):
    return [tree.topLevelItem(i).text(0) for i in range(tree.topLevelItemCount())]


def test_helpers():
    assert name_hue("Silver Guild") == name_hue("Silver Guild")
    assert 0 <= name_hue("Anything at all") < 360
    assert name_hue("Silver Guild") != name_hue("Iron Pact")
    assert initials("Mira Thornwood") == "MT"
    assert initials("old barnaby") == "O"
    # the fields the preview already shows are not repeated in the excerpt
    text = excerpt("Name: Aria\nRace: Elf\nFaction: Guild\n## Notes\nA **wanderer** who [helps](x) people.")
    assert text == "Notes A wanderer who helps people."
    assert excerpt("word " * 100, 20).endswith("…")


def test_primary_images_are_looked_up_in_one_call(temp_db, sample_module):
    first = temp_db.create_document(sample_module, "npc", "A", "x")
    second = temp_db.create_document(sample_module, "npc", "B", "x")
    third = temp_db.create_document(sample_module, "npc", "C", "x")
    image_a = temp_db.save_image_record(sample_module, first, "a.png", "a.png", "/x/a.png", 1, "image/png")
    other_a = temp_db.save_image_record(sample_module, first, "a2.png", "a2.png", "/x/a2.png", 1, "image/png")
    image_b = temp_db.save_image_record(sample_module, second, "b.png", "b.png", "/x/b.png", 1, "image/png")
    temp_db.set_primary_image(first, image_a)
    temp_db.set_primary_image(second, image_b)

    result = temp_db.get_primary_images_for_documents([first, second, third])
    assert set(result) == {first, second}
    assert result[first]['id'] == image_a and result[first]['filename'] == "a.png"
    assert other_a != image_a
    assert temp_db.get_primary_images_for_documents([]) == {}


def test_thumbnail_loader_makes_square_crops(app, tmp_path):
    from services.image_service import ImageService

    picture = QImage(300, 500, QImage.Format.Format_RGB32)
    picture.fill(QColor("red"))
    path = tmp_path / "tall.png"
    picture.save(str(path))
    loader = ThumbnailLoader(ImageService())
    pixmap = loader.pixmap({'id': 1, 'module_id': 1, 'filename': 'tall.png', 'file_path': str(path)}, 96)
    assert pixmap is not None and (pixmap.width(), pixmap.height()) == (96, 96)
    assert loader.pixmap({'id': 1, 'module_id': 1, 'filename': 'tall.png', 'file_path': str(path)}, 96) is pixmap  # cached
    assert loader.pixmap(None) is None
    assert loader.pixmap({'id': 2, 'module_id': 1, 'filename': 'gone.png', 'file_path': str(tmp_path / 'gone.png')}) is None


def test_list_rows_carry_what_is_painted(app):
    window, _db, _module, _ids = _window(NPCS)
    try:
        tree = window.entity_lists['npc']
        assert _titles(tree) == ["Aria", "Borin", "Cora"]
        info = tree.topLevelItem(0).data(0, ROLE_ROW)
        assert (info['race'], info['faction'], info['is_group']) == ("Elf", "Silver Guild", False)
        assert info['hue'] == name_hue("Silver Guild")
        assert tree.topLevelItem(0).data(0, ROLE_DOC)['title'] == "Aria"
        assert tree.isHeaderHidden() and all(tree.isColumnHidden(c) for c in range(1, tree.columnCount()))
        # the painted list renders without errors
        window.resize(1100, 600)
        window.tab_widget.setCurrentWidget(window.entity_tabs['npc'])
        window.show()
        app.processEvents()
        assert not window.grab().isNull()
    finally:
        window.deleteLater()


def test_sort_choice_and_direction(app):
    window, _db, _module, _ids = _window(NPCS)
    try:
        tree = window.entity_lists['npc']
        combo = window.entity_sort_combos['npc']
        assert [combo.itemText(i) for i in range(combo.count())] == \
            ['Name', 'Race', 'Faction', 'Created Date', 'Modified Date', 'Module']

        combo.setCurrentIndex(1)  # race: Dwarf, Elf, Human
        assert _titles(tree) == ["Borin", "Aria", "Cora"]
        window.entity_order_buttons['npc'].click()  # descending; Human, Elf, Dwarf
        assert _titles(tree) == ["Cora", "Aria", "Borin"]
        assert window.entity_order_buttons['npc'].text() == '▼'
        assert window.settings.get_entity_sort_preference('npc') == (1, 'desc')

        combo.setCurrentIndex(2)  # faction: Cora has none and always comes last, in either direction
        assert _titles(tree)[-1] == "Cora"
        window.entity_order_buttons['npc'].click()
        assert _titles(tree)[-1] == "Cora"
    finally:
        window.deleteLater()


def test_grouping_by_faction_and_module(app):
    window, _db, _module, _ids = _window(NPCS)
    try:
        tree = window.entity_lists['npc']
        group = window.entity_group_combos['npc']
        assert [group.itemText(i) for i in range(group.count())] == ['None', 'Module', 'Faction']
        group.setCurrentIndex(group.findData('faction'))
        headers = [tree.topLevelItem(i).data(0, ROLE_ROW) for i in range(tree.topLevelItemCount())]
        assert [(h['title'], h['count']) for h in headers] == [("Iron Pact", 1), ("Silver Guild", 1), ("No faction", 1)]
        assert tree.topLevelItem(0).child(0).data(0, ROLE_DOC)['title'] == "Borin"
        assert window.settings.get_entity_group_preference('npc') == 'faction'
        # a header can be clicked but never becomes the selection
        assert not (tree.topLevelItem(0).flags() & Qt.ItemFlag.ItemIsSelectable)
        window._on_entity_item_clicked(tree.topLevelItem(0), 0)
        assert not tree.topLevelItem(0).isExpanded()
        group.setCurrentIndex(0)
        assert _titles(tree) == ["Aria", "Borin", "Cora"]
        assert window.entity_group_combos['faction'].findData('faction') == -1  # factions have no faction
    finally:
        window.deleteLater()


def test_the_fold_state_of_the_group_without_a_value_survives_a_rebuild(app):
    window, _db, _module, _ids = _window(NPCS)
    try:
        tree = window.entity_lists['npc']
        window.entity_group_combos['npc'].setCurrentIndex(window.entity_group_combos['npc'].findData('faction'))
        none_group = next(tree.topLevelItem(i) for i in range(tree.topLevelItemCount())
                          if tree.topLevelItem(i).data(0, ROLE_ROW)['title'] == "No faction")
        window._on_entity_item_clicked(none_group, 0)                      # fold "No faction"
        assert not none_group.isExpanded()
        window.entity_sort_combos['npc'].setCurrentIndex(1)               # any rebuild
        none_group = next(tree.topLevelItem(i) for i in range(tree.topLevelItemCount())
                          if tree.topLevelItem(i).data(0, ROLE_ROW)['title'] == "No faction")
        assert not none_group.isExpanded()
    finally:
        window.deleteLater()


def test_saving_in_the_editor_keeps_the_filter_and_updates_linked_lists(app):
    window, db, module_id, ids = _window(NPCS)
    try:
        window.entity_search_widgets['npc'].setText("bor")                  # the user filters the list
        assert _titles(window.entity_lists['npc']) == ["Borin"]
        db.update_document(ids["Borin"], "Borin the Bold", "Name: Borin\nRace: Dwarf\nFaction: Iron Pact")
        window._on_document_saved('npc')                                    # what the editor window calls after a save
        assert _titles(window.entity_lists['npc']) == ["Borin the Bold"]    # renamed, and still filtered

        window.entity_search_widgets['npc'].setText("")
        faction = db.get_document(ids["Iron Pact"])
        db.update_document(faction['id'], "Iron Covenant", faction['content'])
        # NPCs name their faction in the text, so only the faction list changes here; the lists are rebuilt without errors
        window._on_document_saved('faction')
        assert "Iron Covenant" in _titles(window.entity_lists['faction'])
    finally:
        window.deleteLater()


def test_delete_waits_for_undo_then_really_deletes(app):
    window, db, module_id, ids = _window(NPCS)
    try:
        tree = window.entity_lists['npc']
        document = db.get_document(ids["Borin"])

        window._schedule_entity_delete('npc', document)
        assert _titles(tree) == ["Aria", "Cora"]            # gone from the list at once
        assert db.get_document(ids["Borin"]) is not None    # but still in the database
        assert window.undo_toast.isVisible() or window.undo_toast.label.text().startswith("'Borin'")

        window._undo_pending_delete()                       # Undo: back in the list, never left the database
        assert _titles(tree) == ["Aria", "Borin", "Cora"]
        assert db.get_document(ids["Borin"]) is not None

        window._schedule_entity_delete('npc', document)
        window._flush_pending_deletes()                     # the undo time is over (or the app closes)
        assert db.get_document(ids["Borin"]) is None
        assert _titles(tree) == ["Aria", "Cora"]
    finally:
        window.deleteLater()


def test_a_second_delete_makes_the_first_final(app):
    window, db, _module, ids = _window(NPCS)
    try:
        window._schedule_entity_delete('npc', db.get_document(ids["Aria"]))
        window._schedule_entity_delete('npc', db.get_document(ids["Cora"]))
        assert db.get_document(ids["Aria"]) is None          # no longer undoable
        assert db.get_document(ids["Cora"]) is not None      # the latest one still is
        window._undo_pending_delete()
        assert _titles(window.entity_lists['npc']) == ["Borin", "Cora"]
    finally:
        window.deleteLater()


def test_preview_follows_the_selected_row(app):
    window, _db, _module, _ids = _window(NPCS)
    try:
        tree = window.entity_lists['npc']
        preview = window.entity_previews['npc']
        tree.setCurrentItem(tree.topLevelItem(0))
        assert preview.title_label.text() == "Aria"
        assert "wanderer" in preview.excerpt_label.text()
        assert preview.discord_button is not None                      # NPCs can be sent to Discord
        assert window.entity_previews['faction'].discord_button is None  # factions cannot (as before)
        tree.clear()
        window._update_entity_preview('npc', tree.currentItem())
        assert not preview.title_label.isVisibleTo(preview)
    finally:
        window.deleteLater()
