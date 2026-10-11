"""
Backup and restore service for RPG Database Manager modules.

Exports module data from the main database to JSON format and packs
it with images into ZIP archives. Restores by importing JSON data
back into the main database with proper ID remapping.
"""

import os
import json
import hashlib
import zipfile
import re
import shutil
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple, Callable
from datetime import datetime

from config.paths import get_data_dir

from utils.logger import get_logger


class BackupService:
    """
    Service for backing up and restoring modules.

    Creates ZIP archives containing:
    - Module data exported as JSON from main database
    - All associated images
    - Metadata JSON with backup information
    """

    BACKUP_VERSION = "2.0"  # Updated version for JSON export format

    # Restore safety limits (guard against zip bombs / junk archives)
    MAX_ZIP_ENTRIES = 20000
    MAX_ENTRY_BYTES = 100 * 1024 * 1024
    MAX_TOTAL_BYTES = 2 * 1024 * 1024 * 1024
    MAX_JSON_BYTES = 100 * 1024 * 1024
    SAFE_IMAGE_NAME = re.compile(r'[\w][\w .()\-]{0,150}')
    WINDOWS_DEVICE_NAMES = frozenset({'CON', 'PRN', 'AUX', 'NUL'} | {f'COM{i}' for i in range(1, 10)}
                                     | {f'LPT{i}' for i in range(1, 10)})
    ALLOWED_IMAGE_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp', '.tiff'}

    @classmethod
    def _check_zip_limits(cls, zf: zipfile.ZipFile) -> None:
        """Raise ValueError if the archive exceeds sane size/entry limits."""
        infos = zf.infolist()
        if len(infos) > cls.MAX_ZIP_ENTRIES:
            raise ValueError(f"Backup has too many entries ({len(infos)})")
        total = 0
        for info in infos:
            limit = cls.MAX_JSON_BYTES if info.filename.endswith('.json') else cls.MAX_ENTRY_BYTES
            if info.file_size > limit:
                raise ValueError(f"Backup entry too large: {info.filename}")
            total += info.file_size
        if total > cls.MAX_TOTAL_BYTES:
            raise ValueError("Backup is too large when uncompressed")

    @classmethod
    def _read_capped(cls, zf: zipfile.ZipFile, name, limit: int) -> bytes:
        """Read an entry but never more than ``limit`` bytes, whatever the zip header claims."""
        with zf.open(name) as src:
            data = src.read(limit + 1)
        if len(data) > limit:
            raise ValueError(f"Backup entry too large: {getattr(name, 'filename', name)}")
        return data

    @classmethod
    def _read_json_text(cls, zf: zipfile.ZipFile, name: str) -> str:
        return cls._read_capped(zf, name, cls.MAX_JSON_BYTES).decode('utf-8')

    @classmethod
    def _copy_capped(cls, src, dst, limit: int) -> None:
        copied = 0
        while True:
            chunk = src.read(1024 * 1024)
            if not chunk:
                return
            copied += len(chunk)
            if copied > limit:
                raise ValueError("Backup image too large")
            dst.write(chunk)

    @classmethod
    def _image_entries(cls, zf: zipfile.ZipFile) -> List[Tuple[str, str]]:
        """Return (zip entry, safe filename) pairs for valid, unique image entries."""
        seen = set()
        result = []
        for name in zf.namelist():
            if not name.startswith('images/'):
                continue
            filename = name[len('images/'):]
            if (not cls.SAFE_IMAGE_NAME.fullmatch(filename)  # no separators, drive letters or ADS colons
                    or filename.endswith(('.', ' '))
                    or filename.split('.')[0].upper() in cls.WINDOWS_DEVICE_NAMES
                    or Path(filename).suffix.lower() not in cls.ALLOWED_IMAGE_EXTENSIONS
                    or filename in seen):
                continue
            seen.add(filename)
            result.append((name, filename))
        return result

    def __init__(self, db_manager, image_service):
        """
        Initialize backup service.

        Args:
            db_manager: DatabaseManager instance
            image_service: ImageService instance
        """
        self.db = db_manager
        self.image_service = image_service
        self.logger = get_logger('backup_service')
        self._progress: Optional[Callable[[str], None]] = None  # set per operation, see _report()

        # Get base paths
        self.base_path = get_data_dir()
        self.images_path = self.base_path / "rpg_images" / "modules"

    def _report(self, message: str) -> None:
        """Tell the caller which stage is running (the GUI shows it while a worker thread runs)."""
        self.logger.info(message)
        callback = self._progress
        if callback is not None:
            try:
                callback(message)
            except Exception:  # a broken progress display must never break a backup/restore
                pass

    def backup_module(self, module_id: int, output_path: str,
                      progress: Optional[Callable[[str], None]] = None) -> Tuple[bool, str, int]:
        """
        Create a backup ZIP file for a module by exporting data to JSON.

        Args:
            module_id: ID of the module to backup
            output_path: Path where ZIP file should be created

        Returns:
            Tuple of (success: bool, message: str, missing_images_count: int)
        """
        previous_progress = self._progress     # a nested call (safety snapshot) must not drop the caller's callback
        if progress is not None:
            self._progress = progress
        try:
            self.logger.info(f"Starting backup of module {module_id} to {output_path}")
            self._report("Exporting module data...")

            # Get module information
            module = self.db.get_module(module_id)
            if not module:
                return False, f"Module {module_id} not found", 0

            # Export all module data from main database
            module_data = self._export_module_data(module_id)
            if not module_data:
                return False, "Failed to export module data", 0

            # Get all images for this module
            self._report("Collecting images...")
            images = self._get_module_images(module_id)

            # Create backup metadata
            metadata = {
                'module_name': module.get('name', 'Unknown'),
                'backup_date': datetime.now().isoformat(),
                'original_module_id': module_id,
                'image_count': len(images),
                'document_count': len(module_data.get('documents', [])),
                'session_count': len(module_data.get('game_sessions', [])),
                'backup_version': self.BACKUP_VERSION
            }

            # Create ZIP file
            self._report("Writing backup file...")
            success, message, missing_count = self._create_zip_backup(
                output_path,
                module_data,
                images,
                metadata
            )

            if success:
                self.logger.info(f"Successfully backed up module {module_id}")
                included = len(images) - missing_count
                summary = f"Backup created with {included} images and {metadata['document_count']} documents"
                return True, summary, missing_count
            else:
                return False, message, 0

        except Exception as e:
            error_msg = f"Error backing up module: {e}"
            self.logger.error(error_msg, exc_info=True)
            return False, error_msg, 0
        finally:
            self._progress = previous_progress

    def _export_module_data(self, module_id: int) -> Optional[Dict[str, Any]]:
        """
        Export all module data from main database to a dictionary.

        Args:
            module_id: ID of the module to export

        Returns:
            Dictionary with all module data or None on error
        """
        try:
            with self.db.connection.transaction() as conn:
                # Get module info
                module_row = conn.execute(
                    "SELECT * FROM modules WHERE id = ?",
                    (module_id,)
                ).fetchone()

                if not module_row:
                    return None

                module_info = dict(module_row)

                # Get all documents
                documents = [
                    dict(row) for row in conn.execute(
                        "SELECT * FROM documents WHERE module_id = ?",
                        (module_id,)
                    ).fetchall()
                ]

                # Get all game sessions
                game_sessions = [
                    dict(row) for row in conn.execute(
                        "SELECT * FROM game_sessions WHERE module_id = ?",
                        (module_id,)
                    ).fetchall()
                ]

                # Get all images
                images = [
                    dict(row) for row in conn.execute(
                        "SELECT * FROM images WHERE module_id = ?",
                        (module_id,)
                    ).fetchall()
                ]

                # Get all relationships (where both documents belong to this module)
                relationships = [
                    dict(row) for row in conn.execute("""
                        SELECT dr.* FROM document_relationships dr
                        INNER JOIN documents d1 ON dr.from_document_id = d1.id
                        INNER JOIN documents d2 ON dr.to_document_id = d2.id
                        WHERE d1.module_id = ? AND d2.module_id = ?
                    """, (module_id, module_id)).fetchall()
                ]

                self.logger.info(
                    f"Exported module data: {len(documents)} docs, {len(game_sessions)} sessions, "
                    f"{len(images)} images, {len(relationships)} relationships"
                )

                # Custom entity types used by this module's documents, so a restore
                # on another install keeps those documents visible
                used_types = {d['entity_type'] for d in documents}
                entity_types = [
                    dict(row) for row in conn.execute(
                        "SELECT key, label_singular, label_plural FROM entity_types WHERE builtin = 0"
                    ).fetchall() if row['key'] in used_types
                ]

                return {
                    'module_info': module_info,
                    'entity_types': entity_types,
                    'documents': documents,
                    'game_sessions': game_sessions,
                    'images': images,
                    'document_relationships': relationships
                }

        except Exception as e:
            self.logger.error(f"Error exporting module data: {e}", exc_info=True)
            return None

    def _get_module_images(self, module_id: int) -> List[Dict[str, Any]]:
        """
        Get all image file paths for a module.

        Args:
            module_id: ID of the module

        Returns:
            List of dicts with 'file_path' and 'filename' keys
        """
        try:
            with self.db.connection.transaction() as conn:
                cursor = conn.execute("""
                    SELECT file_path, filename, original_name
                    FROM images
                    WHERE module_id = ?
                """, (module_id,))

                images = []
                for row in cursor.fetchall():
                    row_dict = dict(row)
                    file_path = row_dict.get('file_path')

                    # Verify file exists
                    if file_path and os.path.exists(file_path):
                        images.append({
                            'file_path': file_path,
                            'filename': row_dict.get('filename', ''),
                            'original_name': row_dict.get('original_name', '')
                        })
                    else:
                        self.logger.warning(f"Image file not found: {file_path}")

                return images

        except Exception as e:
            self.logger.error(f"Error getting module images: {e}", exc_info=True)
            return []

    def _create_zip_backup(self, zip_path: str, module_data: Dict[str, Any],
                          images: List[Dict[str, Any]], metadata: Dict[str, Any]) -> Tuple[bool, str, int]:
        """
        Create ZIP file with module data JSON, images, and metadata.

        Args:
            zip_path: Path for output ZIP file
            module_data: Dictionary with all module data
            images: List of image dicts with file_path and filename
            metadata: Backup metadata dict

        Returns:
            Tuple of (success: bool, message: str, missing_images_count: int)
        """
        try:
            # Convert Path objects to strings for Python 3.13 compatibility
            final_path = str(zip_path)
            # Write next to the target and rename at the end: a crash or full disk never leaves
            # a truncated file under the real name (or destroys an older backup)
            zip_path_str = final_path + '.part'

            # Create ZIP file
            with zipfile.ZipFile(zip_path_str, 'w', zipfile.ZIP_DEFLATED) as zf:
                # Add module data as JSON
                module_data_json = json.dumps(module_data, indent=2, default=str)
                zf.writestr('module_data.json', module_data_json)
                self.logger.debug("Added module_data.json to ZIP")

                # Add metadata
                metadata_json = json.dumps(metadata, indent=2)
                zf.writestr('metadata.json', metadata_json)
                self.logger.debug("Added metadata.json to ZIP")

                # Add images
                missing_images = 0
                missing_paths = []
                for img in images:
                    img_path = img['file_path']
                    img_filename = img['filename']

                    if os.path.exists(img_path):
                        # Use forward slashes in ZIP paths (Windows compatibility)
                        zip_img_path = f'images/{img_filename}'
                        zf.write(str(img_path), zip_img_path)
                    else:
                        missing_images += 1
                        missing_paths.append(img_path)
                        self.logger.warning(f"Image file missing during backup: {img_path}")

                if missing_images > 0:
                    self.logger.warning(f"Skipped {missing_images} missing images during backup")

            # Verify ZIP was created, then move it into place
            if not os.path.exists(zip_path_str):
                return False, "ZIP file was not created", 0
            os.replace(zip_path_str, final_path)
            zip_path_str = final_path

            file_size = os.path.getsize(zip_path_str)
            size_mb = file_size / (1024 * 1024)

            message = f"Backup created: {size_mb:.2f} MB"
            if missing_images > 0:
                message += f" ({missing_images} image files were missing from disk and not included)"

            return True, message, missing_images

        except Exception as e:
            error_msg = f"Error creating ZIP backup: {e}"
            self.logger.error(error_msg, exc_info=True)
            try:
                os.remove(str(zip_path) + '.part')  # do not leave a half-written file next to the target
            except OSError:
                pass
            return False, error_msg, 0

    def validate_backup(self, zip_path: str) -> Tuple[bool, Optional[Dict[str, Any]], str]:
        """
        Validate a backup ZIP file and extract metadata.

        Args:
            zip_path: Path to backup ZIP file

        Returns:
            Tuple of (is_valid: bool, metadata: dict or None, message: str)
        """
        try:
            if not os.path.exists(zip_path):
                return False, None, "Backup file not found"

            zip_path_str = str(zip_path)

            # Check if it's a valid ZIP
            if not zipfile.is_zipfile(zip_path_str):
                return False, None, "File is not a valid ZIP archive"

            # Open and check contents
            with zipfile.ZipFile(zip_path_str, 'r') as zf:
                self._check_zip_limits(zf)
                file_list = zf.namelist()

                # Check required files
                if 'module_data.json' not in file_list:
                    return False, None, "Missing module_data.json in backup"

                if 'metadata.json' not in file_list:
                    return False, None, "Missing metadata.json in backup"

                # Read and parse metadata
                metadata_str = self._read_json_text(zf, 'metadata.json')
                metadata = json.loads(metadata_str)

                # Validate metadata structure
                required_keys = ['module_name', 'backup_date', 'backup_version']
                for key in required_keys:
                    if key not in metadata:
                        return False, None, f"Invalid metadata: missing {key}"

                # Count images
                image_files = [f for f in file_list if f.startswith('images/')]
                metadata['actual_image_count'] = len(image_files)

                return True, metadata, "Backup is valid"

        except json.JSONDecodeError as e:
            return False, None, f"Invalid metadata JSON: {e}"
        except ValueError as e:
            return False, None, str(e)
        except Exception as e:
            error_msg = f"Error validating backup: {e}"
            self.logger.error(error_msg, exc_info=True)
            return False, None, error_msg

    def restore_module(self, zip_path: str, restore_mode: str,
                      target_module_id: Optional[int] = None,
                      progress: Optional[Callable[[str], None]] = None) -> Tuple[bool, Optional[int], str]:
        """
        Restore a module from a backup ZIP file.

        Args:
            zip_path: Path to backup ZIP file
            restore_mode: Either "new" or "overwrite"
            target_module_id: Module ID to overwrite (required if restore_mode is "overwrite")

        Returns:
            Tuple of (success: bool, module_id: int or None, message: str)
        """
        previous_progress = self._progress     # a nested call (safety snapshot) must not drop the caller's callback
        if progress is not None:
            self._progress = progress
        try:
            self.logger.info(f"Starting restore from {zip_path} in {restore_mode} mode")

            # Validate backup
            self._report("Validating backup...")
            is_valid, metadata, validation_msg = self.validate_backup(zip_path)
            if not is_valid:
                return False, None, f"Invalid backup: {validation_msg}"

            # Handle restore based on mode
            if restore_mode == "new":
                result = self._restore_as_new_module(zip_path, metadata)
            elif restore_mode == "overwrite":
                if target_module_id is None:
                    return False, None, "target_module_id required for overwrite mode"
                result = self._restore_overwrite_module(zip_path, metadata, target_module_id)
            else:
                return False, None, f"Invalid restore mode: {restore_mode}"

            if result[0]:
                self._refresh_entity_type_registry()
            return result

        except Exception as e:
            error_msg = f"Error restoring module: {e}"
            self.logger.error(error_msg, exc_info=True)
            return False, None, error_msg
        finally:
            self._progress = previous_progress

    def _restore_as_new_module(self, zip_path: str, metadata: Dict[str, Any]) -> Tuple[bool, Optional[int], str]:
        """
        Restore backup as a new module with ID remapping.

        Args:
            zip_path: Path to backup ZIP file
            metadata: Backup metadata

        Returns:
            Tuple of (success: bool, new_module_id: int or None, message: str)
        """
        try:
            # Read module data from ZIP
            self._report("Reading backup...")
            module_data = self._read_module_data_from_zip(zip_path)
            if not module_data:
                return False, None, "Failed to read module data from backup"

            original_name = metadata.get('module_name', 'Unknown')
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            new_module_name = f"{original_name}_restored_{timestamp}"

            # Create new module entry in main database
            new_module_id = self.db.create_module(new_module_name)
            if new_module_id is None:
                return False, None, "Failed to create new module entry"

            # Import all data with ID remapping
            self._report("Importing documents and sessions...")
            success, message = self._import_module_data(module_data, new_module_id)
            if not success:
                # Cleanup on failure
                self.db.soft_delete_module(new_module_id)
                return False, None, f"Import failed: {message}"

            # Extract and copy images
            self._report("Extracting images...")
            success, message = self._extract_images(zip_path, new_module_id)
            image_warning = ""
            if not success:
                self.logger.warning(f"Image extraction had issues: {message}")
                image_warning = f" WARNING: some images could not be restored ({message})."

            # Regenerate thumbnail cache for restored images
            self._report("Generating thumbnails...")
            self.image_service.regenerate_thumbnails_for_module(new_module_id)

            return True, new_module_id, f"Module restored as '{new_module_name}'.{image_warning}"

        except Exception as e:
            error_msg = f"Error restoring as new module: {e}"
            self.logger.error(error_msg, exc_info=True)
            return False, None, error_msg

    def _restore_overwrite_module(self, zip_path: str, metadata: Dict[str, Any],
                                 target_module_id: int) -> Tuple[bool, Optional[int], str]:
        """
        Restore backup by overwriting an existing module.

        Safe order: extract images to temp dir first (verifies ZIP is readable),
        then delete old data, import new data, move images into place.
        If image extraction fails before deletion, the existing module is untouched.

        Args:
            zip_path: Path to backup ZIP file
            metadata: Backup metadata
            target_module_id: ID of module to overwrite

        Returns:
            Tuple of (success: bool, module_id: int or None, message: str)
        """
        import tempfile
        temp_dir = None
        snapshot_dir = None
        keep_snapshot = False  # set when a rollback failed: the snapshot is then the only copy
        try:
            # Verify target module exists
            target_module = self.db.get_module(target_module_id)
            if not target_module:
                return False, None, f"Target module {target_module_id} not found"

            target_name = target_module.get('name', 'Unknown')

            # Read module data from ZIP first (fail early before touching existing data)
            self._report("Reading backup...")
            module_data = self._read_module_data_from_zip(zip_path)
            if not module_data:
                return False, None, "Failed to read module data from backup"

            # Extract images to a temporary directory BEFORE deleting existing data.
            # This ensures the ZIP is valid and images are accessible before we lose anything.
            self._report("Extracting images...")
            temp_dir = tempfile.mkdtemp(prefix='rpg_restore_')
            try:
                with zipfile.ZipFile(str(zip_path), 'r') as zf:
                    self._check_zip_limits(zf)
                    image_files = self._image_entries(zf)
                    for entry, filename in image_files:
                        with zf.open(entry) as src, open(Path(temp_dir) / filename, 'wb') as dst:
                            self._copy_capped(src, dst, self.MAX_ENTRY_BYTES)
                self.logger.info(f"Pre-extracted {len(image_files)} image entries to temp dir")
            except Exception as e:
                shutil.rmtree(temp_dir, ignore_errors=True)
                return False, None, f"Failed to read images from backup ZIP: {e}"

            # Safety snapshot of the current module so a failed import can be rolled back
            self._report("Creating safety snapshot of the current module...")
            # (own private directory: kept apart from the extracted images, and no racy mktemp name)
            snapshot_dir = tempfile.mkdtemp(prefix='rpg_snapshot_')
            snapshot_zip_final = str(Path(snapshot_dir) / 'snapshot.zip')
            snap_ok, snap_msg, _ = self.backup_module(target_module_id, snapshot_zip_final)
            if not snap_ok:
                return False, None, f"Could not create safety snapshot, nothing was changed: {snap_msg}"

            try:
                # ZIP is valid and images are extracted — safe to replace existing data now
                self._report("Replacing module data...")
                self._delete_module_data(target_module_id)

                # Import all data
                success, message = self._import_module_data(module_data, target_module_id)
            except Exception as e:
                success, message = False, str(e)

            if not success:
                restored = self._rollback_from_snapshot(snapshot_zip_final, target_module_id)
                if not restored:
                    keep_snapshot = True
                suffix = "Previous module data was restored." if restored else (
                    f"Automatic rollback failed; a snapshot of the previous data was kept at {snapshot_zip_final}")
                return False, None, f"Import failed: {message}. {suffix}"

            # Put the images in place without destroying the old ones until the new ones are there
            module_images_dir = self.images_path / str(target_module_id)
            try:
                self._swap_images_dir(Path(temp_dir), module_images_dir)
            except Exception as e:
                self.logger.error(f"Could not place restored images: {e}", exc_info=True)
                restored = self._rollback_from_snapshot(snapshot_zip_final, target_module_id)
                if not restored:
                    keep_snapshot = True
                    return False, None, (f"Could not place the restored images ({e}) and the automatic rollback "
                                         f"failed. A snapshot of the previous data was kept at {snapshot_zip_final}")
                return False, None, f"Could not place the restored images ({e}). Previous module data was restored."

            # Regenerate thumbnail cache for restored images
            self._report("Generating thumbnails...")
            self.image_service.regenerate_thumbnails_for_module(target_module_id)

            return True, target_module_id, f"Module '{target_name}' overwritten successfully"

        except Exception as e:
            error_msg = f"Error overwriting module: {e}"
            self.logger.error(error_msg, exc_info=True)
            return False, None, error_msg
        finally:
            if temp_dir:
                shutil.rmtree(temp_dir, ignore_errors=True)
            if snapshot_dir and not keep_snapshot:
                shutil.rmtree(snapshot_dir, ignore_errors=True)

    @staticmethod
    def _swap_images_dir(new_dir: Path, target: Path) -> None:
        """Replace ``target`` by the contents of ``new_dir``; the old folder comes back on failure."""
        staging = target.with_name(target.name + '.new')
        backup = target.with_name(target.name + '.old')
        for leftover in (staging, backup):
            if leftover.exists():
                shutil.rmtree(leftover)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(new_dir, staging)
        had_old = target.exists()
        try:
            if had_old:
                os.replace(target, backup)
            os.replace(staging, target)
        except Exception:
            if had_old and backup.exists() and not target.exists():
                os.replace(backup, target)
            shutil.rmtree(staging, ignore_errors=True)
            raise
        shutil.rmtree(backup, ignore_errors=True)

    def _refresh_entity_type_registry(self) -> None:
        """Reload entity types after a restore may have added custom ones."""
        try:
            from config.entity_types import get_registry
            get_registry().load_overrides(self.db.get_entity_types())
        except Exception as e:
            self.logger.warning(f"Could not refresh entity types after restore: {e}")

    MAX_NEW_ENTITY_TYPES = 20

    def _ensure_entity_types(self, conn, module_data: Dict[str, Any]) -> None:
        """Register custom entity types referenced by a backup that this install lacks."""
        from config.entity_types import builtin_keys, RESERVED_KEYS, is_valid_key
        from utils.text_utils import TextUtils

        known = set(builtin_keys()) | set(RESERVED_KEYS) | {'session'}
        labels = {}
        for t in module_data.get('entity_types', []) or []:
            if isinstance(t, dict) and isinstance(t.get('key'), str):
                labels[t['key']] = (str(t.get('label_singular') or ''), str(t.get('label_plural') or ''))

        keys = {d.get('entity_type') for d in module_data.get('documents', []) if isinstance(d, dict)}
        next_order = conn.execute("SELECT COALESCE(MAX(sort_order), 0) + 1 FROM entity_types").fetchone()[0]
        added = 0
        for key in sorted(k for k in keys if isinstance(k, str)):
            if key in known or not is_valid_key(key):
                continue
            if conn.execute("SELECT 1 FROM entity_types WHERE key = ?", (key,)).fetchone():
                continue
            added += 1
            if added > self.MAX_NEW_ENTITY_TYPES:  # a hostile backup cannot flood the type list
                self.logger.warning("Backup defines too many new entity types; the rest are ignored")
                break
            singular, plural = labels.get(key, ('', ''))
            fallback = key.replace('_', ' ').title()
            if not singular or not TextUtils.validate_entity_name(singular, max_length=50)['valid']:
                singular = fallback
            if not plural or not TextUtils.validate_entity_name(plural, max_length=50)['valid']:
                plural = singular + 's'
            conn.execute(
                "INSERT INTO entity_types (key, label_singular, label_plural, sort_order, hidden, builtin) "
                "VALUES (?, ?, ?, ?, 0, 0)", (key, singular, plural, next_order))
            next_order += 1

    def _rollback_from_snapshot(self, snapshot_zip: str, module_id: int) -> bool:
        """Restore a module from a safety snapshot after a failed overwrite."""
        try:
            data = self._read_module_data_from_zip(snapshot_zip)
            if not data:
                return False
            self._delete_module_data(module_id)
            ok, _ = self._import_module_data(data, module_id)
            if not ok:
                return False
            images_ok, _ = self._extract_images(snapshot_zip, module_id)
            if not images_ok:
                return False
            self.image_service.regenerate_thumbnails_for_module(module_id)
            return True
        except Exception as e:
            self.logger.error(f"Rollback from snapshot failed: {e}", exc_info=True)
            return False

    def _read_module_data_from_zip(self, zip_path: str) -> Optional[Dict[str, Any]]:
        """
        Read module_data.json from ZIP file.

        Args:
            zip_path: Path to ZIP file

        Returns:
            Module data dictionary or None on error
        """
        try:
            with zipfile.ZipFile(str(zip_path), 'r') as zf:
                module_data_str = self._read_json_text(zf, 'module_data.json')
                return json.loads(module_data_str)
        except Exception as e:
            self.logger.error(f"Error reading module data from ZIP: {e}", exc_info=True)
            return None

    _EMBEDDED_ID_KEYS = ('faction_id', 'module_doc_id', 'parent_document_id')   # parent: owner of an inventory/ability item
    _RPG_LINK_RE = re.compile(r'(rpg://\w+/)(\d+)')

    def _remap_embedded_document_ids(self, conn, doc_id_mapping: Dict[int, int]) -> None:
        """Rewrite old document ids stored in restored documents' metadata and rpg:// links."""
        if not doc_id_mapping:
            return
        for new_id in doc_id_mapping.values():
            row = conn.execute("SELECT content, metadata FROM documents WHERE id = ?", (new_id,)).fetchone()
            if row is None:
                continue
            content, metadata = row[0], row[1]
            new_content = self._RPG_LINK_RE.sub(
                lambda m: m.group(1) + str(doc_id_mapping.get(int(m.group(2)), int(m.group(2)))),
                content or '')
            new_metadata = metadata
            if metadata:
                try:
                    data = json.loads(metadata)
                except (TypeError, ValueError):
                    data = None
                if isinstance(data, dict):
                    for key in self._EMBEDDED_ID_KEYS:
                        if isinstance(data.get(key), int) and data[key] in doc_id_mapping:
                            data[key] = doc_id_mapping[data[key]]
                    # keep "not edited since import" detection valid for imported modules
                    if (new_content != (content or '') and data.get('imported_final_hash')
                            == hashlib.sha1((content or '').encode('utf-8'), usedforsecurity=False).hexdigest()):
                        data['imported_final_hash'] = hashlib.sha1(new_content.encode('utf-8'), usedforsecurity=False).hexdigest()
                    new_metadata = json.dumps(data)
            if new_content != (content or '') or new_metadata != metadata:
                conn.execute("UPDATE documents SET content = ?, metadata = ? WHERE id = ?",
                             (new_content, new_metadata, new_id))

    def _import_module_data(self, module_data: Dict[str, Any], new_module_id: int) -> Tuple[bool, str]:
        """
        Import module data into main database with ID remapping.

        Args:
            module_data: Dictionary with all module data
            new_module_id: ID of the new/target module

        Returns:
            Tuple of (success: bool, message: str)
        """
        from utils.text_utils import TextUtils
        from utils.security_utils import get_security_validator

        validator = get_security_validator()

        try:
            with self.db.connection.transaction() as conn:
                # Make sure custom entity types used by the backup exist (untrusted input)
                self._ensure_entity_types(conn, module_data)

                # Track old ID to new ID mapping for documents
                doc_id_mapping = {}

                # Import documents (untrusted data from the ZIP's JSON - validate before insert)
                for doc in module_data.get('documents', []):
                    old_doc_id = doc['id']

                    entity_type = doc.get('entity_type', '')
                    title = doc.get('title', '')
                    content = doc.get('content', '')
                    metadata = doc.get('metadata')

                    if not TextUtils.validate_entity_name(str(entity_type), max_length=50)['valid'] or \
                       not TextUtils.validate_entity_name(str(title), max_length=255)['valid'] or \
                       not validator.validate_text_content(str(content))['valid'] or \
                       (metadata and not validator.validate_json_input(str(metadata))['valid']):
                        self.logger.warning(f"Skipping invalid document in backup restore (old id={old_doc_id})")
                        continue

                    cursor = conn.execute("""
                        INSERT INTO documents (module_id, entity_type, title, content, metadata,
                                             created_date, modified_date, created_by, status)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        new_module_id,
                        entity_type,
                        title,
                        content,
                        metadata,
                        doc.get('created_date'),
                        doc.get('modified_date'),
                        doc.get('created_by', 'user'),
                        doc.get('status', 'draft')
                    ))
                    doc_id_mapping[old_doc_id] = cursor.lastrowid

                # Track session ID mapping
                session_id_mapping = {}

                # Import game sessions (untrusted data from the ZIP's JSON - validate before insert)
                for session in module_data.get('game_sessions', []):
                    old_session_id = session['id']

                    title = session.get('title', '')
                    content = session.get('content', '')

                    if not TextUtils.validate_entity_name(str(title), max_length=255)['valid'] or \
                       not validator.validate_text_content(str(content))['valid']:
                        self.logger.warning(f"Skipping invalid session in backup restore (old id={old_session_id})")
                        continue

                    cursor = conn.execute("""
                        INSERT INTO game_sessions (module_id, session_date, title, content,
                                                  participants, duration_minutes, created_date, status)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        new_module_id,
                        session.get('session_date'),
                        title,
                        content,
                        session.get('participants'),
                        session.get('duration_minutes'),
                        session.get('created_date'),
                        session.get('status', 'planned')
                    ))
                    session_id_mapping[old_session_id] = cursor.lastrowid

                # Import images (untrusted data from the ZIP's JSON - filename must be
                # reduced to a bare basename and re-validated so the DB-stored file_path
                # can never escape self.images_path, e.g. via '..' segments)
                allowed_image_extensions = sorted(self.ALLOWED_IMAGE_EXTENSIONS)
                for img in module_data.get('images', []):
                    old_doc_id = img.get('document_id')
                    new_doc_id = doc_id_mapping.get(old_doc_id) if old_doc_id else None

                    raw_filename = img.get('filename', '')
                    filename = os.path.basename(str(raw_filename))
                    filename_check = TextUtils.validate_file_path(filename, allowed_extensions=allowed_image_extensions)
                    if not filename_check['valid']:
                        self.logger.warning(
                            f"Skipping image with invalid filename in backup restore: "
                            f"{raw_filename!r} — {filename_check['issues']}"
                        )
                        continue

                    original_name = img.get('original_name') or filename
                    if not TextUtils.validate_entity_name(str(original_name), max_length=255)['valid']:
                        original_name = filename

                    description = img.get('description')
                    if description and not validator.validate_text_content(str(description))['valid']:
                        self.logger.warning(f"Dropping invalid image description on restore for {filename!r}")
                        description = None

                    # file_path now derives from a sanitized bare filename, so it is
                    # guaranteed to stay under self.images_path / new_module_id
                    new_file_path = str(self.images_path / str(new_module_id) / filename)

                    conn.execute("""
                        INSERT INTO images (module_id, document_id, filename, original_name,
                                          file_path, file_size, mime_type, description,
                                          is_primary, uploaded_date)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        new_module_id,
                        new_doc_id,
                        filename,
                        original_name,
                        new_file_path,
                        img.get('file_size'),
                        img.get('mime_type'),
                        description,
                        img.get('is_primary', 0),
                        img.get('uploaded_date')
                    ))

                # Document ids also live inside metadata (faction_id, module_doc_id) and in
                # rpg://type/id links in the text; point them at the restored documents.
                self._remap_embedded_document_ids(conn, doc_id_mapping)

                # Import document relationships with ID remapping
                for rel in module_data.get('document_relationships', []):
                    old_from_id = rel.get('from_document_id')
                    old_to_id = rel.get('to_document_id')

                    new_from_id = doc_id_mapping.get(old_from_id)
                    new_to_id = doc_id_mapping.get(old_to_id)

                    if new_from_id and new_to_id:
                        conn.execute("""
                            INSERT INTO document_relationships (from_document_id, to_document_id,
                                                               relationship_type, description, created_date)
                            VALUES (?, ?, ?, ?, ?)
                        """, (
                            new_from_id,
                            new_to_id,
                            rel.get('relationship_type'),
                            rel.get('description'),
                            rel.get('created_date')
                        ))

                self.logger.info(
                    f"Imported {len(doc_id_mapping)} documents, "
                    f"{len(module_data.get('game_sessions', []))} sessions, "
                    f"{len(module_data.get('images', []))} images"
                )

                return True, "Data imported successfully"

        except Exception as e:
            error_msg = f"Error importing module data: {e}"
            self.logger.error(error_msg, exc_info=True)
            return False, error_msg

    def _extract_images(self, zip_path: str, module_id: int) -> Tuple[bool, str]:
        """
        Extract images from ZIP to module directory.

        Args:
            zip_path: Path to backup ZIP file
            module_id: Module ID for image directory

        Returns:
            Tuple of (success: bool, message: str)
        """
        try:
            # Create module images directory
            module_images_dir = self.images_path / str(module_id)
            if module_images_dir.exists():
                shutil.rmtree(module_images_dir)
            module_images_dir.mkdir(parents=True, exist_ok=True)

            with zipfile.ZipFile(str(zip_path), 'r') as zf:
                self._check_zip_limits(zf)
                image_files = self._image_entries(zf)
                for entry, filename in image_files:
                    with zf.open(entry) as src, open(module_images_dir / filename, 'wb') as dst:
                        shutil.copyfileobj(src, dst)

                self.logger.info(f"Extracted {len(image_files)} images to {module_images_dir}")

            return True, f"Extracted {len(image_files)} images"

        except Exception as e:
            error_msg = f"Error extracting images: {e}"
            self.logger.error(error_msg, exc_info=True)
            return False, error_msg

    def _delete_module_data(self, module_id: int):
        """
        Delete all data for a module from the main database.

        Args:
            module_id: Module ID to delete data for
        """
        try:
            with self.db.connection.transaction() as conn:
                # Delete in correct order (children first due to foreign keys)
                # Legacy AI suggestions table (the feature was removed; the table stays for old databases)
                conn.execute("""
                    DELETE FROM ai_suggestions
                    WHERE document_id IN (SELECT id FROM documents WHERE module_id = ?)
                """, (module_id,))

                # Document relationships
                conn.execute("""
                    DELETE FROM document_relationships
                    WHERE from_document_id IN (SELECT id FROM documents WHERE module_id = ?)
                       OR to_document_id IN (SELECT id FROM documents WHERE module_id = ?)
                """, (module_id, module_id))

                # Images
                conn.execute("DELETE FROM images WHERE module_id = ?", (module_id,))

                # Game sessions
                conn.execute("DELETE FROM game_sessions WHERE module_id = ?", (module_id,))

                # Documents
                conn.execute("DELETE FROM documents WHERE module_id = ?", (module_id,))

                self.logger.info(f"Deleted all data for module {module_id}")

            # Delete images directory
            module_images_dir = self.images_path / str(module_id)
            if module_images_dir.exists():
                shutil.rmtree(module_images_dir)
                self.logger.info(f"Deleted images directory: {module_images_dir}")

        except Exception as e:
            self.logger.error(f"Error deleting module data: {e}", exc_info=True)
            raise
