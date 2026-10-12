"""Health check of a campaign (what needs attention), merging duplicates, and entries not used for a while."""

import json
import re
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from typing import Dict, List, Optional, Tuple

from config.entity_types import CAP_FACTION_LINK, get_registry
from services.link_service import LinkGraph, build_link_graph, session_date_of
from utils.entity_metadata_extractor import extract_npc_metadata
from utils.natural_sort import fold_text, natural_key

SIMILAR = 0.88          # titles this alike (same type) are listed as possible duplicates
UNUSED_AFTER_SESSIONS = 3


@dataclass
class HealthIssue:
    kind: str                       # 'no_faction', 'no_picture', 'unlinked', 'duplicate'
    label: str
    documents: List[dict] = field(default_factory=list)

    @property
    def title(self) -> str:
        return self.label if self.kind == 'duplicate' else f"{len(self.documents)} {self.label}"


def _meta(doc: dict) -> dict:
    try:
        value = json.loads(doc['metadata']) if doc.get('metadata') else {}
        return value if isinstance(value, dict) else {}
    except (TypeError, ValueError):
        return {}


_COPY_SUFFIX = re.compile(r'\s*\(\d+\)$')


def _numbered_series(a: str, b: str) -> bool:
    """True for names that differ only in a number ("Room 10", "Room 11"). "Name (1)" / "Name (2)" are copies, not a series."""
    if _COPY_SUFFIX.search(a) and _COPY_SUFFIX.search(b):
        return False
    return re.sub(r'\d+', '#', a) == re.sub(r'\d+', '#', b)


def check_campaign(db, campaign_id: int, graph: Optional[LinkGraph] = None) -> List[HealthIssue]:
    """The things worth a look: people without a faction, entries without a picture, entries linked to nothing,
    entries with almost the same name. Empty groups are left out."""
    graph = graph or build_link_graph(db, campaign_id)
    registry = get_registry()
    shown = set(registry.keys_for('context')) - {'module', 'session'}      # not abilities, inventory items...
    documents = [d for d in graph.docs.values() if d['entity_type'] in shown]
    factions = {fold_text(d['title']) for d in graph.docs.values() if d['entity_type'] == 'faction'}

    people = [d for d in documents if registry.has_capability(d['entity_type'], CAP_FACTION_LINK)]
    no_faction = []
    for doc in people:
        if _meta(doc).get('faction_id') is not None:
            continue
        written = extract_npc_metadata(doc.get('content', '')).get('faction')
        if not (written and fold_text(written) in factions):
            no_faction.append(doc)

    images = db.get_primary_images_for_documents([d['id'] for d in documents])
    no_picture = [d for d in documents if d['id'] not in images]
    unlinked = [d for d in graph.unlinked() if d['entity_type'] in shown]

    duplicates: List[Tuple[dict, dict]] = []
    by_type: Dict[str, List[dict]] = {}
    for doc in documents:
        by_type.setdefault(doc['entity_type'], []).append(doc)
    for same_type in by_type.values():
        ordered = sorted(same_type, key=lambda d: natural_key(d['title']))
        for index, first in enumerate(ordered):
            a = fold_text(first['title'])
            for second in ordered[index + 1:index + 40]:
                b = fold_text(second['title'])
                if a != b and _numbered_series(a, b):
                    continue            # "Guard 1" and "Guard 2" are two guards
                if a == b or (abs(len(a) - len(b)) <= 3 and len(a) >= 4 and SequenceMatcher(None, a, b).ratio() >= SIMILAR):
                    duplicates.append((first, second))

    issues = []
    if no_faction:
        issues.append(HealthIssue('no_faction', "without a faction", no_faction))
    if no_picture:
        issues.append(HealthIssue('no_picture', "without a picture", no_picture))
    if unlinked:
        issues.append(HealthIssue('unlinked', "linked to nothing", unlinked))
    for first, second in duplicates:
        issues.append(HealthIssue('duplicate', f"Possible duplicate: {first['title']} ≈ {second['title']}", [first, second]))
    return issues


def not_used_for_a_while(graph: LinkGraph, after_sessions: int = UNUSED_AFTER_SESSIONS, limit: int = 12) -> List[Tuple[dict, str]]:
    """Entries mentioned in an earlier session but in none of the last few: (document, last session title)."""
    sessions = sorted((d for d in graph.docs.values() if d['entity_type'] == 'session'),
                      key=lambda d: (session_date_of(d), d['title']), reverse=True)
    if len(sessions) <= after_sessions:
        return []
    recent = {d['id'] for d in sessions[:after_sessions]}
    found = []
    for doc in graph.docs.values():
        if doc['entity_type'] in ('module', 'session'):
            continue
        seen = graph.sessions_of(doc['id'])
        if seen and not any(s['id'] in recent for s in seen):
            found.append((doc, seen[0]))
    found.sort(key=lambda pair: (session_date_of(pair[1]), pair[0]['title'].casefold()))
    return [(doc, session['title']) for doc, session in found[:limit]]


def merge_documents(db, keep_id: int, drop_id: int) -> bool:
    """Fold one entry into another: its text, links, relationships, pictures and modules move to ``keep_id``,
    then it is deleted. Links in other texts that pointed to it now point to the kept entry."""
    keep, drop = db.get_document(keep_id), db.get_document(drop_id)
    if not keep or not drop or keep_id == drop_id or keep['module_id'] != drop['module_id']:
        return False
    content = keep.get('content') or ''
    if (drop.get('content') or '').strip() and (drop['content'].strip() not in content):
        content = f"{content.rstrip()}\n\n---\n\n**Merged from \"{drop['title']}\":**\n\n{drop['content'].strip()}".strip()
    old, new = f"rpg://{drop['entity_type']}/{drop_id}", f"rpg://{keep['entity_type']}/{keep_id}"
    pattern = re.compile(re.escape(old) + r'(?!\d)')

    with db.connection.transaction() as conn:
        conn.execute("UPDATE documents SET content = ?, modified_date = CURRENT_TIMESTAMP WHERE id = ?", (content, keep_id))
        for row in conn.execute("SELECT id, content, metadata FROM documents WHERE module_id = ?", (keep['module_id'],)).fetchall():
            text, meta_text = row[1] or '', row[2]
            changed_text = pattern.sub(new, text) if old in text else text
            changed_meta = meta_text
            if meta_text and str(drop_id) in meta_text:
                try:
                    meta = json.loads(meta_text)
                    for key in ('faction_id', 'parent_document_id', 'module_doc_id'):
                        if isinstance(meta, dict) and meta.get(key) == drop_id:
                            meta[key] = keep_id
                    changed_meta = json.dumps(meta)
                except (TypeError, ValueError):
                    pass
            if changed_text != text or changed_meta != meta_text:
                conn.execute("UPDATE documents SET content = ?, metadata = ? WHERE id = ?", (changed_text, changed_meta, row[0]))
        conn.execute("UPDATE OR IGNORE document_relationships SET from_document_id = ? WHERE from_document_id = ?", (keep_id, drop_id))
        conn.execute("UPDATE OR IGNORE document_relationships SET to_document_id = ? WHERE to_document_id = ?", (keep_id, drop_id))
        conn.execute("DELETE FROM document_relationships WHERE from_document_id = to_document_id")
        has_primary = conn.execute("SELECT 1 FROM images WHERE document_id = ? AND is_primary = 1", (keep_id,)).fetchone()
        if has_primary:
            conn.execute("UPDATE images SET is_primary = 0 WHERE document_id = ?", (drop_id,))
        conn.execute("UPDATE images SET document_id = ? WHERE document_id = ?", (keep_id, drop_id))
    return bool(db.delete_document(drop_id))
