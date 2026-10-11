"""Regression tests for audit fixes."""
import json

import pytest
import sqlite3

from models.database import DatabaseManager
from models.document import DocumentTemplate
from utils.security_utils import get_security_validator


def test_update_document_keeps_metadata_when_omitted(temp_db):
    mod = temp_db.create_module("M", "d")
    doc_id = temp_db.create_document(mod, "npc", "Name", "Body", metadata=json.dumps({"faction": "X"}))
    assert temp_db.update_document(doc_id, title="Name", content="New body")
    assert json.loads(temp_db.get_document(doc_id)["metadata"]) == {"faction": "X"}


def test_accented_metadata_is_valid():
    meta = json.dumps({"name": "Árpád"})  # ensure_ascii -> Árpád
    assert get_security_validator().validate_json_input(meta)["valid"]


def test_template_substitution_single_pass():
    t = DocumentTemplate(entity_type="npc", template_name="t", template_content="[a] [b]")
    assert t.apply_template({"a": "[b]", "b": "x"}) == "[b] x"


def test_existing_db_is_migrated_not_stamped(tmp_path):
    path = str(tmp_path / "old.db")
    db = DatabaseManager(path)
    db.initialize_database()
    db.connection.disconnect()

    # Simulate a v6 database that lacks the v7 status column
    conn = sqlite3.connect(path)
    conn.execute("DROP INDEX IF EXISTS idx_game_sessions_status")
    conn.execute("ALTER TABLE game_sessions DROP COLUMN status")
    conn.execute("DELETE FROM schema_version")
    conn.execute("INSERT INTO schema_version (version) VALUES (6)")
    conn.commit()
    conn.close()

    db2 = DatabaseManager(path)
    db2.initialize_database()
    cols = {r[1] for r in sqlite3.connect(path).execute("PRAGMA table_info(game_sessions)")}
    assert "status" in cols


def test_template_save_keeps_id_and_default_flag(temp_db):
    first = temp_db.save_template("T", "npc", "[a]", is_default=True)
    second = temp_db.save_template("T", "npc", "[a] [b]", is_default=False)
    assert first == second
    row = [t for t in temp_db.get_templates("npc") if t["template_name"] == "T"][0]
    assert row["is_default"] == 1 and row["template_content"] == "[a] [b]"


def test_nested_transaction_inner_failure_rolls_back_everything(temp_db):
    mod = temp_db.create_module("N", "d")
    with pytest.raises(RuntimeError):
        with temp_db.connection.transaction() as conn:
            conn.execute("INSERT INTO documents (module_id, entity_type, title, content) VALUES (?, 'npc', 'x', 'y')", (mod,))
            with temp_db.connection.transaction():
                raise RuntimeError("inner")
    assert temp_db.get_documents(mod) == []


def test_nested_transaction_inner_exit_does_not_commit(temp_db):
    mod = temp_db.create_module("N2", "d")
    try:
        with temp_db.connection.transaction() as conn:
            conn.execute("INSERT INTO documents (module_id, entity_type, title, content) VALUES (?, 'npc', 'x', 'y')", (mod,))
            with temp_db.connection.transaction():
                pass  # inner success must not commit the outer work
            raise RuntimeError("outer fails after inner success")
    except RuntimeError:
        pass
    assert temp_db.get_documents(mod) == []


def test_malformed_session_date_does_not_break_query(temp_db):
    import datetime
    mod = temp_db.create_module("D", "d")
    good = temp_db.create_session(mod, "2025-01-05", "ok", "c")
    bad = temp_db.create_session(mod, "2025-01-06", "bad", "c")
    with temp_db.connection.transaction() as conn:
        conn.execute("UPDATE game_sessions SET session_date='garbage' WHERE id=?", (bad,))
    rows = {r["id"]: r["session_date"] for r in temp_db.get_sessions(mod)}
    assert rows[good] == datetime.date(2025, 1, 5)
    assert rows[bad] == "garbage"
