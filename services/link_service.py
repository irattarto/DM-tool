"""Who mentions whom: the links in the texts (rpg://type/id) and the stored relationships, as one graph.

The graph feeds "Mentioned in", the cast and places of a session, "last seen", "not used for a while", the health
check and the relationship map. It is built from the database on demand and never stored.
"""

import json
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

LINK_RE = re.compile(r'rpg://([a-z0-9_]+)/(\d+)')
EDGE_TYPES = ('references', 'appears_in_session', 'appears_in_scene', 'member_of')
CAST_TYPES_EXCLUDED = ('session', 'module', 'event')   # what a session's cast list leaves out


def session_date_of(doc: dict) -> str:
    """The game date of a session document (ISO text) or ''."""
    try:
        value = json.loads(doc['metadata']).get('session_date') if doc.get('metadata') else ''
    except (TypeError, ValueError, AttributeError):
        value = ''
    return str(value or '')[:10]


@dataclass
class LinkGraph:
    docs: Dict[int, dict] = field(default_factory=dict)          # id -> document (with text)
    out: Dict[int, Set[int]] = field(default_factory=dict)       # doc -> docs it links to
    inn: Dict[int, Set[int]] = field(default_factory=dict)       # doc -> docs that link to it

    def _docs(self, ids) -> List[dict]:
        return [self.docs[i] for i in ids if i in self.docs]

    def mentioned_in(self, doc_id: int) -> List[dict]:
        """Documents whose text or relationships point to this one (module pages leave out)."""
        return sorted((d for d in self._docs(self.inn.get(doc_id, ())) if d['entity_type'] != 'module'),
                      key=lambda d: (d['entity_type'], d['title'].casefold()))

    def mentions(self, doc_id: int) -> List[dict]:
        return sorted((d for d in self._docs(self.out.get(doc_id, ())) if d['entity_type'] != 'module'),
                      key=lambda d: (d['entity_type'], d['title'].casefold()))

    def neighbours(self, doc_id: int) -> List[dict]:
        ids = set(self.out.get(doc_id, ())) | set(self.inn.get(doc_id, ()))
        return sorted((d for d in self._docs(ids) if d['entity_type'] != 'module' and d['id'] != doc_id),
                      key=lambda d: (d['entity_type'], d['title'].casefold()))

    def cast_of(self, session_id: int) -> List[dict]:
        """The people, places, items... of a session: everything it links to or that says it appeared there."""
        return [d for d in self.neighbours(session_id) if d['entity_type'] not in CAST_TYPES_EXCLUDED]

    def sessions_of(self, doc_id: int) -> List[dict]:
        """Sessions that mention this entry, newest game date first."""
        found = [d for d in self.neighbours(doc_id) if d['entity_type'] == 'session']
        return sorted(found, key=lambda d: (session_date_of(d), d['title']), reverse=True)

    def last_seen(self, doc_id: int) -> Optional[Tuple[str, str]]:
        """(date, title) of the latest session that mentions the entry; ('', title) when the session has no date."""
        sessions = self.sessions_of(doc_id)
        return (session_date_of(sessions[0]), sessions[0]['title']) if sessions else None

    def unlinked(self) -> List[dict]:
        """Entries that nothing links to and that link to nothing (modules and sessions excluded)."""
        return [d for d in self.docs.values()
                if d['entity_type'] not in ('module', 'session') and not self.out.get(d['id']) and not self.inn.get(d['id'])]


def build_link_graph(db, campaign_id: int) -> LinkGraph:
    graph = LinkGraph()
    documents = db.get_documents(campaign_id)
    graph.docs = {d['id']: d for d in documents}

    def add(source: int, target: int) -> None:
        if source != target and source in graph.docs and target in graph.docs:
            graph.out.setdefault(source, set()).add(target)
            graph.inn.setdefault(target, set()).add(source)

    for doc in documents:
        for match in LINK_RE.finditer(doc.get('content') or ''):
            add(doc['id'], int(match.group(2)))
    for row in db.get_document_relationships(campaign_id):
        if row['relationship_type'] in EDGE_TYPES:
            add(row['from_document_id'], row['to_document_id'])
    return graph
