"""Worker threads for module backup and restore, so large archives do not freeze the window.

A restore is deliberately not interruptible: it takes a safety snapshot and rolls back on
failure, and stopping half-way would defeat that. ``request_stop`` therefore only prevents a
worker that has not started yet from running.
"""

from typing import Optional

from PyQt6.QtCore import QThread, pyqtSignal

from utils.logger import get_logger


class ModuleRestoreWorker(QThread):
    """Restores a module backup in the background."""

    progress = pyqtSignal(str)                 # current stage
    result_ready = pyqtSignal(bool, object, str)  # success, module id (or None), message

    def __init__(self, backup_service, zip_path: str, restore_mode: str,
                 target_module_id: Optional[int] = None, parent=None):
        super().__init__(parent)
        self.backup_service = backup_service
        self.zip_path = zip_path
        self.restore_mode = restore_mode
        self.target_module_id = target_module_id
        self.logger = get_logger('module_restore_worker')
        self._stop_requested = False

    def request_stop(self):
        """Only effective before the restore has started (see module docstring)."""
        self._stop_requested = True

    def run(self):
        if self._stop_requested:
            self.result_ready.emit(False, None, "Restore cancelled")
            return
        try:
            success, module_id, message = self.backup_service.restore_module(
                self.zip_path, self.restore_mode, self.target_module_id,
                progress=self.progress.emit
            )
        except Exception as e:  # restore_module handles its own errors; this is the last resort
            self.logger.error(f"Restore worker failed: {e}", exc_info=True)
            success, module_id, message = False, None, f"Restore failed: {e}"
        self.result_ready.emit(success, module_id, message)


class ModuleBackupWorker(QThread):
    """Creates a module backup in the background."""

    progress = pyqtSignal(str)
    result_ready = pyqtSignal(bool, str, int)  # success, message, missing image count

    def __init__(self, backup_service, module_id: int, output_path: str, parent=None):
        super().__init__(parent)
        self.backup_service = backup_service
        self.module_id = module_id
        self.output_path = output_path
        self.logger = get_logger('module_backup_worker')
        self._stop_requested = False

    def request_stop(self):
        self._stop_requested = True

    def run(self):
        if self._stop_requested:
            self.result_ready.emit(False, "Backup cancelled", 0)
            return
        try:
            success, message, missing = self.backup_service.backup_module(
                self.module_id, self.output_path, progress=self.progress.emit
            )
        except Exception as e:
            self.logger.error(f"Backup worker failed: {e}", exc_info=True)
            success, message, missing = False, f"Backup failed: {e}", 0
        self.result_ready.emit(success, message, missing)
