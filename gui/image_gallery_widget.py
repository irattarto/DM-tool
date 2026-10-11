"""
Image gallery widget for managing multiple images per entity.
"""

from gui.theme import set_props
from typing import List, Dict, Any, Optional
from pathlib import Path

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QPushButton,
    QFileDialog, QMessageBox, QScrollArea, QFrame, QMenu, QToolButton, QGraphicsDropShadowEffect
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QPixmap, QDragEnterEvent, QDropEvent, QGuiApplication, QAction, QContextMenuEvent, QFont, QColor

from config.paths import resolve_image_path, get_data_dir
from services.image_service import ImageService
from gui.image_preview_dialog import ImagePreviewDialog
from utils.logger import get_logger


class ImageThumbnail(QFrame):
    """Widget for displaying a single image thumbnail with delete button."""

    clicked = pyqtSignal(int)  # image_index
    delete_requested = pyqtSignal(int)  # image_index
    copy_requested = pyqtSignal(int)  # image_index
    copy_path_requested = pyqtSignal(int)  # image_index
    edit_description_requested = pyqtSignal(int)  # image_index
    set_primary_requested = pyqtSignal(int)  # image_index
    discord_requested = pyqtSignal(int)  # image_index

    def __init__(self, image_data: Dict[str, Any], index: int, parent=None):
        """
        Initialize image thumbnail.

        Args:
            image_data: Dictionary with image information
            index: Index of this image in the gallery
            parent: Parent widget
        """
        super().__init__(parent)
        self.image_data = image_data
        self.index = index

        self.setFrameStyle(QFrame.Shape.Box | QFrame.Shadow.Plain)
        self.setLineWidth(1)
        self.setFixedSize(160, 180)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        self._setup_ui()

    def _setup_ui(self):
        """Set up the user interface."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)

        # Image label
        self.image_label = QLabel()
        self.image_label.setFixedSize(150, 150)
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setScaledContents(False)

        # Load thumbnail — resolve path in case data was moved
        file_path = resolve_image_path(self.image_data)
        pixmap = QPixmap(file_path)
        if not pixmap.isNull():
            pixmap = pixmap.scaled(
                150, 150,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            self.image_label.setPixmap(pixmap)
        else:
            self.image_label.setText("Error")

        layout.addWidget(self.image_label)

        # Filename label
        filename = self.image_data.get('original_name', 'Unknown')
        if len(filename) > 20:
            filename = filename[:17] + "..."

        filename_label = QLabel(filename)
        filename_label.setTextFormat(Qt.TextFormat.PlainText)
        filename_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        filename_label.setToolTip(self.image_data.get('original_name', ''))
        layout.addWidget(filename_label)

        # Delete button - red X with no background
        delete_btn = QToolButton(self)
        delete_btn.setFixedSize(24, 24)

        # Use Cross Mark emoji for clear visibility
        delete_btn.setText("❌")
        delete_btn.setFont(QFont(QFont().family(), 12))

        delete_btn.clicked.connect(lambda: self.delete_requested.emit(self.index))
        delete_btn.setToolTip("Delete image")

        # Add white drop shadow for visibility on any background
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(3)
        shadow.setColor(QColor(255, 255, 255, 255))
        shadow.setOffset(0, 0)
        delete_btn.setGraphicsEffect(shadow)

        # Styling: transparent background, bright red X
        delete_btn.setStyleSheet("""
            QToolButton {
                background-color: transparent;
                border: none;
                color: #ff3333;
            }
            QToolButton:hover {
                background-color: rgba(255, 255, 255, 0.8);
                border-radius: 12px;
            }
            QToolButton:pressed {
                background-color: rgba(255, 51, 51, 0.3);
            }
        """)

        # Position in top-right corner
        delete_btn.move(132, 5)

        # Star badge for primary image (shown only if this is primary)
        self.star_badge = QLabel(self)
        self.star_badge.setFixedSize(20, 20)
        self.star_badge.setText("⭐")
        self.star_badge.setFont(QFont(QFont().family(), 12))
        self.star_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.star_badge.setStyleSheet("""
            QLabel {
                background-color: transparent;
                border: none;
            }
        """)

        # Add white drop shadow for visibility on any background
        star_shadow = QGraphicsDropShadowEffect()
        star_shadow.setBlurRadius(3)
        star_shadow.setColor(QColor(255, 255, 255, 255))
        star_shadow.setOffset(0, 0)
        self.star_badge.setGraphicsEffect(star_shadow)

        self.star_badge.setToolTip("Primary Image")
        self.star_badge.move(5, 5)  # Top-left corner

        # Hide by default, show only if image is primary
        is_primary = self.image_data.get('is_primary', False)
        self.star_badge.setVisible(bool(is_primary))

    def mousePressEvent(self, event):
        """Handle mouse press to show full image."""
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.index)

    def contextMenuEvent(self, event: QContextMenuEvent):
        """Handle right-click context menu."""
        menu = QMenu(self)

        # View Full Size action
        view_action = QAction("View Full Size", self)
        view_action.triggered.connect(lambda: self.clicked.emit(self.index))
        menu.addAction(view_action)

        # Copy Image action
        copy_action = QAction("Copy Image", self)
        copy_action.triggered.connect(lambda: self.copy_requested.emit(self.index))
        menu.addAction(copy_action)

        # Copy Image Path action
        copy_path_action = QAction("Copy Image Path", self)
        copy_path_action.triggered.connect(lambda: self.copy_path_requested.emit(self.index))
        menu.addAction(copy_path_action)

        # Edit Description action
        edit_desc_action = QAction("Edit Description", self)
        edit_desc_action.triggered.connect(lambda: self.edit_description_requested.emit(self.index))
        menu.addAction(edit_desc_action)

        send_action = QAction("Send to Discord...", self)
        send_action.triggered.connect(lambda: self.discord_requested.emit(self.index))
        menu.addAction(send_action)

        menu.addSeparator()

        # Set as Primary action (only show if not already primary)
        is_primary = self.image_data.get('is_primary', False)
        if not is_primary:
            set_primary_action = QAction("⭐ Set as Primary Image", self)
            set_primary_action.triggered.connect(lambda: self.set_primary_requested.emit(self.index))
            menu.addAction(set_primary_action)
            menu.addSeparator()

        # Delete Image action
        delete_action = QAction("Delete Image", self)
        delete_action.triggered.connect(lambda: self.delete_requested.emit(self.index))
        menu.addAction(delete_action)

        # Show menu at cursor position
        menu.exec(event.globalPos())


class ImageDropZone(QLabel):
    """Thumbnail-sized label that accepts drag and drop of image files."""

    files_dropped = pyqtSignal(list)  # List of file paths
    clicked = pyqtSignal()  # Emitted when clicked

    def __init__(self, parent=None):
        """Initialize drop zone."""
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Thumbnail-sized (same as ImageThumbnail)
        self.setFixedSize(160, 180)

        # Shorter text for smaller size
        self.setText("+ Add Images\n\nDrag & Drop\nor Click")

        set_props(self, role="dropzone", dragActive=False)

        # Make it look clickable
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def dragEnterEvent(self, event: QDragEnterEvent):
        """Handle drag enter event."""
        if event.mimeData().hasUrls() or event.mimeData().hasImage():
            event.acceptProposedAction()
            set_props(self, dragActive=True)
        else:
            event.ignore()

    def dragLeaveEvent(self, event):
        """Handle drag leave event."""
        set_props(self, dragActive=False)

    def dropEvent(self, event: QDropEvent):
        """Handle drop event."""
        set_props(self, dragActive=False)

        mime_data = event.mimeData()

        # Handle file URLs
        if mime_data.hasUrls():
            file_paths = []
            for url in mime_data.urls():
                if url.isLocalFile():
                    file_paths.append(url.toLocalFile())

            if file_paths:
                self.files_dropped.emit(file_paths)
                event.acceptProposedAction()
                return

        # Handle direct image data (e.g., from browser)
        if mime_data.hasImage():
            # This will be handled by the parent widget
            event.acceptProposedAction()

    def mousePressEvent(self, event):
        """Handle mouse press to trigger file browser."""
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()


class ImageGalleryWidget(QWidget):
    """Widget for managing multiple images for an entity."""

    images_changed = pyqtSignal()  # Emitted when images are added or removed
    primary_changed = pyqtSignal(int)  # Emitted when primary image changes (image_id)

    MAX_IMAGES = 10
    MAX_FILE_SIZE_MB = 10

    def __init__(self, module_id: int, document_id: Optional[int] = None,
                 db_manager=None, image_service: Optional[ImageService] = None, parent=None):
        """
        Initialize image gallery widget.

        Args:
            module_id: ID of the current module
            document_id: Optional ID of the document (None for new entities)
            db_manager: DatabaseManager instance
            image_service: ImageService instance
            parent: Parent widget
        """
        super().__init__(parent)
        self.module_id = module_id
        self.document_id = document_id
        self.db_manager = db_manager
        self.image_service = image_service or ImageService()
        self.logger = get_logger('image_gallery')

        # List of image data dictionaries
        self.images: List[Dict[str, Any]] = []

        # Track images to delete when saved
        self.images_to_delete: List[int] = []

        self._setup_ui()
        self._load_existing_images()

    def _setup_ui(self):
        """Set up the user interface."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)

        # Title and counter
        header_layout = QHBoxLayout()
        title_label = QLabel("Entity Images")
        set_props(title_label, role="heading")
        header_layout.addWidget(title_label)

        header_layout.addStretch()

        self.counter_label = QLabel("0 / 10 images")
        header_layout.addWidget(self.counter_label)

        layout.addLayout(header_layout)

        # Button toolbar
        toolbar_layout = QHBoxLayout()

        self.add_button = QPushButton("Add Images...")
        self.add_button.clicked.connect(self._add_images_from_file)
        toolbar_layout.addWidget(self.add_button)

        self.paste_button = QPushButton("Paste from Clipboard")
        self.paste_button.clicked.connect(self._paste_from_clipboard)
        toolbar_layout.addWidget(self.paste_button)

        self.discord_button = QPushButton("Send to Discord...")
        self.discord_button.setToolTip("Send all images of this entity to Discord, with the entity name")
        self.discord_button.clicked.connect(self._send_all_to_discord)
        toolbar_layout.addWidget(self.discord_button)

        toolbar_layout.addStretch()

        layout.addLayout(toolbar_layout)

        # Create drop zone (will be added to grid in _refresh_gallery)
        self.drop_zone = ImageDropZone()
        self.drop_zone.files_dropped.connect(self._handle_dropped_files)
        self.drop_zone.clicked.connect(self._add_images_from_file)

        # Scroll area for thumbnails
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        # Container for thumbnail grid
        self.thumbnail_container = QWidget()
        self.thumbnail_layout = QGridLayout(self.thumbnail_container)
        self.thumbnail_layout.setSpacing(10)
        self.thumbnail_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)

        scroll_area.setWidget(self.thumbnail_container)
        layout.addWidget(scroll_area)

    def _load_existing_images(self):
        """Load existing images from database."""
        if self.document_id and self.db_manager:
            try:
                self.images = self.db_manager.get_document_images(self.document_id)
                self.logger.info(f"Loaded {len(self.images)} existing images for document {self.document_id}")
                self._refresh_gallery()
            except Exception as e:
                self.logger.error(f"Failed to load existing images: {e}", exc_info=True)

    def _refresh_gallery(self):
        """Refresh the thumbnail display."""
        # Clear existing thumbnails (but preserve drop_zone to avoid deletion)
        while self.thumbnail_layout.count():
            item = self.thumbnail_layout.takeAt(0)
            widget = item.widget()
            if widget and widget is not self.drop_zone:
                # Delete thumbnails but not the drop_zone widget
                widget.deleteLater()

        # Add thumbnails in grid (4 columns)
        for i, image_data in enumerate(self.images):
            row = i // 4
            col = i % 4

            thumbnail = ImageThumbnail(image_data, i)
            thumbnail.clicked.connect(self._show_image_preview)
            thumbnail.delete_requested.connect(self._delete_image)
            thumbnail.copy_requested.connect(self._copy_image_to_clipboard)
            thumbnail.copy_path_requested.connect(self._copy_image_path_to_clipboard)
            thumbnail.edit_description_requested.connect(self._edit_image_description)
            thumbnail.discord_requested.connect(self._send_image_to_discord)
            thumbnail.set_primary_requested.connect(self._set_as_primary)

            self.thumbnail_layout.addWidget(thumbnail, row, col)

        # Add drop zone as next item in grid (if not at max images)
        if len(self.images) < self.MAX_IMAGES:
            next_position = len(self.images)
            row = next_position // 4
            col = next_position % 4
            self.thumbnail_layout.addWidget(self.drop_zone, row, col)

        # Update counter and button states
        self._update_counter()

    def _update_counter(self):
        """Update the image counter label."""
        count = len(self.images)
        self.counter_label.setText(f"{count} / {self.MAX_IMAGES} images")

        # Disable add buttons if at max
        can_add = count < self.MAX_IMAGES
        self.add_button.setEnabled(can_add)
        self.paste_button.setEnabled(can_add)

        # Drop zone is shown/hidden in _refresh_gallery based on can_add
        # No need to disable it here since it won't be in the grid when at max

    def _add_images_from_file(self):
        """Open file dialog to add images."""
        if len(self.images) >= self.MAX_IMAGES:
            QMessageBox.warning(self, "Limit Reached",
                              f"Maximum of {self.MAX_IMAGES} images per entity.")
            return

        # Calculate remaining slots
        remaining = self.MAX_IMAGES - len(self.images)

        file_dialog = QFileDialog(self)
        file_dialog.setFileMode(QFileDialog.FileMode.ExistingFiles)
        file_dialog.setNameFilter("Images (*.png *.jpg *.jpeg *.gif *.bmp *.webp)")

        if file_dialog.exec():
            file_paths = file_dialog.selectedFiles()

            # Limit to remaining slots
            if len(file_paths) > remaining:
                QMessageBox.warning(self, "Too Many Images",
                                  f"You can only add {remaining} more image(s).\n"
                                  f"Only the first {remaining} will be added.")
                file_paths = file_paths[:remaining]

            self._add_image_files(file_paths)

    def _add_image_files(self, file_paths: List[str]):
        """
        Add image files to the gallery.

        Args:
            file_paths: List of file paths to add
        """
        added_count = 0
        errors = []

        for file_path in file_paths:
            if len(self.images) >= self.MAX_IMAGES:
                break

            try:
                # Validate file size
                is_valid, error_msg = self.image_service.validate_file_size(
                    file_path, self.MAX_FILE_SIZE_MB
                )
                if not is_valid:
                    errors.append(f"{Path(file_path).name}: {error_msg}")
                    continue

                # Save image using ImageService
                image_metadata = self.image_service.save_image(
                    file_path,
                    self.module_id,
                    self.document_id,
                    Path(file_path).name
                )

                if image_metadata:
                    # Add to images list (will be saved to DB when document is saved)
                    self.images.append({
                        'id': None,  # Will be set when saved to database
                        'module_id': self.module_id,
                        'document_id': self.document_id,
                        'filename': image_metadata['filename'],
                        'original_name': image_metadata['original_name'],
                        'file_path': image_metadata['file_path'],
                        'file_size': image_metadata['file_size'],
                        'mime_type': image_metadata['mime_type'],
                        'description': None,
                        'uploaded_date': None,
                        '_is_new': True  # Mark as new (not yet in database)
                    })
                    added_count += 1
                else:
                    errors.append(f"{Path(file_path).name}: Failed to save image")

            except Exception as e:
                self.logger.error(f"Error adding image {file_path}: {e}", exc_info=True)
                errors.append(f"{Path(file_path).name}: {str(e)}")

        # Refresh display
        self._refresh_gallery()
        self.images_changed.emit()

        # Show results
        if added_count > 0:
            QMessageBox.information(self, "Success",
                                  f"Added {added_count} image(s) successfully.")

        if errors:
            error_msg = "Some images could not be added:\n\n" + "\n".join(errors[:5])
            if len(errors) > 5:
                error_msg += f"\n\n...and {len(errors) - 5} more errors"
            QMessageBox.warning(self, "Errors", error_msg)

    def _paste_from_clipboard(self):
        """Paste image from clipboard."""
        if len(self.images) >= self.MAX_IMAGES:
            QMessageBox.warning(self, "Limit Reached",
                              f"Maximum of {self.MAX_IMAGES} images per entity.")
            return

        try:
            # Get image data from clipboard
            image_data = self.image_service.get_image_from_clipboard()

            if image_data is None:
                QMessageBox.information(self, "No Image",
                                      "No image found in clipboard.")
                return

            # Generate unique filename
            from datetime import datetime
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"pasted_image_{timestamp}.png"

            # Save image from bytes
            image_metadata = self.image_service.save_image_from_bytes(
                image_data,
                self.module_id,
                filename,
                self.document_id
            )

            if image_metadata:
                self.images.append({
                    'id': None,
                    'module_id': self.module_id,
                    'document_id': self.document_id,
                    'filename': image_metadata['filename'],
                    'original_name': image_metadata['original_name'],
                    'file_path': image_metadata['file_path'],
                    'file_size': image_metadata['file_size'],
                    'mime_type': image_metadata['mime_type'],
                    'description': None,
                    'uploaded_date': None,
                    '_is_new': True
                })

                self._refresh_gallery()
                self.images_changed.emit()

                QMessageBox.information(self, "Success", "Image pasted successfully!")
            else:
                QMessageBox.warning(self, "Error", "Failed to save pasted image.")

        except Exception as e:
            self.logger.error(f"Error pasting from clipboard: {e}", exc_info=True)
            QMessageBox.warning(self, "Error", f"Failed to paste image: {str(e)}")

    def _handle_dropped_files(self, file_paths: List[str]):
        """
        Handle files dropped onto the drop zone.

        Args:
            file_paths: List of dropped file paths
        """
        # Filter for image files only
        image_extensions = ['.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp']
        image_files = [
            fp for fp in file_paths
            if Path(fp).suffix.lower() in image_extensions
        ]

        if not image_files:
            QMessageBox.warning(self, "No Images",
                              "No valid image files were dropped.")
            return

        # Limit to remaining slots
        remaining = self.MAX_IMAGES - len(self.images)
        if len(image_files) > remaining:
            QMessageBox.warning(self, "Too Many Images",
                              f"You can only add {remaining} more image(s).\n"
                              f"Only the first {remaining} will be added.")
            image_files = image_files[:remaining]

        self._add_image_files(image_files)

    def _show_image_preview(self, index: int):
        """
        Show full-size image preview.

        Args:
            index: Index of image to preview
        """
        if 0 <= index < len(self.images):
            dialog = ImagePreviewDialog(self.images, index, self)
            dialog.description_changed.connect(self._update_description)
            dialog.image_deleted.connect(self._handle_image_deleted_from_preview)
            dialog.exec()

    def _copy_image_to_clipboard(self, index: int):
        """
        Copy image to clipboard.

        Args:
            index: Index of image to copy
        """
        if 0 <= index < len(self.images):
            image_data = self.images[index]
            file_path = image_data.get('file_path', '')

            pixmap = QPixmap(file_path)
            if not pixmap.isNull():
                clipboard = QGuiApplication.clipboard()
                clipboard.setPixmap(pixmap)
                QMessageBox.information(self, "Success", "Image copied to clipboard", QMessageBox.StandardButton.Ok)
            else:
                QMessageBox.warning(self, "Error", "Failed to load image", QMessageBox.StandardButton.Ok)

    def _send_image_to_discord(self, index: int):
        """Send one image (right-click menu)."""
        if 0 <= index < len(self.images):
            self._send_to_discord([self.images[index]])

    def _send_all_to_discord(self):
        """Send every image of this entity (toolbar button)."""
        self._send_to_discord(list(self.images))

    def _send_to_discord(self, images):
        from gui.discord_actions import send_images_to_discord, entity_name_for
        name = entity_name_for(self.db_manager, self.document_id)
        send_images_to_discord(self, self.db_manager, self.module_id, images, name)

    def _copy_image_path_to_clipboard(self, index: int):
        """
        Copy image file path to clipboard.

        Args:
            index: Index of image
        """
        if 0 <= index < len(self.images):
            image_data = self.images[index]
            file_path = image_data.get('file_path', '')

            if file_path:
                clipboard = QGuiApplication.clipboard()
                clipboard.setText(file_path)
                QMessageBox.information(self, "Success", f"Path copied to clipboard:\n{file_path}", QMessageBox.StandardButton.Ok)
            else:
                QMessageBox.warning(self, "Error", "No file path available", QMessageBox.StandardButton.Ok)

    def _edit_image_description(self, index: int):
        """
        Open preview dialog with focus on description field.

        Args:
            index: Index of image
        """
        # Just open the preview dialog - user can edit description there
        self._show_image_preview(index)

    def _update_description(self, image_id: int, description: str):
        """
        Update image description.

        Args:
            image_id: ID of the image
            description: New description text
        """
        # Find image in our list
        for img in self.images:
            if img.get('id') == image_id:
                img['description'] = description

                # Update in database if image already exists there
                if image_id and self.db_manager:
                    self.db_manager.update_image_description(image_id, description)

                self.images_changed.emit()
                break

    def _set_as_primary(self, index: int):
        """
        Set an image as the primary image.

        Args:
            index: Index of image to set as primary
        """
        if 0 <= index < len(self.images):
            image_data = self.images[index]
            image_id = image_data.get('id')

            if not image_id:
                # Image not yet saved to database
                QMessageBox.warning(self, "Cannot Set Primary",
                                  "Please save the document first before setting a primary image.")
                return

            if not self.document_id or not self.db_manager:
                return

            # Set as primary in database
            success = self.db_manager.set_primary_image(self.document_id, image_id)

            if success:
                # Update local data - clear all primary flags, then set this one
                for img in self.images:
                    img['is_primary'] = False
                image_data['is_primary'] = True

                # Refresh gallery to show star badge
                self._refresh_gallery()

                # Emit signal so Details tab can update
                self.primary_changed.emit(image_id)

                QMessageBox.information(self, "Success",
                                      "Image set as primary!")
            else:
                QMessageBox.warning(self, "Error",
                                  "Failed to set image as primary.")

    def _delete_image(self, index: int):
        """
        Delete an image from the gallery.

        Args:
            index: Index of image to delete
        """
        if 0 <= index < len(self.images):
            image_data = self.images[index]
            filename = image_data.get('original_name', 'Unknown')

            reply = QMessageBox.question(
                self, "Delete Image",
                f"Are you sure you want to delete '{filename}'?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )

            if reply == QMessageBox.StandardButton.Yes:
                was_primary = image_data.get('is_primary', False)

                # Mark for deletion if it exists in database
                image_id = image_data.get('id')
                if image_id:
                    self.images_to_delete.append(image_id)

                # Remove from list
                self.images.pop(index)

                # If we deleted the primary image, auto-set next image as primary
                if was_primary and self.images and self.document_id and self.db_manager:
                    self.db_manager.auto_set_primary_if_needed(self.document_id)
                    # Reload images to update is_primary flags
                    self.images = self.db_manager.get_document_images(self.document_id)
                    # Emit primary changed signal
                    if self.images:
                        for img in self.images:
                            if img.get('is_primary'):
                                self.primary_changed.emit(img.get('id'))
                                break

                # Refresh display
                self._refresh_gallery()
                self.images_changed.emit()

    def _handle_image_deleted_from_preview(self, image_id: int):
        """
        Handle image deletion triggered from the preview dialog.

        Args:
            image_id: ID of the deleted image
        """
        # Find and remove the image from our list
        for i, img in enumerate(self.images):
            if img.get('id') == image_id:
                was_primary = img.get('is_primary', False)

                # Mark for deletion if it exists in database
                if image_id:
                    self.images_to_delete.append(image_id)

                # Remove from list
                self.images.pop(i)

                # If we deleted the primary image, auto-set next image as primary
                if was_primary and self.images and self.document_id and self.db_manager:
                    self.db_manager.auto_set_primary_if_needed(self.document_id)
                    # Reload images to update is_primary flags
                    self.images = self.db_manager.get_document_images(self.document_id)
                    # Emit primary changed signal
                    if self.images:
                        for img in self.images:
                            if img.get('is_primary'):
                                self.primary_changed.emit(img.get('id'))
                                break

                # Refresh display
                self._refresh_gallery()
                self.images_changed.emit()
                break

    def save_images(self, document_id: int):
        """
        Save all new images to the database and delete marked images.

        Args:
            document_id: ID of the document these images belong to

        Returns:
            True if successful, False otherwise
        """
        if not self.db_manager:
            self.logger.warning("No database manager available")
            return False

        try:
            # Update document_id for all images
            self.document_id = document_id

            # Delete marked images
            for image_id in self.images_to_delete:
                try:
                    # Get image info to delete the file
                    image_info = self.db_manager.get_image_by_id(image_id)
                    if image_info:
                        # Delete from database
                        self.db_manager.delete_image_record(image_id)

                        # Delete physical file (only within the managed images
                        # directory - defense-in-depth against a bad file_path
                        # slipping in from an untrusted source, e.g. backup restore)
                        file_path = image_info.get('file_path')
                        if file_path and Path(file_path).exists():
                            images_root = (get_data_dir() / "rpg_images" / "modules").resolve()
                            resolved = Path(file_path).resolve()
                            if images_root in resolved.parents:
                                resolved.unlink()
                                self.logger.info(f"Deleted image file: {file_path}")
                            else:
                                self.logger.warning(f"Refused to delete image outside managed directory: {file_path}")

                except Exception as e:
                    self.logger.error(f"Error deleting image {image_id}: {e}", exc_info=True)

            self.images_to_delete.clear()

            # Save new images to database
            for image_data in self.images:
                if image_data.get('_is_new'):
                    try:
                        image_id = self.db_manager.save_image_record(
                            module_id=self.module_id,
                            document_id=document_id,
                            filename=image_data['filename'],
                            original_name=image_data['original_name'],
                            file_path=image_data['file_path'],
                            file_size=image_data['file_size'],
                            mime_type=image_data['mime_type'],
                            description=image_data.get('description')
                        )

                        # Update image data with new ID
                        image_data['id'] = image_id
                        image_data['document_id'] = document_id
                        image_data.pop('_is_new', None)

                        self.logger.info(f"Saved image to database: {image_data['original_name']}")

                    except Exception as e:
                        self.logger.error(f"Error saving image to database: {e}", exc_info=True)
                        return False

            # Auto-set first image as primary if no primary exists
            if document_id:
                self.db_manager.auto_set_primary_if_needed(document_id)
                # Reload images to get updated is_primary flags
                self.images = self.db_manager.get_document_images(document_id)
                self._refresh_gallery()

            return True

        except Exception as e:
            self.logger.error(f"Error in save_images: {e}", exc_info=True)
            return False
