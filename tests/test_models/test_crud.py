"""
Tests for basic CRUD operations (Create, Read, Update, Delete).
"""

import pytest


@pytest.mark.unit
class TestModuleCRUD:
    """Tests for module CRUD operations."""

    def test_create_module(self, temp_db):
        """Should create a module and return valid ID."""
        module_id = temp_db.create_module(
            name="Test Campaign",
            description="A test campaign"
        )

        assert module_id > 0, "Should return positive module ID"
        assert isinstance(module_id, int), "Module ID should be integer"

    def test_create_module_minimal(self, temp_db):
        """Should create module with only required fields."""
        module_id = temp_db.create_module(name="Minimal Module")

        assert module_id > 0, "Should create module with just name"

    def test_get_module(self, temp_db):
        """Should retrieve created module."""
        module_id = temp_db.create_module("Test", "Description")
        module = temp_db.get_module(module_id)

        assert module is not None, "Should retrieve module"
        assert module['id'] == module_id
        assert module['name'] == "Test"
        assert module['description'] == "Description"
        assert 'is_active' in module
        assert 'created_date' in module

    def test_get_nonexistent_module(self, temp_db):
        """Should return None for non-existent module."""
        module = temp_db.get_module(99999)
        assert module is None, "Should return None for non-existent module"

    def test_get_modules(self, temp_db):
        """Should retrieve all active modules."""
        # Create multiple modules
        id1 = temp_db.create_module("Module 1")
        id2 = temp_db.create_module("Module 2")
        id3 = temp_db.create_module("Module 3")

        modules = temp_db.get_modules()

        assert isinstance(modules, list), "Should return list"
        assert len(modules) >= 3, "Should have at least 3 modules"
        module_ids = [m['id'] for m in modules]
        assert id1 in module_ids
        assert id2 in module_ids
        assert id3 in module_ids

    def test_rename_module(self, temp_db):
        """Should rename module successfully."""
        module_id = temp_db.create_module("Old Name")
        success = temp_db.rename_module(module_id, "New Name")

        assert success is True, "Rename should succeed"

        module = temp_db.get_module(module_id)
        assert module['name'] == "New Name", "Module should have new name"

    def test_soft_delete_module(self, temp_db):
        """Should soft delete module (mark as inactive)."""
        module_id = temp_db.create_module("To Delete")
        success = temp_db.soft_delete_module(module_id)

        assert success is True, "Soft delete should succeed"

        # Should not appear in active modules list
        modules = temp_db.get_modules()
        assert not any(m['id'] == module_id for m in modules), \
            "Soft-deleted module should not appear in active list"

        # But should still exist in database
        module = temp_db.get_module(module_id)
        assert module is not None, "Soft-deleted module should still exist"
        assert module['is_active'] == 0, "Module should be marked as inactive"

    def test_restore_module(self, temp_db):
        """Should restore soft-deleted module."""
        module_id = temp_db.create_module("To Restore")
        temp_db.soft_delete_module(module_id)
        success = temp_db.restore_module(module_id)

        assert success is True, "Restore should succeed"

        module = temp_db.get_module(module_id)
        assert module['is_active'] == 1, "Module should be active again"

        # Should appear in active modules list
        modules = temp_db.get_modules()
        assert any(m['id'] == module_id for m in modules), \
            "Restored module should appear in active list"


@pytest.mark.unit
class TestDocumentCRUD:
    """Tests for document CRUD operations."""

    def test_create_document(self, temp_db, sample_module):
        """Should create a document and return valid ID."""
        doc_id = temp_db.create_document(
            module_id=sample_module,
            entity_type="npc",
            title="Test NPC",
            content="A test character"
        )

        assert doc_id > 0, "Should return positive document ID"
        assert isinstance(doc_id, int), "Document ID should be integer"

    def test_create_document_all_types(self, temp_db, sample_module):
        """Should create documents of all entity types."""
        entity_types = ["npc", "location", "item", "quest", "faction", "note"]

        for entity_type in entity_types:
            doc_id = temp_db.create_document(
                module_id=sample_module,
                entity_type=entity_type,
                title=f"Test {entity_type}",
                content=f"Content for {entity_type}"
            )
            assert doc_id > 0, f"Should create {entity_type} document"

    def test_get_document(self, temp_db, sample_document):
        """Should retrieve created document."""
        doc = temp_db.get_document(sample_document)

        assert doc is not None, "Should retrieve document"
        assert doc['id'] == sample_document
        assert doc['title'] == "Test NPC"
        assert doc['entity_type'] == "npc"
        assert 'content' in doc
        assert 'module_id' in doc
        assert 'created_date' in doc

    def test_get_nonexistent_document(self, temp_db):
        """Should return None for non-existent document."""
        doc = temp_db.get_document(99999)
        assert doc is None, "Should return None for non-existent document"

    def test_get_documents_by_module(self, temp_db, sample_module):
        """Should retrieve all documents for a module."""
        # Create multiple documents
        doc1 = temp_db.create_document(sample_module, "npc", "NPC 1", "Content 1")
        doc2 = temp_db.create_document(sample_module, "location", "Location 1", "Content 2")
        doc3 = temp_db.create_document(sample_module, "item", "Item 1", "Content 3")

        documents = temp_db.get_documents(module_id=sample_module)

        assert isinstance(documents, list), "Should return list"
        assert len(documents) >= 3, "Should have at least 3 documents"
        doc_ids = [d['id'] for d in documents]
        assert doc1 in doc_ids
        assert doc2 in doc_ids
        assert doc3 in doc_ids

    def test_get_documents_by_entity_type(self, temp_db, sample_module):
        """Should filter documents by entity type."""
        # Create documents of different types
        npc1 = temp_db.create_document(sample_module, "npc", "NPC 1", "Content")
        npc2 = temp_db.create_document(sample_module, "npc", "NPC 2", "Content")
        location1 = temp_db.create_document(sample_module, "location", "Location 1", "Content")

        # Get only NPCs
        npcs = temp_db.get_documents(module_id=sample_module, entity_type="npc")

        assert len(npcs) >= 2, "Should have at least 2 NPCs"
        assert all(d['entity_type'] == "npc" for d in npcs), "All should be NPCs"
        npc_ids = [d['id'] for d in npcs]
        assert npc1 in npc_ids
        assert npc2 in npc_ids
        assert location1 not in npc_ids, "Location should not be in NPC list"

    def test_update_document(self, temp_db, sample_document):
        """Should update document successfully."""
        success = temp_db.update_document(
            sample_document,
            title="Updated Title",
            content="Updated content"
        )

        assert success is True, "Update should succeed"

        doc = temp_db.get_document(sample_document)
        assert doc['title'] == "Updated Title"
        assert doc['content'] == "Updated content"

    def test_update_document_partial(self, temp_db, sample_document):
        """Should update title while preserving content."""
        original = temp_db.get_document(sample_document)

        success = temp_db.update_document(
            sample_document,
            title="New Title Only",
            content=original['content']
        )
        assert success is True

        doc = temp_db.get_document(sample_document)
        assert doc['title'] == "New Title Only", "Title should be updated"
        assert doc['content'] == original['content'], "Content should remain unchanged"

    def test_update_document_with_metadata(self, temp_db, sample_document):
        """Should update document metadata."""
        import json
        original = temp_db.get_document(sample_document)
        metadata = {"tags": ["important", "reviewed"], "status": "approved"}

        success = temp_db.update_document(
            sample_document,
            title=original['title'],
            content=original['content'],
            metadata=json.dumps(metadata)
        )

        assert success is True, "Metadata update should succeed"

        doc = temp_db.get_document(sample_document)
        assert doc['metadata'] is not None
        # Metadata should be stored as JSON

    def test_delete_document(self, temp_db, sample_module):
        """Should delete document successfully."""
        doc_id = temp_db.create_document(sample_module, "npc", "To Delete", "Content")

        success = temp_db.delete_document(doc_id)
        assert success is True, "Delete should succeed"

        doc = temp_db.get_document(doc_id)
        assert doc is None, "Document should not exist after deletion"

    def test_document_timestamps(self, temp_db, sample_module):
        """Document should have creation and update timestamps."""
        # Create document
        doc_id = temp_db.create_document(sample_module, "npc", "Test", "Content")
        doc = temp_db.get_document(doc_id)

        assert 'created_date' in doc, "Should have created_date timestamp"
        assert 'modified_date' in doc, "Should have modified_date timestamp"

        created_date = doc['created_date']

        # Update document
        temp_db.update_document(doc_id, title="Updated", content="Content")
        doc = temp_db.get_document(doc_id)

        # created_date should not change
        assert doc['created_date'] == created_date, "created_date should not change"


@pytest.mark.unit
class TestSessionCRUD:
    """Tests for session CRUD operations."""

    def test_create_session(self, temp_db, sample_module):
        """Should create a game session."""
        session_id = temp_db.create_session(
            module_id=sample_module,
            session_date="2024-11-09",
            title="First Session",
            content="Introduction to the campaign"
        )

        assert session_id > 0, "Should return positive session ID"

    def test_get_sessions(self, temp_db, sample_module):
        """Should retrieve sessions for a module."""
        # Create multiple sessions
        s1 = temp_db.create_session(sample_module, "2024-11-01", "Session 1", "Summary 1")
        s2 = temp_db.create_session(sample_module, "2024-11-08", "Session 2", "Summary 2")

        sessions = temp_db.get_sessions(module_id=sample_module)

        assert isinstance(sessions, list), "Should return list"
        assert len(sessions) >= 2, "Should have at least 2 sessions"
        session_ids = [s['id'] for s in sessions]
        assert s1 in session_ids
        assert s2 in session_ids

    def test_session_ordering(self, temp_db, sample_module):
        """Sessions should be ordered by session date."""
        # Create sessions out of order by date
        temp_db.create_session(sample_module, "2024-11-15", "Third", "Summary")
        temp_db.create_session(sample_module, "2024-11-01", "First", "Summary")
        temp_db.create_session(sample_module, "2024-11-08", "Second", "Summary")

        sessions = temp_db.get_sessions(module_id=sample_module)

        # Should be ordered by session_date DESC (newest first)
        session_dates = [s['session_date'] for s in sessions]
        assert session_dates == sorted(session_dates, reverse=True), \
            "Sessions should be ordered by session date descending"
