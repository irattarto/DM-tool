"""
Entity files: NPCs, factions, locations, items, quests, events and sessions in a Markdown (or JSON) file.

A file holds only entries, no module page. Every entry belongs to the campaign it is imported into, and to no module,
one module or several (``belongs_to_module`` relationships). The Markdown format::

    ---
    format: dm-entities
    pack: raton-pass-npcs          # names the file; equal ids in two files never clash
    modules: [Raton Pass]          # optional
    ---
    ## NPC: Big Boss {#c-boss}
    faction: Iron Guild            # properties sit directly under the heading
    tags: Human, Strong
    image: images/c-boss.jpg
    modules: [Raton Pass, Docks]   # optional, for this entry only

    The text. Links: [the yard](#l-yard) or [[The Yard]].

An entry is recognised on a re-import by ``pack`` + id; an entry without an id is matched by type and title.
"""

import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

from config.entity_types import get_registry
from utils.logger import get_logger

FORMAT_NAME = 'dm-entities'
ACTION_CREATE, ACTION_UPDATE, ACTION_UNCHANGED, ACTION_CONFLICT = 'create', 'update', 'unchanged', 'conflict'

ATTACH_FILE, ATTACH_CHOSEN, ATTACH_NEW, ATTACH_NONE = 'file', 'chosen', 'new', 'none'

_HEADING_RE = re.compile(r'^##\s+([^:{}\n]+?)\s*:\s*(.+?)\s*(?:\{#([\w.\-]+)\})?\s*$')
_PROP_RE = re.compile(r'^([A-Za-z][\w \-]{0,30}?)\s*:\s*(.*)$')
_LINK_RE = re.compile(r'\[([^\]]*)\]\(#([\w.\-]+)\)')
_WIKI_RE = re.compile(r'\[\[([^\]|\n]+)(?:\|([^\]\n]+))?\]\]')
_IMAGE_EXTS = ('.jpg', '.jpeg', '.png', '.webp')
_SESSION_STATUS = ('planned', 'active', 'played')
_LIST_PROPS = ('tags', 'modules', 'participants')
_SPECIAL_PROPS = ('faction', 'tags', 'image', 'modules', 'date', 'status', 'participants', 'id', 'subtype')
_TEXT_EXTS = ('.md', '.markdown', '.txt')
# The subtypes the HTML module import stores (metadata 'subtype'): minor NPC, monster, gift, spell, ...
SUBTYPES = ('minor', 'monster', 'gift', 'spell', 'handout', 'goal', 'hook', 'scene')
# faction values that name no faction; 'unknown' and 'undecided' are kept as the tag "faction: ..."
FACTION_STATES = ('none', 'unknown', 'undecided')
# a front matter comment: a line starting with #, or " # " (a # with whitespace before and after) to the line end
_COMMENT_RE = re.compile(r'^\s*#.*$|\s+#(?:\s.*)?$')


def _hash(text: str) -> str:
    return hashlib.sha1(text.encode('utf-8'), usedforsecurity=False).hexdigest()


def _slug(text: str) -> str:
    return re.sub(r'[^a-z0-9]+', '-', text.casefold()).strip('-') or 'entities'


def type_names() -> Dict[str, str]:
    """Every word that names an entity type in a file ("npc", "NPCs", "World Settings"...) -> its key."""
    registry = get_registry()
    names: Dict[str, str] = {}
    for key in registry.keys_for('context'):
        if key == 'module':
            continue
        for word in (key, registry.label(key), registry.plural(key)):
            names[word.casefold()] = key
    return names


def split_list(value) -> List[str]:
    """"a, b" or "[a, b]" or a real list -> ['a', 'b']. A quoted item keeps its commas: '"Raton Pass, 1. rész"'."""
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    text = str(value or '').strip()
    if text.startswith('[') and text.endswith(']'):
        text = text[1:-1]
    items: List[str] = []
    index = 0
    while index <= len(text):
        while index < len(text) and text[index] in ' \t':
            index += 1
        quote = text[index] if index < len(text) and text[index] in '"\'' else ''
        if quote:
            # the closing quote is the one followed only by spaces up to a comma or the end
            close = re.compile(re.escape(quote) + r'\s*(?:,|$)').search(text, index + 1)
            if close:
                item = text[index + 1:close.start()].strip()
                if item:
                    items.append(item)
                index = close.end()
                continue
        end = text.find(',', index)
        end = len(text) if end == -1 else end
        item = text[index:end].strip().strip('"\'')
        if item:
            items.append(item)
        index = end + 1
    return items


@dataclass
class EntityEntry:
    kind: str
    title: str
    source_id: str = ''
    body: str = ''
    faction: str = ''
    faction_state: str = ''                                 # 'faction: none|unknown|undecided' (then faction is '')
    located_in: str = ''                                    # title of the place this place is inside
    subtype: str = ''                                       # one of SUBTYPES (stored as metadata 'subtype')
    tags: List[str] = field(default_factory=list)
    image: str = ''
    modules: List[str] = field(default_factory=list)
    session_date: str = ''
    status: str = ''
    participants: List[str] = field(default_factory=list)
    extra: Dict[str, str] = field(default_factory=dict)     # other "key: value" lines, kept as text lines


@dataclass
class ParsedEntityFile:
    pack: str
    entries: List[EntityEntry] = field(default_factory=list)
    modules: List[str] = field(default_factory=list)        # modules named at the top of the file
    source_path: str = ''
    format: str = 'markdown'                                # 'markdown', 'json' or 'html'
    suggested_module: str = ''                              # HTML / dm-module files: their own title
    warnings: List[str] = field(default_factory=list)


# --------------------------------------------------------------------------- reading files

def _front_matter(text: str) -> Tuple[Dict[str, str], str]:
    lines = text.lstrip('﻿').split('\n')
    if not lines or lines[0].strip() != '---':
        return {}, text
    for end in range(1, len(lines)):
        if lines[end].strip() == '---':
            props = {}
            for line in lines[1:end]:
                match = _PROP_RE.match(_COMMENT_RE.sub('', line).rstrip())
                if match:
                    props[match.group(1).strip().casefold()] = match.group(2).strip()
            return props, '\n'.join(lines[end + 1:])
    return {}, text


def parse_markdown(text: str, source_name: str = 'entities', source_path: str = '') -> ParsedEntityFile:
    """Read the Markdown format described in the module docstring."""
    props, body = _front_matter(text.replace('\r\n', '\n').replace('\r', '\n'))
    parsed = ParsedEntityFile(pack=_slug(props.get('pack') or source_name), modules=split_list(props.get('modules', '')),
                              source_path=source_path)
    if props.get('format') and props['format'].casefold() != FORMAT_NAME:
        parsed.warnings.append(f"The file says format '{props['format']}', not '{FORMAT_NAME}'; it was read anyway.")
    names = type_names()

    current: Optional[EntityEntry] = None
    lines: List[str] = []
    in_fence = False

    def finish():
        if current is not None:
            _finish_entry(current, lines, parsed)

    for line in body.split('\n'):
        if line.lstrip().startswith('```'):
            in_fence = not in_fence
        match = None if in_fence else _HEADING_RE.match(line)
        if match and match.group(1).strip().casefold() in names:
            finish()
            current = EntityEntry(kind=names[match.group(1).strip().casefold()], title=match.group(2).strip(),
                                  source_id=match.group(3) or '')
            lines = []
        elif current is not None:
            lines.append(line)
    finish()
    if not parsed.entries:
        parsed.warnings.append("No entries found. Each entry starts with a line like '## NPC: Name {#id}'.")
    return parsed


def _finish_entry(entry: EntityEntry, lines: List[str], parsed: ParsedEntityFile) -> None:
    index = 0
    while index < len(lines) and not lines[index].strip():
        index += 1
    while index < len(lines):      # property lines sit directly under the heading
        line = lines[index]
        match = _PROP_RE.match(line) if line.strip() else None
        if not match:
            break
        _apply_property(entry, match.group(1).strip(), match.group(2).strip())
        index += 1
    entry.body = '\n'.join(lines[index:]).strip('\n').rstrip()
    _check_entry(entry, parsed)


def _apply_property(entry: EntityEntry, key: str, value: str) -> None:
    low = key.casefold().replace(' ', '_')
    if low == 'faction':
        state = value.casefold()
        entry.faction, entry.faction_state = ('', state) if state in FACTION_STATES else (value, '')
    elif low == 'subtype':
        entry.subtype = value.casefold()
    elif low == 'located_in':
        entry.located_in = value
    elif low == 'tags':
        entry.tags = split_list(value)
    elif low == 'image':
        entry.image = value
    elif low == 'modules':
        entry.modules = split_list(value)
    elif low == 'date':
        entry.session_date = value
    elif low == 'status':
        entry.status = value.casefold()
    elif low == 'participants':
        entry.participants = split_list(value)
    elif low == 'id':
        entry.source_id = entry.source_id or value
    else:
        entry.extra[key] = value


def _check_entry(entry: EntityEntry, parsed: ParsedEntityFile) -> None:
    if not entry.title:
        parsed.warnings.append("An entry without a title was skipped.")
        return
    if entry.session_date:
        try:
            date.fromisoformat(entry.session_date)
        except ValueError:
            parsed.warnings.append(f"{entry.title}: date '{entry.session_date}' is not YYYY-MM-DD; today was used.")
            entry.session_date = ''
    if entry.status and entry.status not in _SESSION_STATUS:
        parsed.warnings.append(f"{entry.title}: status '{entry.status}' is not planned, active or played.")
        entry.status = ''
    if entry.subtype and entry.subtype not in SUBTYPES:
        parsed.warnings.append(f"{entry.title}: subtype '{entry.subtype}' is not one of {', '.join(SUBTYPES)}; "
                               f"it was left out.")
        entry.subtype = ''
    if entry.faction_state in ('unknown', 'undecided'):         # as the HTML import: a tag, no faction
        tag = f'faction: {entry.faction_state}'
        if tag not in entry.tags:
            entry.tags.append(tag)
    if entry.source_id and any(e.source_id == entry.source_id for e in parsed.entries):
        parsed.warnings.append(f"{entry.title}: the id '{entry.source_id}' is used twice; the second entry was skipped.")
        return
    parsed.entries.append(entry)


def parse_json(data: dict, source_name: str = 'entities', source_path: str = '') -> ParsedEntityFile:
    """Read a JSON entity file: {"format": "dm-entities", "pack": ..., "modules": [...], "entities": [...]}."""
    parsed = ParsedEntityFile(pack=_slug(str(data.get('pack') or source_name)), modules=split_list(data.get('modules', [])),
                              source_path=source_path, format='json')
    names = type_names()
    for raw in data.get('entities', []) or []:
        if not isinstance(raw, dict):
            continue
        kind = names.get(str(raw.get('type', '')).casefold())
        if kind is None:
            parsed.warnings.append(f"Unknown type '{raw.get('type')}' for '{raw.get('title', '?')}': skipped.")
            continue
        entry = EntityEntry(kind=kind, title=str(raw.get('title', '')).strip(), source_id=str(raw.get('id', '') or ''),
                            body=str(raw.get('content', raw.get('body', '')) or '').strip('\n'))
        for key, value in raw.items():
            if key in ('type', 'title', 'id', 'content', 'body'):
                continue
            _apply_property(entry, key, ', '.join(map(str, value)) if isinstance(value, list) else str(value or ''))
        _check_entry(entry, parsed)
    return parsed


def from_module_file(path: Path) -> ParsedEntityFile:
    """An HTML file (cards) or a JSON 'dm-module' file, read with the HTML module parser (its entries only)."""
    from services.html_module_parser import parse_file
    module = parse_file(path)
    by_id = {e.source_id: e for e in module.entities}
    names = {key for key in get_registry().keys_for('context') if key != 'module'}
    parsed = ParsedEntityFile(pack=_slug(module.source_key or Path(path).stem), source_path=str(path), format='html',
                              suggested_module=module.title)
    for entity in module.entities:
        if entity.entity_type not in names:
            continue
        faction = by_id.get(entity.faction_ref).title if entity.faction_ref in by_id else ''
        place = by_id.get(entity.located_in)
        entry = EntityEntry(kind=entity.entity_type, title=entity.title, source_id=entity.source_id,
                            body=entity.content, faction=faction, tags=list(entity.tags), image=entity.image,
                            faction_state='' if faction else entity.faction_state,
                            located_in=place.title if place is not None and place.entity_type == 'location' else '',
                            subtype=entity.subtype if entity.subtype in SUBTYPES else '')
        _check_entry(entry, parsed)
    if not parsed.entries:
        parsed.warnings.append("No entries were found in this file.")
    return parsed


def read_entity_file(path) -> ParsedEntityFile:
    """Read any supported file: Markdown, JSON (dm-entities or dm-module) or HTML cards."""
    path = Path(path)
    suffix = path.suffix.lower()
    if suffix in ('.html', '.htm'):
        return from_module_file(path)
    text = path.read_text(encoding='utf-8-sig', errors='replace')
    if suffix == '.json':
        data = json.loads(text)
        if isinstance(data, dict) and data.get('format') == 'dm-module':
            return from_module_file(path)
        return parse_json(data if isinstance(data, dict) else {}, path.stem, str(path))
    return parse_markdown(text, path.stem, str(path))


# --------------------------------------------------------------------------- planning

@dataclass
class EntryPlan:
    entry: EntityEntry
    action: str
    selected: bool
    content: str                       # what is written (before links are turned into rpg:// links)
    raw_hash: str
    existing_id: Optional[int] = None
    reason: str = ''
    warnings: List[str] = field(default_factory=list)

    @property
    def title(self) -> str:
        return self.entry.title

    @property
    def kind(self) -> str:
        return self.entry.kind


@dataclass
class EntityImportPlan:
    parsed: ParsedEntityFile
    campaign_id: int
    items: List[EntryPlan] = field(default_factory=list)


@dataclass
class AttachOptions:
    mode: str = ATTACH_FILE            # ATTACH_FILE, ATTACH_CHOSEN, ATTACH_NEW, ATTACH_NONE
    module_doc_id: Optional[int] = None
    new_module_title: str = ''
    create_missing_factions: bool = True    # a faction named by an entry that exists nowhere is created


@dataclass
class EntityImportResult:
    created: int = 0
    updated: int = 0
    skipped: int = 0
    links: int = 0
    images: int = 0
    module_links: int = 0
    errors: List[str] = field(default_factory=list)


def render_content(entry: EntityEntry) -> str:
    """The text stored for an entry: its property lines (as the templates write them), then its body."""
    lines = []
    for key, value in entry.extra.items():
        lines.append(f"{key[:1].upper()}{key[1:]}: {value}")
    if entry.faction:
        lines.append(f"Faction: {entry.faction}")
    head = '  \n'.join(lines)       # two spaces end a line inside a paragraph: the lines stay apart when shown
    return f"{head}\n\n{entry.body}".strip('\n') if head and entry.body else (head or entry.body)


def _meta(doc: Optional[dict]) -> dict:
    if not doc or not doc.get('metadata'):
        return {}
    try:
        value = json.loads(doc['metadata'])
        return value if isinstance(value, dict) else {}
    except (TypeError, ValueError):
        return {}


class EntityFileService:
    def __init__(self, db, image_service=None):
        self.db = db
        self.image_service = image_service
        self.logger = get_logger('entity_file_service')

    def build_plan(self, parsed: ParsedEntityFile, campaign_id: int) -> EntityImportPlan:
        plan = EntityImportPlan(parsed=parsed, campaign_id=campaign_id)
        docs = self.db.get_documents(campaign_id)
        by_id: Dict[str, dict] = {}
        by_title: Dict[Tuple[str, str], dict] = {}
        for doc in docs:
            meta = _meta(doc)
            if meta.get('entity_pack') == parsed.pack and meta.get('source_id'):
                by_id[meta['source_id']] = doc
            by_title.setdefault((doc['entity_type'], doc['title'].casefold()), doc)
        for entry in parsed.entries:
            content = render_content(entry)
            item = EntryPlan(entry=entry, action=ACTION_CREATE, selected=True, content=content, raw_hash=_hash(content))
            existing = by_id.get(entry.source_id) if entry.source_id else None
            if existing is not None and existing['entity_type'] != entry.kind:
                existing = None
            if existing is None:       # no id, or an id this pack never imported (e.g. a file exported from this campaign)
                existing = by_title.get((entry.kind, entry.title.casefold()))
                if existing is not None:
                    item.reason = 'Matched by title'
            if existing is not None:
                self._compare(item, existing)
            plan.items.append(item)
        return plan

    @staticmethod
    def _compare(item: EntryPlan, existing: dict) -> None:
        """Decide what a re-import does with an entry that already exists."""
        meta = _meta(existing)
        item.existing_id = existing['id']
        if meta.get('imported_raw_hash') is None:        # made by hand (matched by title): never overwrite unasked
            item.action, item.selected = ACTION_CONFLICT, False
            item.reason = 'An entry with this title exists already - overwrite?'
            return
        edited = (meta.get('imported_final_hash') is not None
                  and _hash(existing.get('content') or '') != meta.get('imported_final_hash'))
        if meta.get('imported_raw_hash') == item.raw_hash and existing['title'] == item.entry.title:
            item.action, item.selected = ACTION_UNCHANGED, False
        elif edited:
            item.action, item.selected, item.reason = ACTION_CONFLICT, False, 'Edited in the DM tool since the last import'
        else:
            item.action = ACTION_UPDATE

    # ---------------------------------------------------------------- applying

    def module_titles_for(self, plan: EntityImportPlan, item: EntryPlan, options: AttachOptions) -> List[str]:
        """Names of the modules an entry is attached to under the chosen option (existing-by-id modules excluded)."""
        if options.mode == ATTACH_NONE:
            return []
        if options.mode == ATTACH_FILE:
            return list(dict.fromkeys(plan.parsed.modules + item.entry.modules))
        if options.mode == ATTACH_NEW:
            return [options.new_module_title.strip()] if options.new_module_title.strip() else []
        return []

    def apply(self, plan: EntityImportPlan, options: Optional[AttachOptions] = None,
              progress: Optional[Callable[[int, int, str], None]] = None) -> EntityImportResult:
        options = options or AttachOptions()
        result = EntityImportResult()
        campaign_id, parsed = plan.campaign_id, plan.parsed
        todo = [i for i in plan.items if i.selected]
        total = len(todo) + 2
        step = 0

        docs = self.db.get_documents(campaign_id)
        titles = {d['title'].casefold(): d for d in docs if d['entity_type'] == 'module'}
        module_ids: Dict[str, int] = {}

        def module_id_for(name: str) -> Optional[int]:
            key = name.casefold()
            if key in module_ids:
                return module_ids[key]
            doc = titles.get(key)
            try:
                doc_id = doc['id'] if doc else self.db.create_document(
                    campaign_id, 'module', name, f"Module: {name}", created_by='user', status='draft')
            except Exception as e:
                result.errors.append(f"Module '{name}': {e}")
                return None
            module_ids[key] = doc_id
            return doc_id

        # pass 1: create or update the documents
        id_map: Dict[str, Tuple[int, str]] = {}            # source id -> (document id, type)
        title_map: Dict[str, Tuple[int, str]] = {}         # title -> (document id, type), for [[wiki links]]
        for doc in docs:
            meta = _meta(doc)
            if meta.get('entity_pack') == parsed.pack and meta.get('source_id'):
                id_map[meta['source_id']] = (doc['id'], doc['entity_type'])
            if doc['entity_type'] != 'module':
                title_map.setdefault(doc['title'].casefold(), (doc['id'], doc['entity_type']))
        written: List[Tuple[EntryPlan, int]] = []
        faction_docs = {d['title'].casefold(): d for d in docs if d['entity_type'] == 'faction'}
        ordered = sorted(todo, key=lambda i: i.kind != 'faction')       # factions first, so people can join them
        for item in ordered:
            step += 1
            if progress:
                progress(step, total, item.title)
            entry = item.entry
            try:
                meta = {'entity_pack': parsed.pack, 'imported_raw_hash': item.raw_hash}
                if entry.source_id:
                    meta['source_id'] = entry.source_id
                if entry.tags:
                    meta['tags'] = entry.tags
                if entry.subtype:
                    meta['subtype'] = entry.subtype
                if entry.kind == 'session':
                    meta.update({'session_date': entry.session_date or date.today().isoformat(),
                                 'status': entry.status or 'planned', 'participants': entry.participants,
                                 'duration_minutes': None, 'session_type': 'game_session'})
                faction_doc = faction_docs.get(entry.faction.casefold()) if entry.faction else None
                if faction_doc is None and entry.faction and options.create_missing_factions and entry.kind != 'faction':
                    new_faction = self.db.create_document(campaign_id, 'faction', entry.faction,
                                                          f"Faction: {entry.faction}", created_by='user', status='draft')
                    faction_doc = faction_docs[entry.faction.casefold()] = self.db.get_document(new_faction)
                    result.created += 1
                if faction_doc is not None:
                    meta['faction_id'] = faction_doc['id']
                if item.existing_id is None:
                    doc_id = self.db.create_document(campaign_id, entry.kind, entry.title, item.content,
                                                     created_by='user', status='draft', metadata=json.dumps(meta))
                    result.created += 1
                else:
                    doc_id = item.existing_id
                    current = self.db.get_document(doc_id)
                    merged = {**_meta(current), **meta}
                    self.db.update_document(doc_id, entry.title, item.content, json.dumps(merged))
                    result.updated += 1
                if entry.source_id:
                    id_map[entry.source_id] = (doc_id, entry.kind)
                title_map[entry.title.casefold()] = (doc_id, entry.kind)
                written.append((item, doc_id))
                if entry.kind == 'faction':
                    faction_docs[entry.title.casefold()] = self.db.get_document(doc_id)
            except Exception as e:
                result.errors.append(f"{entry.title}: {e}")

        # a faction that was created later in the file than its members: link them now
        for item, doc_id in written:
            entry = item.entry
            if entry.faction and entry.faction.casefold() in faction_docs:
                faction = faction_docs[entry.faction.casefold()]
                current = self.db.get_document(doc_id)
                meta = _meta(current)
                if meta.get('faction_id') != faction['id']:
                    meta['faction_id'] = faction['id']
                    self.db.update_document(doc_id, current['title'], current['content'], json.dumps(meta), record_history=False)

        # where places are located: the named place, from this file or the campaign
        places = {d['title'].casefold(): d['id'] for d in docs if d['entity_type'] == 'location'}
        for item, doc_id in written:
            if item.kind == 'location':
                places[item.entry.title.casefold()] = doc_id
        for item, doc_id in written:
            wanted = item.entry.located_in.strip()
            if item.kind != 'location' or not wanted:
                continue
            parent = places.get(wanted.casefold())
            if parent is None:
                result.errors.append(f"{item.title}: the place '{wanted}' was not found, so it is located nowhere.")
            elif not self.db.set_parent_link(doc_id, parent):
                result.errors.append(f"{item.title}: it cannot be located inside '{wanted}'.")

        # pass 2: links in the text, relationships, modules, pictures
        step += 1
        if progress:
            progress(step, total, 'Linking')
        existing_rel = {(r['from_document_id'], r['to_document_id'], r['relationship_type'])
                        for r in self.db.get_document_relationships(campaign_id)}
        base_dir = Path(parsed.source_path).parent if parsed.source_path else None
        chosen_module = options.module_doc_id if options.mode == ATTACH_CHOSEN else None
        for item, doc_id in written:
            entry = item.entry
            try:
                targets: List[Tuple[int, str]] = []
                final = self._rewrite_links(item.content, id_map, title_map, targets)
                current = self.db.get_document(doc_id)
                meta = _meta(current)
                meta['imported_final_hash'] = _hash(final)
                self.db.update_document(doc_id, current['title'], final, json.dumps(meta), record_history=False)
                for target_id, target_kind in targets:
                    if target_id == doc_id:
                        continue
                    if entry.kind == 'session' and target_kind != 'session':
                        edge = (target_id, doc_id, 'appears_in_session')
                    elif target_kind != 'session':
                        edge = (doc_id, target_id, 'references')
                    else:
                        continue
                    if edge not in existing_rel:
                        self.db.create_document_relationship(*edge)
                        existing_rel.add(edge)
                        result.links += 1
                if entry.faction and entry.faction.casefold() in faction_docs:
                    edge = (doc_id, faction_docs[entry.faction.casefold()]['id'], 'member_of')
                    if edge not in existing_rel:
                        self.db.create_document_relationship(*edge)
                        existing_rel.add(edge)
                        result.links += 1
                wanted: List[int] = []
                for name in self.module_titles_for(plan, item, options):
                    module_doc = module_id_for(name)
                    if module_doc is not None:
                        wanted.append(module_doc)
                if chosen_module is not None:
                    wanted.append(chosen_module)
                for module_doc in dict.fromkeys(wanted):
                    result.module_links += self.db.set_module_membership([doc_id], module_doc, True)
                if entry.image and base_dir is not None and self.image_service is not None:
                    path = self._image_path(base_dir, entry.image)
                    if path is not None:
                        from services.html_module_import_service import HtmlModuleImportService
                        helper = HtmlModuleImportService(self.db, self.image_service)
                        if helper._attach_image(campaign_id, doc_id, path, entry.source_id or _slug(entry.title)):
                            result.images += 1
                    else:
                        result.errors.append(f"{entry.title}: picture '{entry.image}' was not found next to the file.")
            except Exception as e:
                result.errors.append(f"{entry.title} (links): {e}")
        result.skipped = len(plan.items) - len(todo)
        if progress:
            progress(total, total, 'Done')
        return result

    @staticmethod
    def _image_path(base_dir: Path, relative: str) -> Optional[Path]:
        try:
            candidate = (base_dir / relative).resolve()
            candidate.relative_to(base_dir.resolve())      # never read outside the file's folder
        except (ValueError, OSError):
            return None
        return candidate if candidate.is_file() and candidate.suffix.lower() in _IMAGE_EXTS else None

    @staticmethod
    def _rewrite_links(content: str, id_map: Dict[str, Tuple[int, str]], title_map: Dict[str, Tuple[int, str]],
                       targets: List[Tuple[int, str]]) -> str:
        def by_id(match: re.Match) -> str:
            text, target = match.group(1), match.group(2)
            if target in id_map:
                doc_id, kind = id_map[target]
                targets.append((doc_id, kind))
                return f"[{text}](rpg://{kind}/{doc_id})"
            return text                               # the target is not in this file: plain text

        def by_name(match: re.Match) -> str:
            name, label = match.group(1).strip(), (match.group(2) or match.group(1)).strip()
            found = title_map.get(name.casefold())
            if found is None:
                return label
            targets.append(found)
            return f"[{label}](rpg://{found[1]}/{found[0]})"

        return _WIKI_RE.sub(by_name, _LINK_RE.sub(by_id, content))
