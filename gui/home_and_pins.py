"""Home page and pinned entries ("Tonight") of the main window.

These methods belong to MainWindow (they use its database, pages and lists); they live here
so the main window file stays readable.
"""

import json
from collections import Counter
from typing import Dict, List

from PyQt6.QtWidgets import QTreeWidgetItem

from config.entity_types import CAP_FACTION_LINK, get_registry
from gui.components.entity_list import ROLE_DOC, ROLE_ROW, name_hue
from utils.entity_metadata_extractor import extract_npc_metadata, format_date

PINS_KEY = "pins_{module_id}"   # app_meta key holding the pinned document ids of one campaign (JSON list)
RECENT_ENTRIES = 6
TILE_PICTURES = 3
MAX_FACTIONS = 8
RECENT_SESSIONS = 3


class HomeAndPinsMixin:
    """Methods of MainWindow for the Home page and the pinned tray."""

    # --- pins ----------------------------------------------------------------------------------------

    def _init_pins(self):
        self._pins: List[int] = []

    def _load_pins(self):
        """Read this campaign's pins (kept in the database next to the campaign)."""
        self._pins = []
        if not self.current_module_id:
            return
        try:
            stored = json.loads(self.db.get_app_meta(PINS_KEY.format(module_id=self.current_module_id), '[]') or '[]')
            self._pins = [int(doc_id) for doc_id in stored if isinstance(doc_id, (int, str)) and str(doc_id).isdigit()]
        except (TypeError, ValueError) as e:
            self.logger.warning(f"Could not read pinned entries: {e}")

    def _save_pins(self):
        if self.current_module_id:
            self.db.set_app_meta(PINS_KEY.format(module_id=self.current_module_id), json.dumps(self._pins))

    def _is_pinned(self, doc_id: int) -> bool:
        return doc_id in self._pins

    def _toggle_pin(self, doc_id: int):
        """Pin an entry for tonight, or unpin it."""
        if doc_id in self._pins:
            self._pins.remove(doc_id)
        else:
            self._pins.append(doc_id)
        self._save_pins()
        self._refresh_pin_marks()

    def _on_pin_item(self, item: QTreeWidgetItem):
        """The star of a list row was clicked."""
        document = item.data(0, ROLE_DOC)
        if document:
            self._toggle_pin(document['id'])

    def _refresh_pin_marks(self):
        """Redraw the stars in every list, the preview buttons and the tray."""
        for entity_type, tree in self.entity_lists.items():
            stack = [tree.topLevelItem(i) for i in range(tree.topLevelItemCount())]
            while stack:
                item = stack.pop()
                document = item.data(0, ROLE_DOC)
                if document:
                    info = dict(item.data(0, ROLE_ROW) or {})
                    info['pinned'] = document['id'] in self._pins
                    item.setData(0, ROLE_ROW, info)
                stack.extend(item.child(i) for i in range(item.childCount()))
            tree.viewport().update()
            self._update_entity_preview(entity_type, tree.currentItem())
        self._refresh_pin_tray()

    def _refresh_pin_tray(self):
        """Show the pinned entries in the tray; pins whose entry is gone are dropped."""
        if not hasattr(self, 'pin_tray'):
            return
        documents = []
        for doc_id in list(self._pins):
            document = self.db.get_document(doc_id)
            if document and document.get('module_id') == self.current_module_id:
                documents.append(document)
        if len(documents) != len(self._pins):
            self._pins = [document['id'] for document in documents]
            self._save_pins()
        images = self.db.get_primary_images_for_documents(self._pins)
        self.pin_tray.set_pins([{'id': d['id'], 'title': d['title'], 'image': images.get(d['id']),
                                 'hue': self._row_hue(d)} for d in documents
                                if d['id'] not in self._pending_deletes])

    def _open_pinned(self, doc_id: int):
        document = self.db.get_document(doc_id)
        if document:
            self._open_palette_entry(document)

    def _row_hue(self, document: dict) -> int:
        """The colour of an entry's placeholder: its faction's, as in the lists."""
        tree = self.entity_lists.get(document.get('entity_type'))
        item = self._find_entity_item(tree, document['id']) if tree is not None else None
        info = item.data(0, ROLE_ROW) if item is not None else None
        return info['hue'] if info else name_hue(document.get('title', ''))

    # --- home page -----------------------------------------------------------------------------------

    def _refresh_home(self):
        """Fill the Home page from the open campaign (counts, recent edits, factions, sessions)."""
        if not hasattr(self, 'home_tab'):
            return
        if not self.current_module_id:
            self.home_tab.show_data({'name': '', 'status': 'Create or open a campaign to begin.'})
            return
        registry = get_registry()
        documents = [d for d in self.db.get_document_summaries(self.current_module_id)
                     if d['id'] not in self._pending_deletes]  # no texts: Home only needs titles and dates
        by_type: Dict[str, List[dict]] = {}
        for document in documents:  # newest first
            by_type.setdefault(document['entity_type'], []).append(document)

        context_labels = {key: registry.label(key) for key in registry.keys_for('context')}
        recent = [d for d in documents if d['entity_type'] in context_labels][:RECENT_ENTRIES]

        # Factions: every faction with the number of people that belong to it. Counted from the database,
        # not from the lists, which a search box or a delete waiting for Undo can thin out.
        faction_titles = {d['id']: d['title'] for d in by_type.get('faction', [])}
        known_factions = {title.casefold() for title in faction_titles.values()}
        member_counts: Counter = Counter()
        people_label = ''
        for entity_type in self.entity_types:
            if not registry.has_capability(entity_type, CAP_FACTION_LINK):
                continue
            people_label = people_label or self.entity_types[entity_type]
            for person in self.db.get_documents(self.current_module_id, entity_type):
                if person['id'] not in self._pending_deletes:
                    name = self._faction_name_of(person, faction_titles, known_factions)
                    if name:
                        member_counts[name.casefold()] += 1
        faction_docs = by_type.get('faction', []) if 'faction' in self.entity_types else []
        faction_rows = []
        for document in sorted(faction_docs, key=lambda d: (-member_counts.get(d['title'].casefold(), 0),
                                                            d['title'].casefold()))[:MAX_FACTIONS]:
            count = member_counts.get(document['title'].casefold(), 0)
            faction_rows.append({'doc': document, 'label': f"{count} {people_label or 'members'}"})

        tiles = []
        needed = {d['id'] for d in recent}
        for entity_type, label in self.entity_types.items():
            entries = by_type.get(entity_type, [])
            needed.update(d['id'] for d in entries[:TILE_PICTURES])
            tiles.append({'key': entity_type, 'label': label, 'count': len(entries), 'docs': entries[:TILE_PICTURES]})
        images = self.db.get_primary_images_for_documents(sorted(needed))

        def entry(document):
            return {'doc': document, 'image': images.get(document['id']), 'hue': self._row_hue(document)}

        # Sessions are documents of type 'session', as on the Sessions page; newest game date first
        played = []
        for document in by_type.get('session', []):
            try:
                played_on = json.loads(document['metadata']).get('session_date') if document.get('metadata') else None
            except (TypeError, ValueError, AttributeError):
                played_on = None
            played.append((str(played_on or ''), document['title']))
        played.sort(reverse=True)
        sessions = [{'title': title, 'date': date[:10]} for date, title in played[:RECENT_SESSIONS]]

        self.home_tab.show_data({
            'name': self._campaign_name,
            'status': self._campaign_status,
            'tiles': [{'key': t['key'], 'label': t['label'], 'count': t['count'],
                       'pictures': [entry(d) for d in t['docs']]} for t in tiles],
            'recent': [dict(entry(d), type_label=context_labels.get(d['entity_type'], ''),
                            when=format_date(d.get('modified_date'))) for d in recent],
            'factions': [dict(row, **entry(row['doc'])) for row in faction_rows],
            'sessions': sessions,
        })

    @staticmethod
    def _faction_name_of(person: dict, faction_titles: Dict[int, str], known_factions: set) -> str:
        """The faction of a person, by the same rules as the lists: the chosen faction, else a valid name in the text."""
        if person.get('metadata'):
            try:
                faction_id = json.loads(person['metadata']).get('faction_id')
            except (TypeError, ValueError, AttributeError):
                faction_id = None
            if faction_id is not None and faction_titles.get(faction_id):
                return faction_titles[faction_id]
        written = extract_npc_metadata(person.get('content', '')).get('faction')
        return written if written and written.casefold() in known_factions else ''
