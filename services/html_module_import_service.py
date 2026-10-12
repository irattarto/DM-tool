"""
Import a parsed HTML adventure module into a campaign.

Hierarchy created in the selected campaign (a ``modules`` row in the database):

* one ``module`` document - the backbone, holding the introduction and prose;
* ``session`` documents - one per scene of the module;
* ``npc`` / ``faction`` / ``location`` / ``item`` / ``event`` documents.

Everything carries ``metadata.module_doc_id`` and ``metadata.source_id`` (the id in
the HTML, e.g. ``c-maria``). Re-importing matches on those, so existing documents
are updated instead of duplicated. Documents edited in the DM tool since the last
import are reported as conflicts and only overwritten when explicitly selected.

Links live in ``document_relationships``:

====================== =====================================================
``belongs_to_module``  every imported document -> the module document
``appears_in_scene``   entity -> scene (event) that mentions it
``member_of``          npc -> faction
``references``         entity -> entity, from the HTML cross references
====================== =====================================================
"""

import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

from config.paths import resolve_image_path
from services.html_module_parser import ParsedEntity, ParsedModule, ParsedSession
from utils.logger import get_logger

REL_MODULE = 'belongs_to_module'
REL_SESSION = 'appears_in_session'
REL_SCENE = 'appears_in_scene'
REL_FACTION = 'member_of'
REL_REF = 'references'

ACTION_CREATE = 'create'
ACTION_UPDATE = 'update'
ACTION_UNCHANGED = 'unchanged'
ACTION_CONFLICT = 'conflict'
_PICTURE_SAME, _PICTURE_NEW, _PICTURE_CHANGED = 'same', 'new', 'changed'

_IMAGE_EXTS = ('.jpg', '.jpeg', '.png', '.webp')
_LINK_RE = re.compile(r'\[([^\]]*)\]\(#([\w-]+)\)')
_AUDIO_RE = re.compile(r'🔊 \*Audio: ([^*\n]+?)\*')       # written by the parser, see to_markdown

# Fallback factions created on request for NPCs the module does not place in a faction.
AUTO_FACTION_MONSTERS = 'f-auto-monsters'
AUTO_FACTION_UNAFFILIATED = 'f-auto-unaffiliated'
AUTO_FACTION_IDS = (AUTO_FACTION_MONSTERS, AUTO_FACTION_UNAFFILIATED)
NEW_FACTION_PREFIX = 'f-new-'       # factions the user typed in the preview
# Choices of the faction drop-down that link no faction but record what is known; 'none' is simply ''.
FACTION_STATE_IDS = {'__unknown__': 'unknown', '__undecided__': 'undecided'}
_STATE_TO_CHOICE = {'none': '', 'unknown': '__unknown__', 'undecided': '__undecided__'}
_NEW_FACTION_TEXT = 'Created in the module import preview. Rename or delete it freely.'
_TOOLTIP_CHARS = 700
_AUTO_FACTION_TITLES = {
    'hu': {AUTO_FACTION_MONSTERS: 'Szörnyek', AUTO_FACTION_UNAFFILIATED: 'Függetlenek'},
    'en': {AUTO_FACTION_MONSTERS: 'Monsters', AUTO_FACTION_UNAFFILIATED: 'Unaffiliated'},
}
_AUTO_FACTION_TEXT = ('Created automatically by the module import for characters the module does not place '
                      'in a faction. Rename or delete it freely.')


def _hash(text: str) -> str:
    return hashlib.sha1(text.encode('utf-8'), usedforsecurity=False).hexdigest()  # content fingerprint, not a security use


@dataclass
class ImportOptions:
    import_images: bool = True
    import_prompts: bool = True
    # Scenes are always created as events. Where their text is ALSO copied to:
    #   'new'  - the module's own first session (default),  None - nowhere,
    #   int    - the id of an existing session document of the campaign
    scenes_to_session: object = 'new'
    # NPC source id -> faction source id chosen in the preview ('' = no faction). Only used for NPCs
    # the module itself leaves without a faction; an id that is not a faction of this plan is ignored.
    faction_choices: Dict[str, str] = field(default_factory=dict)
    auto_factions: bool = False         # NPCs without a faction -> "Unaffiliated", monsters -> "Monsters"
    # Factions typed in by the user: (source id starting with 'f-new-', title). Selectable for every NPC;
    # a faction document is created only when at least one NPC uses it.
    new_factions: List[Tuple[str, str]] = field(default_factory=list)
    gear_to_inventory: bool = True      # one inventory item per line of an NPC's gear list


SCENES_HEADING = 'Scenes'


def _file_hash(path: Path) -> str:
    with open(path, 'rb') as handle:
        return hashlib.sha256(handle.read()).hexdigest()


@dataclass
class PlanItem:
    kind: str                   # 'module', 'session' or an entity type key
    source_id: str
    title: str
    action: str
    selected: bool
    content: str                # raw markdown (anchors still as #id)
    subtype: str = ""
    existing_id: Optional[int] = None
    reason: str = ""
    faction_source_id: str = ""
    refs: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    image_path: Optional[Path] = None
    raw_hash: str = ""
    extra_images: List[Tuple[Path, str]] = field(default_factory=list)   # (file, caption), never primary
    parent_source_id: str = ""      # inventory items: source id of the NPC that carries them
    pictures_changed: bool = False  # a picture of the card is new or differs from the one stored earlier


@dataclass
class FactionPrompt:
    """An NPC the module leaves without a faction; the preview lets the user pick one."""
    source_id: str
    title: str
    current: str = ""               # faction source id that will be used ('' = none)
    description: str = ""           # plain-text summary of the NPC, to help the user decide
    stated: str = ""                # what the module itself says: 'none', 'unknown', 'undecided' or ''


@dataclass
class ImportPlan:
    module: ParsedModule
    campaign_id: int
    options: ImportOptions
    items: List[PlanItem] = field(default_factory=list)
    unlinked: List[str] = field(default_factory=list)   # NPCs that end up without a faction
    faction_prompts: List[FactionPrompt] = field(default_factory=list)
    factions: List[Tuple[str, str]] = field(default_factory=list)   # (source id, title) a prompt may choose

    def counts(self) -> Dict[str, Dict[str, int]]:
        out: Dict[str, Dict[str, int]] = {}
        for item in self.items:
            out.setdefault(item.kind, {}).setdefault(item.action, 0)
            out[item.kind][item.action] += 1
        return out


@dataclass
class ImportResult:
    created: int = 0
    updated: int = 0
    skipped: int = 0
    links: int = 0
    images: int = 0
    errors: List[str] = field(default_factory=list)
    module_doc_id: Optional[int] = None


class HtmlModuleImportService:
    def __init__(self, db, image_service=None):
        self.db = db
        self.image_service = image_service
        self.logger = get_logger('html_module_import')

    # ------------------------------------------------------------ planning

    def build_plan(self, parsed: ParsedModule, campaign_id: int,
                   options: Optional[ImportOptions] = None) -> ImportPlan:
        options = options or ImportOptions()
        plan = ImportPlan(module=parsed, campaign_id=campaign_id, options=options)
        docs = self.db.get_documents(campaign_id)
        module_doc = self._find_module_doc(docs, parsed.source_key)
        module_id = module_doc['id'] if module_doc else None
        existing = {}
        for doc in docs:
            meta = self._meta(doc)
            if module_id is not None and meta.get('module_doc_id') == module_id and meta.get('source_id'):
                existing[meta['source_id']] = doc

        factions = [e for e in parsed.entities if e.entity_type == 'faction']
        html_dir = Path(parsed.source_path).parent if parsed.source_path else None
        link_audio = (lambda text: self._link_audio(text, html_dir)) if html_dir is not None else (lambda text: text)

        module_content = link_audio(parsed.content)
        plan.items.append(self._plan_item(
            'module', parsed.source_key, parsed.title, module_content, module_doc, '', [], []))

        scenes = [ParsedSession(s.source_id, s.title, s.label, link_audio(s.content), s.refs)
                  for s in parsed.sessions]
        for scene in scenes:                           # a scene is an event, not a session
            plan.items.append(self._plan_item(
                'event', scene.source_id, scene.title, scene.content,
                self._existing_doc(existing, scene.source_id, 'event'), 'scene', list(scene.refs), []))

        if options.scenes_to_session == 'new' or not scenes:
            main = self._main_session(parsed, options, scenes)
            plan.items.append(self._plan_item(
                'session', main.source_id, main.title, main.content,
                self._existing_doc(existing, main.source_id, 'session'), '', list(main.refs), []))

        taken = {f.source_id for f in factions} | set(AUTO_FACTION_IDS)
        new_factions = [(sid, title) for sid, title in options.new_factions
                        if sid.startswith(NEW_FACTION_PREFIX) and sid not in taken and title.strip()]
        plan.factions = [(f.source_id, f.title) for f in factions] + new_factions
        auto_used: List[str] = []              # automatic and user-typed factions that somebody uses
        gear_items: List[PlanItem] = []

        for entity in parsed.entities:
            content = link_audio(entity.content)
            if options.import_prompts and entity.image_prompt:
                content = f'{content}\n\n---\n\n**Image prompt:** {entity.image_prompt}'.strip()
            existing_doc = self._existing_doc(existing, entity.source_id, entity.entity_type)
            item = self._plan_item(
                entity.entity_type, entity.source_id, entity.title, content, existing_doc,
                entity.subtype, list(entity.refs), list(entity.tags))
            if entity.entity_type == 'npc':
                self._assign_faction(plan, item, entity, factions, parsed, existing_doc, auto_used)
                self._mark_faction_change(item, existing_doc, existing)
            if options.import_images and html_dir is not None:
                item.image_path = self._find_image(html_dir, entity)
                item.extra_images = self._find_extra_images(html_dir, entity, item.image_path)
                self._mark_picture_change(item, existing_doc)
            plan.items.append(item)
            if options.gear_to_inventory and entity.entity_type in ('npc', 'character'):
                for number, gear in enumerate(entity.gear, start=1):
                    source_id = f'{entity.source_id}#gear-{number}'
                    gear_item = self._plan_item(
                        'inventory_item', source_id, gear.title, gear.content,
                        self._existing_doc(existing, source_id, 'inventory_item'), '', [], [])
                    gear_item.parent_source_id = entity.source_id
                    gear_items.append(gear_item)

        titles = self.auto_faction_titles(parsed.language)
        for auto_id in AUTO_FACTION_IDS:              # fallback factions exist only when somebody uses them
            if auto_id in auto_used:
                plan.items.append(self._plan_item(
                    'faction', auto_id, titles[auto_id], _AUTO_FACTION_TEXT,
                    self._existing_doc(existing, auto_id, 'faction'), 'auto', [], ['auto-created']))
        for new_id, new_title in new_factions:
            if new_id in auto_used:
                plan.items.append(self._plan_item(
                    'faction', new_id, new_title.strip()[:200], _NEW_FACTION_TEXT,
                    self._existing_doc(existing, new_id, 'faction'), 'custom', [], ['user-created']))
        plan.items.extend(gear_items)
        return plan

    @staticmethod
    def plain_summary(content: str, limit: int = _TOOLTIP_CHARS) -> str:
        """Readable one-paragraph text of an entity's notes (markdown marks removed), for tooltips."""
        text = content.split('\n\n---\n\n**Image prompt:**')[0]
        text = re.sub(r'\[([^\]]*)\]\([^)]*\)', r'\1', text)          # [text](link) -> text
        text = re.sub(r'(?m)^\s*(?:#{1,6}|>)\s*', '', text)           # heading / quote marks at line start
        text = re.sub(r'[*`]+', '', text)                              # emphasis and code marks
        text = re.sub(r'\s+', ' ', text).strip()
        return text if len(text) <= limit else text[:limit].rstrip() + '…'

    @staticmethod
    def auto_faction_titles(language: str) -> Dict[str, str]:
        return _AUTO_FACTION_TITLES['hu' if (language or '').lower().startswith('hu') else 'en']

    def _assign_faction(self, plan: ImportPlan, item: PlanItem, entity: ParsedEntity,
                        factions: List[ParsedEntity], parsed: ParsedModule,
                        existing_doc: Optional[dict], auto_used: List[str]) -> None:
        """Faction of an NPC: the faction the module names, else what an earlier import/the user already
        set, else the user's choice in the preview, else what the module says about it (``none`` /
        ``unknown`` / ``undecided``), else (if asked for) a fallback faction.

        ``unknown`` and ``undecided`` link nothing; they are kept as a tag on the NPC."""
        options = plan.options
        item.faction_source_id = '' if entity.faction_state else self._resolve_faction(entity, factions, parsed)
        if item.faction_source_id:
            return
        if existing_doc is not None and self._meta(existing_doc).get('faction_id') is not None:
            return                                              # keep what is there; never ask again
        real = {f.source_id for f in factions} | {sid for sid, _ in plan.factions}
        if options.auto_factions:
            real |= set(AUTO_FACTION_IDS)
        valid = real | set(FACTION_STATE_IDS)
        if entity.faction_state:
            chosen = _STATE_TO_CHOICE[entity.faction_state]
        elif options.auto_factions:
            chosen = AUTO_FACTION_MONSTERS if entity.subtype == 'monster' else AUTO_FACTION_UNAFFILIATED
        else:
            chosen = ''
        choice = options.faction_choices.get(entity.source_id)
        if choice is not None and (choice == '' or choice in valid):
            chosen = choice
        if chosen in FACTION_STATE_IDS:                         # a note, not a link
            tag = f'faction: {FACTION_STATE_IDS[chosen]}'
            if tag not in item.tags:
                item.tags.append(tag)
            item.faction_source_id = ''
        else:
            item.faction_source_id = chosen
            if chosen and chosen not in {f.source_id for f in factions} and chosen not in auto_used:
                auto_used.append(chosen)
        if real or entity.faction_state:                        # nothing to choose from in a module without factions
            plan.faction_prompts.append(FactionPrompt(entity.source_id, entity.title, chosen,
                                                      self.plain_summary(entity.content), entity.faction_state))
        if not item.faction_source_id:
            plan.unlinked.append(entity.title)

    def _mark_faction_change(self, item: PlanItem, existing_doc: Optional[dict], existing: Dict[str, dict]) -> None:
        """A new faction choice must reach an NPC whose text did not change (it would be skipped as unchanged)."""
        if existing_doc is None or item.action != ACTION_UNCHANGED:
            return
        meta = self._meta(existing_doc)
        wanted = existing.get(item.faction_source_id) if item.faction_source_id else None
        changed = bool(item.faction_source_id) and (wanted is None or meta.get('faction_id') != wanted['id'])
        have = {t for t in meta.get('tags', []) if str(t).startswith('faction: ')}
        want = {t for t in item.tags if str(t).startswith('faction: ')}
        if changed or have != want:
            item.action, item.selected, item.reason = ACTION_UPDATE, True, 'Faction changed'

    def _mark_picture_change(self, item: PlanItem, existing_doc: Optional[dict]) -> None:
        """Flag a re-imported card whose pictures are new or different from the stored ones."""
        if existing_doc is None:
            return
        pictures = ([(item.image_path, item.source_id)] if item.image_path is not None else []) + \
                   [(path, path.stem) for path, _ in item.extra_images]
        item.pictures_changed = any(
            self._picture_state(existing_doc['id'], name, path) != _PICTURE_SAME for path, name in pictures)
        if item.pictures_changed and item.action == ACTION_UNCHANGED:
            item.reason = 'Pictures changed'

    def _stored_pictures(self, doc_id: int, name: str) -> List[dict]:
        """Images of a document that an earlier import made from the picture called ``name`` (any extension)."""
        return [img for img in self.db.get_document_images(doc_id)
                if Path(img.get('original_name') or '').stem == name]

    def _picture_state(self, doc_id: int, name: str, path: Path) -> str:
        stored = self._stored_pictures(doc_id, name)
        if not stored:
            return _PICTURE_NEW
        wanted = _file_hash(path)
        for img in stored:
            stored_path = resolve_image_path(img)
            if stored_path and Path(stored_path).is_file() and _file_hash(Path(stored_path)) == wanted:
                return _PICTURE_SAME
        return _PICTURE_CHANGED

    def _link_audio(self, text: str, html_dir: Path) -> str:
        """Turn the parser's ``🔊 *Audio: path*`` lines into links to the real file (module folder only)."""
        if '🔊' not in text:
            return text

        def repl(match: re.Match) -> str:
            relative = match.group(1).strip()
            target = self._inside(html_dir, html_dir / relative)
            if target is None or not target.is_file():
                return match.group(0)
            return f'🔊 [Audio: {relative}]({target.as_uri()})'
        return _AUDIO_RE.sub(repl, text)

    @staticmethod
    def _inside(root_dir: Path, candidate: Path) -> Optional[Path]:
        """``candidate`` resolved (``..`` and symlinks followed), or None when it leaves ``root_dir``."""
        try:
            resolved = candidate.resolve()
            resolved.relative_to(root_dir.resolve())
            return resolved
        except (ValueError, OSError):
            return None

    @staticmethod
    def _existing_doc(existing: Dict[str, dict], source_id: str, kind: str) -> Optional[dict]:
        """An earlier import counts only if it has the same document type (an old import may have
        stored a scene as a session or a character hook as an event; those stay as they are)."""
        doc = existing.get(source_id)
        return doc if doc is not None and doc.get('entity_type') == kind else None

    @staticmethod
    def scenes_block(scenes: List[ParsedSession]) -> str:
        parts = [f'## {SCENES_HEADING}']
        for scene in scenes:
            parts.append(f'### {scene.title}\n\n{scene.content}'.rstrip())
        return '\n\n'.join(parts)

    def _main_session(self, parsed: ParsedModule, options: ImportOptions,
                      scenes: Optional[List[ParsedSession]] = None) -> ParsedSession:
        """The one session a campaign starts with; later sessions are added by the user."""
        scenes = parsed.sessions if scenes is None else scenes
        intro = f'First session of the module *{parsed.title}*.'
        if scenes:
            content = f'{intro}\n\n{self.scenes_block(scenes)}' if options.scenes_to_session == 'new' else intro
            refs: List[str] = []
        else:
            content = f'{intro} Split it into more sessions as you play.'
            refs = [e.source_id for e in parsed.entities]
        return ParsedSession(source_id='session-main', title=f'{parsed.title} — session 1',
                             content=content, refs=refs)

    def _plan_item(self, kind, source_id, title, content, existing_doc, subtype, refs, tags) -> PlanItem:
        raw_hash = _hash(content)
        item = PlanItem(kind=kind, source_id=source_id, title=title, content=content, subtype=subtype,
                        refs=refs, tags=tags, raw_hash=raw_hash, action=ACTION_CREATE, selected=True)
        if existing_doc is None:
            return item
        meta = self._meta(existing_doc)
        item.existing_id = existing_doc['id']
        edited = (meta.get('imported_final_hash') is not None
                  and _hash(existing_doc.get('content') or '') != meta.get('imported_final_hash'))
        if meta.get('imported_raw_hash') == raw_hash and existing_doc['title'] == title:
            item.action, item.selected = ACTION_UNCHANGED, False
        elif edited:
            item.action, item.selected = ACTION_CONFLICT, False
            item.reason = 'Edited in the DM tool since the last import'
        else:
            item.action = ACTION_UPDATE
        return item

    def _resolve_faction(self, entity: ParsedEntity, factions: List[ParsedEntity], parsed: ParsedModule) -> str:
        if not factions:
            return ''
        ids = {f.source_id for f in factions}
        if entity.faction_ref in ids:
            return entity.faction_ref
        hint = entity.faction_hint.lower()
        if hint:
            for faction in factions:
                names = {faction.title.lower()}
                names.update(part.strip().lower() for part in re.split(r'\s[—–-]\s|\(|\)', faction.title) if len(part.strip()) > 3)
                if any(name and name in hint for name in names):
                    return faction.source_id
        # the faction card itself names the NPC (and the NPC names no other faction)
        for faction in factions:
            if entity.source_id in faction.refs:
                return faction.source_id
        return ''

    def _find_image(self, html_dir: Path, entity: ParsedEntity) -> Optional[Path]:
        candidates = []
        if entity.image:
            candidates.append(html_dir / entity.image)
        images_dir = html_dir / 'images'
        if images_dir.is_dir():
            for sub in ('portraits', 'rooms', 'items', 'creatures'):
                for ext in _IMAGE_EXTS:
                    candidates.append(images_dir / sub / f'{entity.source_id}{ext}')
        for candidate in candidates:
            path = self._inside(html_dir, candidate)    # never read outside the module folder
            if path is not None and path.is_file():
                return path
        return None

    def _find_extra_images(self, html_dir: Path, entity: ParsedEntity,
                           primary: Optional[Path]) -> List[Tuple[Path, str]]:
        """The other pictures of a card (for example the gear picture), as (file, caption)."""
        found: List[Tuple[Path, str]] = []
        seen = {primary} if primary is not None else set()
        for relative in entity.extra_images:
            path = self._inside(html_dir, html_dir / relative)
            if (path is None or not path.is_file() or path in seen
                    or path.suffix.lower() not in _IMAGE_EXTS):
                continue
            seen.add(path)
            found.append((path, entity.extra_image_captions.get(relative, '')))
        return found

    # ------------------------------------------------------------ applying

    def apply(self, plan: ImportPlan,
              progress: Optional[Callable[[int, int, str], None]] = None) -> ImportResult:
        result = ImportResult()
        campaign_id = plan.campaign_id
        docs = self.db.get_documents(campaign_id)
        module_item = next(i for i in plan.items if i.kind == 'module')
        module_doc = self._find_module_doc(docs, plan.module.source_key)

        todo = [i for i in plan.items if i.selected and i.kind != 'module']
        total = len(todo) + 2
        step = 0

        module_meta = {
            'source_key': plan.module.source_key, 'source_file': plan.module.source_path,
            'rule_system': plan.module.rule_system, 'language': plan.module.language,
            'parser': plan.module.parser, 'imported_raw_hash': module_item.raw_hash,
        }
        try:
            if module_doc is None:
                module_id = self.db.create_document(
                    campaign_id, 'module', plan.module.title, module_item.content,
                    created_by='user', status='draft', metadata=json.dumps(module_meta))
                result.created += 1
            else:
                module_id = module_doc['id']
                if module_item.selected:
                    self.db.update_document(module_id, plan.module.title, module_item.content,
                                            json.dumps({**self._meta(module_doc), **module_meta}))
                    result.updated += 1
        except Exception as e:
            result.errors.append(f'Module document: {e}')
            return result
        result.module_doc_id = module_id

        # id map: source id -> (document id, entity type); includes untouched existing documents
        id_map: Dict[str, Tuple[int, str]] = {}
        for doc in self.db.get_documents(campaign_id):
            meta = self._meta(doc)
            if meta.get('module_doc_id') == module_id and meta.get('source_id'):
                id_map[meta['source_id']] = (doc['id'], doc['entity_type'])

        # pass 1: create / update documents with their raw content
        created: List[PlanItem] = []
        for item in todo:
            step += 1
            if progress:
                progress(step, total, item.title)
            meta = {'module_doc_id': module_id, 'source_id': item.source_id,
                    'imported_raw_hash': item.raw_hash}
            if item.subtype:
                meta['subtype'] = item.subtype
            if item.tags:
                meta['tags'] = item.tags
            if item.kind == 'session':
                meta.update({'session_date': date.today().isoformat(), 'participants': [],
                             'duration_minutes': None, 'session_type': 'game_session', 'status': 'planned'})
            if item.kind == 'inventory_item':
                parent = id_map.get(item.parent_source_id)
                if parent is None:                  # the NPC was not imported (deselected); nothing to attach to
                    continue
                meta['parent_document_id'] = parent[0]
                if item.existing_id is None:        # a re-import must not reset what the user changed
                    meta.update({'item_type': 'misc', 'quantity': 1, 'equipped': False})
            try:
                if item.existing_id is None:
                    doc_id = self.db.create_document(
                        campaign_id, item.kind, item.title, item.content,
                        created_by='user', status='active' if item.kind == 'inventory_item' else 'draft',
                        metadata=json.dumps(meta))
                    result.created += 1
                else:
                    doc_id = item.existing_id
                    current = self.db.get_document(doc_id)
                    self.db.update_document(doc_id, item.title, item.content,
                                            json.dumps({**self._meta(current), **meta}))
                    result.updated += 1
                id_map[item.source_id] = (doc_id, item.kind)
                created.append(item)
            except Exception as e:
                result.errors.append(f'{item.title}: {e}')

        # pass 2: faction ids, final links in the text, hashes of what was written
        step += 1
        if progress:
            progress(step, total, 'Linking')
        for item in created:
            doc_id = id_map[item.source_id][0]
            try:
                current = self.db.get_document(doc_id)
                meta = self._meta(current)
                faction = id_map.get(item.faction_source_id)
                if faction:
                    meta['faction_id'] = faction[0]
                final = self._rewrite_links(item.content, id_map, module_id)
                meta['imported_final_hash'] = _hash(final)
                self.db.update_document(doc_id, item.title, final, json.dumps(meta), record_history=False)
            except Exception as e:
                result.errors.append(f'{item.title} (links): {e}')

        if module_item.selected:
            try:
                current = self.db.get_document(module_id)
                final = self._rewrite_links(module_item.content, id_map, module_id)
                meta = {**self._meta(current), 'imported_final_hash': _hash(final)}
                self.db.update_document(module_id, plan.module.title, final, json.dumps(meta), record_history=False)
            except Exception as e:
                result.errors.append(f'Module document (links): {e}')

        result.links = self._create_relationships(plan, created, id_map, module_id, result)
        self._copy_scenes_to_existing_session(plan, id_map, module_id, result)

        if plan.options.import_images:
            # a card whose text did not change still gets its new or changed pictures
            refresh = [i for i in plan.items if i.action == ACTION_UNCHANGED and i.pictures_changed
                       and i.source_id in id_map]
            for item in created + refresh:
                doc_id = id_map[item.source_id][0]
                if item.image_path is not None and self._attach_image(
                        campaign_id, doc_id, item.image_path, item.source_id):
                    result.images += 1
                for path, caption in item.extra_images:      # e.g. the gear picture; never the primary one
                    if self._attach_image(campaign_id, doc_id, path, path.stem,
                                          description=caption or None, primary=False):
                        result.images += 1

        result.skipped = len([i for i in plan.items if not i.selected and i.kind != 'module'])
        if progress:
            progress(total, total, 'Done')
        return result

    def _copy_scenes_to_existing_session(self, plan: ImportPlan, id_map: Dict[str, Tuple[int, str]],
                                         module_id: int, result: ImportResult) -> None:
        """Put the scene texts into the session the user picked (replacing an earlier copy)."""
        target_id = plan.options.scenes_to_session
        if not isinstance(target_id, int) or isinstance(target_id, bool):
            return
        scenes = [i for i in plan.items if i.kind == 'event' and i.subtype == 'scene']
        if not scenes:
            return
        try:
            session = self.db.get_document(target_id)
            if not session or session.get('entity_type') != 'session':
                result.errors.append('The chosen session no longer exists; the scenes were not copied.')
                return
            block = self._rewrite_links(self.scenes_block(
                [ParsedSession(s.source_id, s.title, '', s.content, s.refs) for s in scenes]), id_map, module_id)
            content = session.get('content') or ''
            marker = f'## {SCENES_HEADING}'
            start = content.find(marker)
            if start == -1:
                content = f'{content.rstrip()}\n\n{block}\n' if content.strip() else f'{block}\n'
            else:                                  # replace the earlier copy up to the next top-level section
                nxt = re.search(r'^## ', content[start + len(marker):], re.M)
                end = start + len(marker) + nxt.start() if nxt else len(content)
                content = f'{content[:start]}{block}\n\n{content[end:].lstrip()}'.rstrip() + '\n'
            self.db.update_document(target_id, session['title'], content, session.get('metadata'))
        except Exception as e:
            result.errors.append(f'Copying scenes to the session: {e}')

    def _rewrite_links(self, content: str, id_map: Dict[str, Tuple[int, str]], module_id: int) -> str:
        def repl(match: re.Match) -> str:
            text, target = match.group(1), match.group(2)
            if target in id_map:
                doc_id, kind = id_map[target]
                return f'[{text}](rpg://{kind}/{doc_id})'
            if re.match(r'^(c|g|m|f|l|item|gift|pw|h|hook|j)-', target):
                return text                       # target was not imported
            return f'[{text}](rpg://module/{module_id})'   # a section anchor of the module
        return _LINK_RE.sub(repl, content)

    def _create_relationships(self, plan: ImportPlan, items: List[PlanItem],
                              id_map: Dict[str, Tuple[int, str]], module_id: int,
                              result: ImportResult) -> int:
        existing = {(r['from_document_id'], r['to_document_id'], r['relationship_type'])
                    for r in self.db.get_document_relationships(plan.campaign_id)}
        count = 0

        def link(src: int, dst: int, rel: str) -> None:
            nonlocal count
            key = (src, dst, rel)
            if src == dst or key in existing:
                return
            try:
                self.db.create_document_relationship(src, dst, rel)
                existing.add(key)
                count += 1
            except Exception as e:
                result.errors.append(f'Link {rel}: {e}')

        scenes = {i.source_id: i for i in items if i.kind == 'event' and i.subtype == 'scene'}
        scene_doc_ids = {id_map[sid][0] for sid in scenes if sid in id_map}
        # entity -> scenes mentioning it
        mentioned: Dict[str, List[str]] = {}
        for sid, scene in scenes.items():
            for ref in scene.refs:
                mentioned.setdefault(ref, []).append(sid)

        for item in items:
            if item.kind == 'inventory_item':          # owned by its NPC through metadata, not a graph node
                continue
            doc_id = id_map[item.source_id][0]
            link(doc_id, module_id, REL_MODULE)
            if item.source_id in scenes:
                continue
            for sid in mentioned.get(item.source_id, []):
                if sid in id_map:
                    link(doc_id, id_map[sid][0], REL_SCENE)
            if item.kind == 'session':
                for ref in item.refs:              # a session without scenes lists everything it covers
                    target = id_map.get(ref)
                    if target:
                        link(doc_id, target[0], REL_SESSION)
                continue
            if item.faction_source_id and item.faction_source_id in id_map:
                link(doc_id, id_map[item.faction_source_id][0], REL_FACTION)
            for ref in item.refs:
                target = id_map.get(ref)
                if target and target[1] != 'session' and target[0] not in scene_doc_ids:
                    link(doc_id, target[0], REL_REF)
        return count

    def _attach_image(self, campaign_id: int, doc_id: int, path: Path, source_id: str,
                      description: Optional[str] = None, primary: bool = True) -> bool:
        """Store the picture of a card. A picture that changed since an earlier import replaces the old one
        (keeping its caption and primary flag); an identical one is left alone."""
        if self.image_service is None:
            return False
        original = f'{source_id}{path.suffix.lower()}'
        try:
            state = self._picture_state(doc_id, source_id, path)
            if state == _PICTURE_SAME:
                return False
            old = self._stored_pictures(doc_id, source_id)[0] if state == _PICTURE_CHANGED else None
            saved = self.image_service.save_image(str(path), campaign_id, doc_id, original)
            if not saved:
                return False
            image_id = self.db.save_image_record(
                campaign_id, doc_id, saved['filename'], saved['original_name'], saved['file_path'],
                saved['file_size'], saved['mime_type'], description or (old or {}).get('description'))
            was_primary = bool(old and old.get('is_primary'))
            if old is not None:
                self.db.delete_image_record(old['id'])
                self.image_service.delete_image(old.get('module_id') or campaign_id, old['filename'])
            if was_primary or (primary and not self.db.get_primary_image(doc_id)):
                self.db.set_primary_image(doc_id, image_id)
            return True
        except Exception as e:
            self.logger.warning(f'Image for {source_id} not imported: {e}')
            return False

    # ------------------------------------------------------------ helpers

    @staticmethod
    def _meta(doc: Optional[dict]) -> dict:
        if not doc or not doc.get('metadata'):
            return {}
        try:
            value = json.loads(doc['metadata'])
            return value if isinstance(value, dict) else {}
        except (TypeError, ValueError):
            return {}

    def _find_module_doc(self, docs: List[dict], source_key: str) -> Optional[dict]:
        for doc in docs:
            if doc['entity_type'] == 'module' and self._meta(doc).get('source_key') == source_key:
                return doc
        return None
