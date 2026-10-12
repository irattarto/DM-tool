"""Link graph, "last seen", health check, merging, new names and the helpers built on them."""
import json

import pytest

pytest.importorskip("PyQt6")
from PyQt6.QtCore import QStandardPaths
from PyQt6.QtWidgets import QApplication

from models.database import DatabaseManager
from services.health_service import check_campaign, merge_documents, not_used_for_a_while
from services.link_service import build_link_graph


@pytest.fixture(scope="module")
def app():
    QStandardPaths.setTestModeEnabled(True)
    return QApplication.instance() or QApplication([])


def _world():
    db = DatabaseManager(":memory:")
    db.initialize_database()
    campaign = db.create_module("C", "d")
    ids = {}
    for kind, title in (("npc", "Mira"), ("npc", "Kaz"), ("npc", "Mirra"), ("location", "Gate"), ("faction", "Guild")):
        ids[title] = db.create_document(campaign, kind, title, "Race: Elf")
    for number in range(1, 6):
        ids[f"S{number}"] = db.create_document(campaign, "session", f"Session {number}", "",
                                               metadata=json.dumps({"session_date": f"2026-10-0{number}"}))
    return db, campaign, ids


def _write(db, doc_id, text):
    doc = db.get_document(doc_id)
    db.update_document(doc_id, doc['title'], text, doc['metadata'])


def test_link_graph_combines_text_links_and_relationships():
    db, campaign, ids = _world()
    _write(db, ids["S2"], f"We meet [Mira](rpg://npc/{ids['Mira']}) at [the gate](rpg://location/{ids['Gate']}).")
    db.create_document_relationship(ids["Kaz"], ids["S1"], "appears_in_session")
    graph = build_link_graph(db, campaign)
    assert [d['title'] for d in graph.mentioned_in(ids["Mira"])] == ["Session 2"]
    assert sorted(d['title'] for d in graph.cast_of(ids["S2"])) == ["Gate", "Mira"]
    assert [d['title'] for d in graph.cast_of(ids["S1"])] == ["Kaz"]
    assert graph.last_seen(ids["Mira"]) == ("2026-10-02", "Session 2")
    assert graph.last_seen(ids["Kaz"]) == ("2026-10-01", "Session 1")
    assert graph.last_seen(ids["Guild"]) is None
    assert {d['title'] for d in graph.unlinked()} == {"Mirra", "Guild"}


def test_not_used_for_a_while_lists_entries_missing_from_the_last_sessions():
    db, campaign, ids = _world()
    _write(db, ids["S1"], f"[Kaz](rpg://npc/{ids['Kaz']}) arrives")
    _write(db, ids["S5"], f"[Mira](rpg://npc/{ids['Mira']}) arrives")
    graph = build_link_graph(db, campaign)
    assert [(d['title'], s) for d, s in not_used_for_a_while(graph)] == [("Kaz", "Session 1")]


def test_health_check_finds_missing_factions_pictures_unlinked_and_duplicates():
    db, campaign, ids = _world()
    db.set_documents_faction([ids["Mira"]], ids["Guild"])
    issues = {i.kind: i for i in check_campaign(db, campaign)}
    assert {d['title'] for d in issues['no_faction'].documents} == {"Kaz", "Mirra"}
    assert {d['title'] for d in issues['no_picture'].documents} >= {"Mira", "Gate"}
    pair = issues['duplicate'].documents
    assert {d['title'] for d in pair} == {"Mira", "Mirra"} or {d['title'] for d in pair} == {"Mirra", "Mira"}


def test_merge_moves_links_relationships_and_modules():
    db, campaign, ids = _world()
    module = db.create_document(campaign, "module", "M", "x")
    _write(db, ids["S1"], f"[Mira](rpg://npc/{ids['Mirra']}) arrives")
    db.set_module_membership([ids["Mirra"]], module, True)
    db.create_document_relationship(ids["Mirra"], ids["Gate"], "references")
    _write(db, ids["Mira"], "The real Mira")
    db.set_documents_faction([ids["Kaz"], ids["Mirra"]], ids["Guild"])
    assert merge_documents(db, ids["Mira"], ids["Mirra"])
    assert db.get_document(ids["Mirra"]) is None
    assert f"rpg://npc/{ids['Mira']})" in db.get_document(ids["S1"])['content']
    assert "The real Mira" in db.get_document(ids["Mira"])['content'] and "Merged from" in db.get_document(ids["Mira"])['content']
    assert not merge_documents(db, ids["Mira"], ids["Mira"])
    rels = {(r['from_document_id'], r['to_document_id'], r['relationship_type']) for r in db.get_document_relationships(campaign)}
    assert (ids["Mira"], ids["Gate"], "references") in rels


def test_editor_offers_new_names_and_links_them(app, monkeypatch):
    from PyQt6.QtWidgets import QDialog
    from config.settings import Settings
    from gui.dialogs import health_dialogs
    from gui.dialogs.document_viewer import DocumentViewerWindow
    from gui.main_window import MainWindow
    from models.document import Document

    db, campaign, ids = _world()
    settings = Settings()
    settings.set_last_module_id(campaign)
    window = MainWindow(settings, db)
    try:
        viewer = DocumentViewerWindow(Document.from_dict(db.get_document(ids["S1"])), db, window)
        viewer.show()
        viewer.content_edit.set_content("The party meets Brannoch Gale at dawn. Brannoch Gale smiles.")
        monkeypatch.setattr(health_dialogs.NewNamesDialog, "exec", lambda self: QDialog.DialogCode.Accepted)
        monkeypatch.setattr(health_dialogs.NewNamesDialog, "choices", lambda self: {"Brannoch Gale": "npc"})
        viewer._on_save()
        created = [d for d in db.get_documents(campaign, "npc") if d['title'] == "Brannoch Gale"]
        assert len(created) == 1
        saved = db.get_document(ids["S1"])['content']
        assert f"(rpg://npc/{created[0]['id']})" in saved
        graph = window._get_link_graph()
        assert [d['title'] for d in graph.mentioned_in(created[0]['id'])] == ["Session 1"]
        viewer._is_dirty = False
        viewer.close()
    finally:
        window.deleteLater()


def test_home_shows_attention_and_last_seen_column(app):
    from config.settings import Settings
    from gui.main_window import MainWindow

    db, campaign, ids = _world()
    _write(db, ids["S3"], f"[Mira](rpg://npc/{ids['Mira']}) arrives")
    settings = Settings()
    settings.set_last_module_id(campaign)
    window = MainWindow(settings, db)
    try:
        assert any("without a faction" in line for line in window._attention_lines())
        tree = window.entity_lists['npc']
        labels = [tree.headerItem().text(i) for i in range(tree.columnCount())]
        rows = {tree.topLevelItem(i).text(0): tree.topLevelItem(i).text(labels.index("Last seen"))
                for i in range(tree.topLevelItemCount())}
        assert rows["Mira"] == "2026-10-03" and rows["Kaz"] == ""
    finally:
        window.deleteLater()


def test_numbered_series_are_not_duplicates_but_copies_are():
    from services.health_service import _numbered_series
    assert _numbered_series("guard 1", "guard 2") and _numbered_series("room 10", "room 11")
    assert not _numbered_series("lucas price (1)", "lucas price (2)")
    assert not _numbered_series("mira", "mirra")


def test_health_check_leaves_out_abilities_and_inventory_items():
    db, campaign, ids = _world()
    db.create_document(campaign, "ability_item", "Imported Abilities (1)", "x")
    db.create_document(campaign, "ability_item", "Imported Abilities (2)", "x")
    issues = check_campaign(db, campaign)
    assert not any("Imported Abilities" in d['title'] for i in issues for d in i.documents)
