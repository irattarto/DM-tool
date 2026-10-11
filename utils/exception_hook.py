"""Global exception hooks.

PyQt6 aborts the whole process when a slot raises and no ``sys.excepthook`` is set.
The hook installed here logs the traceback and shows one non-blocking error message
instead, so a bug in a single handler no longer takes the application (and unsaved
work) down.
"""

import sys
import threading
import traceback
from typing import Callable, Optional

from utils.logger import get_logger

_reporting = False
_notifier: Optional[Callable[[str], None]] = None


def _default_notifier(summary: str) -> None:
    """Show a non-blocking message box when a QApplication exists."""
    try:
        from PyQt6.QtCore import Qt, QTimer
        from PyQt6.QtWidgets import QApplication, QMessageBox
        if QApplication.instance() is None:
            return

        def show():
            box = QMessageBox(QMessageBox.Icon.Warning, "Unexpected error",
                              "Something went wrong. The details were written to the log file.\n"
                              "You can keep working, but consider saving and restarting.")
            box.setDetailedText(summary)
            box.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
            box.setWindowModality(Qt.WindowModality.NonModal)
            box.show()

        QTimer.singleShot(0, show)
    except Exception:
        pass


def handle_exception(exc_type, exc_value, exc_tb) -> None:
    """sys.excepthook replacement: log, notify once, never recurse."""
    global _reporting
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_tb)
        return
    text = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
    try:
        get_logger('exceptions').error(f"Unhandled exception:\n{text}")
    except Exception:
        sys.stderr.write(text)
    if _reporting:
        return
    _reporting = True
    try:
        (_notifier or _default_notifier)(text[-2000:])
    except Exception:
        pass
    finally:
        _reporting = False


def _thread_hook(args) -> None:
    handle_exception(args.exc_type, args.exc_value, args.exc_traceback)


def _unraisable_hook(unraisable) -> None:
    try:
        get_logger('exceptions').error(
            f"Unraisable exception in {unraisable.object!r}: {unraisable.exc_value!r}")
    except Exception:
        pass


def install(notifier: Optional[Callable[[str], None]] = None) -> None:
    """Install the hooks (idempotent). ``notifier`` replaces the message box (tests)."""
    global _notifier
    _notifier = notifier
    sys.excepthook = handle_exception
    threading.excepthook = _thread_hook
    sys.unraisablehook = _unraisable_hook
