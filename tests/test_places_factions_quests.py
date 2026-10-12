"""Places inside places, "+ Add new faction...", and quests in HTML modules."""
import json

import pytest

pytest.importorskip("PyQt6")
from PyQt6.QtCore import QStandardPaths
from PyQt6.QtWidgets import QApplication

from gui.components.entity_list import ROLE_ROW
from models.database import DatabaseManager


@pytest.fixture(scope="module")
def app():
    QStandardPaths.setTestModeEnabled(True)
    return QApplication.instance() or QApplication([])


def _db():
    db = DatabaseManager(":memory:")
    db.initialize_database()
    return db, db.create_module("C", "d")


def test_parent_links_reject_cycles_and_can_be_cleared():
    db, campaign = _db()
    city = db.create_document(campaign, "location", "Chicago", "x")
    district = db.create_document(campaign, "location", "Downtown", "x")
    street = db.create_document(campaign, "location", "Wacker Drive", "x")
    assert db.set_parent_link(district, city) and db.set_parent_link(street, district)
    assert db.get_parent_links(campaign) == {district: city, street: district}
    assert not db.set_parent_link(city, street)                # a city inside its own street
    assert not db.set_parent_link(city, city)
    assert db.set_parent_link(street, city)                    # moved: one parent only
    assert db.get_parent_links(campaign)[street] == city
    assert db.set_parent_link(street, None) and street not in db.get_parent_links(campaign)


def _window():
    from config.settings import Settings
    from gui.main_window import MainWindow
    db, campaign = _db()
    ids = {name: db.create_document(campaign, "location", name, "x")
           for name in ("Chicago", "Downtown", "Wacker Drive", "Elm Road", "Springfield")}
    db.set_parent_link(ids["Downtown"], ids["Chicago"])
    db.set_parent_link(ids["Wacker Drive"], ids["Downtown"])
    db.set_parent_link(ids["Elm Road"], ids["Springfield"])
    settings = Settings()
    settings.set_last_module_id(campaign)
    return MainWindow(settings, db), db, campaign, ids


def _names(tree):
    out = []
    for i in range(tree.topLevelItemCount()):
        item = tree.topLevelItem(i)
        out.append(item.text(0))
    return sorted(out)


def test_locations_list_shows_filters_groups_and_sorts_by_located_in(app):
    window, db, campaign, ids = _window()
    try:
        tree = window.entity_lists['location']
        labels = [tree.headerItem().text(i) for i in range(tree.columnCount())]
        column = labels.index("Located in")
        rows = {tree.topLevelItem(i).text(0): tree.topLevelItem(i).text(column) for i in range(tree.topLevelItemCount())}
        assert rows["Wacker Drive"] == "Chicago › Downtown" and rows["Downtown"] == "Chicago" and rows["Chicago"] == ""
        combo = window.entity_location_filters['location']
        combo.setCurrentIndex(combo.findData(ids["Chicago"]))                 # everything inside Chicago, at any depth
        assert _names(tree) == ["Downtown", "Wacker Drive"]
        combo.setCurrentIndex(combo.findData('none'))
        assert _names(tree) == ["Chicago", "Springfield"]
        combo.setCurrentIndex(0)
        group = window.entity_group_combos['location']
        group.setCurrentIndex(group.findData('located_in'))
        titles = [tree.topLevelItem(i).data(0, ROLE_ROW)['title'] for i in range(tree.topLevelItemCount())]
        assert titles == ["Chicago", "Chicago › Downtown", "Springfield", "Not located in a place"]
        group.setCurrentIndex(0)
        sort = window.entity_sort_combos['location']
        sort.setCurrentIndex(sort.findText("Located in"))
        names = [tree.topLevelItem(i).text(0) for i in range(tree.topLevelItemCount())]
        assert names == ["Downtown", "Wacker Drive", "Elm Road", "Chicago", "Springfield"]   # by path; places located nowhere last
    finally:
        window.deleteLater()


def test_bulk_set_located_in_and_the_editor_box(app):
    from gui.dialogs.document_viewer import DocumentViewerWindow
    from models.document import Document
    window, db, campaign, ids = _window()
    try:
        window._bulk_set_location('location', [ids["Elm Road"]], ids["Chicago"])
        assert db.get_parent_links(campaign)[ids["Elm Road"]] == ids["Chicago"]
        window._bulk_set_location('location', [ids["Chicago"]], ids["Wacker Drive"])      # refused: inside itself
        assert ids["Chicago"] not in db.get_parent_links(campaign)
        viewer = DocumentViewerWindow(Document.from_dict(db.get_document(ids["Downtown"])), db, window)
        combo = viewer.location_combo
        assert combo.currentData() == ids["Chicago"]
        assert combo.findData(ids["Wacker Drive"]) == -1 and combo.findData(ids["Downtown"]) == -1   # not itself, not what it holds
        combo.setCurrentIndex(combo.findData(ids["Springfield"]))
        viewer._on_save()
        assert db.get_parent_links(campaign)[ids["Downtown"]] == ids["Springfield"]
        viewer._is_dirty = False
        viewer.close()
    finally:
        window.deleteLater()


def test_add_new_faction_in_the_editor_and_the_bulk_menu(app, monkeypatch):
    from PyQt6.QtWidgets import QInputDialog
    from config.settings import Settings
    from gui.dialogs.document_viewer import DocumentViewerWindow
    from gui.main_window import MainWindow
    from models.document import Document

    db, campaign = _db()
    guild = db.create_document(campaign, "faction", "Iron Guild", "x")
    npc = db.create_document(campaign, "npc", "Kaz", "Race: Halfling")
    other = db.create_document(campaign, "npc", "Mira", "Race: Elf")
    settings = Settings()
    settings.set_last_module_id(campaign)
    window = MainWindow(settings, db)
    try:
        viewer = DocumentViewerWindow(Document.from_dict(db.get_document(npc)), db, window)
        combo = viewer.faction_combo
        assert combo.itemText(combo.count() - 1) == "+ Add new faction..."
        monkeypatch.setattr(QInputDialog, "getText", staticmethod(lambda *a, **k: ("Night Court", True)))
        combo.setCurrentIndex(combo.count() - 1)
        created = [d for d in db.get_documents(campaign, "faction") if d['title'] == "Night Court"]
        assert len(created) == 1 and combo.currentText() == "Night Court" and viewer._is_dirty
        viewer._on_save()
        assert json.loads(db.get_document(npc)['metadata'])['faction_id'] == created[0]['id']
        monkeypatch.setattr(QInputDialog, "getText", staticmethod(lambda *a, **k: ("", False)))      # cancelled: nothing changes
        combo.setCurrentIndex(combo.count() - 1)
        assert combo.currentText() == "Night Court"
        monkeypatch.setattr(QInputDialog, "getText", staticmethod(lambda *a, **k: ("iron guild", True)))   # the same faction again
        combo.setCurrentIndex(combo.count() - 1)
        assert combo.currentText() == "Iron Guild" and len(db.get_documents(campaign, "faction")) == 2
        viewer._is_dirty = False
        viewer.close()

        monkeypatch.setattr(QInputDialog, "getText", staticmethod(lambda *a, **k: ("Blood Moon", True)))
        window._bulk_new_faction('npc', [npc, other])
        blood = next(d for d in db.get_documents(campaign, "faction") if d['title'] == "Blood Moon")
        assert json.loads(db.get_document(other)['metadata'])['faction_id'] == blood['id']
        assert guild
    finally:
        window.deleteLater()


def test_entity_files_carry_located_in_and_create_missing_factions(tmp_path):
    from services.entity_file_export import export_documents
    from services.entity_file_service import ATTACH_NONE, AttachOptions, EntityFileService, parse_markdown, read_entity_file

    db, campaign = _db()
    text = ("## Location: Chicago {#l-c}\nA city\n\n## Location: Downtown {#l-d}\nlocated_in: Chicago\n\nA district\n\n"
            "## Location: Lost {#l-x}\nlocated in: Nowhereville\n\nx\n\n## NPC: Kaz {#c-k}\nfaction: Night Court\n\nA courier\n")
    service = EntityFileService(db)
    result = service.apply(service.build_plan(parse_markdown(text, "p"), campaign), AttachOptions(ATTACH_NONE))
    docs = {d['title']: d for d in db.get_documents(campaign)}
    assert db.get_parent_links(campaign) == {docs["Downtown"]['id']: docs["Chicago"]['id']}
    assert any("Nowhereville" in e for e in result.errors)
    assert json.loads(docs["Kaz"]['metadata'])['faction_id'] == docs["Night Court"]['id']
    path = tmp_path / "out.md"
    export_documents(db, [docs["Chicago"], docs["Downtown"]], path)
    assert "located_in: Chicago" in path.read_text(encoding="utf-8")
    assert read_entity_file(path).entries[1].located_in == "Chicago"

    db2, campaign2 = _db()
    s2 = EntityFileService(db2)
    s2.apply(s2.build_plan(parse_markdown(text, "p"), campaign2), AttachOptions(ATTACH_NONE, create_missing_factions=False))
    kaz = next(d for d in db2.get_documents(campaign2, "npc"))
    assert 'faction_id' not in json.loads(kaz['metadata']) and not db2.get_documents(campaign2, "faction")


QUEST_HTML = """<!doctype html><html lang="en"><body><h1>Quest Module</h1>
<details class="npc-card" id="c-boss"><summary class="card-summary"><div class="npc-name">Big Boss</div></summary>
<div class="card-body"><p>Boss.</p></div></details>
<details class="room" id="l-yard"><summary class="card-summary"><h4>The Yard</h4></summary><div class="card-body"><p>Dusty.</p></div></details>
<details class="card" id="q-cellar"><summary class="card-summary"><span class="badge b-ally">open</span><h4>Find the cellar</h4></summary>
<div class="card-body"><p><b>Goal:</b> Find it under <a class="xref" href="#l-yard">the yard</a>.</p>
<p><b>Given by:</b> <a class="xref" href="#c-boss">Big Boss</a></p><p><b>Status:</b> open</p></div></details>
<div class="card" id="goal-trust"><h4>Win the guild's trust</h4><p>After <a class="xref" href="#q-cellar">the cellar</a>.</p></div>
</body></html>"""


def test_html_modules_import_quests_and_goals(tmp_path):
    from services.html_module_import_service import HtmlModuleImportService
    from services.html_module_parser import parse_html

    parsed = parse_html(QUEST_HTML, str(tmp_path / "quests.html"))
    assert parsed.warnings == []
    kinds = {e.source_id: (e.entity_type, e.subtype) for e in parsed.entities}
    assert kinds["q-cellar"] == ("quest", "") and kinds["goal-trust"] == ("quest", "goal")
    db, campaign = _db()
    service = HtmlModuleImportService(db)
    result = service.apply(service.build_plan(parsed, campaign))
    assert result.errors == []
    quests = {d['title']: d for d in db.get_documents(campaign, "quest")}
    assert set(quests) == {"Find the cellar", "Win the guild's trust"}
    yard = next(d for d in db.get_documents(campaign, "location"))
    assert f"rpg://location/{yard['id']}" in quests["Find the cellar"]['content']
    assert f"rpg://quest/{quests['Find the cellar']['id']}" in quests["Win the guild's trust"]['content']
    assert "Status" in quests["Find the cellar"]['content']
