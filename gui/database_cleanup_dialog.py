"""
Database Cleanup Dialog for RPG Database Manager.
"""

from gui.theme import set_props
from typing import Dict, Any

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QTableWidget,
    QTableWidgetItem, QMessageBox, QLabel, QCheckBox, QGroupBox,
    QLineEdit
)
from PyQt6.QtCore import Qt

from models.database import DatabaseManager
from services.image_service import ImageService
from utils.logger import get_logger
from utils.ui_helpers import show_error, show_warning, show_info


class DatabaseCleanupDialog(QDialog):
    """Dialog for permanently deleting inactive campaigns and cleaning up orphaned files."""

    def __init__(self, db_manager: DatabaseManager, image_service: ImageService, parent=None):
        super().__init__(parent)
        self.db = db_manager
        self.image_service = image_service
        self.logger = get_logger('database_cleanup')

        self.setWindowTitle("Database Cleanup")
        self.setMinimumSize(800, 500)

        self._setup_ui()
        self._load_inactive_modules()

    def _setup_ui(self):
        """Set up the user interface."""
        layout = QVBoxLayout(self)

        # Header with warning
        header = QLabel("Database Cleanup - Permanent Deletion")
        header.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        set_props(header, role="h1")
        layout.addWidget(header)

        warning = QLabel(
            "⚠️ WARNING: This operation permanently deletes inactive campaigns and their data.\n"
            "This action CANNOT be undone. Make sure you have backups if needed."
        )
        warning.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        warning.setStyleSheet("padding: 10px; border: 2px solid palette(highlight); border-radius: 5px; font-weight: bold;")
        warning.setWordWrap(True)
        layout.addWidget(warning)

        # Inactive modules table
        modules_group = QGroupBox("Inactive Campaigns")
        modules_layout = QVBoxLayout(modules_group)

        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels([
            "ID", "Name", "Documents", "Images", "Sessions", "DB Size (KB)"
        ])

        # Set column widths
        self.table.setColumnWidth(0, 50)   # ID
        self.table.setColumnWidth(1, 300)  # Name
        self.table.setColumnWidth(2, 90)   # Documents
        self.table.setColumnWidth(3, 80)   # Images
        self.table.setColumnWidth(4, 80)   # Sessions
        self.table.setColumnWidth(5, 100)  # DB Size

        # Table settings
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.MultiSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)

        modules_layout.addWidget(self.table)

        # Select all button
        select_all_layout = QHBoxLayout()
        self.select_all_btn = QPushButton("Select All")
        self.select_all_btn.clicked.connect(self._select_all)
        select_all_layout.addWidget(self.select_all_btn)

        self.deselect_all_btn = QPushButton("Deselect All")
        self.deselect_all_btn.clicked.connect(self._deselect_all)
        select_all_layout.addWidget(self.deselect_all_btn)

        select_all_layout.addStretch()
        modules_layout.addLayout(select_all_layout)

        layout.addWidget(modules_group)

        # Options group
        options_group = QGroupBox("Deletion Options")
        options_layout = QVBoxLayout(options_group)

        self.delete_db_files_checkbox = QCheckBox("Delete database files from disk")
        self.delete_db_files_checkbox.setChecked(True)
        self.delete_db_files_checkbox.setToolTip("Remove the physical .db files for deleted campaigns")
        options_layout.addWidget(self.delete_db_files_checkbox)

        self.delete_images_checkbox = QCheckBox("Delete image files from disk")
        self.delete_images_checkbox.setChecked(True)
        self.delete_images_checkbox.setToolTip("Remove all image files associated with deleted campaigns")
        options_layout.addWidget(self.delete_images_checkbox)

        layout.addWidget(options_group)

        # Confirmation input
        confirm_group = QGroupBox("Confirmation")
        confirm_layout = QVBoxLayout(confirm_group)

        confirm_label = QLabel("Type 'DELETE' to enable the Delete button:")
        confirm_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        confirm_layout.addWidget(confirm_label)

        self.confirm_input = QLineEdit()
        self.confirm_input.setPlaceholderText("Type DELETE here")
        self.confirm_input.textChanged.connect(self._on_confirm_text_changed)
        confirm_layout.addWidget(self.confirm_input)

        layout.addWidget(confirm_group)

        # Button layout
        button_layout = QHBoxLayout()

        button_layout.addStretch()

        self.delete_btn = QPushButton("Delete Selected Campaigns")
        self.delete_btn.setEnabled(False)
        set_props(self.delete_btn, variant="danger")
        self.delete_btn.clicked.connect(self._on_delete)
        button_layout.addWidget(self.delete_btn)

        self.close_btn = QPushButton("Close")
        self.close_btn.clicked.connect(self.reject)
        button_layout.addWidget(self.close_btn)

        layout.addLayout(button_layout)

    def _load_inactive_modules(self):
        """Load inactive campaigns into the table."""
        try:
            inactive_modules = self.db.get_inactive_modules()

            self.table.setRowCount(0)

            if not inactive_modules:
                show_info(self, "No Inactive Campaigns", "There are no inactive campaigns to clean up.")
                return

            for module in inactive_modules:
                self._add_module_row(module)

            self.logger.info(f"Loaded {len(inactive_modules)} inactive campaigns")

        except Exception as e:
            self.logger.error(f"Error loading inactive campaigns: {e}", exc_info=True)
            show_error(self, "Error", f"Failed to load inactive campaigns: {e}")

    def _add_module_row(self, module: Dict[str, Any]):
        """Add an inactive campaign to the table."""
        row = self.table.rowCount()
        self.table.insertRow(row)

        # ID
        id_item = QTableWidgetItem(str(module.get('id', '')))
        id_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self.table.setItem(row, 0, id_item)

        # Name
        name_item = QTableWidgetItem(module.get('name', ''))
        self.table.setItem(row, 1, name_item)

        # Documents
        doc_item = QTableWidgetItem(str(module.get('document_count', 0)))
        doc_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self.table.setItem(row, 2, doc_item)

        # Images
        img_item = QTableWidgetItem(str(module.get('image_count', 0)))
        img_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self.table.setItem(row, 3, img_item)

        # Sessions
        session_item = QTableWidgetItem(str(module.get('session_count', 0)))
        session_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self.table.setItem(row, 4, session_item)

        # Database size
        db_size = module.get('database_size', 0)
        size_kb = db_size / 1024 if db_size else 0
        size_item = QTableWidgetItem(f"{size_kb:.1f}")
        size_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self.table.setItem(row, 5, size_item)

    def _select_all(self):
        """Select all campaigns in the table."""
        self.table.selectAll()

    def _deselect_all(self):
        """Deselect all campaigns in the table."""
        self.table.clearSelection()

    def _on_confirm_text_changed(self, text: str):
        """Enable/disable delete button based on confirmation text."""
        self.delete_btn.setEnabled(text.strip().upper() == "DELETE")

    def _on_delete(self):
        """Handle delete button click."""
        # Get selected modules
        selected_rows = set(item.row() for item in self.table.selectedItems())

        if not selected_rows:
            show_warning(self, "No Selection", "Please select at least one campaign to delete.")
            return

        # Get module IDs and names
        modules_to_delete = []
        for row in selected_rows:
            module_id = int(self.table.item(row, 0).text())
            module_name = self.table.item(row, 1).text()
            doc_count = int(self.table.item(row, 2).text())
            img_count = int(self.table.item(row, 3).text())
            session_count = int(self.table.item(row, 4).text())

            modules_to_delete.append({
                'id': module_id,
                'name': module_name,
                'document_count': doc_count,
                'image_count': img_count,
                'session_count': session_count
            })

        # Build confirmation message
        total_docs = sum(m['document_count'] for m in modules_to_delete)
        total_images = sum(m['image_count'] for m in modules_to_delete)
        total_sessions = sum(m['session_count'] for m in modules_to_delete)

        delete_files = self.delete_db_files_checkbox.isChecked()
        delete_images = self.delete_images_checkbox.isChecked()

        message = (
            f"You are about to PERMANENTLY DELETE {len(modules_to_delete)} campaign(s):\n\n"
        )

        for module in modules_to_delete[:5]:  # Show first 5
            message += f"  - {module['name']}\n"

        if len(modules_to_delete) > 5:
            message += f"  ... and {len(modules_to_delete) - 5} more\n"

        message += (
            f"\nTotal data to be deleted:\n"
            f"  - {total_docs} documents\n"
            f"  - {total_images} images\n"
            f"  - {total_sessions} game sessions\n\n"
        )

        if delete_files:
            message += "Database files will be deleted from disk.\n"
        if delete_images:
            message += "Image files will be deleted from disk.\n"

        message += "\nThis action CANNOT be undone. Are you absolutely sure?"

        # Double confirmation
        reply = QMessageBox.warning(
            self,
            "Confirm Permanent Deletion",
            message,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        if reply != QMessageBox.StandardButton.Yes:
            return

        # Perform deletion
        success_count = 0
        failed_modules = []

        for module in modules_to_delete:
            try:
                # Hard delete from database
                success = self.db.hard_delete_module(module['id'], delete_files=delete_files)

                if success:
                    # Delete image files if requested
                    if delete_images:
                        self.image_service.delete_module_images(module['id'])

                    success_count += 1
                    self.logger.info(f"Permanently deleted campaign {module['id']}: {module['name']}")
                else:
                    failed_modules.append(module['name'])

            except Exception as e:
                self.logger.error(f"Error deleting campaign {module['id']}: {e}", exc_info=True)
                failed_modules.append(module['name'])

        # Show results
        if failed_modules:
            show_warning(
                self,
                "Partial Success",
                f"Deleted {success_count} campaign(s).\n\nFailed to delete:\n" + "\n".join(f"  - {name}" for name in failed_modules)
            )
        else:
            show_info(self, "Success", f"Successfully deleted {success_count} campaign(s).")

        # Refresh table and close
        self._load_inactive_modules()
        self.confirm_input.clear()
