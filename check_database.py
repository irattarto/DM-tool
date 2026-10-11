#!/usr/bin/env python3
"""
Database corruption recovery tool for RPG Database Manager.

This script helps recover from severe database corruption by:
1. Locating the corrupted database file
2. Attempting to salvage data using SQLite's dump/recovery tools
3. Creating a fresh database if recovery fails
"""

import sqlite3
import sys
from pathlib import Path
from datetime import datetime

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from PyQt6.QtWidgets import QApplication
from config.paths import get_data_dir

# get_data_dir() uses QStandardPaths which requires a QApplication.
_app = QApplication.instance() or QApplication(sys.argv)
_app.setApplicationName("RPG Database Manager")
_app.setOrganizationName("RPG Database Manager")


def get_database_path():
    """Get the path to the database file."""
    return get_data_dir() / "rpg_database_manager.db"


def check_database_exists(db_path):
    """Check if database file exists."""
    if not db_path.exists():
        print(f"[X] Database file not found at: {db_path}")
        return False

    file_size = db_path.stat().st_size
    print(f"[OK] Database file found: {db_path}")
    print(f"  File size: {file_size:,} bytes ({file_size / 1024 / 1024:.2f} MB)")
    return True


def test_basic_connection(db_path):
    """Test if we can open the database at all."""
    print("\n[?] Testing basic connection...")
    try:
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        cursor.execute("SELECT sqlite_version()")
        version = cursor.fetchone()[0]
        print(f"[OK] SQLite version: {version}")
        conn.close()
        return True
    except Exception as e:
        print(f"[X] Cannot open database: {e}")
        return False


def check_integrity(db_path):
    """Check database integrity."""
    print("\n[?] Checking database integrity...")
    try:
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        cursor.execute("PRAGMA integrity_check")
        results = cursor.fetchall()
        conn.close()

        if results and results[0][0] == 'ok':
            print("[OK] Database integrity check: OK")
            return True
        else:
            print("[X] Database integrity check FAILED:")
            for result in results[:10]:  # Show first 10 errors
                print(f"   - {result[0]}")
            return False
    except Exception as e:
        print(f"[X] Integrity check failed: {e}")
        return False


def attempt_recovery(db_path):
    """Attempt to recover data from corrupted database."""
    print("\n[!] Attempting data recovery...")

    backup_path = db_path.parent / f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"

    try:
        # Try SQL dump recovery
        print("  Attempting SQL dump recovery...")
        dump_path = db_path.parent / "recovery_dump.sql"

        # Use SQLite's .recover command via sqlite3 CLI if available
        import subprocess

        # Try to dump the database
        result = subprocess.run(
            ['sqlite3', str(db_path), '.dump'],
            capture_output=True,
            text=True,
            timeout=60
        )
        if result.returncode == 0:
            with open(dump_path, 'w', encoding='utf-8') as f:   # closed (flushed) before it is read back
                f.write(result.stdout)
            print(f"[OK] SQL dump created: {dump_path}")

            # Create new database from dump
            print("  Creating new database from dump...")
            if backup_path.exists():
                backup_path.unlink()

            conn = sqlite3.connect(str(backup_path))
            with open(dump_path, 'r', encoding='utf-8') as f:
                conn.executescript(f.read())
            conn.close()

            print(f"[OK] Recovery database created: {backup_path}")
            return backup_path
        else:
            print(f"[X] Dump failed: {result.stderr}")

    except subprocess.TimeoutExpired:
        print("[X] Recovery timed out")
    except FileNotFoundError:
        print("[X] sqlite3 command-line tool not found")
        print("   Install SQLite command-line tools to enable recovery")
    except Exception as e:
        print(f"[X] Recovery failed: {e}")

    return None


def rename_corrupted_database(db_path):
    """Rename the corrupted database file."""
    print("\n[!] Renaming corrupted database...")

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    corrupted_path = db_path.parent / f"corrupted_{timestamp}_{db_path.name}"

    try:
        db_path.rename(corrupted_path)
        for suffix in ('-wal', '-shm'):          # journal files belong to the renamed database
            side = db_path.with_name(db_path.name + suffix)
            if side.exists():
                side.rename(corrupted_path.with_name(corrupted_path.name + suffix))
        print(f"[OK] Corrupted database renamed to: {corrupted_path}")
        print("  You can delete this file later if you don't need it")
        return True
    except Exception as e:
        print(f"[X] Failed to rename database: {e}")
        return False


def create_fresh_database():
    """Instructions for creating a fresh database."""
    print("\n[+] Next steps to create a fresh database:")
    print("  1. The corrupted database has been renamed")
    print("  2. When you start the application, a new database will be created automatically")
    print("  3. Your data from the old database may be lost, but you can start fresh")
    print("\nIMPORTANT: If you have backup files, you may be able to restore data manually")


def main():
    """Main recovery function."""
    print("=" * 70)
    print("RPG Database Manager - Database Recovery Tool")
    print("=" * 70)

    # Get database path
    db_path = get_database_path()
    print(f"\nDatabase location: {db_path}")

    # Check if database exists
    if not check_database_exists(db_path):
        print("\n[OK] No database file found - application will create a fresh one on next start")
        return 0

    # Test basic connection
    test_basic_connection(db_path)

    # Check integrity
    is_healthy = check_integrity(db_path)

    if is_healthy:
        print("\n[OK] Database is healthy!")
        print("  The error may be transient. Try starting the application again.")
        return 0

    # Database is corrupted
    print("\n" + "=" * 70)
    print("[!] DATABASE CORRUPTION DETECTED")
    print("=" * 70)

    # Ask user what to do
    print("\nOptions:")
    print("  1. Attempt data recovery (requires sqlite3 command-line tool)")
    print("  2. Rename corrupted database and start fresh")
    print("  3. Exit without making changes")

    choice = input("\nEnter your choice (1-3): ").strip()

    if choice == '1':
        recovered_db = attempt_recovery(db_path)
        if recovered_db:
            print("\n[OK] Recovery successful!")
            print(f"  Recovered database: {recovered_db}")
            print(f"  Original database: {db_path}")
            print("\nTo use the recovered database:")
            print("  1. Close this script")
            print(f"  2. Rename {db_path} to something else")
            print(f"  3. Rename {recovered_db} to {db_path.name}")
            print("  4. Start the application")
        else:
            print("\n[X] Recovery failed")
            retry = input("\nWould you like to rename the corrupted database and start fresh? (y/n): ").strip().lower()
            if retry == 'y':
                if rename_corrupted_database(db_path):
                    create_fresh_database()
                    return 0
                else:
                    return 1

    elif choice == '2':
        if rename_corrupted_database(db_path):
            create_fresh_database()
            return 0
        else:
            return 1

    else:
        print("\n[!] Exiting without making changes")
        print("   You can run this script again when ready")
        return 0


if __name__ == "__main__":
    try:
        exit_code = main()
        print("\n" + "=" * 70)
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n\n[!] Interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n[X] Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
