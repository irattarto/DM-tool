"""Theme manager: scheme detection, palette + stylesheet application, live switching."""

from typing import Optional

from PyQt6 import sip
from PyQt6.QtCore import QObject, Qt, pyqtSignal
from PyQt6.QtGui import QGuiApplication, QPalette
from PyQt6.QtWidgets import QApplication, QWidget

from gui.theme.qss import build_qss
from gui.theme.tokens import tokens_for, tokens_to_qpalette
from utils.logger import get_logger

# The OS palette, captured before we ever replace it. Used to guess the scheme when
# the platform does not report one (Qt returns ColorScheme.Unknown there).
_system_palette: Optional[QPalette] = None


def _remember_system_palette() -> None:
    global _system_palette
    if _system_palette is None and QGuiApplication.instance() is not None:
        _system_palette = QPalette(QGuiApplication.palette())


def resolve_scheme(setting: str) -> str:
    """Resolve a theme setting ('auto' | 'dark' | 'light') to 'dark' or 'light'."""
    setting = (setting or 'auto').lower()
    if setting in ('dark', 'light'):
        return setting

    app = QGuiApplication.instance()
    if app is None:
        return 'dark'
    _remember_system_palette()

    scheme = QGuiApplication.styleHints().colorScheme()
    if scheme == Qt.ColorScheme.Dark:
        return 'dark'
    if scheme == Qt.ColorScheme.Light:
        return 'light'
    # Unknown: judge by the lightness of the OS window colour
    palette = _system_palette or QGuiApplication.palette()
    return 'dark' if palette.color(QPalette.ColorRole.Window).lightness() < 128 else 'light'


def repolish(widget: QWidget) -> None:
    """Re-evaluate the stylesheet after a dynamic property (role/variant/state) changed."""
    style = widget.style()
    style.unpolish(widget)
    style.polish(widget)
    widget.update()


def set_props(widget: QWidget, **props) -> QWidget:
    """Set styling properties (role / variant / state / dragActive) and re-polish.

    Replaces per-widget ``setStyleSheet`` colour strings; see gui/theme/qss.py.
    """
    for name, value in props.items():
        widget.setProperty(name, value)
    repolish(widget)
    return widget


class ThemeManager(QObject):
    """Applies the theme to the whole application and follows the OS scheme in 'auto'."""

    theme_changed = pyqtSignal(str)  # concrete scheme: 'dark' | 'light'

    def __init__(self):
        super().__init__()
        self.logger = get_logger('theme')
        self._setting = 'auto'
        self._scheme = 'dark'
        self._connected = False

    @property
    def scheme(self) -> str:
        return self._scheme

    @property
    def setting(self) -> str:
        return self._setting

    def tokens(self):
        return tokens_for(self._scheme)

    def apply(self, app: Optional[QApplication], setting: str) -> str:
        """Apply the theme ('auto' | 'dark' | 'light'). Returns the concrete scheme."""
        from gui.theme.style_manager import get_style_manager

        app = app or QApplication.instance()
        self._setting = (setting or 'auto').lower()
        self._scheme = resolve_scheme(self._setting)
        if app is None:
            return self._scheme

        tokens = tokens_for(self._scheme)
        style_manager = get_style_manager(theme=self._scheme)

        app.setStyle('Fusion')  # the only style that honours a full custom palette everywhere
        app.setPalette(tokens_to_qpalette(tokens))
        app.setStyleSheet(build_qss(tokens, style_manager._typography))

        self._watch_system_scheme()
        self.logger.info(f"Applied '{self._setting}' theme ({self._scheme})")
        self.theme_changed.emit(self._scheme)
        return self._scheme

    def _watch_system_scheme(self) -> None:
        if self._connected:
            return
        try:
            QGuiApplication.styleHints().colorSchemeChanged.connect(self._on_system_scheme_changed)
            self._connected = True
        except Exception as e:  # very old Qt builds
            self.logger.warning(f"Cannot follow system colour scheme: {e}")

    def _on_system_scheme_changed(self, *_args) -> None:
        # Only 'auto' follows the OS; an explicit dark/light choice is left alone
        if self._setting == 'auto':
            new_scheme = resolve_scheme('auto')
            if new_scheme != self._scheme:
                self.apply(QApplication.instance(), 'auto')


_theme_manager: Optional[ThemeManager] = None


def get_theme_manager() -> ThemeManager:
    global _theme_manager
    # The QObject can be destroyed together with its QApplication (tests create several)
    if _theme_manager is None or sip.isdeleted(_theme_manager):
        _theme_manager = ThemeManager()
    return _theme_manager
