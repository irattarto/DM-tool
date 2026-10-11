"""Backup/restore run on worker threads and keep the dialog responsive and locked."""
import threading
import time

import pytest

pytest.importorskip("PyQt6")
from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtWidgets import QApplication

from gui.workers.module_backup_worker import ModuleBackupWorker, ModuleRestoreWorker
from models.database import DatabaseManager
from services.backup_service import BackupService


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def _wait(cond, app, timeout=10):
    end = time.time() + timeout
    while time.time() < end and not cond():
        app.processEvents()
        time.sleep(0.01)
    return cond()


class _StubImages:
    def regenerate_thumbnails_for_module(self, module_id):
        return 0


def _service(db, tmp_path):
    svc = BackupService(db, _StubImages())
    svc.base_path = tmp_path
    svc.images_path = tmp_path / "rpg_images" / "modules"
    return svc


class _RecordingService:
    """Stands in for BackupService: records the thread it runs on and reports progress."""

    def __init__(self):
        self.thread_id = None

    def restore_module(self, zip_path, mode, target, progress=None):
        self.thread_id = threading.get_ident()
        progress("Importing...")
        return True, 7, "done"

    def backup_module(self, module_id, path, progress=None):
        self.thread_id = threading.get_ident()
        progress("Writing...")
        return True, "ok", 2


def test_restore_worker_runs_off_the_gui_thread_and_reports_progress(app):
    svc = _RecordingService()
    worker = ModuleRestoreWorker(svc, "x.zip", "new")
    stages, results = [], []
    worker.progress.connect(stages.append)
    worker.result_ready.connect(lambda *a: results.append(a))
    worker.start()
    assert _wait(lambda: results, app)
    worker.wait()
    assert svc.thread_id != threading.get_ident()
    assert stages == ["Importing..."]
    assert results == [(True, 7, "done")]


def test_backup_worker_reports_missing_images(app):
    svc = _RecordingService()
    worker = ModuleBackupWorker(svc, 1, "x.zip")
    results = []
    worker.result_ready.connect(lambda *a: results.append(a))
    worker.start()
    assert _wait(lambda: results, app)
    worker.wait()
    assert results == [(True, "ok", 2)]
    assert svc.thread_id != threading.get_ident()


def test_worker_that_never_started_can_be_cancelled(app):
    svc = _RecordingService()
    worker = ModuleRestoreWorker(svc, "x.zip", "new")
    worker.request_stop()
    results = []
    worker.result_ready.connect(lambda *a: results.append(a))
    worker.start()
    assert _wait(lambda: results, app)
    worker.wait()
    assert results[0][0] is False and svc.thread_id is None


def test_real_backup_and_restore_round_trip_on_worker_threads(app, tmp_path):
    db = DatabaseManager(":memory:")
    db.initialize_database()
    mod = db.create_module("Source", "d")
    db.create_document(mod, "npc", "Aria", "Elf archer")
    svc = _service(db, tmp_path)
    zip_path = str(tmp_path / "b.zip")

    backup = ModuleBackupWorker(svc, mod, zip_path)
    done = []
    backup.result_ready.connect(lambda *a: done.append(a))
    backup.start()
    assert _wait(lambda: done, app)
    backup.wait()
    assert done[0][0] is True

    restore = ModuleRestoreWorker(svc, zip_path, "new")
    restored, stages = [], []
    restore.progress.connect(stages.append)
    restore.result_ready.connect(lambda *a: restored.append(a))
    restore.start()
    assert _wait(lambda: restored, app)
    restore.wait()
    ok, new_id, message = restored[0]
    assert ok and new_id != mod
    assert [d['title'] for d in db.get_documents(new_id)] == ["Aria"]
    assert "Validating backup..." in stages and "Importing documents and sessions..." in stages


def test_corrupt_backup_fails_cleanly_and_changes_nothing(app, tmp_path):
    db = DatabaseManager(":memory:")
    db.initialize_database()
    mod = db.create_module("Keep", "d")
    db.create_document(mod, "npc", "Stays", "body")
    bad = tmp_path / "bad.zip"
    bad.write_bytes(b"not a zip at all")
    worker = ModuleRestoreWorker(_service(db, tmp_path), str(bad), "overwrite", mod)
    results = []
    worker.result_ready.connect(lambda *a: results.append(a))
    worker.start()
    assert _wait(lambda: results, app)
    worker.wait()
    assert results[0][0] is False
    assert [d['title'] for d in db.get_documents(mod)] == ["Stays"]


class _SlowWorker(QThread):
    progress = pyqtSignal(str)
    result_ready = pyqtSignal(bool, object, str)

    def run(self):
        self.progress.emit("Stage 1")
        time.sleep(0.4)
        self.result_ready.emit(True, 1, "ok")


def test_database_dialog_locks_while_a_worker_runs_and_unlocks_after(app, tmp_path):
    from gui.database_dialog import DatabaseDialog
    from services.image_service import ImageService

    db = DatabaseManager(":memory:")
    db.initialize_database()
    dialog = DatabaseDialog(db, ImageService(tmp_path / "imgs"))
    try:
        worker = _SlowWorker(dialog)
        dialog._start_worker(worker, "Working...")
        assert dialog.is_busy()
        assert not dialog.restore_btn.isEnabled() and not dialog.close_btn.isEnabled()
        assert not dialog.progress_bar.isHidden()
        assert dialog.status_label.text() in ("Working...", "Stage 1") or _wait(
            lambda: dialog.status_label.text() == "Stage 1", app)

        dialog.show()
        dialog.reject()           # Escape while busy is ignored
        assert dialog.isVisible()

        assert _wait(lambda: dialog._worker is None, app)
        assert dialog.restore_btn.isEnabled() and dialog.close_btn.isEnabled()
        assert dialog.progress_bar.isHidden()
    finally:
        dialog.close()
        dialog.deleteLater()
