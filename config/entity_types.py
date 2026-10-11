"""
Entity type registry.

Single source of truth for the entity types ("npc", "location", ...) that were
previously hardcoded in a dozen places. The built-in registry reproduces the
old behaviour exactly; custom types can be added later without touching call
sites.

Rules:
- ``key`` is an immutable slug. It is stored in ``documents.entity_type``, in
  internal links and in saved sort/column-width settings. Only labels change.
- Reserved types (sessions, abilities, inventory) are stored as documents too,
  but are never offered as user-managed types.
"""

import re
from dataclasses import dataclass, replace
from typing import Dict, List, Optional, Tuple

# Capability flags (behaviour that used to be keyed on type names)
CAP_FACTION_LINK = "faction_link"        # list shows a faction column and a faction picker
CAP_RACE_COLUMN = "race_column"          # list shows a race column extracted from content
CAP_ABILITIES = "abilities"              # document viewer offers an Abilities tab
CAP_INVENTORY = "inventory"              # document viewer offers an Inventory tab
CAP_SESSION = "session"                  # session document with date/participants


@dataclass(frozen=True)
class EntityTypeDef:
    key: str
    label_singular: str
    label_plural: str
    own_tab: bool = False              # has a dedicated widget instead of a generic list tab
    builtin: bool = True
    capabilities: Tuple[str, ...] = ()
    keywords: Tuple[str, ...] = ()     # used by the text parser to guess types
    icon: str = ""
    color: str = ""
    hidden: bool = False

    def has(self, capability: str) -> bool:
        return capability in self.capabilities


# Order here is the order of the main window tabs (session has its own tab).
_BUILTINS: List[EntityTypeDef] = [
    EntityTypeDef(
        'character', 'Character', 'Characters',
        capabilities=(CAP_ABILITIES, CAP_INVENTORY)),
    EntityTypeDef(
        'npc', 'NPC', 'NPCs',
        capabilities=(CAP_FACTION_LINK, CAP_RACE_COLUMN, CAP_ABILITIES, CAP_INVENTORY),
        keywords=('npc', 'character', 'person', 'individual', 'villager', 'merchant',
                  'guard', 'noble', 'beggar', 'priest', 'mage', 'warrior', 'thief')),
    EntityTypeDef(
        'faction', 'Faction', 'Factions',
        capabilities=(CAP_RACE_COLUMN,),
        keywords=('guild', 'order', 'clan', 'organization', 'faction', 'group',
                  'society', 'brotherhood', 'sisterhood', 'cult', 'religion')),
    EntityTypeDef(
        'location', 'Location', 'Locations',
        keywords=('town', 'city', 'village', 'castle', 'tower', 'dungeon', 'forest',
                  'mountain', 'river', 'cave', 'temple', 'inn', 'shop', 'tavern')),
    EntityTypeDef(
        'item', 'Item', 'Items',
        keywords=('sword', 'shield', 'armor', 'potion', 'ring', 'amulet', 'weapon',
                  'artifact', 'treasure', 'gold', 'coin', 'gem')),
    EntityTypeDef('event', 'Event', 'Events'),
    EntityTypeDef(
        'quest', 'Quest', 'Quests',
        keywords=('quest', 'mission', 'task', 'adventure', 'journey', 'objective')),
    EntityTypeDef('setting', 'Setting', 'World Settings'),
    EntityTypeDef(
        'session', 'Session', 'Sessions',
        own_tab=True, capabilities=(CAP_SESSION,)),
    EntityTypeDef('module', 'Module', 'Modules'),
]


# Per-surface orderings of the built-in types. Different parts of the UI have
# always shown the types in slightly different orders; keeping them here makes
# that explicit. Custom types are appended after the built-ins.
SURFACE_ORDERS: Dict[str, List[str]] = {
    # main window tabs (session has its own tab)
    'tabs': ['character', 'npc', 'faction', 'location', 'item', 'event', 'quest', 'setting', 'module'],
    # every type, for link validation
    'context': ['setting', 'module', 'session', 'character', 'npc', 'location', 'faction',
                'quest', 'item', 'event'],
    # text parser: first matching keyword list wins, so order matters
    'parse': ['npc', 'faction', 'location', 'quest', 'item'],
    # create-document / template editor dialogs
    'create': ['character', 'npc', 'faction', 'location', 'quest', 'item', 'event',
               'setting', 'session'],
}

def is_valid_key(key: str) -> bool:
    """Keys are 1-50 ASCII lowercase letters, digits and underscores (immutable slugs)."""
    return isinstance(key, str) and re.fullmatch(r'[a-z0-9_]{1,50}', key) is not None


def builtin_keys() -> List[str]:
    return [d.key for d in _BUILTINS]


# Stored as documents but never user-managed
RESERVED_KEYS = frozenset({'ability_item', 'inventory_item'})


class EntityTypeRegistry:
    """Ordered collection of entity types."""

    # Surfaces where the user's own order and visibility choices apply. The link list
    # and the parser keep their fixed order and always list every type.
    USER_ORDERED_SURFACES = frozenset({'tabs', 'create'})

    def __init__(self, defs: Optional[List[EntityTypeDef]] = None):
        self._defs: Dict[str, EntityTypeDef] = {}
        self._user_order: Optional[List[str]] = None
        for d in (defs if defs is not None else _BUILTINS):
            self._defs[d.key] = d

    # --- lookup -------------------------------------------------------
    def get(self, key: str) -> Optional[EntityTypeDef]:
        return self._defs.get(key)

    def keys(self, include_own_tab: bool = True, include_hidden: bool = False) -> List[str]:
        return [d.key for d in self._defs.values()
                if (include_own_tab or not d.own_tab) and (include_hidden or not d.hidden)]

    def keys_for(self, surface: str) -> List[str]:
        """Type keys for a UI surface, in that surface's order."""
        user_surface = surface in self.USER_ORDERED_SURFACES
        order = SURFACE_ORDERS.get(surface, [])

        def visible(key: str) -> bool:
            d = self._defs.get(key)
            return d is not None and not (user_surface and d.hidden)

        known = [k for k in order if visible(k)]
        extra = [d.key for d in self._defs.values()
                 if d.key not in order and not d.own_tab and visible(d.key)]
        keys = known + extra
        if user_surface and self._user_order:
            rank = {k: i for i, k in enumerate(self._user_order)}
            keys = sorted(keys, key=lambda k: rank.get(k, len(rank) + keys.index(k)))
        return keys

    def editable_types(self) -> List[EntityTypeDef]:
        """All user-manageable types (including hidden) in the user's order, for the editor."""
        keys = [d.key for d in self._defs.values() if not d.own_tab]
        base = [k for k in SURFACE_ORDERS['tabs'] if k in keys]
        base += [k for k in keys if k not in base]
        if self._user_order:
            rank = {k: i for i, k in enumerate(self._user_order)}
            base = sorted(base, key=lambda k: rank.get(k, len(rank) + base.index(k)))
        return [self._defs[k] for k in base]

    # --- persistence --------------------------------------------------
    def load_overrides(self, rows: List[Dict[str, object]]) -> None:
        """Rebuild the registry from the built-ins plus stored customisations."""
        self._defs = {d.key: d for d in _BUILTINS}
        self._user_order = None
        if not rows:
            return
        ordered = sorted(rows, key=lambda r: (r.get('sort_order', 0), r['key']))
        for row in ordered:
            key = row['key']
            if key in RESERVED_KEYS:
                continue
            existing = self._defs.get(key)
            if existing is not None:
                self._defs[key] = replace(
                    existing, label_singular=row['label_singular'], label_plural=row['label_plural'],
                    hidden=bool(row.get('hidden')))
            else:
                self._defs[key] = EntityTypeDef(
                    key, row['label_singular'], row['label_plural'],
                    builtin=False, hidden=bool(row.get('hidden')))
        self._user_order = [r['key'] for r in ordered]

    def to_rows(self) -> List[Dict[str, object]]:
        """Current user-manageable types as rows for DatabaseManager.save_entity_types()."""
        return [{
            'key': d.key, 'label_singular': d.label_singular, 'label_plural': d.label_plural,
            'hidden': d.hidden, 'builtin': d.builtin,
        } for d in self.editable_types()]

    def set_rows(self, rows: List[Dict[str, object]]) -> None:
        """Apply editor rows (already validated/saved) to the in-memory registry."""
        self.load_overrides([dict(r, sort_order=i) for i, r in enumerate(rows)])

    def with_capability(self, capability: str) -> List[str]:
        return [d.key for d in self._defs.values() if d.has(capability)]

    def has_capability(self, key: str, capability: str) -> bool:
        d = self._defs.get(key)
        return bool(d and d.has(capability))

    # --- labels (safe for unknown keys) -------------------------------
    @staticmethod
    def _fallback(key: str) -> str:
        return key.replace('_', ' ').title()

    def label(self, key: str) -> str:
        d = self._defs.get(key)
        return d.label_singular if d else self._fallback(key)

    def plural(self, key: str) -> str:
        d = self._defs.get(key)
        return d.label_plural if d else self._fallback(key) + 's'

    def keyword_map(self) -> Dict[str, List[str]]:
        order = self.keys_for('parse')
        order += [k for k, d in self._defs.items() if d.keywords and k not in order]
        return {k: list(self._defs[k].keywords) for k in order if self._defs[k].keywords}

    # --- mutation (keys are immutable; only presentation changes) -----
    def register(self, definition: EntityTypeDef) -> None:
        if definition.key in RESERVED_KEYS:
            raise ValueError(f"'{definition.key}' is reserved")
        if definition.key in self._defs:
            raise ValueError(f"Entity type '{definition.key}' already exists")
        if not is_valid_key(definition.key):
            raise ValueError("Entity type keys must be lowercase letters, digits or underscores")
        self._defs[definition.key] = replace(definition, builtin=False)

    def rename(self, key: str, label_singular: str, label_plural: Optional[str] = None) -> None:
        d = self._defs[key]
        self._defs[key] = replace(d, label_singular=label_singular,
                                  label_plural=label_plural or label_singular + 's')

    def reorder(self, ordered_keys: List[str]) -> None:
        rest = [k for k in self._defs if k not in ordered_keys]
        self._defs = {k: self._defs[k] for k in list(ordered_keys) + rest if k in self._defs}

_registry = EntityTypeRegistry()

def get_registry() -> EntityTypeRegistry:
    return _registry
