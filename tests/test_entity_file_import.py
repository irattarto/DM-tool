"""Entity files: parsing (Markdown, JSON, HTML), planning, importing, re-importing, modules and links."""
import json
from pathlib import Path

from models.database import DatabaseManager
from services.entity_file_service import (ACTION_CONFLICT, ACTION_CREATE, ACTION_UNCHANGED, ACTION_UPDATE, ATTACH_CHOSEN,
                                          ATTACH_FILE, ATTACH_NEW, ATTACH_NONE, AttachOptions, EntityFileService,
                                          parse_json, parse_markdown, read_entity_file, split_list)

ROOT = Path(__file__).resolve().parent.parent
MD_TEMPLATE = ROOT / "tools" / "entity_files" / "entities_template.md"
JSON_TEMPLATE = ROOT / "tools" / "entity_files" / "entities_template.json"

SAMPLE = """---
format: dm-entities
pack: Test Pack
modules: [Raton Pass]
---
## NPC: Big Boss {#c-boss}
race: Human
faction: Iron Guild
tags: Human, Strong
modules: [Docks]

Runs things from [the yard](#l-yard). Knows [[Kaz]].

## NPC: Kaz
A courier.

## Faction: Iron Guild {#f-guild}
A guild.

## Location: The Yard {#l-yard}
Dusty.

## Session: Arrival {#s-1}
date: 2026-10-12
status: played
participants: Ana, Ben

The party meets [Big Boss](#c-boss).
"""


def _db():
    db = DatabaseManager(":memory:")
    db.initialize_database()
    return db, db.create_module("Campaign", "d")


def test_markdown_is_parsed_into_typed_entries():
    parsed = parse_markdown(SAMPLE)
    assert parsed.pack == "test-pack" and parsed.modules == ["Raton Pass"] and parsed.warnings == []
    boss = parsed.entries[0]
    assert (boss.kind, boss.title, boss.source_id) == ("npc", "Big Boss", "c-boss")
    assert boss.faction == "Iron Guild" and boss.tags == ["Human", "Strong"] and boss.modules == ["Docks"]
    assert boss.extra == {"race": "Human"} and boss.body.startswith("Runs things")
    assert parsed.entries[1].source_id == "" and parsed.entries[1].body == "A courier."
    session = parsed.entries[4]
    assert (session.session_date, session.status, session.participants) == ("2026-10-12", "played", ["Ana", "Ben"])


def test_unknown_type_headings_stay_in_the_text_and_bad_values_warn():
    text = "## NPC: A {#a}\nbody\n\n## Notes: not a type\nmore\n\n## NPC: B {#a}\nx\n\n## Session: S\ndate: 12.10.2026\nstatus: soon\n"
    parsed = parse_markdown(text, "file")
    assert [e.title for e in parsed.entries] == ["A", "S"]
    assert "## Notes: not a type" in parsed.entries[0].body
    assert any("used twice" in w for w in parsed.warnings)
    assert any("not YYYY-MM-DD" in w for w in parsed.warnings) and any("status" in w for w in parsed.warnings)
    assert parse_markdown("just text").warnings and split_list("[a, b]") == ["a", "b"]


def test_templates_in_the_repository_are_valid():
    md = read_entity_file(MD_TEMPLATE)
    assert md.warnings == [] and {e.kind for e in md.entries} >= {"npc", "faction", "location", "item", "quest", "session"}
    js = read_entity_file(JSON_TEMPLATE)
    assert js.warnings == [] and [e.title for e in js.entries] == ["Iron Guild", "Big Boss", "The Yard", "Arrival"]
    assert js.entries[1].extra == {"race": "Human"}


def test_import_creates_links_modules_and_factions():
    db, campaign = _db()
    service = EntityFileService(db)
    plan = service.build_plan(parse_markdown(SAMPLE), campaign)
    assert [i.action for i in plan.items] == [ACTION_CREATE] * 5
    result = service.apply(plan, AttachOptions(ATTACH_FILE))
    assert result.created == 5 and result.errors == []
    docs = {d['title']: d for d in db.get_documents(campaign)}
    boss = docs["Big Boss"]
    meta = json.loads(boss['metadata'])
    assert meta['faction_id'] == docs["Iron Guild"]['id'] and meta['entity_pack'] == "test-pack"
    assert f"rpg://location/{docs['The Yard']['id']}" in boss['content']
    assert f"rpg://npc/{docs['Kaz']['id']}" in boss['content']                # [[wiki link]] by title
    assert "Race: Human" in boss['content'] and "Faction: Iron Guild" in boss['content']
    assert docs["Raton Pass"]['entity_type'] == "module" and docs["Docks"]['entity_type'] == "module"
    links = db.get_module_links(campaign)
    assert sorted(links[boss['id']]) == sorted([docs["Raton Pass"]['id'], docs["Docks"]['id']])
    assert links[docs["Kaz"]['id']] == [docs["Raton Pass"]['id']]
    session_meta = json.loads(docs["Arrival"]['metadata'])
    assert session_meta['session_date'] == "2026-10-12" and session_meta['participants'] == ["Ana", "Ben"]
    relations = {(r['relationship_type'], r['from_document_id'], r['to_document_id'])
                 for r in db.get_document_relationships(campaign)}
    assert ('appears_in_session', boss['id'], docs["Arrival"]['id']) in relations
    assert ('member_of', boss['id'], docs["Iron Guild"]['id']) in relations


def test_attach_options():
    db, campaign = _db()
    existing = db.create_document(campaign, "module", "Mine", "x")
    parsed = parse_markdown("## NPC: A {#a}\nx\n\n## NPC: B {#b}\nmodules: [Own]\ny\n", "p")
    for options, expected in ((AttachOptions(ATTACH_NONE), []), (AttachOptions(ATTACH_CHOSEN, existing), ["Mine"]),
                              (AttachOptions(ATTACH_NEW, new_module_title="Fresh"), ["Fresh"]),
                              (AttachOptions(ATTACH_FILE), [])):
        db2, camp2 = _db()
        mine = db2.create_document(camp2, "module", "Mine", "x")
        options.module_doc_id = mine if options.mode == ATTACH_CHOSEN else None
        s2 = EntityFileService(db2)
        s2.apply(s2.build_plan(parsed, camp2), options)
        names = {d['id']: d['title'] for d in db2.get_documents(camp2)}
        links = {names[doc]: sorted(names[m] for m in mods) for doc, mods in db2.get_module_links(camp2).items()}
        assert links.get("A", []) == expected
        assert links.get("B", []) == (["Own"] if options.mode == ATTACH_FILE else expected)


def test_reimport_updates_keeps_edits_and_matches_by_title():
    db, campaign = _db()
    service = EntityFileService(db)
    service.apply(service.build_plan(parse_markdown(SAMPLE), campaign), AttachOptions(ATTACH_NONE))
    again = service.build_plan(parse_markdown(SAMPLE), campaign)
    assert {i.action for i in again.items if i.entry.source_id} == {ACTION_UNCHANGED}
    # the entry without an id matches the entry it created by title: unchanged too
    assert [i.action for i in again.items if not i.entry.source_id] == [ACTION_UNCHANGED]
    changed = parse_markdown(SAMPLE.replace("Dusty.", "Very dusty."))
    plan = service.build_plan(changed, campaign)
    assert [i.action for i in plan.items if i.entry.title == "The Yard"] == [ACTION_UPDATE]
    service.apply(plan, AttachOptions(ATTACH_NONE))
    assert len(db.get_documents(campaign, "location")) == 1
    yard = db.get_documents(campaign, "location")[0]
    db.update_document(yard['id'], yard['title'], yard['content'] + "\nmy own note", yard['metadata'])
    plan = service.build_plan(parse_markdown(SAMPLE.replace("Dusty.", "Even dustier.")), campaign)
    item = next(i for i in plan.items if i.entry.title == "The Yard")
    assert item.action == ACTION_CONFLICT and item.selected is False
    # an entry made by hand with the same title is never overwritten unasked
    hand = db.create_document(campaign, "npc", "Lonely", "mine")
    plan = service.build_plan(parse_markdown("## NPC: Lonely\ntheirs\n", "other"), campaign)
    assert plan.items[0].action == ACTION_CONFLICT and plan.items[0].existing_id == hand and not plan.items[0].selected


def test_equal_ids_in_two_packs_do_not_clash():
    db, campaign = _db()
    service = EntityFileService(db)
    for pack, title in (("one", "First"), ("two", "Second")):
        plan = service.build_plan(parse_markdown(f"---\npack: {pack}\n---\n## NPC: {title} {{#c-1}}\nx\n"), campaign)
        assert plan.items[0].action == ACTION_CREATE
        service.apply(plan, AttachOptions(ATTACH_NONE))
    assert sorted(d['title'] for d in db.get_documents(campaign, "npc")) == ["First", "Second"]


def test_json_and_html_files(tmp_path):
    data = {"format": "dm-entities", "pack": "j", "entities": [
        {"type": "NPC", "id": "n1", "title": "Json Guy", "faction": "F", "tags": ["a"], "content": "hi", "race": "Elf"},
        {"type": "bogus", "title": "x"}]}
    parsed = parse_json(data)
    assert [e.title for e in parsed.entries] == ["Json Guy"] and parsed.warnings
    page = tmp_path / "cards.html"
    page.write_text(Path(ROOT / "tools" / "html_module" / "module_template.html").read_text(encoding="utf-8"), encoding="utf-8")
    cards = read_entity_file(page)
    assert cards.format == "html" and {"c-boss", "l-yard"} <= {e.source_id for e in cards.entries} and cards.suggested_module


def test_pictures_are_read_from_the_files_folder_only(tmp_path):
    from PIL import Image

    db, campaign = _db()
    (tmp_path / "images").mkdir()
    Image.new("RGB", (8, 8), "red").save(tmp_path / "images" / "boss.png")
    (tmp_path / "secret.png").write_bytes(b"x")
    parsed = parse_markdown("## NPC: Boss {#b}\nimage: images/boss.png\n\nx\n\n## NPC: Evil {#e}\nimage: ../outside.png\n\ny\n",
                            "p", str(tmp_path / "e.md"))

    class FakeImages:                      # records what would be stored
        saved = []

        def save_image(self, path, campaign_id, doc_id, original):
            FakeImages.saved.append((Path(path).name, original))
            return {'filename': original, 'original_name': original, 'file_path': path, 'file_size': 1, 'mime_type': 'image/png'}

        def delete_image(self, *a):
            pass

    service = EntityFileService(db, FakeImages())
    result = service.apply(service.build_plan(parsed, campaign), AttachOptions(ATTACH_NONE))
    assert FakeImages.saved == [("boss.png", "b.png")] and result.images == 1
    assert any("../outside.png" in e for e in result.errors)
