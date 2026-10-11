"""Helpers for shutting worker threads down without QThread.terminate()."""

from PyQt6.QtCore import QThread

_retired = set()


def retire_worker(worker: QThread, wait_ms: int = 1000) -> None:
    """Ask a worker to stop and, if it is still busy, keep it alive until it ends.

    QThread.terminate() can leave locks held and corrupt state, so a worker that
    is still waiting on a network call is parked here (strong reference, no
    parent) and released when its thread finishes on its own.
    """
    if worker is None:
        return
    if hasattr(worker, "request_stop"):
        worker.request_stop()
    if not worker.isRunning() or worker.wait(wait_ms):
        return
    worker.setParent(None)
    _disconnect_result_signals(worker)   # the dialog that owned the slots may be destroyed by now
    _retired.add(worker)
    worker.finished.connect(lambda w=worker: _retired.discard(w))


def _disconnect_result_signals(worker: QThread) -> None:
    """Disconnect every signal the worker declares itself (not QThread's own ``finished``)."""
    meta = worker.metaObject()
    own_from = QThread.staticMetaObject.methodCount()
    for i in range(own_from, meta.methodCount()):
        method = meta.method(i)
        if method.methodType() != method.MethodType.Signal:
            continue
        name = bytes(method.name()).decode()
        try:
            getattr(worker, name).disconnect()
        except (TypeError, RuntimeError, AttributeError):
            pass
