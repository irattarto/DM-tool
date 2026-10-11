"""Worker thread lifecycle tests (offscreen Qt)."""
import time

import pytest

pytest.importorskip("PyQt6")
from PyQt6.QtCore import QCoreApplication, QThread

from gui.workers import lifecycle


@pytest.fixture(scope="module")
def app():
    return QCoreApplication.instance() or QCoreApplication([])


def _wait(cond, app, timeout=5):
    end = time.time() + timeout
    while time.time() < end and not cond():
        app.processEvents()
        time.sleep(0.01)
    return cond()


def test_retire_worker_parks_running_thread_instead_of_terminating(app):
    class Slow(QThread):
        def request_stop(self):
            self.stop = True

        def run(self):
            time.sleep(0.3)

    w = Slow()
    w.start()
    lifecycle.retire_worker(w, wait_ms=10)
    assert w in lifecycle._retired and w.isRunning()
    assert _wait(lambda: w not in lifecycle._retired, app)
