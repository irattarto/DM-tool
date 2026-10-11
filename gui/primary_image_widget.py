"""
Primary image widget for displaying entity main image.
"""

from config.paths import resolve_image_path
from gui.theme import set_props
from typing import Optional, Dict, Any
from pathlib import Path

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QMenu
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QPixmap, QGuiApplication, QAction, QContextMenuEvent

from services.image_service import ImageService
from gui.image_preview_dialog import ImagePreviewDialog
from utils.logger import get_logger


class PrimaryImageWidget(QWidget):
    """
    Widget displaying primary image thumbnail (50x50px) with interactions.
    Shows in Details tab header next to entity name.
    """

    go_to_images_tab = pyqtSignal()  # Emitted when user wants to go to Images tab

    def __init__(self, document_id: int, document_title: str, db_manager, parent=None):
        """
        Initialize primary image widget.

        Args:
            document_id: ID of the document
            document_title: Title of the document/entity
            db_manager: DatabaseManager instance
            parent: Parent widget
        """
        super().__init__(parent)
        self.document_id = document_id
        self.document_title = document_title
        self.db_manager = db_manager
        self.image_service = ImageService()
        self.logger = get_logger('primary_image_widget')

        # Current primary image data
        self.current_image: Optional[Dict[str, Any]] = None

        self._setup_ui()
        self.load_primary_image()

    def _setup_ui(self):
        """Set up the user interface."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 10, 0)  # Small right margin
        layout.setSpacing(2)

        # Image label
        self.image_label = QLabel()
        self.image_label.setFixedSize(50, 50)
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        set_props(self.image_label, role="card")
        self.image_label.setCursor(Qt.CursorShape.PointingHandCursor)

        # Install event filter for mouse clicks
        self.image_label.mousePressEvent = self._on_image_clicked

        layout.addWidget(self.image_label)

    def load_primary_image(self):
        """Load and display the primary image."""
        if not self.document_id or not self.db_manager:
            self._show_no_image()
            return

        try:
            # Get primary image from database
            primary_image = self.db_manager.get_primary_image(self.document_id)

            if primary_image:
                self.current_image = primary_image
                file_path = resolve_image_path(primary_image)  # also finds images in a moved data folder

                if file_path and Path(file_path).exists():
                    # Load thumbnail
                    thumbnail = self.image_service.get_thumbnail(file_path, size=50)

                    if thumbnail and not thumbnail.isNull():
                        set_props(self.image_label, role="card")
                        self.image_label.setPixmap(thumbnail)
                        self.image_label.setToolTip(f"Primary Image\n{primary_image.get('original_name', '')}\nLeft-click: Enlarge\nRight-click: Options")
                        return

            # No primary image or failed to load
            self._show_no_image()

        except Exception as e:
            self.logger.error(f"Error loading primary image: {e}", exc_info=True)
            self._show_no_image()

    def _show_no_image(self):
        """Show placeholder when no primary image exists."""
        self.current_image = None
        self.image_label.clear()
        self.image_label.setText("?")
        set_props(self.image_label, role="dropzone", dragActive=False)
        placeholder_font = self.image_label.font()
        placeholder_font.setPointSize(20)
        self.image_label.setFont(placeholder_font)
        self.image_label.setToolTip("No primary image\nClick to go to Images tab")

    def refresh(self):
        """Reload the primary image (called when primary changes)."""
        self.load_primary_image()

    def _on_image_clicked(self, event):
        """Handle mouse click on image."""
        if event.button() == Qt.MouseButton.LeftButton:
            if self.current_image:
                # Open full-size preview
                self._show_full_preview()
            else:
                # No image - go to Images tab
                self.go_to_images_tab.emit()

    def contextMenuEvent(self, event: QContextMenuEvent):
        """Handle right-click context menu."""
        if not self.current_image:
            # No image - only show "Go to Images Tab"
            menu = QMenu(self)
            go_to_images_action = QAction("🖼️ Go to Images Tab", self)
            go_to_images_action.triggered.connect(lambda: self.go_to_images_tab.emit())
            menu.addAction(go_to_images_action)
            menu.exec(event.globalPos())
            return

        # Show full context menu for image
        menu = QMenu(self)

        # View Full Size
        view_action = QAction("🔍 View Full Size", self)
        view_action.triggered.connect(self._show_full_preview)
        menu.addAction(view_action)

        # Copy Image
        copy_action = QAction("📋 Copy Image", self)
        copy_action.triggered.connect(self._copy_image)
        menu.addAction(copy_action)

        # Copy Image Path
        copy_path_action = QAction("📄 Copy Image Path", self)
        copy_path_action.triggered.connect(self._copy_path)
        menu.addAction(copy_path_action)

        menu.addSeparator()

        # Go to Images Tab
        go_to_images_action = QAction("🖼️ Go to Images Tab", self)
        go_to_images_action.triggered.connect(lambda: self.go_to_images_tab.emit())
        menu.addAction(go_to_images_action)

        menu.exec(event.globalPos())

    def _show_full_preview(self):
        """Open the full-size preview dialog."""
        if not self.current_image:
            return

        try:
            # Create preview dialog with just this image
            images = [self.current_image]
            dialog = ImagePreviewDialog(images, 0, self)
            dialog.exec()
        except Exception as e:
            self.logger.error(f"Error showing preview: {e}", exc_info=True)

    def _copy_image(self):
        """Copy the image to clipboard."""
        if not self.current_image:
            return

        try:
            file_path = resolve_image_path(self.current_image)
            pixmap = QPixmap(file_path)

            if not pixmap.isNull():
                clipboard = QGuiApplication.clipboard()
                clipboard.setPixmap(pixmap)
                self.logger.info("Primary image copied to clipboard")
            else:
                self.logger.warning("Failed to load image for copying")

        except Exception as e:
            self.logger.error(f"Error copying image: {e}", exc_info=True)

    def _copy_path(self):
        """Copy the image file path to clipboard."""
        if not self.current_image:
            return

        try:
            file_path = resolve_image_path(self.current_image)
            if file_path:
                clipboard = QGuiApplication.clipboard()
                clipboard.setText(file_path)
                self.logger.info("Image path copied to clipboard")

        except Exception as e:
            self.logger.error(f"Error copying path: {e}", exc_info=True)
