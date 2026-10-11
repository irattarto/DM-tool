"""Faction choices / automatic factions, gear -> inventory items, extra pictures, audio links."""

import json
from pathlib import Path

import pytest

from services.html_module_import_service import (
    ACTION_UNCHANGED, AUTO_FACTION_MONSTERS, AUTO_FACTION_UNAFFILIATED,
    HtmlModuleImportService, ImportOptions)
from services.html_module_parser import ParsedEntity, module_from_json, module_to_json, parse_file, parse_html

PAGE = """<!doctype html><html lang="{lang}"><body><h1>Gear Pass</h1>
<section id="s">
<div class="card" id="f-crew"><h4>The Crew</h4><p>x</p></div>
<details class="npc-card" id="c-ana" data-faction="f-crew"><summary><div class="npc-name">Ana</div></summary>
<div class="card-body"><p>Scout.</p>
<div class="gear"><span class="lbl">Gear</span><ul class="itemlist">
<li><b>Dart rifle</b> (air), 6 darts <span class="val">Rare</span></li>
<li><b>Field journal</b> with sketches</li>
<li>Loose coins</li></ul>
<img class="gen-image gen-item" data-gen-id="c-ana-item" src="images/items/c-ana-item.png">
<details class="prompt-toggle"><div class="imgprompt">her tools</div></details></div>
<p>Listen: <audio src="audio/theme.mp3"></audio></p></div>
<img class="gen-image gen-portrait" data-gen-id="c-ana" src="images/portraits/c-ana.png">
<details class="prompt-toggle"><div class="imgprompt">ana portrait</div></details></details>
<details class="npc-card" id="c-bob"><summary><div class="npc-name">Bob</div></summary><div class="card-body"><p>Drifter.</p></div></details>
<details class="npc-card" id="c-cy" data-faction="none"><summary><div class="npc-name">Cy</div></summary><div class="card-body"><p>Loner by choice.</p></div></details>
<details class="creature-card" id="m-wolf"><summary><div class="npc-name">Wolf</div></summary><div class="card-body"><p>Howls.</p></div></details>
<table><tr><th>Name</th><th>Role</th></tr><tr id="g-clerk"><td>Clerk</td><td>Books</td></tr></table>
</section></body></html>"""


@pytest.fixture
def campaign(temp_db):
    return temp_db.create_module("Campaign", "desc")


def _write_module(tmp_path, lang="en", with_images=False):
    path = tmp_path / "Gear_Pass.html"
    path.write_text(PAGE.format(lang=lang), encoding="utf-8")
    (tmp_path / "audio").mkdir()
    (tmp_path / "audio" / "theme.mp3").write_bytes(b"ID3")
    if with_images:
        from PyQt6.QtGui import QColor, QImage
        for sub, name in (('items', 'c-ana-item'), ('portraits', 'c-ana')):
            (tmp_path / 'images' / sub).mkdir(parents=True, exist_ok=True)
            img = QImage(8, 8, QImage.Format.Format_RGB32)
            img.fill(QColor("red"))
            img.save(str(tmp_path / 'images' / sub / f'{name}.png'))
    return path


def _doc(db, campaign, source_id):
    for d in db.get_documents(campaign):
        if d['metadata'] and json.loads(d['metadata']).get('source_id') == source_id:
            return d
    return None


def _meta(doc):
    return json.loads(doc['metadata'])


# ---------------------------------------------------------------- parser

def test_parser_reads_gear_and_faction_state(tmp_path):
    parsed = parse_file(_write_module(tmp_path))
    ana = next(e for e in parsed.entities if e.source_id == 'c-ana')
    assert [g.title for g in ana.gear] == ['Dart rifle', 'Field journal', 'Loose coins']
    assert 'Rare' in ana.gear[0].content
    assert ana.extra_images == ['images/items/c-ana-item.png']
    assert ana.extra_image_captions == {'images/items/c-ana-item.png': 'Gear'}
    cy = next(e for e in parsed.entities if e.source_id == 'c-cy')
    assert cy.faction_state == 'none' and cy.faction_ref == '' and cy.faction_line
    wolf = next(e for e in parsed.entities if e.source_id == 'm-wolf')
    assert wolf.gear == []


def test_json_contract_round_trips_gear(tmp_path):
    parsed = parse_file(_write_module(tmp_path))
    again = module_from_json(module_to_json(parsed))
    ana = next(e for e in again.entities if e.source_id == 'c-ana')
    assert len(ana.gear) == 3 and ana.extra_image_captions
    assert next(e for e in again.entities if e.source_id == 'c-cy').faction_state == 'none'


# ---------------------------------------------------------------- factions

def test_plan_prompts_only_unplaced_regular_npcs(temp_db, campaign, tmp_path):
    svc = HtmlModuleImportService(temp_db)
    plan = svc.build_plan(parse_file(_write_module(tmp_path)), campaign)
    assert [(p.source_id, p.stated) for p in plan.faction_prompts] == [   # not Ana (has a faction)
        ('c-bob', ''), ('c-cy', 'none'), ('m-wolf', ''), ('g-clerk', '')]
    assert plan.faction_prompts[0].current == ''
    assert plan.factions == [('f-crew', 'The Crew')]
    assert not any(i.kind == 'faction' and i.subtype == 'auto' for i in plan.items)


def test_user_choice_is_linked_and_survives_reimport(temp_db, campaign, tmp_path):
    svc = HtmlModuleImportService(temp_db)
    parsed = parse_file(_write_module(tmp_path))
    plan = svc.build_plan(parsed, campaign, ImportOptions(faction_choices={'c-bob': 'f-crew', 'c-cy': 'f-crew',
                                                                          'c-ana': '', 'c-bogus': 'f-crew'}))
    result = svc.apply(plan)
    assert result.errors == []
    crew = _doc(temp_db, campaign, 'f-crew')
    assert _meta(_doc(temp_db, campaign, 'c-bob'))['faction_id'] == crew['id']
    assert _meta(_doc(temp_db, campaign, 'c-cy'))['faction_id'] == crew['id']    # the user may override a stated "none"
    assert _meta(_doc(temp_db, campaign, 'c-ana'))['faction_id'] == crew['id']   # module's own data wins
    # second import without any choice: Bob and Cy keep the faction and are no longer asked
    again = svc.build_plan(parsed, campaign)
    assert [p.source_id for p in again.faction_prompts] == ['m-wolf', 'g-clerk']
    assert {i.action for i in again.items} == {ACTION_UNCHANGED}


def test_invalid_choice_is_ignored(temp_db, campaign, tmp_path):
    svc = HtmlModuleImportService(temp_db)
    plan = svc.build_plan(parse_file(_write_module(tmp_path)), campaign,
                          ImportOptions(faction_choices={'c-bob': AUTO_FACTION_UNAFFILIATED}))
    assert plan.faction_prompts[0].current == ''            # auto option is off, so that id is not valid


@pytest.mark.parametrize("lang,monsters,unaffiliated", [("hu", "Szörnyek", "Függetlenek"),
                                                       ("en", "Monsters", "Unaffiliated")])
def test_auto_factions_are_created_once_and_used(temp_db, campaign, tmp_path, lang, monsters, unaffiliated):
    svc = HtmlModuleImportService(temp_db)
    parsed = parse_file(_write_module(tmp_path, lang))
    result = svc.apply(svc.build_plan(parsed, campaign, ImportOptions(auto_factions=True)))
    assert result.errors == []
    mon = _doc(temp_db, campaign, AUTO_FACTION_MONSTERS)
    una = _doc(temp_db, campaign, AUTO_FACTION_UNAFFILIATED)
    assert mon['title'] == monsters and una['title'] == unaffiliated
    assert _meta(mon)['tags'] == ['auto-created']
    assert _meta(_doc(temp_db, campaign, 'm-wolf'))['faction_id'] == mon['id']
    assert _meta(_doc(temp_db, campaign, 'c-bob'))['faction_id'] == una['id']
    assert 'faction_id' not in _meta(_doc(temp_db, campaign, 'c-cy'))         # data-faction="none"
    again = svc.build_plan(parsed, campaign, ImportOptions(auto_factions=True))
    assert {i.action for i in again.items} == {ACTION_UNCHANGED}
    assert len(temp_db.get_documents(campaign, 'faction')) == 3               # crew + two automatic ones


def test_auto_factions_off_by_default(temp_db, campaign, tmp_path):
    svc = HtmlModuleImportService(temp_db)
    svc.apply(svc.build_plan(parse_file(_write_module(tmp_path)), campaign))
    assert len(temp_db.get_documents(campaign, 'faction')) == 1
    assert 'faction_id' not in _meta(_doc(temp_db, campaign, 'c-bob'))


# ---------------------------------------------------------------- gear -> inventory

def test_gear_becomes_inventory_items_and_reimport_keeps_user_edits(temp_db, campaign, tmp_path):
    from services.inventory_service import InventoryService

    svc = HtmlModuleImportService(temp_db)
    parsed = parse_file(_write_module(tmp_path))
    result = svc.apply(svc.build_plan(parsed, campaign))
    assert result.errors == []
    ana = _doc(temp_db, campaign, 'c-ana')
    inventory = InventoryService(temp_db)
    items = inventory.get_inventory_items(campaign, ana['id'])
    assert sorted(i.title for i in items) == ['Dart rifle', 'Field journal', 'Loose coins']
    rifle = next(i for i in items if i.title == 'Dart rifle')
    assert rifle.item_type == 'misc' and rifle.quantity == 1 and not rifle.equipped
    assert 'Rare' in rifle.content
    # the user marks the rifle equipped; a re-import must neither duplicate nor reset it
    inventory.update_inventory_item(rifle.id, rifle.title, rifle.content, 'weapon', 2, True)
    again = svc.build_plan(parsed, campaign)
    assert {i.action for i in again.items} == {ACTION_UNCHANGED}
    svc.apply(again)
    items = inventory.get_inventory_items(campaign, ana['id'])
    assert len(items) == 3
    rifle = next(i for i in items if i.title == 'Dart rifle')
    assert (rifle.item_type, rifle.quantity, rifle.equipped) == ('weapon', 2, True)
    # inventory items are not graph nodes of the module
    assert not any(r['relationship_type'] == 'belongs_to_module' and r['from_document_id'] == rifle.id
                   for r in temp_db.get_document_relationships(campaign))
    assert 'Dart rifle' in ana['content']                 # the NPC text still carries the gear


def test_gear_option_off_and_deselected_owner(temp_db, campaign, tmp_path):
    svc = HtmlModuleImportService(temp_db)
    parsed = parse_file(_write_module(tmp_path))
    svc.apply(svc.build_plan(parsed, campaign, ImportOptions(gear_to_inventory=False)))
    assert temp_db.get_documents(campaign, 'inventory_item') == []

    other = temp_db.create_module("Other", "d")
    plan = svc.build_plan(parsed, other)
    for item in plan.items:
        if item.source_id == 'c-ana':
            item.selected = False
    result = svc.apply(plan)
    assert result.errors == [] and temp_db.get_documents(other, 'inventory_item') == []


def test_restore_as_new_keeps_the_owner_of_inventory_items(temp_db, campaign, tmp_path):
    from services.backup_service import BackupService
    from services.inventory_service import InventoryService

    class _Images:
        def regenerate_thumbnails_for_module(self, module_id):
            return 0

    svc = HtmlModuleImportService(temp_db)
    svc.apply(svc.build_plan(parse_file(_write_module(tmp_path)), campaign))
    backup = BackupService(temp_db, _Images())
    backup.base_path = tmp_path
    backup.images_path = tmp_path / "rpg_images" / "modules"
    zip_path = str(tmp_path / "b.zip")
    assert backup.backup_module(campaign, zip_path)[0]
    ok, restored_id, _ = backup.restore_module(zip_path, "new")
    assert ok
    ana = _doc(temp_db, restored_id, 'c-ana')
    items = InventoryService(temp_db).get_inventory_items(restored_id, ana['id'])
    assert len(items) == 3


# ---------------------------------------------------------------- pictures and audio

def test_gear_picture_is_a_secondary_image_with_caption(temp_db, campaign, tmp_path):
    from services.image_service import ImageService

    path = _write_module(tmp_path, with_images=True)
    svc = HtmlModuleImportService(temp_db, ImageService(tmp_path / "store"))
    plan = svc.build_plan(parse_file(path), campaign)
    ana_item = next(i for i in plan.items if i.source_id == 'c-ana')
    assert ana_item.image_path.name == 'c-ana.png' and [p.name for p, _ in ana_item.extra_images] == ['c-ana-item.png']
    result = svc.apply(plan)
    assert result.errors == [] and result.images == 2
    ana = _doc(temp_db, campaign, 'c-ana')
    images = temp_db.get_document_images(ana['id'])
    assert len(images) == 2
    assert temp_db.get_primary_image(ana['id'])['original_name'] == 'c-ana.png'
    gear = next(i for i in images if i['original_name'] == 'c-ana-item.png')
    assert gear['description'] == 'Gear'
    svc.apply(svc.build_plan(parse_file(path), campaign, ImportOptions()))
    assert len(temp_db.get_document_images(ana['id'])) == 2          # no duplicates on re-import


def test_audio_becomes_a_link_to_the_file_inside_the_module_folder(temp_db, campaign, tmp_path):
    path = _write_module(tmp_path)
    svc = HtmlModuleImportService(temp_db)
    plan = svc.build_plan(parse_file(path), campaign)
    ana = next(i for i in plan.items if i.source_id == 'c-ana')
    uri = (tmp_path / 'audio' / 'theme.mp3').resolve().as_uri()
    assert f'🔊 [Audio: audio/theme.mp3]({uri})' in ana.content

    escape = parse_html('<h1>x</h1>', str(path))
    escape.entities.append(ParsedEntity('c-x', 'npc', 'X', content='🔊 *Audio: ../outside.mp3*'))
    (tmp_path.parent / 'outside.mp3').write_bytes(b'x')
    x = next(i for i in svc.build_plan(escape, campaign).items if i.source_id == 'c-x')
    assert 'file:' not in x.content                       # outside the module folder: stays plain text


def test_local_audio_path_accepts_only_local_audio_files(tmp_path):
    from PyQt6.QtCore import QUrl
    from utils.local_files import local_audio_path

    song = tmp_path / "my song.mp3"
    song.write_bytes(b"x")
    exe = tmp_path / "run.exe"
    exe.write_bytes(b"x")
    assert local_audio_path(QUrl.fromLocalFile(str(song))) == song.resolve()
    assert local_audio_path(QUrl.fromLocalFile(str(exe))) is None
    assert local_audio_path(QUrl.fromLocalFile(str(tmp_path / "missing.mp3"))) is None
    assert local_audio_path(QUrl("file://server/share/x.mp3")) is None
    assert local_audio_path(QUrl("file:////server/share/x.mp3")) is None
    assert local_audio_path(QUrl("https://example.com/x.mp3")) is None


# ---------------------------------------------------------------- factions typed in by the user

def test_user_typed_faction_is_created_only_when_used_and_usable_for_every_npc(temp_db, campaign, tmp_path):
    svc = HtmlModuleImportService(temp_db)
    parsed = parse_file(_write_module(tmp_path))
    new = [('f-new-wanderers', 'Wanderers'), ('f-new-unused', 'Unused'), ('bogus-id', 'Bogus')]
    plan = svc.build_plan(parsed, campaign, ImportOptions(
        new_factions=new, faction_choices={'c-bob': 'f-new-wanderers'}))
    assert ('f-new-wanderers', 'Wanderers') in plan.factions and ('bogus-id', 'Bogus') not in plan.factions
    assert plan.faction_prompts[0].description.startswith('Drifter.')
    created = [i for i in plan.items if i.kind == 'faction' and i.subtype == 'custom']
    assert [i.source_id for i in created] == ['f-new-wanderers']         # unused one is not created
    assert svc.apply(plan).errors == []
    wanderers = _doc(temp_db, campaign, 'f-new-wanderers')
    assert wanderers['title'] == 'Wanderers' and _meta(wanderers)['tags'] == ['user-created']
    assert _meta(_doc(temp_db, campaign, 'c-bob'))['faction_id'] == wanderers['id']
    assert _doc(temp_db, campaign, 'f-new-unused') is None
    # the later import does not ask again and leaves everything unchanged
    again = svc.build_plan(parsed, campaign, ImportOptions())
    assert [p.source_id for p in again.faction_prompts] == ['c-cy', 'm-wolf', 'g-clerk'] and {i.action for i in again.items} == {ACTION_UNCHANGED}


def test_plain_summary_strips_markdown_and_limits_length():
    text = HtmlModuleImportService.plain_summary(
        '*The Head*\n\n**Tags:** Human\n\nRuns things at [the yard](rpg://x/1).\n\n---\n\n**Image prompt:** secret')
    assert text == 'The Head Tags: Human Runs things at the yard.'
    assert len(HtmlModuleImportService.plain_summary('word ' * 500)) <= 701


# ---------------------------------------------------------------- faction line, states, groups

STATES_PAGE = """<html lang="en"><body><h1>States</h1><section id="s">
<div class="card" id="f-crew"><h4>The Crew</h4><p>x</p></div>
<details class="npc-card" id="c-a"><summary><div class="npc-name">A</div></summary><div class="card-body">
<div class="npc-faction">Faction: <a class="xref" href="#f-crew">The Crew</a></div><p>Member.</p></div></details>
<details class="npc-card" id="c-b"><summary><div class="npc-name">B</div></summary><div class="card-body">
<div class="npc-faction" data-faction="unknown">Faction: unknown</div><p>Mystery.</p></div></details>
<details class="npc-card" id="c-c"><summary><div class="npc-name">C</div>
<div class="npc-faction" data-faction="undecided">Faction: not decided yet</div></summary><div class="card-body"><p>Open.</p></div></details>
<details class="npc-card" id="c-d" data-faction="none"><summary><div class="npc-name">D</div></summary><div class="card-body"><p>Free.</p></div></details>
<details class="npc-card" id="g-guards" data-count="4" data-faction="f-crew"><summary><div class="npc-name">Crew guards</div></summary><div class="card-body"><p>Generic.</p></div></details>
<details class="npc-card" id="c-e"><summary><div class="npc-name">E and her escorts</div></summary><div class="card-body"><p>No faction line.</p></div></details>
</section></body></html>"""


def test_faction_line_states_and_groups(temp_db, campaign, tmp_path):
    path = tmp_path / "States.html"
    path.write_text(STATES_PAGE, encoding="utf-8")
    parsed = parse_file(path)
    by_id = {e.source_id: e for e in parsed.entities}
    assert (by_id['c-a'].faction_ref, by_id['c-a'].faction_state, by_id['c-a'].faction_line) == ('f-crew', '', True)
    assert (by_id['c-b'].faction_ref, by_id['c-b'].faction_state) == ('', 'unknown')
    assert by_id['c-c'].faction_state == 'undecided'                # the line may sit in the summary
    assert 'Faction: not decided yet' in by_id['c-c'].content        # and is still shown once in the notes
    assert by_id['c-c'].content.count('not decided yet') == 1
    assert by_id['c-d'].faction_state == 'none'
    assert (by_id['g-guards'].count, by_id['g-guards'].tags, by_id['g-guards'].faction_ref) == (4, ['×4'], 'f-crew')
    assert by_id['c-e'].faction_line is False

    svc = HtmlModuleImportService(temp_db)
    plan = svc.build_plan(parsed, campaign)
    prompts = {p.source_id: p for p in plan.faction_prompts}
    assert set(prompts) == {'c-b', 'c-c', 'c-d', 'c-e'}                # explicit factions are not asked
    assert (prompts['c-b'].current, prompts['c-b'].stated) == ('__unknown__', 'unknown')
    assert (prompts['c-c'].current, prompts['c-d'].current, prompts['c-e'].current) == ('__undecided__', '', '')
    assert svc.apply(plan).errors == []
    crew = _doc(temp_db, campaign, 'f-crew')
    assert _meta(_doc(temp_db, campaign, 'c-a'))['faction_id'] == crew['id']
    assert _meta(_doc(temp_db, campaign, 'g-guards'))['faction_id'] == crew['id']
    for sid, tag in (('c-b', 'faction: unknown'), ('c-c', 'faction: undecided')):
        meta = _meta(_doc(temp_db, campaign, sid))
        assert 'faction_id' not in meta and tag in meta['tags']
    assert 'tags' not in _meta(_doc(temp_db, campaign, 'c-d')) or 'faction: none' not in _meta(_doc(temp_db, campaign, 'c-d'))['tags']
    assert _meta(_doc(temp_db, campaign, 'g-guards'))['tags'] == ['×4']

    # the user turns an "unknown" into a real faction, and an unmentioned NPC into "undecided"
    plan = svc.build_plan(parsed, campaign, ImportOptions(
        faction_choices={'c-b': 'f-crew', 'c-e': '__undecided__', 'c-bogus': '__unknown__'}))
    assert svc.apply(plan).errors == []
    assert _meta(_doc(temp_db, campaign, 'c-b'))['faction_id'] == crew['id']
    assert 'faction: undecided' in _meta(_doc(temp_db, campaign, 'c-e'))['tags']


def test_automatic_factions_do_not_override_what_the_module_states(temp_db, campaign, tmp_path):
    path = tmp_path / "States.html"
    path.write_text(STATES_PAGE, encoding="utf-8")
    svc = HtmlModuleImportService(temp_db)
    plan = svc.build_plan(parse_file(path), campaign, ImportOptions(auto_factions=True))
    current = {p.source_id: p.current for p in plan.faction_prompts}
    assert current == {'c-b': '__unknown__', 'c-c': '__undecided__', 'c-d': '', 'c-e': AUTO_FACTION_UNAFFILIATED}


def test_validator_flags_missing_faction_line_and_bundled_cards(tmp_path):
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'tools' / 'html_module'))
    from validate_module import validate

    path = tmp_path / "States.html"
    path.write_text(STATES_PAGE.replace('data-faction="f-crew"', 'data-faction="f-nowhere"'), encoding="utf-8")
    errors, warnings, _ = validate(path)
    assert any('c-e: no faction line' in w for w in warnings)
    assert any('c-e: looks like several people' in w for w in warnings)
    assert not any('g-guards: looks like' in w for w in warnings)
    assert any('g-guards: data-faction points to unknown faction f-nowhere' in e for e in errors)


def _repaint(path, color):
    from PyQt6.QtGui import QColor, QImage
    img = QImage(8, 8, QImage.Format.Format_RGB32)
    img.fill(QColor(color))
    assert img.save(str(path))


def test_reimport_replaces_a_changed_picture_and_keeps_primary_and_caption(temp_db, campaign, tmp_path):
    from services.image_service import ImageService

    path = _write_module(tmp_path, with_images=True)
    store = ImageService(tmp_path / "store")
    svc = HtmlModuleImportService(temp_db, store)
    svc.apply(svc.build_plan(parse_file(path), campaign))
    ana = _doc(temp_db, campaign, 'c-ana')
    old_primary = temp_db.get_primary_image(ana['id'])
    old_file = old_primary['file_path']

    # nothing changed: nothing happens, and the card is still "unchanged"
    plan = svc.build_plan(parse_file(path), campaign)
    assert not any(i.pictures_changed for i in plan.items)
    assert svc.apply(plan).images == 0

    # the portrait and the gear picture are redrawn; the text stays the same
    _repaint(tmp_path / 'images' / 'portraits' / 'c-ana.png', 'blue')
    _repaint(tmp_path / 'images' / 'items' / 'c-ana-item.png', 'green')
    plan = svc.build_plan(parse_file(path), campaign)
    ana_item = next(i for i in plan.items if i.source_id == 'c-ana')
    assert ana_item.action == 'unchanged' and ana_item.pictures_changed and ana_item.reason == 'Pictures changed'
    result = svc.apply(plan)
    assert result.errors == [] and result.images == 2

    images = temp_db.get_document_images(ana['id'])
    assert len(images) == 2                                             # replaced, not added
    new_primary = temp_db.get_primary_image(ana['id'])
    assert new_primary['original_name'] == 'c-ana.png' and new_primary['id'] != old_primary['id']
    assert Path(new_primary['file_path']).read_bytes() == (tmp_path / 'images' / 'portraits' / 'c-ana.png').read_bytes()
    assert not Path(old_file).exists()                                  # the outdated file is removed
    assert next(i for i in images if i['original_name'] == 'c-ana-item.png')['description'] == 'Gear'

    # and a further re-import is quiet again
    assert not any(i.pictures_changed for i in svc.build_plan(parse_file(path), campaign).items)


def test_reimport_adds_a_picture_that_did_not_exist_at_the_first_import(temp_db, campaign, tmp_path):
    from services.image_service import ImageService

    path = _write_module(tmp_path)                                       # no pictures yet
    svc = HtmlModuleImportService(temp_db, ImageService(tmp_path / "store"))
    svc.apply(svc.build_plan(parse_file(path), campaign))
    ana = _doc(temp_db, campaign, 'c-ana')
    assert temp_db.get_document_images(ana['id']) == []

    for sub, name in (('items', 'c-ana-item'), ('portraits', 'c-ana')):  # the pictures were generated later
        (tmp_path / 'images' / sub).mkdir(parents=True, exist_ok=True)
        _repaint(tmp_path / 'images' / sub / f'{name}.png', 'red')
    plan = svc.build_plan(parse_file(path), campaign)
    assert next(i for i in plan.items if i.source_id == 'c-ana').pictures_changed
    assert svc.apply(plan).images == 2
    assert temp_db.get_primary_image(ana['id'])['original_name'] == 'c-ana.png'
