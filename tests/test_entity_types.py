"""Entity type registry: must reproduce the old hardcoded lists exactly."""
import pytest

from config.entity_types import (
    EntityTypeDef, EntityTypeRegistry, get_registry, RESERVED_KEYS,
    CAP_FACTION_LINK, CAP_RACE_COLUMN, CAP_ABILITIES, CAP_INVENTORY, CAP_SESSION,
)


def test_builtin_orders_match_old_hardcoded_lists():
    r = get_registry()
    assert r.keys_for('tabs') == ['character', 'npc', 'faction', 'location', 'item', 'event', 'quest', 'setting', 'module']
    assert r.keys_for('context') == ['setting', 'module', 'session', 'character', 'npc', 'location', 'faction', 'quest', 'item', 'event']
    assert list(r.keyword_map()) == ['npc', 'faction', 'location', 'quest', 'item']


def test_builtin_labels_match_old_tab_labels():
    r = get_registry()
    assert [r.plural(k) for k in r.keys_for('tabs')] == [
        'Characters', 'NPCs', 'Factions', 'Locations', 'Items', 'Events', 'Quests', 'World Settings', 'Modules']
    assert r.label('setting') == 'Setting' and r.label('npc') == 'NPC'


def test_unknown_key_fallbacks():
    r = get_registry()
    assert r.label('monster_group') == 'Monster Group'
    assert r.plural('monster') == 'Monsters'


def test_capabilities_replace_type_name_checks():
    r = get_registry()
    assert r.with_capability(CAP_FACTION_LINK) == ['npc']
    assert set(r.with_capability(CAP_RACE_COLUMN)) == {'npc', 'faction'}
    assert set(r.with_capability(CAP_ABILITIES)) == {'character', 'npc'}
    assert set(r.with_capability(CAP_INVENTORY)) == {'character', 'npc'}
    assert r.with_capability(CAP_SESSION) == ['session']


def test_custom_type_register_rename_reorder_without_touching_key():
    r = EntityTypeRegistry()
    r.register(EntityTypeDef('monster', 'Monster', 'Monsters'))
    assert 'monster' in r.keys_for('tabs')  # appended after built-ins
    r.rename('monster', 'Beast', 'Beasts')
    assert r.get('monster').key == 'monster' and r.plural('monster') == 'Beasts'
    r.reorder(['monster', 'npc'])
    assert r.keys()[:2] == ['monster', 'npc']


@pytest.mark.parametrize("key", ['Bad Key', 'UPPER', 'a-b', *RESERVED_KEYS, 'npc'])
def test_register_rejects_bad_or_reserved_keys(key):
    with pytest.raises(ValueError):
        EntityTypeRegistry().register(EntityTypeDef(key, 'X', 'Xs'))
