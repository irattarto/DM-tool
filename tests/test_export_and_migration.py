"""Entity file export (round trip), the scope menu clicks, and the schema v10 -> v11 migration."""
import json
import sqlite3

import pytest

from models.database import DatabaseManager
from services.entity_file_export import build_export, export_documents, to_json, to_markdown
from services.entity_file_service import (ACTION_CONFLICT, ACTION_CREATE, ATTACH_NONE, AttachOptions, EntityFileService,
                                          parse_markdown, read_entity_file)


def _world():
    db = DatabaseManager(":memory:")
    db.initialize_database()
    campaign = db.create_module("C", "d")
    module = db.create_document(campaign, "module", "Raton Pass", "x")
    guild = db.create_document(campaign, "faction", "Iron Guild", "A guild")
    boss = db.create_document(campaign, "npc", "Big Boss", "Race: Human", metadata=json.dumps({"tags": ["Human"]}))
    yard = db.create_document(campaign, "location", "The Yard", f"Dusty. [Boss](rpg://npc/{boss}) [Gone](rpg://npc/9999)")
    session = db.create_document(campaign, "session", "Arrival", f"We meet [Big Boss](rpg://npc/{boss}).",
                                 metadata=json.dumps({"session_date": "2026-10-12", "status": "played", "participants": ["Ana", "Ben"]}))
    db.set_documents_faction([boss], guild)
    db.set_module_membership([boss, yard], module, True)
    return db, campaign, dict(module=module, guild=guild, boss=boss, yard=yard, session=session)


def _docs(db, ids, *names):
    return [db.get_document(ids[n]) for n in names]


def test_export_writes_properties_modules_and_internal_links():
    db, campaign, ids = _world()
    parsed = build_export(db, _docs(db, ids, "boss", "yard", "session"), "demo")
    text = to_markdown(parsed)
    assert "format: dm-entities" in text and "pack: demo" in text
    assert "## NPC: Big Boss {#npc-" in text and "faction: Iron Guild" in text and "tags: Human" in text
    assert "modules: [Raton Pass]" in text and "date: 2026-10-12" in text and "participants: Ana, Ben" in text
    assert "[Boss](#npc-" in text and "[Gone]" not in text and "Gone" in text          # links inside the file, plain text outside
    assert "rpg://" not in text
    data = to_json(parsed)
    assert data["format"] == "dm-entities" and [e["type"] for e in data["entities"]] == ["Location", "NPC", "Session"]


def test_exported_file_imports_into_another_campaign_with_everything_in_place(tmp_path):
    db, campaign, ids = _world()
    path = tmp_path / "out.md"
    result = export_documents(db, _docs(db, ids, "guild", "boss", "yard", "session"), path)
    assert result.entries == 4 and path.exists()

    other = DatabaseManager(":memory:")
    other.initialize_database()
    new_campaign = other.create_module("Other", "d")
    service = EntityFileService(other)
    plan = service.build_plan(read_entity_file(path), new_campaign)
    assert {i.action for i in plan.items} == {ACTION_CREATE}
    assert service.apply(plan, AttachOptions("file")).errors == []
    docs = {d['title']: d for d in other.get_documents(new_campaign)}
    boss = docs["Big Boss"]
    assert json.loads(boss['metadata'])['faction_id'] == docs["Iron Guild"]['id']
    assert f"rpg://npc/{boss['id']}" in docs["The Yard"]['content']
    assert docs["Raton Pass"]['entity_type'] == "module"
    assert other.get_module_links(new_campaign)[boss['id']] == [docs["Raton Pass"]['id']]
    assert json.loads(docs["Arrival"]['metadata'])['participants'] == ["Ana", "Ben"]
    assert "Race: Human" in boss['content']


def test_importing_the_export_back_into_the_same_campaign_makes_no_duplicates(tmp_path):
    db, campaign, ids = _world()
    path = tmp_path / "same.json"
    export_documents(db, _docs(db, ids, "boss", "yard"), path)
    service = EntityFileService(db)
    plan = service.build_plan(read_entity_file(path), campaign)
    assert {i.action for i in plan.items} == {ACTION_CONFLICT} and not any(i.selected for i in plan.items)
    for item in plan.items:
        item.selected = True
    service.apply(plan, AttachOptions(ATTACH_NONE))
    assert len(db.get_documents(campaign, "npc")) == 1 and len(db.get_documents(campaign, "location")) == 1


def test_export_copies_the_primary_picture(tmp_path, monkeypatch):
    from PIL import Image
    db, campaign, ids = _world()
    source = tmp_path / "src.png"
    Image.new("RGB", (4, 4), "blue").save(source)
    monkeypatch.setattr("services.entity_file_export.resolve_image_path", lambda image: str(source))
    monkeypatch.setattr(db, "get_primary_images_for_documents", lambda doc_ids: {ids["boss"]: {"filename": "x.png"}})
    out = tmp_path / "pack" / "e.md"
    out.parent.mkdir()
    result = export_documents(db, _docs(db, ids, "boss"), out)
    assert result.images == 1 and (out.parent / "images").is_dir()
    assert "image: images/" in out.read_text(encoding="utf-8")
    again = parse_markdown(out.read_text(encoding="utf-8"), "e", str(out))
    assert again.entries[0].image.startswith("images/")


def test_migrating_a_v10_database_adds_the_history_table(tmp_path):
    path = tmp_path / "old.db"
    db = DatabaseManager(str(path))
    db.initialize_database()
    db.close()
    conn = sqlite3.connect(path)
    conn.execute("DROP TABLE document_versions")
    conn.execute("DELETE FROM schema_version WHERE version > 10")
    conn.commit()
    conn.close()
    reopened = DatabaseManager(str(path))
    reopened.initialize_database()
    campaign = reopened.create_module("C", "d")
    doc = reopened.create_document(campaign, "npc", "A", "one")
    reopened.update_document(doc, "A", "two")
    assert [v['content'] for v in reopened.get_document_versions(doc)] == ["one"]
    reopened.close()


@pytest.fixture(scope="module")
def app():
    from PyQt6.QtCore import QStandardPaths
    from PyQt6.QtWidgets import QApplication
    QStandardPaths.setTestModeEnabled(True)
    return QApplication.instance() or QApplication([])


def test_scope_menu_clicks_keep_the_menu_and_the_scope_in_step(app):
    from config.settings import Settings
    from gui.main_window import MainWindow

    db, campaign, ids = _world()
    settings = Settings()
    settings.set_last_module_id(campaign)
    window = MainWindow(settings, db)
    try:
        window._fill_scope_menu()
        actions = window._scope_actions
        actions[ids["module"]].setChecked(True)                      # a click on the module
        assert window._scope_modules == {ids["module"]} and not window._scope_all and not actions['all'].isChecked()
        assert window.scope_button.text().startswith("Scope: Raton Pass")
        actions['none'].setChecked(True)
        assert window._scope_none and "2 modules" in window.scope_button.text()
        actions[ids["module"]].setChecked(False)
        actions['none'].setChecked(False)                            # nothing left: back to the whole campaign
        assert window._scope_all and actions['all'].isChecked()
        actions['all'].setChecked(False)                             # cannot be switched off by itself
        assert window._scope_all
        # the export menu entry exists and exports the selected rows
        assert window.export_entities_action.text().startswith("E")
    finally:
        window.deleteLater()


def test_export_from_the_window_uses_selected_rows(app, tmp_path, monkeypatch):
    from PyQt6.QtWidgets import QFileDialog
    from config.settings import Settings
    from gui.main_window import MainWindow

    db, campaign, ids = _world()
    settings = Settings()
    settings.set_last_module_id(campaign)
    window = MainWindow(settings, db)
    try:
        target = tmp_path / "rows.md"
        monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *a, **k: (str(target), ""))
        window._on_sidebar_selected('npc')
        window._on_export_entities()                                 # nothing selected: the whole list
        assert "Big Boss" in target.read_text(encoding="utf-8")
        window._on_sidebar_selected('location')
        tree = window.entity_lists['location']
        tree.setCurrentItem(tree.topLevelItem(0))
        window._on_export_entities()
        assert "The Yard" in target.read_text(encoding="utf-8") and "Big Boss" not in target.read_text(encoding="utf-8").split("## ")[1]
    finally:
        window.deleteLater()
