"""HTML module import: cards that match entries the campaign already has, and data-located-in."""

import json
import sys
from pathlib import Path

import pytest

from services.html_module_import_service import (
    ACTION_CREATE, ACTION_LINK, ACTION_OVERWRITE, ACTION_UNCHANGED, LINKED_ENTRIES_KEY, MATCH_NEW, MATCH_OVERWRITE,
    HtmlModuleImportService, ImportOptions)
from services.html_module_parser import module_from_json, module_to_json, parse_file

PAGE = """<!doctype html><html lang="en"><body><h1>Raton Pass</h1>
<section id="intro"><p>Meet <a class="xref" href="#c-boss">the boss</a> of
<a class="xref" href="#f-guild">the guild</a>.</p></section>
<section id="cast">
<div class="card" id="f-guild"><h4>Iron Guild</h4><p>A guild.</p></div>
<details class="npc-card" id="c-boss" data-faction="f-guild"><summary><div class="npc-name">Big Boss</div>
<span class="tag">Human</span></summary><div class="card-body"><p>Module text of the boss.</p>
<img class="gen-portrait" data-gen-id="c-boss" src="images/portraits/c-boss.png"></div></details>
<details class="npc-card" id="c-aide" data-faction="f-guild"><summary><div class="npc-name">Aide</div></summary>
<div class="card-body"><p>Works for <a class="xref" href="#c-boss">the boss</a>.</p></div></details>
<table><tr><th>Name</th><th>Role</th></tr>
<tr id="g-thugs" data-count="4" data-faction="f-guild"><td>Thugs</td><td>Muscle</td></tr></table>
<details class="room" id="l-city"><summary><h4>Chicago</h4></summary><div class="card-body"><p>A city.</p></div></details>
<details class="room" id="l-street" data-located-in="l-city"><summary><h4>Wacker Drive</h4></summary>
<div class="card-body"><p>A street.</p></div></details>
<details class="room" id="l-lost" data-located-in="l-nowhere"><summary><h4>Lost Alley</h4></summary>
<div class="card-body"><p>Somewhere.</p></div></details>
</section>
<section id="plot"><div class="scene" id="j-1"><span class="scene-no">1. scene</span><h4>Arrival</h4>
<p>Meet <a class="xref" href="#c-boss">the boss</a>.</p></div></section></body></html>"""


@pytest.fixture
def campaign(temp_db):
    return temp_db.create_module("Campaign", "desc")


def _write(tmp_path, page=PAGE, with_picture=False):
    path = tmp_path / "Raton_Pass.html"
    path.write_text(page, encoding="utf-8")
    if with_picture:
        from PyQt6.QtGui import QColor, QImage
        (tmp_path / 'images' / 'portraits').mkdir(parents=True, exist_ok=True)
        img = QImage(8, 8, QImage.Format.Format_RGB32)
        img.fill(QColor("red"))
        img.save(str(tmp_path / 'images' / 'portraits' / 'c-boss.png'))
    return path


def _meta(doc):
    return json.loads(doc['metadata']) if doc.get('metadata') else {}


def _module_doc(db, campaign):
    return next(d for d in db.get_documents(campaign, 'module'))


def _existing(db, campaign, faction_title="Iron Guild"):
    """A campaign made by hand before the module: a faction and the boss (in that faction)."""
    faction = db.create_document(campaign, 'faction', faction_title, "My own guild notes.")
    boss = db.create_document(campaign, 'npc', "big boss", "My own boss notes.",
                              metadata=json.dumps({'faction_id': faction, 'tags': ['Mine']}))
    return faction, boss


def test_matching_cards_use_the_existing_entries_by_default(temp_db, campaign, tmp_path):
    faction, boss = _existing(temp_db, campaign)
    svc = HtmlModuleImportService(temp_db)
    plan = svc.build_plan(parse_file(_write(tmp_path)), campaign)
    items = {i.source_id: i for i in plan.items}
    assert items['c-boss'].action == ACTION_LINK and items['c-boss'].match_id == boss and items['c-boss'].selected
    assert items['f-guild'].action == ACTION_LINK and items['f-guild'].match_id == faction
    assert items['c-aide'].action == ACTION_CREATE and items['c-aide'].match_id is None
    assert items['c-boss'].notes == []                    # same faction: nothing to report

    result = svc.apply(plan)
    assert result.errors == []
    assert len(temp_db.get_documents(campaign, 'npc')) == 3        # boss reused; aide and thugs are new
    assert len(temp_db.get_documents(campaign, 'faction')) == 1    # the same-named module faction is the existing one
    kept = temp_db.get_document(boss)
    assert kept['content'] == "My own boss notes." and kept['title'] == "big boss"
    assert 'module_doc_id' not in _meta(kept) and 'imported_raw_hash' not in _meta(kept)
    module = _module_doc(temp_db, campaign)
    assert f"rpg://npc/{boss}" in module['content'] and f"rpg://faction/{faction}" in module['content']
    assert _meta(module)[LINKED_ENTRIES_KEY] == {'c-boss': boss, 'f-guild': faction}
    links = temp_db.get_module_links(campaign)
    assert module['id'] in links[boss] and module['id'] in links[faction]   # added to this module
    aide = next(d for d in temp_db.get_documents(campaign, 'npc') if d['title'] == "Aide")
    assert _meta(aide)['faction_id'] == faction
    assert f"rpg://npc/{boss}" in aide['content']
    rels = {(r['from_document_id'], r['to_document_id'], r['relationship_type'])
            for r in temp_db.get_document_relationships(campaign)}
    scene = next(d for d in temp_db.get_documents(campaign, 'event'))
    assert (boss, scene['id'], 'appears_in_scene') in rels
    assert not any(src == boss and kind == 'references' for src, _, kind in rels)   # its own text links nothing new


def test_a_saved_choice_finds_the_entry_again_without_asking(temp_db, campaign, tmp_path):
    _, boss = _existing(temp_db, campaign)
    path = _write(tmp_path)
    svc = HtmlModuleImportService(temp_db)
    svc.apply(svc.build_plan(parse_file(path), campaign))
    temp_db.update_document(boss, "Boss Prime", "Renamed by hand.", temp_db.get_document(boss)['metadata'])
    plan = svc.build_plan(parse_file(path), campaign)
    item = next(i for i in plan.items if i.source_id == 'c-boss')
    assert item.action == ACTION_LINK and item.match_id == boss and item.match_saved
    svc.apply(plan)
    assert len(temp_db.get_documents(campaign, 'npc')) == 3
    assert temp_db.get_document(boss)['content'] == "Renamed by hand."


def test_overwrite_replaces_the_text_and_keeps_the_entry(temp_db, campaign, tmp_path):
    faction, boss = _existing(temp_db, campaign)
    svc = HtmlModuleImportService(temp_db)
    plan = svc.build_plan(parse_file(_write(tmp_path)), campaign,
                          ImportOptions(match_choices={'c-boss': MATCH_OVERWRITE}))
    item = next(i for i in plan.items if i.source_id == 'c-boss')
    assert item.action == ACTION_OVERWRITE
    assert svc.apply(plan).errors == []
    doc = temp_db.get_document(boss)
    meta = _meta(doc)
    assert "Module text of the boss." in doc['content'] and doc['title'] == "Big Boss"
    assert meta['faction_id'] == faction and meta['tags'] == ['Mine', 'Human']
    assert 'module_doc_id' not in meta and 'imported_final_hash' not in meta
    assert len(temp_db.get_documents(campaign, 'npc')) == 3
    assert _meta(_module_doc(temp_db, campaign))[LINKED_ENTRIES_KEY]['c-boss'] == boss


def test_create_new_makes_a_second_entry_and_forgets_the_saved_choice(temp_db, campaign, tmp_path):
    _, boss = _existing(temp_db, campaign)
    path = _write(tmp_path)
    svc = HtmlModuleImportService(temp_db)
    svc.apply(svc.build_plan(parse_file(path), campaign))
    assert 'c-boss' in _meta(_module_doc(temp_db, campaign))[LINKED_ENTRIES_KEY]
    svc.apply(svc.build_plan(parse_file(path), campaign, ImportOptions(match_choices={'c-boss': MATCH_NEW})))
    bosses = [d for d in temp_db.get_documents(campaign, 'npc') if d['title'].casefold() == "big boss"]
    assert len(bosses) == 2
    assert 'c-boss' not in _meta(_module_doc(temp_db, campaign))[LINKED_ENTRIES_KEY]
    plan = svc.build_plan(parse_file(path), campaign)           # now the module's own entry: no question
    item = next(i for i in plan.items if i.source_id == 'c-boss')
    assert item.match_id is None and item.action == ACTION_UNCHANGED


def test_a_different_faction_is_a_note_and_an_empty_one_is_filled(temp_db, campaign, tmp_path):
    other = temp_db.create_document(campaign, 'faction', "Night Court", "x")
    boss = temp_db.create_document(campaign, 'npc', "Big Boss", "Mine.", metadata=json.dumps({'faction_id': other}))
    aide = temp_db.create_document(campaign, 'npc', "Aide", "Mine too.")
    svc = HtmlModuleImportService(temp_db)
    plan = svc.build_plan(parse_file(_write(tmp_path)), campaign)
    items = {i.source_id: i for i in plan.items}
    assert items['c-boss'].notes == ["Faction differs: keeps 'Night Court', the module says 'Iron Guild'"]
    assert items['c-boss'].faction_source_id == '' and items['c-aide'].faction_source_id == 'f-guild'
    assert svc.apply(plan).errors == []
    guild = next(d for d in temp_db.get_documents(campaign, 'faction') if d['title'] == "Iron Guild")
    assert _meta(temp_db.get_document(boss))['faction_id'] == other           # nothing changed
    assert _meta(temp_db.get_document(aide))['faction_id'] == guild['id']     # it had none
    assert temp_db.get_document(aide)['content'] == "Mine too."
    rels = {(r['from_document_id'], r['to_document_id'], r['relationship_type'])
            for r in temp_db.get_document_relationships(campaign)}
    assert (boss, guild['id'], 'member_of') not in rels and (aide, guild['id'], 'member_of') in rels


def test_a_picture_is_added_only_when_the_entry_has_none(temp_db, campaign, tmp_path):
    from services.image_service import ImageService

    path = _write(tmp_path, with_picture=True)
    boss = temp_db.create_document(campaign, 'npc', "Big Boss", "Mine.")
    svc = HtmlModuleImportService(temp_db, ImageService(tmp_path / "store"))
    assert svc.apply(svc.build_plan(parse_file(path), campaign)).images == 1
    assert len(temp_db.get_document_images(boss)) == 1

    db2 = type(temp_db)(":memory:")
    db2.initialize_database()
    campaign2 = db2.create_module("C2", "d")
    boss2 = db2.create_document(campaign2, 'npc', "Big Boss", "Mine.")
    svc2 = HtmlModuleImportService(db2, ImageService(tmp_path / "store2"))
    svc2._attach_image(campaign2, boss2, tmp_path / 'images' / 'portraits' / 'c-boss.png', 'my-own')
    for choice in ({}, {'c-boss': MATCH_OVERWRITE}):
        svc2.apply(svc2.build_plan(parse_file(path), campaign2, ImportOptions(match_choices=choice)))
        assert [i['original_name'] for i in db2.get_document_images(boss2)] == ['my-own.png']


def test_same_title_twice_only_the_first_card_uses_the_entry(temp_db, campaign, tmp_path):
    boss = temp_db.create_document(campaign, 'npc', "Big Boss", "Mine.")
    page = PAGE.replace('<div class="npc-name">Aide</div>', '<div class="npc-name">Big Boss</div>')
    svc = HtmlModuleImportService(temp_db)
    plan = svc.build_plan(parse_file(_write(tmp_path, page)), campaign)
    items = {i.source_id: i for i in plan.items}
    assert items['c-boss'].match_id == boss and items['c-aide'].match_id is None
    assert items['c-aide'].action == ACTION_CREATE
    assert any('c-aide' in w and 'c-boss' in w for w in plan.warnings)


def test_scenes_sessions_gear_and_groups_of_extras_are_never_matched(temp_db, campaign, tmp_path):
    temp_db.create_document(campaign, 'event', "1. Arrival", "x")
    temp_db.create_document(campaign, 'npc', "Thugs", "x")
    temp_db.create_document(campaign, 'session', "Raton Pass — session 1", "x")
    svc = HtmlModuleImportService(temp_db)
    plan = svc.build_plan(parse_file(_write(tmp_path)), campaign)
    matched = {i.source_id for i in plan.items if i.match_id is not None}
    assert matched == set()


def test_data_located_in_sets_the_place_and_warns_about_an_unknown_one(temp_db, campaign, tmp_path):
    path = _write(tmp_path)
    parsed = parse_file(path)
    street = next(e for e in parsed.entities if e.source_id == 'l-street')
    assert street.located_in == 'l-city'
    assert module_from_json(module_to_json(parsed)).entities[-2].located_in == 'l-city'     # JSON contract
    svc = HtmlModuleImportService(temp_db)
    plan = svc.build_plan(parsed, campaign)
    assert any("Lost Alley" in w and 'l-nowhere' in w for w in plan.warnings)
    assert svc.apply(plan).errors == []
    places = {d['title']: d['id'] for d in temp_db.get_documents(campaign, 'location')}
    assert temp_db.get_parent_links(campaign) == {places["Wacker Drive"]: places["Chicago"]}

    plan = svc.build_plan(parse_file(path), campaign)                     # nothing changed: nothing to do
    assert next(i for i in plan.items if i.source_id == 'l-street').action == ACTION_UNCHANGED
    temp_db.set_parent_link(places["Wacker Drive"], None)                 # taken out by hand: the module puts it back
    plan = svc.build_plan(parse_file(path), campaign)
    assert next(i for i in plan.items if i.source_id == 'l-street').reason == 'Located in changed'
    svc.apply(plan)
    assert temp_db.get_parent_links(campaign) == {places["Wacker Drive"]: places["Chicago"]}


def test_an_existing_place_keeps_where_it_is(temp_db, campaign, tmp_path):
    county = temp_db.create_document(campaign, 'location', "Cook County", "x")
    street = temp_db.create_document(campaign, 'location', "Wacker Drive", "Mine.")
    temp_db.set_parent_link(street, county)
    svc = HtmlModuleImportService(temp_db)
    svc.apply(svc.build_plan(parse_file(_write(tmp_path)), campaign))
    assert temp_db.get_parent_links(campaign) == {street: county}


def test_validator_warns_about_quests_located_in_and_same_titles(tmp_path):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'tools' / 'html_module'))
    from validate_module import validate

    page = tmp_path / 'Checks.html'
    page.write_text(
        '<html><body><h1>Checks</h1>'
        '<details class="card" id="q-a"><summary><h4>Quest A</h4></summary><div class="card-body">'
        '<p><b>Goal:</b> find it.</p></div></details>'
        '<details class="card" id="q-b"><summary><h4>Quest B</h4></summary><div class="card-body">'
        '<p><b>Cél:</b> x</p><p><span class="lbl">Állapot</span> nyitott</p></div></details>'
        '<details class="room" id="l-a" data-located-in="c-x"><summary><h4>Same</h4></summary><p>x</p></details>'
        '<div class="card" id="item-a"><h4>same</h4><p>x</p></div>'
        '</body></html>', encoding='utf-8')
    _, warnings, _ = validate(page)
    assert any(w.startswith('q-a: no Status: line') for w in warnings)
    assert not any(w.startswith('q-b:') for w in warnings)
    assert any(w.startswith('l-a: data-located-in points to c-x') for w in warnings)
    assert any(w.startswith('l-a, item-a: the same title on 2 cards') for w in warnings)
