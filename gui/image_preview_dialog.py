"""
Image preview dialog for viewing full-size images.
"""

from typing import List, Dict, Any
from pathlib import Path
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTextEdit, QScrollArea, QMessageBox, QMenu, QFileDialog
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QPixmap, QGuiApplication, QAction, QContextMenuEvent

from config.paths import resolve_image_path
from utils.logger import get_logger


class ContextMenuLabel(QLabel):
    """QLabel that supports context menu events."""

    context_menu_requested = pyqtSignal(object)  # QContextMenuEvent

    def contextMenuEvent(self, event: QContextMenuEvent):
        """Handle context menu event."""
        self.context_menu_requested.emit(event)


class ImagePreviewDialog(QDialog):
    """Dialog for viewing and navigating through full-size images."""

    description_changed = pyqtSignal(int, str)  # image_id, new_description
    image_deleted = pyqtSignal(int)  # image_id

    def __init__(self, images: List[Dict[str, Any]], current_index: int = 0, parent=None):
        """
        Initialize image preview dialog.

        Args:
            images: List of image dictionaries with keys: id, file_path, description, original_name
            current_index: Index of image to display initially
            parent: Parent widget
        """
        super().__init__(parent)
        self.images = images
        self.current_index = current_index
        self.logger = get_logger('image_preview')

        self.setWindowTitle("Image Preview")
        self.resize(800, 600)

        self._setup_ui()
        self._load_current_image()

    def _setup_ui(self):
        """Set up the user interface."""
        layout = QVBoxLayout(self)

        # Image display area (scrollable)
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.image_label = ContextMenuLabel()
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setScaledContents(False)
        self.image_label.context_menu_requested.connect(self._show_context_menu)
        scroll_area.setWidget(self.image_label)

        layout.addWidget(scroll_area, stretch=1)

        # Image info label
        self.info_label = QLabel()
        self.info_label.setWordWrap(True)
        layout.addWidget(self.info_label)

        # Description editor
        description_layout = QVBoxLayout()
        desc_label = QLabel("Description:")
        description_layout.addWidget(desc_label)

        self.description_edit = QTextEdit()
        self.description_edit.setMaximumHeight(80)
        self.description_edit.setPlaceholderText("Enter image description (optional)...")
        description_layout.addLayout(description_layout)
        layout.addWidget(self.description_edit)

        # Navigation buttons
        nav_layout = QHBoxLayout()

        self.prev_button = QPushButton("Previous")
        self.prev_button.clicked.connect(self._show_previous)
        nav_layout.addWidget(self.prev_button)

        self.copy_button = QPushButton("Copy to Clipboard")
        self.copy_button.clicked.connect(self._copy_to_clipboard)
        nav_layout.addWidget(self.copy_button)

        self.save_desc_button = QPushButton("Save Description")
        self.save_desc_button.clicked.connect(self._save_description)
        nav_layout.addWidget(self.save_desc_button)

        self.next_button = QPushButton("Next")
        self.next_button.clicked.connect(self._show_next)
        nav_layout.addWidget(self.next_button)

        layout.addLayout(nav_layout)

        # Close button
        close_layout = QHBoxLayout()
        close_layout.addStretch()

        close_button = QPushButton("Close")
        close_button.clicked.connect(self.accept)
        close_layout.addWidget(close_button)

        layout.addLayout(close_layout)

    def _load_current_image(self):
        """Load and display the current image."""
        if not self.images or self.current_index < 0 or self.current_index >= len(self.images):
            return

        image_data = self.images[self.current_index]
        file_path = resolve_image_path(image_data)

        # Load and display image
        pixmap = QPixmap(file_path)
        if not pixmap.isNull():
            # Scale if too large, but maintain aspect ratio
            max_size = 1200
            if pixmap.width() > max_size or pixmap.height() > max_size:
                pixmap = pixmap.scaled(
                    max_size, max_size,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                )
            self.image_label.setPixmap(pixmap)
        else:
            self.image_label.setText("Failed to load image")

        # Update info label
        original_name = image_data.get('original_name', 'Unknown')
        file_size = image_data.get('file_size', 0)
        size_kb = file_size / 1024
        info_text = f"Image {self.current_index + 1} of {len(self.images)} | {original_name} | {size_kb:.1f} KB"
        self.info_label.setText(info_text)

        # Load description
        description = image_data.get('description', '') or ''
        self.description_edit.setPlainText(description)

        # Update navigation buttons
        self.prev_button.setEnabled(self.current_index > 0)
        self.next_button.setEnabled(self.current_index < len(self.images) - 1)

    def _show_previous(self):
        """Show the previous image."""
        if self.current_index > 0:
            self.current_index -= 1
            self._load_current_image()

    def _show_next(self):
        """Show the next image."""
        if self.current_index < len(self.images) - 1:
            self.current_index += 1
            self._load_current_image()

    def _copy_to_clipboard(self):
        """Copy the current image to the clipboard."""
        if not self.images or self.current_index < 0 or self.current_index >= len(self.images):
            return

        image_data = self.images[self.current_index]
        file_path = resolve_image_path(image_data)

        pixmap = QPixmap(file_path)
        if not pixmap.isNull():
            clipboard = QGuiApplication.clipboard()
            clipboard.setPixmap(pixmap)
            QMessageBox.information(self, "Success", "Image copied to clipboard")
        else:
            QMessageBox.warning(self, "Error", "Failed to load image")

    def _save_description(self):
        """Save the current description."""
        if not self.images or self.current_index < 0 or self.current_index >= len(self.images):
            return

        image_data = self.images[self.current_index]
        image_id = image_data.get('id')
        new_description = self.description_edit.toPlainText()

        # Emit signal with the updated description
        self.description_changed.emit(image_id, new_description)

        # Update local data
        image_data['description'] = new_description

        QMessageBox.information(self, "Success", "Description saved")

    def _show_context_menu(self, event: QContextMenuEvent):
        """Show context menu on the image."""
        if not self.images or self.current_index < 0 or self.current_index >= len(self.images):
            return

        menu = QMenu(self)

        # Copy Image action
        copy_action = QAction("Copy Image", self)
        copy_action.triggered.connect(self._copy_to_clipboard)
        menu.addAction(copy_action)

        # Copy Image Path action
        copy_path_action = QAction("Copy Image Path", self)
        copy_path_action.triggered.connect(self._copy_path_to_clipboard)
        menu.addAction(copy_path_action)

        # Save Image As action
        save_as_action = QAction("Save Image As...", self)
        save_as_action.triggered.connect(self._save_image_as)
        menu.addAction(save_as_action)

        menu.addSeparator()

        # Delete Image action
        delete_action = QAction("Delete Image", self)
        delete_action.triggered.connect(self._delete_current_image)
        menu.addAction(delete_action)

        # Show menu at cursor position
        menu.exec(event.globalPos())

    def _copy_path_to_clipboard(self):
        """Copy the current image path to clipboard."""
        if not self.images or self.current_index < 0 or self.current_index >= len(self.images):
            return

        image_data = self.images[self.current_index]
        file_path = resolve_image_path(image_data)

        if file_path:
            clipboard = QGuiApplication.clipboard()
            clipboard.setText(file_path)
            QMessageBox.information(self, "Success", f"Path copied to clipboard:\n{file_path}")
        else:
            QMessageBox.warning(self, "Error", "No file path available")

    def _save_image_as(self):
        """Save a copy of the current image to a user-selected location."""
        if not self.images or self.current_index < 0 or self.current_index >= len(self.images):
            return

        image_data = self.images[self.current_index]
        file_path = resolve_image_path(image_data)
        original_name = image_data.get('original_name', 'image.png')

        if not file_path or not Path(file_path).exists():
            QMessageBox.warning(self, "Error", "Image file not found")
            return

        # Open save dialog
        save_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Image As",
            original_name,
            "Images (*.png *.jpg *.jpeg *.gif *.bmp *.webp);;All Files (*)"
        )

        if save_path:
            try:
                # Copy file to new location
                import shutil
                shutil.copy2(file_path, save_path)
                QMessageBox.information(self, "Success", f"Image saved to:\n{save_path}")
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Failed to save image:\n{str(e)}")

    def _delete_current_image(self):
        """Delete the current image."""
        if not self.images or self.current_index < 0 or self.current_index >= len(self.images):
            return

        image_data = self.images[self.current_index]
        original_name = image_data.get('original_name', 'Unknown')
        image_id = image_data.get('id')

        reply = QMessageBox.question(
            self, "Delete Image",
            f"Are you sure you want to delete '{original_name}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            # Emit signal to notify gallery
            if image_id:
                self.image_deleted.emit(image_id)

            # Remove from local list
            self.images.pop(self.current_index)

            # Navigate to next image or close if no images left
            if not self.images:
                QMessageBox.information(self, "Info", "All images deleted")
                self.accept()
            else:
                # Stay at same index if possible, or go back one
                if self.current_index >= len(self.images):
                    self.current_index = len(self.images) - 1
                self._load_current_image()
