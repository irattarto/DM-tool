"""
Database management dialog for RPG Database Manager.

Provides tools for database maintenance including integrity checks,
repairs, cleanup, and location management.
"""

from gui.theme import set_props
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel,
    QPushButton, QFileDialog, QFormLayout, QProgressBar
)
from PyQt6.QtCore import Qt
import os

from utils.ui_helpers import show_error, show_warning, show_info, show_question
from utils.logger import get_logger
from gui.components.dialog_button_bar import DialogButtonBar
from services.backup_service import BackupService
from gui.dialogs.module_backup_dialogs import ModuleSelectionDialog, RestoreOptionsDialog
from gui.workers.module_backup_worker import ModuleBackupWorker, ModuleRestoreWorker


class DatabaseDialog(QDialog):
    """
    Dialog for database management and maintenance tools.

    Features:
    - View database information (path, size)
    - Change database location
    - Check database integrity
    - Repair database
    - Cleanup database (remove inactive campaigns and orphaned files)
    """

    def __init__(self, db_manager, image_service, parent=None):
        super().__init__(parent)
        self.db_manager = db_manager
        self.image_service = image_service
        self.logger = get_logger('database_dialog')
        self.backup_service = BackupService(db_manager, image_service)
        self._worker = None  # running backup/restore thread, if any
        self._pending_backup_path = ""
        self._pending_restore_mode = ""

        self.setWindowTitle("Database Management")
        self.setModal(True)
        self.resize(600, 400)

        self._setup_ui()
        self._load_database_info()

    def _setup_ui(self):
        """Setup the dialog UI."""
        layout = QVBoxLayout(self)

        # Database Information Section
        info_group = QGroupBox("Database Information")
        info_layout = QFormLayout(info_group)

        self.db_path_label = QLabel("Loading...")
        self.db_path_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.db_path_label.setWordWrap(True)
        info_layout.addRow("Database Path:", self.db_path_label)

        self.db_size_label = QLabel("Calculating...")
        self.db_size_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        info_layout.addRow("Database Size:", self.db_size_label)

        layout.addWidget(info_group)

        # Database Tools Section
        tools_group = QGroupBox("Database Maintenance Tools")
        tools_layout = QVBoxLayout(tools_group)

        # Integrity check button
        self.integrity_btn = QPushButton("Check Database Integrity")
        self.integrity_btn.setToolTip("Verify database health and detect corruption")
        self.integrity_btn.clicked.connect(self._on_database_integrity_check)
        tools_layout.addWidget(self.integrity_btn)

        # Repair button
        self.repair_btn = QPushButton("Repair Database")
        self.repair_btn.setToolTip("Fix database corruption and optimize")
        self.repair_btn.clicked.connect(self._on_database_repair)
        tools_layout.addWidget(self.repair_btn)

        # Cleanup button
        self.cleanup_btn = QPushButton("Cleanup Database")
        self.cleanup_btn.setToolTip("Permanently delete inactive campaigns and orphaned files")
        self.cleanup_btn.clicked.connect(self._on_database_cleanup)
        tools_layout.addWidget(self.cleanup_btn)

        layout.addWidget(tools_group)

        # Module Backup & Restore Section
        backup_group = QGroupBox("Campaign Backup && Restore")
        backup_layout = QVBoxLayout(backup_group)

        # Backup button
        self.backup_btn = QPushButton("Backup Campaign...")
        self.backup_btn.setToolTip("Create a ZIP backup of a campaign (database + images)")
        self.backup_btn.clicked.connect(self._on_backup_module)
        backup_layout.addWidget(self.backup_btn)

        # Restore button
        self.restore_btn = QPushButton("Restore from Backup...")
        self.restore_btn.setToolTip("Restore a campaign from a ZIP backup file")
        self.restore_btn.clicked.connect(self._on_restore_module)
        backup_layout.addWidget(self.restore_btn)

        layout.addWidget(backup_group)

        # Status label
        self.status_label = QLabel("")
        self.status_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        # Busy indicator for long backup/restore runs (hidden otherwise)
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)  # indeterminate
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        # Button bar
        button_bar = DialogButtonBar(alignment='right', parent=self)
        self.close_btn = button_bar.add_button("Close")
        self.close_btn.clicked.connect(self.accept)
        layout.addWidget(button_bar)

    # --- long-running backup / restore -----------------------------------
    def _set_busy(self, busy: bool, text: str = "") -> None:
        """Lock the dialog while a worker thread runs; show its current stage."""
        for button in (self.integrity_btn, self.repair_btn, self.cleanup_btn,
                       self.backup_btn, self.restore_btn, self.close_btn):
            button.setEnabled(not busy)
        self.progress_bar.setVisible(busy)
        if text:
            self.status_label.setText(text)

    def is_busy(self) -> bool:
        return self._worker is not None and self._worker.isRunning()

    def reject(self):
        """Escape/close must not abandon a restore that is writing to the database."""
        if self.is_busy():
            return
        super().reject()

    def closeEvent(self, event):
        if self.is_busy():
            event.ignore()
            return
        super().closeEvent(event)

    def _start_worker(self, worker, busy_text: str) -> None:
        self._worker = worker
        worker.progress.connect(self.status_label.setText)
        worker.finished.connect(self._on_worker_thread_finished)  # QThread.finished
        self._set_busy(True, busy_text)
        worker.start()

    def _on_worker_thread_finished(self):
        worker, self._worker = self._worker, None
        self._set_busy(False)
        if worker is not None:
            worker.deleteLater()

    def _load_database_info(self):
        """Load and display current database information."""
        try:
            if self.db_manager and hasattr(self.db_manager, 'db_path'):
                db_path = self.db_manager.db_path
                self.db_path_label.setText(str(db_path))

                # Calculate file size
                if os.path.exists(db_path):
                    file_size = os.path.getsize(db_path)
                    size_mb = file_size / (1024 * 1024)
                    self.db_size_label.setText(f"{size_mb:.2f} MB ({file_size:,} bytes)")
                else:
                    self.db_size_label.setText("File not found")
            else:
                self.db_path_label.setText("No database loaded")
                self.db_size_label.setText("N/A")

        except Exception as e:
            self.logger.error(f"Error loading database info: {e}")
            self.db_path_label.setText("Error loading path")
            self.db_size_label.setText("Error calculating size")

    def _on_database_integrity_check(self):
        """Handle database integrity check."""
        try:
            self.status_label.setText("Checking database integrity...")
            self.integrity_btn.setEnabled(False)

            # Run integrity check
            integrity_results = self.db_manager.check_database_integrity()

            # Show results in a dialog
            self._show_integrity_results_dialog(integrity_results)

            self.status_label.setText("Integrity check completed")
            self.integrity_btn.setEnabled(True)

        except Exception as e:
            self.logger.error(f"Error during database integrity check: {e}", exc_info=True)
            show_error(self, "Error", f"Failed to check database integrity: {e}")
            self.status_label.setText("Integrity check failed")
            self.integrity_btn.setEnabled(True)

    def _on_database_repair(self):
        """Handle database repair."""
        try:
            self.status_label.setText("Checking database health...")

            # First check if repair is needed
            integrity_results = self.db_manager.check_database_integrity()

            if integrity_results['is_healthy']:
                show_info(self, "Database Healthy", "Database is already healthy and doesn't need repair.")
                self.status_label.setText("Database is healthy")
                return

            # Show confirmation dialog
            error_summary = "\n".join(f"• {error}" for error in integrity_results['errors'])
            if not show_question(
                self,
                "Database Repair Required",
                "Database integrity issues detected:\n\n"
                f"{error_summary}\n\n"
                "Attempting repair may fix these issues but could result in data loss.\n\n"
                "Do you want to proceed with repair?"
            ):
                self.status_label.setText("Repair cancelled")
                return

            self.status_label.setText("Repairing database...")
            self.repair_btn.setEnabled(False)

            # Run repair
            repair_results = self.db_manager.repair_database()

            # Show repair results
            self._show_repair_results_dialog(repair_results)

            self.status_label.setText("Repair completed")
            self.repair_btn.setEnabled(True)

        except Exception as e:
            self.logger.error(f"Error during database repair: {e}", exc_info=True)
            show_error(self, "Error", f"Failed to repair database: {e}")
            self.status_label.setText("Repair failed")
            self.repair_btn.setEnabled(True)

    def _on_database_cleanup(self):
        """Handle database cleanup."""
        try:
            # Warning before opening
            reply = show_question(
                self,
                "Database Cleanup",
                "This tool allows you to permanently delete inactive campaigns and orphaned files.\n\n"
                "This action cannot be undone. Do you want to continue?"
            )

            if reply:
                from gui.database_cleanup_dialog import DatabaseCleanupDialog
                dialog = DatabaseCleanupDialog(self.db_manager, self.image_service, self)
                if dialog.exec() == QDialog.DialogCode.Accepted:
                    self.status_label.setText("Cleanup completed")
                    # Refresh database info
                    self._load_database_info()
                else:
                    self.status_label.setText("Cleanup cancelled")

        except Exception as e:
            self.logger.error(f"Error opening database cleanup: {e}", exc_info=True)
            show_error(self, "Error", f"Failed to open database cleanup: {e}")
            self.status_label.setText("Cleanup failed")

    def _show_integrity_results_dialog(self, integrity_results):
        """Show database integrity check results in a dialog."""
        dialog = QDialog(self)
        dialog.setWindowTitle("Database Integrity Check Results")
        dialog.setModal(True)
        dialog.resize(600, 500)

        layout = QVBoxLayout(dialog)

        # Status
        status_label = QLabel(f"Database Status: {'HEALTHY' if integrity_results['is_healthy'] else 'CORRUPTED'}")
        set_props(status_label, role="status", state="ok" if integrity_results['is_healthy'] else "error")
        layout.addWidget(status_label)

        # Database info
        info_group = QGroupBox("Database Information")
        info_layout = QFormLayout(info_group)

        info_layout.addRow("Database Path:", QLabel(integrity_results['database_path']))
        info_layout.addRow("Connection Status:", QLabel("Connected" if integrity_results['is_connected'] else "Disconnected"))

        if integrity_results['pragma_info']:
            info_layout.addRow("Page Size:", QLabel(str(integrity_results['pragma_info'].get('PRAGMA page_size', 'Unknown'))))
            info_layout.addRow("Page Count:", QLabel(str(integrity_results['pragma_info'].get('PRAGMA page_count', 'Unknown'))))

        layout.addWidget(info_group)

        # Integrity check results
        if integrity_results['integrity_check']:
            integrity_group = QGroupBox("Integrity Check")
            integrity_layout = QVBoxLayout(integrity_group)
            integrity_layout.addWidget(QLabel(f"Result: {integrity_results['integrity_check']}"))
            layout.addWidget(integrity_group)

        # Foreign key check
        if integrity_results['foreign_key_check']:
            fk_group = QGroupBox("Foreign Key Constraints")
            fk_layout = QVBoxLayout(fk_group)
            if integrity_results['foreign_key_check']:
                fk_layout.addWidget(QLabel(f"Violations found: {len(integrity_results['foreign_key_check'])}"))
                for violation in integrity_results['foreign_key_check'][:5]:  # Show first 5
                    fk_layout.addWidget(QLabel(f"• Table: {violation.get('table', 'Unknown')}, "
                                              f"Row: {violation.get('rowid', 'Unknown')}"))
            else:
                fk_layout.addWidget(QLabel("No violations found"))
            layout.addWidget(fk_group)

        # Errors
        if integrity_results['errors']:
            errors_group = QGroupBox("Issues Found")
            errors_layout = QVBoxLayout(errors_group)
            for error in integrity_results['errors']:
                errors_layout.addWidget(QLabel(f"• {error}"))
            layout.addWidget(errors_group)

        # Buttons
        button_layout = QHBoxLayout()

        if not integrity_results['is_healthy']:
            repair_btn = QPushButton("Repair Database")
            repair_btn.clicked.connect(lambda: self._on_database_repair_from_dialog(dialog))
            button_layout.addWidget(repair_btn)

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(dialog.accept)
        button_layout.addWidget(close_btn)

        layout.addLayout(button_layout)

        dialog.exec()

    def _on_database_repair_from_dialog(self, parent_dialog):
        """Handle repair from integrity check dialog."""
        parent_dialog.accept()  # Close the integrity dialog
        self._on_database_repair()  # Run repair

    def _show_repair_results_dialog(self, repair_results):
        """Show database repair results in a dialog."""
        dialog = QDialog(self)
        dialog.setWindowTitle("Database Repair Results")
        dialog.setModal(True)
        dialog.resize(500, 400)

        layout = QVBoxLayout(dialog)

        # Status
        status_label = QLabel(f"Repair Status: {'SUCCESS' if repair_results['success'] else 'FAILED'}")
        set_props(status_label, role="status", state="ok" if repair_results['success'] else "error")
        layout.addWidget(status_label)

        # Actions taken
        if repair_results['actions_taken']:
            actions_group = QGroupBox("Actions Performed")
            actions_layout = QVBoxLayout(actions_group)
            for action in repair_results['actions_taken']:
                actions_layout.addWidget(QLabel(f"• {action}"))
            layout.addWidget(actions_group)

        # Errors
        if repair_results['errors']:
            errors_group = QGroupBox("Errors Encountered")
            errors_layout = QVBoxLayout(errors_group)
            for error in repair_results['errors']:
                errors_layout.addWidget(QLabel(f"• {error}"))
            layout.addWidget(errors_group)

        # Final check recommendation
        if repair_results['success']:
            layout.addWidget(QLabel("✅ Database repair completed successfully. "
                                  "You may need to restart the application."))
        else:
            layout.addWidget(QLabel("❌ Database repair failed. "
                                  "Consider restoring from backup or recreating the database."))

        # Buttons
        button_layout = QHBoxLayout()

        if repair_results['success']:
            restart_btn = QPushButton("Restart Application")
            restart_btn.clicked.connect(lambda: self._restart_application())
            button_layout.addWidget(restart_btn)

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(dialog.accept)
        button_layout.addWidget(close_btn)

        layout.addLayout(button_layout)

        dialog.exec()

    def _restart_application(self):
        """Restart the application."""
        self.logger.info("User requested application restart after database repair")
        # Close the main window to trigger application exit
        if hasattr(self.parent(), 'close'):
            self.parent().close()

    def _on_backup_module(self):
        """Handle backup campaign button click."""
        try:
            # Show module selection dialog
            selection_dialog = ModuleSelectionDialog(self.db_manager, self)
            if selection_dialog.exec() != QDialog.DialogCode.Accepted:
                return

            module_id = selection_dialog.get_selected_module_id()
            if not module_id:
                return

            # Get module info for default filename
            module = self.db_manager.get_module(module_id)
            if not module:
                show_error(self, "Error", f"Module {module_id} not found")
                return

            module_name = module.get('name', 'module')
            from datetime import datetime
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            default_filename = f"{module_name}_backup_{timestamp}.zip"

            # Show file save dialog
            file_path, _ = QFileDialog.getSaveFileName(
                self,
                "Save Campaign Backup",
                default_filename,
                "ZIP Files (*.zip);;All Files (*)"
            )

            if not file_path:
                return

            # Ensure .zip extension
            if not file_path.lower().endswith('.zip'):
                file_path += '.zip'

            # Perform backup in the background
            self._pending_backup_path = file_path
            worker = ModuleBackupWorker(self.backup_service, module_id, file_path, self)
            worker.result_ready.connect(self._on_backup_finished)
            self._start_worker(worker, f"Backing up campaign '{module_name}'...")

        except Exception as e:
            self.logger.error(f"Error during backup: {e}", exc_info=True)
            show_error(self, "Error", f"Failed to create backup: {e}")
            self.status_label.setText("Backup failed")
            self._set_busy(False)

    def _on_backup_finished(self, success: bool, message: str, missing_count: int):
        file_path = self._pending_backup_path
        if success:
            show_info(self, "Backup Successful", f"{message}\n\nBackup saved to:\n{file_path}")
            self.status_label.setText(f"Backup created: {file_path}")
            if missing_count > 0:
                show_warning(
                    self,
                    "Missing Images Warning",
                    f"{missing_count} image file(s) were referenced in the database but not found "
                    f"on disk and were NOT included in the backup.\n\n"
                    f"The backup is otherwise complete, but restoring it will not recover those images.\n\n"
                    f"You may want to check the Images section of the affected documents."
                )
        else:
            show_error(self, "Backup Failed", message)
            self.status_label.setText("Backup failed")

    def _on_restore_module(self):
        """Handle restore campaign button click."""
        try:
            # Show file open dialog
            file_path, _ = QFileDialog.getOpenFileName(
                self,
                "Select Backup File",
                "",
                "ZIP Files (*.zip);;All Files (*)"
            )

            if not file_path:
                return

            # Validate backup and get metadata
            self.status_label.setText("Validating backup...")
            is_valid, metadata, validation_msg = self.backup_service.validate_backup(file_path)

            if not is_valid:
                show_error(self, "Invalid Backup", f"The selected file is not a valid backup:\n\n{validation_msg}")
                self.status_label.setText("Invalid backup file")
                return

            # Show restore options dialog
            restore_dialog = RestoreOptionsDialog(self.db_manager, metadata, self)
            if restore_dialog.exec() != QDialog.DialogCode.Accepted:
                self.status_label.setText("Restore cancelled")
                return

            restore_mode, target_module_id = restore_dialog.get_restore_options()

            # Confirm overwrite mode
            if restore_mode == "overwrite":
                target_module = self.db_manager.get_module(target_module_id)
                target_name = target_module.get('name', 'Unknown') if target_module else 'Unknown'

                confirm_msg = (
                    f"Are you sure you want to overwrite campaign '{target_name}'?\n\n"
                    "⚠ WARNING: This will permanently delete all existing data in this campaign:\n"
                    "  - All documents, NPCs, locations, quests\n"
                    "  - All images\n"
                    "  - All game sessions\n"
                    "  - All relationships\n\n"
                    "This action CANNOT be undone!"
                )

                if not show_question(self, "Confirm Overwrite", confirm_msg):
                    self.status_label.setText("Restore cancelled")
                    return

            # Perform restore in the background (the dialog stays locked until it ends)
            self._pending_restore_mode = restore_mode
            worker = ModuleRestoreWorker(self.backup_service, file_path, restore_mode, target_module_id, self)
            worker.result_ready.connect(self._on_restore_finished)
            self._start_worker(worker, "Restoring campaign...")

        except Exception as e:
            self.logger.error(f"Error during restore: {e}", exc_info=True)
            show_error(self, "Error", f"Failed to restore campaign: {e}")
            self.status_label.setText("Restore failed")
            self._set_busy(False)

    def _on_restore_finished(self, success: bool, new_module_id, message: str):
        if success:
            if self._pending_restore_mode == "new":
                new_module = self.db_manager.get_module(new_module_id)
                new_name = new_module.get('name', 'Unknown') if new_module else 'Unknown'
                show_info(
                    self,
                    "Restore Successful",
                    f"{message}\n\nNew campaign ID: {new_module_id}\nModule name: {new_name}"
                )
            else:
                show_info(self, "Restore Successful", message)

            self.status_label.setText(f"Campaign restored successfully (ID: {new_module_id})")
        else:
            show_error(self, "Restore Failed", message)
            self.status_label.setText("Restore failed")
