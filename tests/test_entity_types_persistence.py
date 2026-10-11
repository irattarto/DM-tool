"""Entity type customisation: storage, migration, backup, editor and live tab rebuild."""
import sqlite3

import pytest

from config.entity_types import get_registry
from models.database import DatabaseManager


def _rows(*triples):
    return [dict(key=k, label_singular=s, label_plural=p, hidden=h, builtin=b)
            for k, s, p, h, b in triples]


# --- registry ------------------------------------------------------------
def test_load_overrides_rename_reorder_hide_and_custom():
    r = get_registry()
    r.load_overrides([
        dict(key='monster', label_singular='Monster', label_plural='Monsters', sort_order=0, hidden=0),
        dict(key='npc', label_singular='Person', label_plural='People', sort_order=1, hidden=0),
        dict(key='event', label_singular='Event', label_plural='Events', sort_order=2, hidden=1),
    ])
    tabs = r.keys_for('tabs')
    assert tabs[:2] == ['monster', 'npc'] and 'event' not in tabs
    assert r.label('npc') == 'Person' and r.plural('npc') == 'People'
    # hidden types stay in the link list because their documents still exist
    assert 'event' in r.keys_for('context')
    assert [d.key for d in r.editable_types()][:3] == ['monster', 'npc', 'event']
    assert 'module' in tabs                       # builtins missing from stored rows are still offered
    r.load_overrides([])
    assert r.keys_for('tabs')[0] == 'character'


# --- database ------------------------------------------------------------
def test_save_and_load_entity_types_and_default_template_for_custom(temp_db):
    temp_db.save_entity_types(_rows(('monster', 'Monster', 'Monsters', False, False),
                                    ('npc', 'NPC', 'NPCs', False, True)))
    stored = temp_db.get_entity_types()
    assert [t['key'] for t in stored] == ['monster', 'npc']
    assert temp_db.get_default_template('monster') is not None


def test_invalid_keys_and_labels_rejected(temp_db):
    with pytest.raises(ValueError):
        temp_db.save_entity_types(_rows(('Bad Key', 'X', 'Xs', False, False)))
    with pytest.raises(ValueError):
        temp_db.save_entity_types(_rows(('ability_item', 'X', 'Xs', False, False)))
    with pytest.raises(ValueError):
        temp_db.save_entity_types(_rows(('a', 'X', 'Xs', False, False), ('a', 'Y', 'Ys', False, False)))


def test_delete_custom_type_blocked_while_documents_exist(temp_db):
    temp_db.save_entity_types(_rows(('monster', 'Monster', 'Monsters', False, False)))
    mod = temp_db.create_module("M", "d")
    temp_db.create_document(mod, "monster", "Orc", "body")
    assert temp_db.count_documents_of_type('monster') == 1
    assert temp_db.delete_entity_type('monster') is False
    with pytest.raises(ValueError):
        temp_db.save_entity_types([])  # would silently orphan the documents
    temp_db.save_entity_types(_rows(('monster', 'Monster', 'Monsters', False, False)))
    assert [d['title'] for d in temp_db.get_documents(mod, 'monster')] == ['Orc']


def test_delete_unused_custom_type_removes_it_and_its_templates(temp_db):
    temp_db.save_entity_types(_rows(('deity', 'Deity', 'Deities', False, False)))
    assert temp_db.delete_entity_type('deity') is True
    assert temp_db.get_entity_types() == []
    assert temp_db.get_default_template('deity') is None


def test_builtin_types_cannot_be_deleted(temp_db):
    temp_db.save_entity_types(_rows(('npc', 'NPC', 'NPCs', False, True)))
    assert temp_db.delete_entity_type('npc') is False


# --- migration & seeding ---------------------------------------------------
def test_migration_v8_backfills_custom_types_and_does_not_reseed(tmp_path):
    path = str(tmp_path / "v7.db")
    db = DatabaseManager(path)
    db.initialize_database()
    mod = db.create_module("M", "d")
    db.create_document(mod, "monster", "Orc", "body")
    deleted = db.get_default_template('quest')
    assert deleted
    with db.connection.transaction() as conn:
        conn.execute("DELETE FROM document_templates WHERE entity_type = 'quest'")
    db.connection.disconnect()

    # Simulate a v7 database
    conn = sqlite3.connect(path)
    conn.execute("DROP TABLE entity_types")
    conn.execute("DROP TABLE app_meta")
    conn.execute("DELETE FROM schema_version")
    conn.execute("INSERT INTO schema_version (version) VALUES (7)")
    conn.commit()
    conn.close()

    db2 = DatabaseManager(path)
    db2.initialize_database()
    assert [t['key'] for t in db2.get_entity_types()] == ['monster']
    assert db2.get_default_template('quest') is None  # deleted default stays deleted
    db2.connection.disconnect()
    db3 = DatabaseManager(path)
    db3.initialize_database()
    assert db3.get_default_template('quest') is None  # and across restarts


def test_fresh_database_seeds_templates_once(temp_db):
    assert temp_db.get_default_template('npc') is not None
    with temp_db.connection.transaction() as conn:
        conn.execute("DELETE FROM document_templates WHERE entity_type = 'npc'")
    temp_db.initialize_database()
    assert temp_db.get_default_template('npc') is None


# --- backup ------------------------------------------------------------------
class _StubImages:
    def regenerate_thumbnails_for_module(self, module_id):
        return 0


def test_restore_registers_missing_custom_type(temp_db, tmp_path):
    from services.backup_service import BackupService
    temp_db.save_entity_types(_rows(('monster', 'Beast', 'Beasts', False, False)))
    mod = temp_db.create_module("M", "d")
    temp_db.create_document(mod, "monster", "Orc", "body")
    data = BackupService(temp_db, _StubImages())._export_module_data(mod)
    assert data['entity_types'] == [{'key': 'monster', 'label_singular': 'Beast', 'label_plural': 'Beasts'}]

    other = DatabaseManager(":memory:")
    other.initialize_database()
    new_mod = other.create_module("Restored", "d")
    ok, msg = BackupService(other, _StubImages())._import_module_data(data, new_mod)
    assert ok, msg
    assert [(t['key'], t['label_plural']) for t in other.get_entity_types()] == [('monster', 'Beasts')]
    assert [d['title'] for d in other.get_documents(new_mod, 'monster')] == ['Orc']


def test_restore_ignores_invalid_custom_type_keys(temp_db):
    from services.backup_service import BackupService
    svc = BackupService(temp_db, _StubImages())
    mod = temp_db.create_module("M", "d")
    with temp_db.connection.transaction() as conn:
        svc._ensure_entity_types(conn, {'documents': [{'entity_type': 'Bad Key!'}, {'entity_type': 'npc'}],
                                        'entity_types': [{'key': 'Bad Key!', 'label_singular': 'x'}]})
    assert temp_db.get_entity_types() == []
