#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Schema consistency checker.
Compares database schema with CREATE TABLE statements in code.
"""

import sys
import sqlite3
import re
from pathlib import Path

# Fix Windows console encoding
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

# Allow overriding paths via command-line arguments
# Usage: python check_schema_consistency.py [db_path] [code_path]
_project_root = Path(__file__).parent
sys.path.insert(0, str(_project_root))
from config.paths import get_data_dir  # noqa: E402  (same folder resolution as the application)
_default_db = get_data_dir() / "rpg_database_manager.db"

DB_PATH = sys.argv[1] if len(sys.argv) > 1 else str(_default_db)
CODE_PATH = sys.argv[2] if len(sys.argv) > 2 else str(_project_root / "models" / "database.py")


def get_db_schema():
    """Get actual database schema."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    schema = {}
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    tables = [row[0] for row in cursor.fetchall()]

    for table in tables:
        if table.startswith('sqlite_') or table.endswith('_fts') or '_fts_' in table:
            continue
        cursor.execute(f'PRAGMA table_info({table})')
        columns = {row[1]: row[2] for row in cursor.fetchall()}
        schema[table] = columns

    conn.close()
    return schema


def get_code_schema():
    """Extract CREATE TABLE statements from code."""
    with open(CODE_PATH, 'r', encoding='utf-8') as f:
        content = f.read()

    schema = {}

    # Find all CREATE TABLE statements; the column list ends at the BALANCED closing parenthesis
    # (types like DECIMAL(10,2) and DEFAULT (...) contain parentheses and commas of their own)
    for match in re.finditer(r'CREATE TABLE IF NOT EXISTS (\w+) \(', content):
        table_name = match.group(1)
        depth, end = 1, match.end()
        while end < len(content) and depth:
            depth += {'(': 1, ')': -1}.get(content[end], 0)
            end += 1
        table_def = re.sub(r'--[^\n]*', '', content[match.end():end - 1])   # comments may contain commas

        columns = {}
        parts_top, depth, current = [], 0, ''
        for ch in table_def:
            if ch == ',' and depth == 0:
                parts_top.append(current)
                current = ''
                continue
            depth += {'(': 1, ')': -1}.get(ch, 0)
            current += ch
        parts_top.append(current)
        for line in parts_top:
            line = line.strip()
            if not line or line.upper().startswith(('FOREIGN', 'UNIQUE', 'PRIMARY', 'CHECK', 'CONSTRAINT')):
                continue

            parts = line.split()
            if len(parts) >= 2:
                col_name = parts[0]
                col_type = parts[1]
                columns[col_name] = col_type

        schema[table_name] = columns

    return schema


def compare_schemas():
    """Compare database schema with code schema."""
    print("=" * 80)
    print("SCHEMA CONSISTENCY CHECK")
    print("=" * 80)
    print()

    db_schema = get_db_schema()
    code_schema = get_code_schema()

    all_tables = set(db_schema.keys()) | set(code_schema.keys())

    issues_found = []

    for table in sorted(all_tables):
        print(f"\n📋 Table: {table}")
        print("-" * 80)

        if table not in db_schema:
            print("   ⚠️  Table exists in CODE but NOT in DATABASE")
            issues_found.append(f"{table}: missing from database")
            continue

        if table not in code_schema:
            print("   ⚠️  Table exists in DATABASE but NOT in CODE")
            issues_found.append(f"{table}: missing from code")
            continue

        db_cols = db_schema[table]
        code_cols = code_schema[table]

        all_cols = set(db_cols.keys()) | set(code_cols.keys())

        missing_in_code = []
        missing_in_db = []
        type_mismatches = []

        for col in sorted(all_cols):
            if col in db_cols and col in code_cols:
                # Both have it - check type
                db_type = db_cols[col].upper()
                code_type = code_cols[col].upper()

                # Normalize types
                if db_type == code_type or \
                   (db_type.startswith('INT') and code_type.startswith('INT')) or \
                   (db_type == 'BOOL' and code_type == 'BOOLEAN') or \
                   (db_type == 'BOOLEAN' and code_type == 'BOOL'):
                    print(f"   ✓ {col}: {db_type}")
                else:
                    print(f"   ⚠️  {col}: DB has {db_type}, CODE has {code_type}")
                    type_mismatches.append(f"{col} (DB:{db_type} vs CODE:{code_type})")
            elif col in db_cols:
                # In DB but not in code
                print(f"   ❌ {col}: EXISTS in DB ({db_cols[col]}) but MISSING in CODE")
                missing_in_code.append(f"{col} ({db_cols[col]})")
            else:
                # In code but not in DB
                print(f"   ❌ {col}: EXISTS in CODE ({code_cols[col]}) but MISSING in DB")
                missing_in_db.append(f"{col} ({code_cols[col]})")

        if missing_in_code:
            issues_found.append(f"{table}: columns in DB but not in code: {', '.join(missing_in_code)}")
        if missing_in_db:
            issues_found.append(f"{table}: columns in code but not in DB: {', '.join(missing_in_db)}")
        if type_mismatches:
            issues_found.append(f"{table}: type mismatches: {', '.join(type_mismatches)}")

    print()
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)

    if issues_found:
        print(f"\n❌ Found {len(issues_found)} issue(s):\n")
        for i, issue in enumerate(issues_found, 1):
            print(f"{i}. {issue}")
        return False
    else:
        print("\n✅ All schemas are consistent!")
        return True


if __name__ == "__main__":
    try:
        success = compare_schemas()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
