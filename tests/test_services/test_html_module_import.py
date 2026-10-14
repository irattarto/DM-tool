"""Tests for the HTML adventure-module importer."""

import json
from pathlib import Path

import pytest

from services.html_module_import_service import (
    ACTION_CONFLICT, ACTION_CREATE, ACTION_UNCHANGED, ACTION_UPDATE, MATCH_NEW,
    HtmlModuleImportService, ImportOptions)
from services.html_module_parser import parse_file, parse_html

MODULE_HTML = """<!doctype html><html lang="hu"><head><title>x</title><style>.a{}</style></head><body>
<header><p class="eyebrow">NED · Test · Kampánymodul</p><h1>Test Pass</h1><p class="sub">An adventure.</p></header>
<div class="toc"><ol><li><a href="#intro">Bevezető</a></li><li><a href="#cast">Szereplők</a></li></ol></div>
<section id="intro"><div class="section-header"><h2>Bevezető</h2></div>
<p>Welcome to <a class="xref" href="#l-yard">the yard</a>. See <a class="xref" href="#cast">cast</a>.</p></section>
<section id="cast"><div class="section-header"><h2>Szereplők</h2></div>
<div class="card" id="f-guild"><h4>Iron Guild</h4><p><span class="badge b-foe">Rival</span></p>
  <p>They hire <a class="xref" href="#c-boss">Boss</a>.</p></div>
<details class="npc-card" id="c-boss"><summary class="card-summary"><div class="npc-name">Big Boss</div>
  <div class="npc-epithet">The Head</div><div class="npc-meta"><span class="tag">Iron Guild — leader</span></div></summary>
  <div class="card-body"><p>Runs things. Lives at <a class="xref" href="#l-yard">the yard</a>.</p>
  <details class="prompt-toggle"><summary>Kép-prompt</summary><div class="imgprompt">a big boss</div></details></div></details>
<details class="npc-card" id="c-loner"><summary class="card-summary"><div class="npc-name">Lone Wolf</div></summary>
  <div class="card-body"><p>Answers to nobody.</p></div></details>
<table><thead><tr><th>Név</th><th>Szerep</th><th>Kép-prompt</th></tr></thead>
<tr id="g-clerk"><td>Dusty Clerk</td><td>Keeps books</td><td style="font-family:'Courier New'">a clerk</td></tr></table>
<details class="room" id="l-yard"><summary class="card-summary"><span class="room-tag rt-village">Town</span><h4>The Yard</h4></summary>
  <div class="card-body"><p>A dusty yard.</p><div class="loot"><span class="lbl">Found</span> a key</div></div></details>
<details class="card" id="item-key"><summary class="card-summary"><h4>Rusty Key</h4></summary>
  <div class="card-body"><p>Opens the cellar.</p></div></details>
</section>
<section id="plot"><div class="scene" id="j-1"><span class="scene-no">1. jelenet · Yard</span><h4>Arrival</h4>
  <div class="readaloud">Dust everywhere.</div><p>Meet <a class="xref" href="#c-boss">the boss</a> at <a class="xref" href="#l-yard">yard</a>.</p></div>
<div class="scene" id="j-2"><span class="scene-no">2. jelenet · Cellar</span><h4>Below</h4><p>Find <a class="xref" href="#item-key">the key</a>.</p></div></section>
<script>/* x */</script></body></html>"""

SAMPLE_MODULE = Path(__file__).resolve().parent.parent / "fixtures" / "Sample_Module.html"


@pytest.fixture
def campaign(temp_db):
    return temp_db.create_module("Campaign", "desc")


@pytest.fixture
def module_file(tmp_path):
    path = tmp_path / "Test_Pass_NED.html"
    path.write_text(MODULE_HTML, encoding="utf-8")
    return path


def _meta(doc):
    return json.loads(doc['metadata'])


def _by_source(db, campaign, source_id):
    for doc in db.get_documents(campaign):
        if doc['metadata'] and _meta(doc).get('source_id') == source_id:
            return doc
    return None


def test_parse_entities_and_sessions(module_file):
    parsed = parse_file(module_file)
    assert parsed.title == "Test Pass"
    assert parsed.rule_system == "NED"
    kinds = {e.source_id: (e.entity_type, e.subtype) for e in parsed.entities}
    assert kinds == {
        'f-guild': ('faction', ''), 'c-boss': ('npc', ''), 'c-loner': ('npc', ''),
        'g-clerk': ('npc', 'minor'), 'l-yard': ('location', ''), 'item-key': ('item', '')}
    assert [s.title for s in parsed.sessions] == ['1. Arrival', '2. Below']
    boss = next(e for e in parsed.entities if e.source_id == 'c-boss')
    assert boss.title == "Big Boss"
    assert boss.image_prompt == "a big boss"
    assert "a big boss" not in boss.content            # prompt is stored separately
    assert "[the yard](#l-yard)" in boss.content
    clerk = next(e for e in parsed.entities if e.source_id == 'g-clerk')
    assert clerk.title == "Dusty Clerk" and clerk.image_prompt == "a clerk"
    assert "Keeps books" in clerk.content
    assert "## Bevezető" in parsed.content             # section title from the TOC


def test_import_creates_hierarchy_and_links(temp_db, campaign, module_file):
    svc = HtmlModuleImportService(temp_db)
    plan = svc.build_plan(parse_file(module_file), campaign)
    assert all(i.action == ACTION_CREATE for i in plan.items)
    result = svc.apply(plan)
    assert result.errors == []

    docs = temp_db.get_documents(campaign)
    types = sorted(d['entity_type'] for d in docs)
    assert types == ['event', 'event', 'faction', 'item', 'location', 'module', 'npc', 'npc', 'npc', 'session']

    module = next(d for d in docs if d['entity_type'] == 'module')
    assert result.module_doc_id == module['id']
    for doc in docs:
        if doc['entity_type'] != 'module':
            assert _meta(doc)['module_doc_id'] == module['id']

    boss = _by_source(temp_db, campaign, 'c-boss')
    yard = _by_source(temp_db, campaign, 'l-yard')
    guild = _by_source(temp_db, campaign, 'f-guild')
    assert f"rpg://location/{yard['id']}" in boss['content']
    assert "(#" not in boss['content']
    assert _meta(boss)['faction_id'] == guild['id']
    assert 'faction_id' not in _meta(_by_source(temp_db, campaign, 'c-loner'))
    assert f"rpg://module/{module['id']}" in module['content']      # section anchor -> module

    rels = {(r['from_document_id'], r['to_document_id'], r['relationship_type'])
            for r in temp_db.get_document_relationships(campaign)}
    session1 = _by_source(temp_db, campaign, 'j-1')
    assert (boss['id'], module['id'], 'belongs_to_module') in rels
    assert (session1['id'], module['id'], 'belongs_to_module') in rels
    assert (boss['id'], guild['id'], 'member_of') in rels
    assert (boss['id'], session1['id'], 'appears_in_scene') in rels
    assert (yard['id'], session1['id'], 'appears_in_scene') in rels
    assert (boss['id'], yard['id'], 'references') in rels
    assert session1['entity_type'] == 'event' and _meta(session1)['subtype'] == 'scene'   # scenes are events
    first = _by_source(temp_db, campaign, 'session-main')
    assert first['entity_type'] == 'session' and _meta(first)['session_type'] == 'game_session'
    assert '## Scenes' in first['content'] and '1. Arrival' in first['content']        # scene text copied in


def test_import_prompts_option(temp_db, campaign, module_file):
    svc = HtmlModuleImportService(temp_db)
    svc.apply(svc.build_plan(parse_file(module_file), campaign, ImportOptions(import_prompts=False)))
    assert 'Image prompt' not in _by_source(temp_db, campaign, 'c-boss')['content']


def test_reimport_updates_instead_of_duplicating(temp_db, campaign, module_file):
    svc = HtmlModuleImportService(temp_db)
    svc.apply(svc.build_plan(parse_file(module_file), campaign))
    count = len(temp_db.get_documents(campaign))

    again = svc.build_plan(parse_file(module_file), campaign)
    assert {i.action for i in again.items} == {ACTION_UNCHANGED}

    module_file.write_text(MODULE_HTML.replace("Runs things.", "Runs everything."), encoding="utf-8")
    changed = svc.build_plan(parse_file(module_file), campaign)
    actions = {i.source_id: i.action for i in changed.items}
    assert actions['c-boss'] == ACTION_UPDATE
    assert actions['c-loner'] == ACTION_UNCHANGED
    result = svc.apply(changed)
    assert result.errors == [] and result.updated >= 1
    assert len(temp_db.get_documents(campaign)) == count
    assert "Runs everything." in _by_source(temp_db, campaign, 'c-boss')['content']
    assert len(temp_db.get_document_relationships(campaign)) == len(
        {(r['from_document_id'], r['to_document_id'], r['relationship_type'])
         for r in temp_db.get_document_relationships(campaign)})


def test_user_edit_is_a_conflict_until_selected(temp_db, campaign, module_file):
    svc = HtmlModuleImportService(temp_db)
    svc.apply(svc.build_plan(parse_file(module_file), campaign))
    boss = _by_source(temp_db, campaign, 'c-boss')
    temp_db.update_document(boss['id'], boss['title'], boss['content'] + "\n\nMy own notes.", boss['metadata'])

    module_file.write_text(MODULE_HTML.replace("Runs things.", "Runs everything."), encoding="utf-8")
    plan = svc.build_plan(parse_file(module_file), campaign)
    item = next(i for i in plan.items if i.source_id == 'c-boss')
    assert item.action == ACTION_CONFLICT and not item.selected

    svc.apply(plan)
    assert "My own notes." in _by_source(temp_db, campaign, 'c-boss')['content']   # untouched

    item.selected = True
    svc.apply(plan)
    refreshed = _by_source(temp_db, campaign, 'c-boss')
    assert "Runs everything." in refreshed['content'] and "My own notes." not in refreshed['content']


def test_unselected_items_are_not_imported_and_links_degrade(temp_db, campaign, module_file):
    svc = HtmlModuleImportService(temp_db)
    plan = svc.build_plan(parse_file(module_file), campaign)
    for item in plan.items:
        if item.source_id == 'l-yard':
            item.selected = False
    svc.apply(plan)
    assert _by_source(temp_db, campaign, 'l-yard') is None
    boss = _by_source(temp_db, campaign, 'c-boss')
    assert "the yard" in boss['content'] and "l-yard" not in boss['content']


def test_module_without_scenes_gets_placeholder_session(temp_db, campaign, tmp_path):
    html = MODULE_HTML.replace('id="j-', 'id="scene-')
    path = tmp_path / "Plain.html"
    path.write_text(html, encoding="utf-8")
    svc = HtmlModuleImportService(temp_db)
    result = svc.apply(svc.build_plan(parse_file(path), campaign))
    assert result.errors == []
    sessions = temp_db.get_documents(campaign, 'session')
    assert len(sessions) == 1 and sessions[0]['title'] == "Test Pass — session 1"


def test_two_modules_in_one_campaign_stay_separate(temp_db, campaign, module_file, tmp_path):
    other = tmp_path / "Other_Pass.html"
    other.write_text(MODULE_HTML.replace("Test Pass", "Other Pass"), encoding="utf-8")
    svc = HtmlModuleImportService(temp_db)
    svc.apply(svc.build_plan(parse_file(module_file), campaign))
    plan = svc.build_plan(parse_file(other), campaign)
    matched = [i.source_id for i in plan.items if i.match_id is not None]       # same titles: offered as existing
    assert set(matched) == {'f-guild', 'c-boss', 'c-loner', 'g-clerk', 'l-yard', 'item-key'}
    plan = svc.build_plan(parse_file(other), campaign,
                          ImportOptions(match_choices={sid: MATCH_NEW for sid in matched}))
    assert all(i.action == ACTION_CREATE for i in plan.items)
    svc.apply(plan)
    modules = temp_db.get_documents(campaign, 'module')
    assert len(modules) == 2
    assert len(temp_db.get_documents(campaign, 'npc')) == 6


def test_embedded_json_contract_is_preferred(tmp_path):
    data = {
        "format": "dm-module", "formatVersion": 1,
        "module": {"title": "From JSON", "ruleSystem": "NED", "content": "Intro"},
        "sessions": [{"id": "j-1", "title": "1. Start", "content": "Go", "refs": ["c-a"]}],
        "entities": [{"id": "c-a", "type": "npc", "title": "Anna", "content": "Hi", "tags": ["x"]}],
    }
    html = f'<html><body><h1>Ignored</h1><div id="c-z"><h4>Z</h4></div>' \
           f'<script type="application/json" id="dm-module-data">{json.dumps(data)}</script></body></html>'
    parsed = parse_html(html, str(tmp_path / "x.html"))
    assert parsed.parser == 'json' and parsed.title == "From JSON"
    assert [e.title for e in parsed.entities] == ["Anna"]
    assert parsed.sessions[0].refs == ["c-a"]


def test_newer_json_format_is_rejected(tmp_path):
    html = ('<html><body><script type="application/json" id="dm-module-data">'
            '{"format":"dm-module","formatVersion":99}</script></body></html>')
    with pytest.raises(ValueError):
        parse_html(html)


def test_sample_module_counts(temp_db, campaign):
    """Checked-in module with at least one element of every id prefix the importer understands."""
    parsed = parse_file(SAMPLE_MODULE)
    by_type = {}
    for e in parsed.entities:
        by_type[e.source_id.split('-')[0]] = by_type.get(e.source_id.split('-')[0], 0) + 1
    assert by_type == {'c': 2, 'g': 1, 'm': 2, 'f': 2, 'l': 2, 'item': 1, 'gift': 1, 'pw': 1, 'h': 1, 'hook': 1}
    assert len(parsed.sessions) == 3
    assert parsed.warnings == []
    svc = HtmlModuleImportService(temp_db)
    result = svc.apply(svc.build_plan(parsed, campaign))
    assert result.errors == []
    again = svc.build_plan(parsed, campaign)
    assert {i.action for i in again.items} == {ACTION_UNCHANGED}


def test_backup_restore_keeps_module_links_and_reimport_matching(temp_db, campaign, module_file, tmp_path):
    from services.backup_service import BackupService

    class _Images:
        def regenerate_thumbnails_for_module(self, module_id):
            return 0

    svc = HtmlModuleImportService(temp_db)
    svc.apply(svc.build_plan(parse_file(module_file), campaign))

    backup = BackupService(temp_db, _Images())
    backup.base_path = tmp_path
    backup.images_path = tmp_path / "rpg_images" / "modules"
    zip_path = str(tmp_path / "b.zip")
    assert backup.backup_module(campaign, zip_path)[0]
    ok, restored_id, _ = backup.restore_module(zip_path, "new")
    assert ok and restored_id != campaign

    module = temp_db.get_documents(restored_id, 'module')[0]
    boss = _by_source(temp_db, restored_id, 'c-boss')
    yard = _by_source(temp_db, restored_id, 'l-yard')
    guild = _by_source(temp_db, restored_id, 'f-guild')
    meta = _meta(boss)
    assert meta['module_doc_id'] == module['id']                  # not the original campaign's module
    assert meta['faction_id'] == guild['id']
    assert f"rpg://location/{yard['id']}" in boss['content']

    # the restored copy still recognises its documents as unedited imports
    plan = svc.build_plan(parse_file(module_file), restored_id)
    assert {i.action for i in plan.items} == {ACTION_UNCHANGED}


def test_json_export_round_trips_and_is_preferred_as_sidecar(temp_db, campaign, module_file):
    from services.html_module_parser import module_from_json, module_to_json

    parsed = parse_file(module_file)
    again = module_from_json(json.loads(json.dumps(module_to_json(parsed))), str(module_file))
    assert [(e.source_id, e.entity_type, e.title, e.content, e.faction_ref, e.refs) for e in again.entities] == \
           [(e.source_id, e.entity_type, e.title, e.content, e.faction_ref, e.refs) for e in parsed.entities]
    assert [(s.source_id, s.title, s.refs) for s in again.sessions] == \
           [(s.source_id, s.title, s.refs) for s in parsed.sessions]

    # a hand-edited sidecar wins over the HTML
    data = module_to_json(parsed)
    data['entities'][0]['title'] = "Edited in sidecar"
    (module_file.parent / "module-export.json").write_text(json.dumps(data), encoding="utf-8")
    assert parse_file(module_file).entities[0].title == "Edited in sidecar"


def _hook_module(tmp_path):
    html = """<html><head><title>Hooks</title></head><body><h1>Hooks</h1>
<section id="horgok"><div class="hook-box" id="hook-zsoldos"><h4>A zsoldos</h4><p>Anyja eltunt.</p></div></section>
<section id="menet"><div class="scene" id="j-1"><span class="scene-no">1. jelenet</span><p>Indul.</p></div></section>
</body></html>"""
    path = tmp_path / "hooks.html"
    path.write_text(html, encoding="utf-8")
    return path


def test_character_hooks_become_characters_not_events(temp_db, campaign, tmp_path):
    svc = HtmlModuleImportService(temp_db)
    svc.apply(svc.build_plan(parse_file(_hook_module(tmp_path)), campaign))
    hook = _by_source(temp_db, campaign, 'hook-zsoldos')
    assert hook['entity_type'] == 'character' and _meta(hook)['subtype'] == 'hook'


def test_scenes_can_be_copied_into_a_chosen_existing_session(temp_db, campaign, tmp_path):
    svc = HtmlModuleImportService(temp_db)
    session_id = temp_db.create_document(campaign, 'session', 'Session 5', 'Notes so far.')
    parsed = parse_file(_hook_module(tmp_path))
    plan = svc.build_plan(parsed, campaign, ImportOptions(scenes_to_session=session_id))
    assert not any(i.kind == 'session' for i in plan.items)          # no extra first session
    assert svc.apply(plan).errors == []
    content = temp_db.get_document(session_id)['content']
    assert content.startswith('Notes so far.') and '## Scenes' in content and 'Indul.' in content
    svc.apply(svc.build_plan(parsed, campaign, ImportOptions(scenes_to_session=session_id)))
    assert temp_db.get_document(session_id)['content'].count('## Scenes') == 1   # replaced, not duplicated


def test_scenes_only_as_events_when_not_copied(temp_db, campaign, tmp_path):
    svc = HtmlModuleImportService(temp_db)
    plan = svc.build_plan(parse_file(_hook_module(tmp_path)), campaign, ImportOptions(scenes_to_session=None))
    assert [i.kind for i in plan.items if i.subtype == 'scene'] == ['event']
    assert not any(i.kind == 'session' for i in plan.items)


def test_reimport_of_the_new_layout_is_unchanged(temp_db, campaign, tmp_path):
    svc = HtmlModuleImportService(temp_db)
    parsed = parse_file(_hook_module(tmp_path))
    svc.apply(svc.build_plan(parsed, campaign))
    scene = _by_source(temp_db, campaign, 'j-1')
    plan = svc.build_plan(parsed, campaign)
    assert scene['entity_type'] == 'event' and {i.action for i in plan.items} == {ACTION_UNCHANGED}


EXTRAS_HTML = """<html lang="en"><body><header><h1>Extras</h1><p class="warn">Fan work</p></header>
<section id="s"><div class="card" id="f-crew"><h4>The Crew</h4><p>x</p></div>
<details class="npc-card" id="c-ana" data-faction="f-crew"><summary><div class="npc-name">Ana</div></summary>
<div class="card-body"><p>Gear:</p><img class="gen-image gen-item" data-gen-id="c-ana-item" src="images/items/c-ana-item.jpg">
<details class="prompt-toggle"><div class="imgprompt">her tools</div></details>
<audio src="audio/ana.mp3"></audio></div>
<img class="gen-image gen-portrait" data-gen-id="c-ana" src="images/portraits/c-ana.jpg">
<details class="prompt-toggle"><div class="imgprompt">ana portrait</div></details></details>
<div class="hook-box" id="hook-kim" data-character="Kim"><h4>Kim's hook</h4><p>Owes a debt.</p></div>
<table><tr><th>A</th><th>B</th></tr><tr><td>1</td><td>2</td></tr></table>
<div class="svg-wrap"><svg><image href="images/maps/m.jpg"/><a href="#l-x"><text>Spot</text></a></svg></div>
<details class="room" id="l-x"><summary><h4>Spot</h4></summary><div class="card-body"><p>Here.</p></div></details>
</section></body></html>"""


def test_parser_extras():
    parsed = parse_html(EXTRAS_HTML, "Extras.html")
    ana = next(e for e in parsed.entities if e.source_id == 'c-ana')
    assert ana.image == 'images/portraits/c-ana.jpg'          # not the belongings picture
    assert ana.extra_images == ['images/items/c-ana-item.jpg']
    assert ana.image_prompt == 'ana portrait'
    assert ana.faction_ref == 'f-crew'                         # data-faction attribute
    assert 'Audio: audio/ana.mp3' in ana.content
    hook = next(e for e in parsed.entities if e.source_id == 'hook-kim')
    assert '**Character:** Kim' in hook.content
    assert '> Fan work' in parsed.content
    assert '| A | B |' in parsed.content and '| --- | --- |' in parsed.content
    assert 'Map image: images/maps/m.jpg' in parsed.content
    assert '[Spot](#l-x)' in parsed.content


def test_parser_warns_when_nothing_recognised():
    parsed = parse_html("<html><body><h1>Plain</h1><p>text</p></body></html>", "Plain.html")
    assert any('No entities' in w for w in parsed.warnings)
