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
from utils.entity_metadata_extractor import format_date

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
        documents = [d for d in self.db.get_documents(self.current_module_id) if d['id'] not in self._pending_deletes]
        by_type: Dict[str, List[dict]] = {}
        for document in documents:  # newest first
            by_type.setdefault(document['entity_type'], []).append(document)

        context_labels = {key: registry.label(key) for key in registry.keys_for('context')}
        recent = [d for d in documents if d['entity_type'] in context_labels][:RECENT_ENTRIES]

        # Factions: every faction with the number of people that belong to it
        faction_rows = []
        people_label = ''
        member_counts: Counter = Counter()
        for entity_type, tree in self.entity_lists.items():
            if not registry.has_capability(entity_type, CAP_FACTION_LINK):
                continue
            people_label = people_label or self.entity_types.get(entity_type, '')
            for i in range(tree.topLevelItemCount()):
                stack = [tree.topLevelItem(i)]
                while stack:
                    item = stack.pop()
                    info = item.data(0, ROLE_ROW) or {}
                    if item.data(0, ROLE_DOC) and info.get('faction'):
                        member_counts[info['faction']] += 1
                    stack.extend(item.child(c) for c in range(item.childCount()))
        faction_docs = by_type.get('faction', []) if 'faction' in self.entity_types else []
        for document in sorted(faction_docs, key=lambda d: (-member_counts.get(d['title'], 0), d['title'].casefold()))[:MAX_FACTIONS]:
            faction_rows.append({'doc': document, 'label': f"{member_counts.get(document['title'], 0)} {people_label or 'members'}"})

        tiles = []
        needed = {d['id'] for d in recent}
        for entity_type, label in self.entity_types.items():
            entries = by_type.get(entity_type, [])
            needed.update(d['id'] for d in entries[:TILE_PICTURES])
            tiles.append({'key': entity_type, 'label': label, 'count': len(entries), 'docs': entries[:TILE_PICTURES]})
        images = self.db.get_primary_images_for_documents(sorted(needed))

        def entry(document):
            return {'doc': document, 'image': images.get(document['id']), 'hue': self._row_hue(document)}

        sessions = [{'title': s['title'], 'date': str(s.get('session_date') or '')[:10]}
                    for s in self.db.get_sessions(self.current_module_id)[:RECENT_SESSIONS]]
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
