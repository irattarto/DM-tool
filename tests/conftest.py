"""
Pytest configuration and shared fixtures.
"""

import pytest
import tempfile
from pathlib import Path
import sys
import os

# Add parent directory to Python path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models.database import DatabaseManager

# Tests must never touch the developer's real data, keyring or settings:
# - RPG_DB_NO_KEYRING keeps the OS keyring out (tests/test_crypto_keyring.py opts in)
# - RPG_DB_DATA_DIR redirects get_data_dir() (database, images, key file, logs) to a temp folder
# - XDG_CONFIG_HOME redirects QSettings on Linux
os.environ.setdefault("RPG_DB_NO_KEYRING", "1")
_TEST_HOME = tempfile.mkdtemp(prefix="rpgdb-tests-")
os.environ.setdefault("RPG_DB_DATA_DIR", os.path.join(_TEST_HOME, "data"))
os.environ.setdefault("XDG_CONFIG_HOME", os.path.join(_TEST_HOME, "config"))


@pytest.fixture
def temp_db():
    """
    Create a temporary in-memory database for testing.

    Yields:
        DatabaseManager: Initialized database manager with fresh schema
    """
    # Use in-memory database for speed
    db = DatabaseManager(":memory:")
    db.initialize_database()

    yield db

    # Cleanup
    try:
        db.close()
    except Exception:
        pass


@pytest.fixture
def temp_db_file():
    """
    Create a temporary file-based database for testing.
    Useful for tests that need to verify file operations or persistence.

    Yields:
        tuple: (DatabaseManager, Path) - database manager and path to the file
    """
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = Path(f.name)

    db = DatabaseManager(str(db_path))
    db.initialize_database()

    yield db, db_path

    # Cleanup
    try:
        db.close()
    except Exception:
        pass

    try:
        db_path.unlink(missing_ok=True)
    except Exception:
        pass


@pytest.fixture
def sample_module(temp_db):
    """
    Create a sample module for testing.

    Args:
        temp_db: Database fixture

    Returns:
        int: Module ID
    """
    module_id = temp_db.create_module(
        name="Test Campaign",
        description="A test campaign for unit tests"
    )
    return module_id


@pytest.fixture
def sample_document(temp_db, sample_module):
    """
    Create a sample document for testing.

    Args:
        temp_db: Database fixture
        sample_module: Module fixture

    Returns:
        int: Document ID
    """
    doc_id = temp_db.create_document(
        module_id=sample_module,
        entity_type="npc",
        title="Test NPC",
        content="A test character with interesting backstory"
    )
    return doc_id


@pytest.fixture
def multiple_documents(temp_db, sample_module):
    """
    Create multiple sample documents for testing.

    Args:
        temp_db: Database fixture
        sample_module: Module fixture

    Returns:
        list: List of document IDs
    """
    doc_ids = []

    # Create various entity types
    entities = [
        ("npc", "Dragon Lord", "A powerful dragon who guards ancient treasure"),
        ("npc", "Village Elder", "Wise old man who knows the local legends"),
        ("location", "Dark Forest", "A mysterious forest filled with dangerous creatures"),
        ("item", "Magic Sword", "An enchanted blade with runes of power"),
        ("quest", "Rescue Mission", "Save the princess from the evil wizard"),
    ]

    for entity_type, title, content in entities:
        doc_id = temp_db.create_document(
            module_id=sample_module,
            entity_type=entity_type,
            title=title,
            content=content
        )
        doc_ids.append(doc_id)

    return doc_ids


@pytest.fixture
def large_content_document(temp_db, sample_module):
    """
    Create a document with large content (>50KB) for testing corruption risk.

    Args:
        temp_db: Database fixture
        sample_module: Module fixture

    Returns:
        int: Document ID
    """
    # Create content larger than DB_LARGE_CONTENT_THRESHOLD (50000 bytes)
    large_content = "This is a test paragraph. " * 2500  # ~60KB

    doc_id = temp_db.create_document(
        module_id=sample_module,
        entity_type="npc",
        title="Large Document",
        content=large_content
    )
    return doc_id


@pytest.fixture
def problematic_content_document(temp_db, sample_module):
    """
    Create a document with problematic characters for testing edge cases.

    Args:
        temp_db: Database fixture
        sample_module: Module fixture

    Returns:
        int: Document ID
    """
    # Content with control characters that can cause FTS5 issues
    bad_content = "Normal text\x00\x01\x02with control characters\x03\x04"

    doc_id = temp_db.create_document(
        module_id=sample_module,
        entity_type="npc",
        title="Problematic Content",
        content=bad_content
    )
    return doc_id


@pytest.fixture(autouse=True)
def _reset_entity_type_registry():
    """The registry is a process-wide singleton; never leak customisations between tests."""
    yield
    from config.entity_types import get_registry
    get_registry().load_overrides([])


def pytest_sessionfinish(session, exitstatus):
    """Let Qt threads and queued events finish before the interpreter tears Qt down.

    Without this a rare crash at process exit was seen when a worker thread was still winding down.
    """
    try:
        import gc
        import time
        from PyQt6.QtCore import QThread
        from PyQt6.QtWidgets import QApplication
        app = QApplication.instance()
        deadline = time.time() + 5
        while time.time() < deadline:
            if app is not None:
                app.processEvents()
            running = [o for o in gc.get_objects() if isinstance(o, QThread) and _alive(o)]
            if not running:
                break
            time.sleep(0.05)
        gc.collect()
        if app is not None:
            app.processEvents()
    except Exception:
        pass


def _alive(thread) -> bool:
    try:
        return thread.isRunning()
    except RuntimeError:  # the C++ object is already gone
        return False
