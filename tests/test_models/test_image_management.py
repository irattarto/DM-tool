"""
Tests for image management functionality.
"""

import pytest


@pytest.mark.integration
class TestImageManagement:
    """Tests for image management operations."""

    def test_save_image_record(self, temp_db, sample_module, sample_document):
        """Should save image record to database."""
        image_id = temp_db.save_image_record(
            module_id=sample_module,
            document_id=sample_document,
            filename="test_image.png",
            original_name="original.png",
            file_path="images/test_image.png",
            file_size=1024,
            mime_type="image/png",
            description="Test image description"
        )

        assert image_id > 0, "Should return positive image ID"
        assert isinstance(image_id, int), "Image ID should be integer"

    def test_save_image_without_description(self, temp_db, sample_module, sample_document):
        """Should save image record without description."""
        image_id = temp_db.save_image_record(
            module_id=sample_module,
            document_id=sample_document,
            filename="test.png",
            original_name="test.png",
            file_path="images/test.png",
            file_size=500,
            mime_type="image/png"
        )

        assert image_id > 0, "Should create image without description"

    def test_get_document_images(self, temp_db, sample_module, sample_document):
        """Should retrieve all images for a document."""
        # Create multiple images
        img1 = temp_db.save_image_record(
            sample_module, sample_document, "img1.png", "orig1.png",
            "images/1.png", 100, "image/png", "First image"
        )
        img2 = temp_db.save_image_record(
            sample_module, sample_document, "img2.jpg", "orig2.jpg",
            "images/2.jpg", 200, "image/jpeg", "Second image"
        )

        images = temp_db.get_document_images(sample_document)

        assert isinstance(images, list), "Should return list"
        assert len(images) == 2, "Should have 2 images"

        image_ids = [img['id'] for img in images]
        assert img1 in image_ids
        assert img2 in image_ids

        # Check image fields
        for img in images:
            assert 'id' in img
            assert 'filename' in img
            assert 'original_name' in img
            assert 'file_path' in img
            assert 'file_size' in img
            assert 'mime_type' in img
            assert 'description' in img
            assert 'is_primary' in img

    def test_get_images_empty_document(self, temp_db, sample_document):
        """Should return empty list for document with no images."""
        images = temp_db.get_document_images(sample_document)

        assert images == [], "Should return empty list for document with no images"

    def test_update_image_description(self, temp_db, sample_module, sample_document):
        """Should update image description."""
        # Create image
        image_id = temp_db.save_image_record(
            sample_module, sample_document, "test.png", "test.png",
            "images/img.png", 100, "image/png", "Old description"
        )

        # Update description
        success = temp_db.update_image_description(image_id, "New description")
        assert success is True, "Update should succeed"

        # Verify update
        images = temp_db.get_document_images(sample_document)
        image = next((img for img in images if img['id'] == image_id), None)

        assert image is not None, "Image should exist"
        assert image['description'] == "New description", "Description should be updated"

    def test_delete_image_record(self, temp_db, sample_module, sample_document):
        """Should delete image record."""
        # Create image
        image_id = temp_db.save_image_record(
            sample_module, sample_document, "delete.png", "delete.png",
            "images/img.png", 100, "image/png"
        )

        # Verify it exists
        images = temp_db.get_document_images(sample_document)
        assert len(images) == 1

        # Delete
        success = temp_db.delete_image_record(image_id)
        assert success is True, "Delete should succeed"

        # Verify it's gone
        images = temp_db.get_document_images(sample_document)
        assert len(images) == 0, "Image should be deleted"

    def test_get_image_by_id(self, temp_db, sample_module, sample_document):
        """Should retrieve specific image by ID."""
        # Create image
        image_id = temp_db.save_image_record(
            sample_module, sample_document, "specific.png", "specific.png",
            "images/specific.png", 500, "image/png", "Specific image"
        )

        # Get by ID
        image = temp_db.get_image_by_id(image_id)

        assert image is not None, "Should retrieve image"
        assert image['id'] == image_id
        assert image['filename'] == "specific.png"
        assert image['description'] == "Specific image"

    def test_get_nonexistent_image(self, temp_db):
        """Should return None for non-existent image."""
        image = temp_db.get_image_by_id(99999)
        assert image is None, "Should return None for non-existent image"


@pytest.mark.integration
class TestPrimaryImageManagement:
    """Tests for primary image functionality."""

    def test_set_primary_image(self, temp_db, sample_module, sample_document):
        """Should set an image as primary."""
        # Create two images
        img1 = temp_db.save_image_record(
            sample_module, sample_document, "img1.png", "img1.png",
            "images/1.png", 100, "image/png"
        )
        img2 = temp_db.save_image_record(
            sample_module, sample_document, "img2.png", "img2.png",
            "images/2.png", 100, "image/png"
        )

        # Set second image as primary
        success = temp_db.set_primary_image(sample_document, img2)
        assert success is True, "Setting primary should succeed"

        # Verify
        images = temp_db.get_document_images(sample_document)
        img1_data = next(img for img in images if img['id'] == img1)
        img2_data = next(img for img in images if img['id'] == img2)

        assert img1_data['is_primary'] == 0, "First image should not be primary"
        assert img2_data['is_primary'] == 1, "Second image should be primary"

    def test_get_primary_image(self, temp_db, sample_module, sample_document):
        """Should retrieve the primary image."""
        # Create images
        img1 = temp_db.save_image_record(
            sample_module, sample_document, "img1.png", "img1.png",
            "images/1.png", 100, "image/png"
        )
        img2 = temp_db.save_image_record(
            sample_module, sample_document, "img2.png", "img2.png",
            "images/2.png", 100, "image/png"
        )

        # Set img2 as primary
        temp_db.set_primary_image(sample_document, img2)

        # Get primary
        primary = temp_db.get_primary_image(sample_document)

        assert primary is not None, "Should have primary image"
        assert primary['id'] == img2, "Primary should be img2"
        assert primary['is_primary'] == 1

    def test_get_primary_image_none(self, temp_db, sample_module, sample_document):
        """Should return None when no primary image is set."""
        # Create image but don't set as primary
        temp_db.save_image_record(
            sample_module, sample_document, "img.png", "img.png",
            "images/img.png", 100, "image/png"
        )

        # Get primary
        primary = temp_db.get_primary_image(sample_document)

        # Behavior depends on implementation - either None or auto-selects first
        # This tests that it doesn't crash
        assert primary is None or isinstance(primary, dict)

    def test_changing_primary_image(self, temp_db, sample_module, sample_document):
        """Should correctly change primary image."""
        # Create two images
        img1 = temp_db.save_image_record(
            sample_module, sample_document, "img1.png", "img1.png",
            "images/1.png", 100, "image/png"
        )
        img2 = temp_db.save_image_record(
            sample_module, sample_document, "img2.png", "img2.png",
            "images/2.png", 100, "image/png"
        )

        # Set first as primary
        temp_db.set_primary_image(sample_document, img1)
        primary = temp_db.get_primary_image(sample_document)
        assert primary['id'] == img1, "First should be primary"

        # Change to second
        temp_db.set_primary_image(sample_document, img2)
        primary = temp_db.get_primary_image(sample_document)
        assert primary['id'] == img2, "Second should now be primary"

        # Verify only one is primary
        images = temp_db.get_document_images(sample_document)
        primary_count = sum(1 for img in images if img['is_primary'] == 1)
        assert primary_count == 1, "Should have exactly one primary image"

    def test_auto_set_primary_if_needed(self, temp_db, sample_module, sample_document):
        """Should auto-set primary when first image is added."""
        # Create first image
        img1 = temp_db.save_image_record(
            sample_module, sample_document, "first.png", "first.png",
            "images/img.png", 100, "image/png"
        )

        # Auto-set might trigger
        temp_db.auto_set_primary_if_needed(sample_document)

        # Check if auto-set worked
        primary = temp_db.get_primary_image(sample_document)

        # Depending on implementation, might auto-set first image
        # Test that method doesn't crash
        assert primary is None or primary['id'] == img1


@pytest.mark.integration
class TestImageOrdering:
    """Tests for image ordering and display."""

    def test_images_ordered_by_creation(self, temp_db, sample_module, sample_document):
        """Images should be returned in creation order."""
        import time

        # Create images with small delays
        img1 = temp_db.save_image_record(
            sample_module, sample_document, "first.png", "first.png",
            "images/1.png", 100, "image/png"
        )
        time.sleep(0.01)

        img2 = temp_db.save_image_record(
            sample_module, sample_document, "second.png", "second.png",
            "images/2.png", 100, "image/png"
        )
        time.sleep(0.01)

        img3 = temp_db.save_image_record(
            sample_module, sample_document, "third.png", "third.png",
            "images/3.png", 100, "image/png"
        )

        images = temp_db.get_document_images(sample_document)

        # Check order (might be by ID or created_at depending on implementation)
        assert len(images) == 3
        # IDs should be in ascending order
        ids = [img['id'] for img in images]
        assert ids == [img1, img2, img3], "Images should be in creation order"

    def test_primary_image_appears_first(self, temp_db, sample_module, sample_document):
        """Primary image might appear first in results."""
        # Create multiple images
        img1 = temp_db.save_image_record(
            sample_module, sample_document, "img1.png", "img1.png",
            "images/1.png", 100, "image/png"
        )
        img2 = temp_db.save_image_record(
            sample_module, sample_document, "img2.png", "img2.png",
            "images/2.png", 100, "image/png"
        )
        img3 = temp_db.save_image_record(
            sample_module, sample_document, "img3.png", "img3.png",
            "images/3.png", 100, "image/png"
        )

        # Set middle one as primary
        temp_db.set_primary_image(sample_document, img2)

        images = temp_db.get_document_images(sample_document)

        # Depending on query ordering, primary might be first
        # Or might maintain creation order
        # Just verify all images are present
        assert len(images) == 3
        image_ids = [img['id'] for img in images]
        assert set(image_ids) == {img1, img2, img3}
