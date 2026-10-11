"""
Image storage and management service for RPG Database Manager.
"""

import shutil
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime
import uuid

from PyQt6.QtCore import QSize, Qt, QBuffer, QIODevice
from PyQt6.QtGui import QImage, QPixmap, QGuiApplication

from config.paths import get_data_dir
from utils.logger import get_logger


class ImageService:
    """
    Service for managing images in the RPG Database Manager.

    Handles image storage, organization by module, thumbnail generation,
    and integration with documents.
    """

    def __init__(self, base_storage_path: Optional[str] = None):
        """
        Initialize image service.

        Args:
            base_storage_path: Base directory for image storage.
                             If None, uses standard app data location.
        """
        if base_storage_path is None:
            base_storage_path = get_data_dir() / "rpg_images"

        self.base_path = Path(base_storage_path)
        self.base_path.mkdir(parents=True, exist_ok=True)

        # Create subdirectories
        self.modules_path = self.base_path / "modules"
        self.thumbnails_path = self.base_path / "thumbnails"
        self.temp_path = self.base_path / "temp"

        for path in [self.modules_path, self.thumbnails_path, self.temp_path]:
            path.mkdir(exist_ok=True)

        self.logger = get_logger('image_service')

        # Supported image formats
        self.supported_formats = ['.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp']

        # Thumbnail settings
        self.thumbnail_size = QSize(200, 200)
        self.thumbnail_quality = 85

    def save_image(self, image_path: str, module_id: int,
                  document_id: Optional[int] = None,
                  original_filename: str = None) -> Optional[Dict[str, Any]]:
        """
        Save an image to the storage system.

        Args:
            image_path: Path to the source image file
            module_id: ID of the associated module
            document_id: Optional ID of the associated document
            original_filename: Original filename (if different from image_path)

        Returns:
            Dictionary with image metadata or None if failed
        """
        try:
            # Validate module_id to prevent path traversal
            if not isinstance(module_id, int) or module_id <= 0:
                self.logger.error(f"Invalid module_id: {module_id}. Must be a positive integer.")
                return None

            # Additional safety: ensure module_id doesn't contain path separators when converted to string
            module_id_str = str(module_id)
            if '/' in module_id_str or '\\' in module_id_str or '..' in module_id_str:
                self.logger.error(f"Invalid module_id contains path separators: {module_id}")
                return None

            source_path = Path(image_path)
            if not source_path.exists():
                self.logger.error(f"Source image not found: {image_path}")
                return None

            # Generate unique filename
            file_extension = source_path.suffix.lower()
            if file_extension not in self.supported_formats:
                self.logger.error(f"Unsupported image format: {file_extension}")
                return None

            if not self._check_image_limits(source_path):
                return None

            unique_id = str(uuid.uuid4())
            new_filename = f"{unique_id}{file_extension}"
            original_name = original_filename or source_path.name

            # Create module directory with validated module_id
            module_path = self.modules_path / module_id_str
            module_path.mkdir(exist_ok=True)

            # Copy image to storage
            destination_path = module_path / new_filename
            shutil.copy2(source_path, destination_path)

            # Get image info
            image_info = self._get_image_info(destination_path)

            # Generate thumbnail
            thumbnail_path = self._generate_thumbnail(destination_path, unique_id)

            # Create metadata
            metadata = {
                'id': None,  # Will be set by database
                'module_id': module_id,
                'document_id': document_id,
                'filename': new_filename,
                'original_name': original_name,
                'file_path': str(destination_path),
                'thumbnail_path': str(thumbnail_path) if thumbnail_path else None,
                'file_size': destination_path.stat().st_size,
                'mime_type': image_info.get('mime_type', ''),
                'width': image_info.get('width', 0),
                'height': image_info.get('height', 0),
                'uploaded_date': datetime.now().isoformat(),
            }

            self.logger.info(f"Saved image: {new_filename} for module {module_id}")
            return metadata

        except Exception as e:
            self.logger.error(f"Error saving image: {e}")
            return None

    MAX_IMAGE_PIXELS = 100_000_000  # 100 megapixels

    def _safe_module_file(self, module_id: int, filename: str) -> Optional[Path]:
        """Resolve a stored image path, refusing anything outside the module folder."""
        if not isinstance(module_id, int) or module_id <= 0:
            return None
        base = (self.modules_path / str(module_id)).resolve()
        candidate = (base / Path(str(filename)).name).resolve()
        if candidate.parent != base:
            return None
        return candidate

    def _check_image_limits(self, source) -> bool:
        """Reject files that are too large on disk or too large in pixels."""
        from PyQt6.QtGui import QImageReader
        from config.constants import IMAGE_MAX_SIZE_BYTES
        try:
            if Path(source).stat().st_size > IMAGE_MAX_SIZE_BYTES:
                self.logger.error(f"Image exceeds size limit: {source}")
                return False
            size = QImageReader(str(source)).size()
            if size.isValid() and size.width() * size.height() > self.MAX_IMAGE_PIXELS:
                self.logger.error(f"Image exceeds pixel limit: {source}")
                return False
            return True
        except OSError:
            return False

    def get_image_path(self, module_id: int, filename: str) -> Optional[Path]:
        """Get the full path to an image file."""
        image_path = self._safe_module_file(module_id, filename)

        if image_path and image_path.exists():
            return image_path
        else:
            self.logger.warning(f"Image not found: {image_path}")
            return None

    def get_thumbnail_path(self, image_id: str) -> Optional[Path]:
        """Get the path to a thumbnail image."""
        thumbnail_path = self.thumbnails_path / f"{image_id}.jpg"

        if thumbnail_path.exists():
            return thumbnail_path
        else:
            return None

    def delete_image(self, module_id: int, filename: str) -> bool:
        """Delete an image and its thumbnail."""
        try:
            image_path = self._safe_module_file(module_id, filename)
            if image_path is None:
                self.logger.error(f"Refusing to delete unsafe image path: {module_id}/{filename}")
                return False

            # Delete main image
            if image_path.exists():
                image_path.unlink()

            # Delete thumbnail (extract ID from filename)
            image_id = image_path.stem
            thumbnail_path = self.thumbnails_path / f"{image_id}.jpg"
            # thumbnails are keyed by file name, so a restored copy in another module shares it
            still_used = any(
                (other / image_path.name).exists()
                for other in self.modules_path.iterdir() if other.is_dir()
            )
            if thumbnail_path.exists() and not still_used:
                thumbnail_path.unlink()

            # Clean up empty module directory
            module_path = self.modules_path / str(module_id)
            if module_path.exists() and not any(module_path.iterdir()):
                module_path.rmdir()

            self.logger.info(f"Deleted image: {filename} from module {module_id}")
            return True

        except Exception as e:
            self.logger.error(f"Error deleting image: {e}")
            return False

    def get_module_images(self, module_id: int) -> List[Dict[str, Any]]:
        """Get all images for a specific module."""
        images = []

        try:
            module_path = self.modules_path / str(module_id)

            if not module_path.exists():
                return images

            for image_file in module_path.iterdir():
                if image_file.suffix.lower() in self.supported_formats:
                    image_info = self._get_image_info(image_file)
                    thumbnail_path = self.get_thumbnail_path(image_file.stem)

                    images.append({
                        'filename': image_file.name,
                        'original_name': image_file.name,
                        'file_path': str(image_file),
                        'thumbnail_path': str(thumbnail_path) if thumbnail_path else None,
                        'file_size': image_file.stat().st_size,
                        'width': image_info.get('width', 0),
                        'height': image_info.get('height', 0),
                        'mime_type': image_info.get('mime_type', ''),
                        'modified_date': datetime.fromtimestamp(image_file.stat().st_mtime).isoformat(),
                    })

        except Exception as e:
            self.logger.error(f"Error getting module images: {e}")

        return images

    def get_document_images(self, module_id: int, document_id: int) -> List[Dict[str, Any]]:
        """Get images associated with a specific document."""
        # This would need to be implemented with database queries
        # For now, return all module images
        return self.get_module_images(module_id)

    def _get_image_info(self, image_path: Path) -> Dict[str, Any]:
        """Get information about an image file."""
        info = {}

        try:
            # Use QImage to get image information
            image = QImage(str(image_path))

            if not image.isNull():
                info['width'] = image.width()
                info['height'] = image.height()
                info['mime_type'] = self._get_mime_type(image_path)

        except Exception as e:
            self.logger.warning(f"Error getting image info for {image_path}: {e}")

        return info

    def _get_mime_type(self, image_path: Path) -> str:
        """Get MIME type for an image file."""
        extension = image_path.suffix.lower()

        mime_types = {
            '.png': 'image/png',
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.gif': 'image/gif',
            '.bmp': 'image/bmp',
            '.webp': 'image/webp',
        }

        return mime_types.get(extension, 'application/octet-stream')

    def _generate_thumbnail(self, image_path: Path, unique_id: str) -> Optional[Path]:
        """Generate a thumbnail for an image."""
        try:
            # Load image
            image = QImage(str(image_path))
            if image.isNull():
                return None

            # Create thumbnail
            thumbnail = image.scaled(
                self.thumbnail_size,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )

            # Save thumbnail
            thumbnail_path = self.thumbnails_path / f"{unique_id}.jpg"
            success = thumbnail.save(str(thumbnail_path), "JPG", self.thumbnail_quality)

            if success:
                return thumbnail_path
            else:
                self.logger.warning(f"Failed to save thumbnail: {thumbnail_path}")
                return None

        except Exception as e:
            self.logger.error(f"Error generating thumbnail: {e}")
            return None

    def cleanup_orphan_thumbnails(self) -> int:
        """Delete cached thumbnails whose image no longer exists (deleted campaigns/images). Returns the count."""
        try:
            existing = {f.stem for module_dir in self.modules_path.iterdir() if module_dir.is_dir()
                        for f in module_dir.iterdir() if f.suffix.lower() in self.supported_formats}
            removed = 0
            for thumb in self.thumbnails_path.iterdir():
                if thumb.is_file() and thumb.suffix.lower() == '.jpg' and thumb.stem not in existing:
                    thumb.unlink()
                    removed += 1
            if removed:
                self.logger.info(f"Removed {removed} orphan thumbnail(s)")
            return removed
        except Exception as e:
            self.logger.warning(f"Thumbnail cleanup skipped: {e}")
            return 0

    def get_supported_formats(self) -> List[str]:
        """Get list of supported image formats."""
        return [fmt.lstrip('.') for fmt in self.supported_formats]

    def get_thumbnail(self, image_path: str, size: int = 50) -> Optional[QPixmap]:
        """
        Get a small thumbnail pixmap for an image.

        Args:
            image_path: Path to the image file
            size: Thumbnail size in pixels (square)

        Returns:
            Scaled pixmap or None if failed
        """
        try:
            pixmap = QPixmap(image_path)
            if pixmap.isNull():
                return None

            # Scale to thumbnail size with smooth transformation
            thumbnail = pixmap.scaled(
                size, size,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )

            return thumbnail

        except Exception as e:
            self.logger.error(f"Error getting thumbnail: {e}")
            return None

    def regenerate_thumbnails_for_module(self, module_id: int) -> int:
        """
        Regenerate cached thumbnail JPGs for all images in a module directory.
        Called after restore to rebuild the thumbnail cache.

        Args:
            module_id: Module ID whose images need thumbnails

        Returns:
            Number of thumbnails successfully generated
        """
        count = 0
        module_path = self.modules_path / str(module_id)

        if not module_path.exists():
            return 0

        for image_file in module_path.iterdir():
            if image_file.suffix.lower() in self.supported_formats:
                unique_id = image_file.stem
                thumbnail_path = self.thumbnails_path / f"{unique_id}.jpg"
                if not thumbnail_path.exists():
                    result = self._generate_thumbnail(image_file, unique_id)
                    if result:
                        count += 1

        self.logger.info(f"Regenerated {count} thumbnails for module {module_id}")
        return count

    def delete_module_images(self, module_id: int) -> bool:
        """
        Delete all image files for a specific module.

        Args:
            module_id: ID of the module

        Returns:
            True if successful, False otherwise
        """
        try:
            module_path = self.modules_path / str(module_id)

            if not module_path.exists():
                self.logger.info(f"No image directory found for module {module_id}")
                return True

            # Remove the entire module directory and all its contents
            shutil.rmtree(module_path)
            self.logger.info(f"Deleted image directory for module {module_id}: {module_path}")

            return True

        except Exception as e:
            self.logger.error(f"Error deleting images for module {module_id}: {e}", exc_info=True)
            return False

    def save_image_from_bytes(self, image_data: bytes, module_id: int,
                              original_filename: str = "pasted_image.png",
                              document_id: Optional[int] = None) -> Optional[Dict[str, Any]]:
        """
        Save an image from raw bytes (e.g., from clipboard or drag & drop).

        Args:
            image_data: Raw image data as bytes
            module_id: ID of the associated module
            original_filename: Name to use for the image
            document_id: Optional ID of the associated document

        Returns:
            Dictionary with image metadata or None if failed
        """
        try:
            from config.constants import IMAGE_MAX_SIZE_BYTES
            if not isinstance(module_id, int) or module_id <= 0:
                self.logger.error(f"Invalid module_id: {module_id}")
                return None
            if len(image_data) > IMAGE_MAX_SIZE_BYTES:
                self.logger.error("Image data exceeds size limit")
                return None

            # Create QImage from bytes
            image = QImage()
            if not image.loadFromData(image_data):
                self.logger.error("Failed to load image from bytes")
                return None

            if image.width() * image.height() > self.MAX_IMAGE_PIXELS:
                self.logger.error("Image exceeds pixel limit")
                return None

            # Generate unique filename
            file_extension = Path(original_filename).suffix.lower()
            if not file_extension or file_extension not in self.supported_formats:
                file_extension = '.png'  # Default to PNG

            unique_id = str(uuid.uuid4())
            new_filename = f"{unique_id}{file_extension}"

            # Create module directory
            module_path = self.modules_path / str(module_id)
            module_path.mkdir(exist_ok=True)

            # Save image to file
            destination_path = module_path / new_filename

            if not image.save(str(destination_path)):
                self.logger.error(f"Failed to save image to {destination_path}")
                return None

            # Generate thumbnail
            thumbnail_path = self._generate_thumbnail(destination_path, unique_id)

            # Get file info
            file_size = destination_path.stat().st_size
            mime_type = self._get_mime_type(destination_path)

            return {
                'filename': new_filename,
                'original_name': original_filename,
                'file_path': str(destination_path),
                'file_size': file_size,
                'mime_type': mime_type,
                'module_id': module_id,
                'document_id': document_id,
                'thumbnail_path': str(thumbnail_path) if thumbnail_path else None
            }

        except Exception as e:
            self.logger.error(f"Failed to save image from bytes: {e}", exc_info=True)
            return None

    def validate_file_size(self, file_path: str, max_size_mb: int = 10) -> Tuple[bool, Optional[str]]:
        """
        Validate that an image file doesn't exceed the maximum size.

        Args:
            file_path: Path to the image file
            max_size_mb: Maximum allowed size in megabytes

        Returns:
            Tuple of (is_valid, error_message)
        """
        try:
            path = Path(file_path)
            if not path.exists():
                return False, "File does not exist"

            file_size = path.stat().st_size
            max_size_bytes = max_size_mb * 1024 * 1024

            if file_size > max_size_bytes:
                size_mb = file_size / (1024 * 1024)
                return False, f"File size ({size_mb:.1f} MB) exceeds maximum allowed size ({max_size_mb} MB)"

            return True, None

        except Exception as e:
            self.logger.error(f"Error validating file size: {e}")
            return False, str(e)

    def get_image_from_clipboard(self) -> Optional[bytes]:
        """
        Get image data from the system clipboard.

        Returns:
            Image data as bytes, or None if no image in clipboard
        """
        try:
            clipboard = QGuiApplication.clipboard()
            mime_data = clipboard.mimeData()

            if mime_data.hasImage():
                image = QImage(mime_data.imageData())
                if image.isNull():
                    return None

                # Convert to bytes (PNG format)
                buffer = QBuffer()
                buffer.open(QIODevice.OpenModeFlag.WriteOnly)
                image.save(buffer, "PNG")
                return buffer.data().data()

            return None

        except Exception as e:
            self.logger.error(f"Error getting image from clipboard: {e}", exc_info=True)
            return None