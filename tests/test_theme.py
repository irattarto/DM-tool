"""Theme system: tokens, palette, stylesheet, scheme resolution and live switching."""
import pytest

pytest.importorskip("PyQt6")
from PyQt6.QtCore import Qt, QtMsgType, qInstallMessageHandler
from PyQt6.QtGui import QPalette
from PyQt6.QtWidgets import QApplication, QLabel, QPushButton

from gui.theme import (DARK_PALETTE, LIGHT_PALETTE, ThemeManager, resolve_scheme, to_qcolor,
                       tokens_for, tokens_to_qpalette)
from gui.theme.manager import repolish
from gui.theme.qss import build_qss


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def test_palettes_have_identical_keys():
    assert set(DARK_PALETTE) == set(LIGHT_PALETTE)


def test_css_colour_notation_is_converted_correctly():
    # '#RRGGBBAA' has alpha LAST; QColor('#RRGGBBAA') would read it as '#AARRGGBB'
    c = to_qcolor('#4a9eff33')
    assert (c.red(), c.green(), c.blue(), c.alpha()) == (0x4a, 0x9e, 0xff, 0x33)
    c = to_qcolor('rgba(255, 255, 255, 0.05)')
    assert (c.red(), c.alpha()) == (255, 13)
    assert to_qcolor('#112233').alpha() == 255


@pytest.mark.parametrize("scheme", ["dark", "light"])
def test_palette_maps_tokens_including_disabled_group(app, scheme):
    t = tokens_for(scheme)
    p = tokens_to_qpalette(t)
    assert p.color(QPalette.ColorRole.Window) == to_qcolor(t['surface'])
    assert p.color(QPalette.ColorRole.Base) == to_qcolor(t['background'])
    assert p.color(QPalette.ColorRole.Highlight) == to_qcolor(t['primary'])
    assert p.color(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text) == to_qcolor(t['text-disabled'])


def test_text_is_readable_on_base_in_both_schemes(app):
    for scheme in ("dark", "light"):
        p = tokens_to_qpalette(tokens_for(scheme))
        text, base = p.color(QPalette.ColorRole.Text), p.color(QPalette.ColorRole.Base)
        assert abs(text.lightnessF() - base.lightnessF()) > 0.6


def test_stylesheet_parses_without_qt_warnings(app):
    from gui.theme.style_manager import get_style_manager
    messages = []
    previous = qInstallMessageHandler(lambda mode, ctx, msg: messages.append((mode, msg)))
    try:
        probe = QPushButton("x")
        probe.setStyleSheet(build_qss(DARK_PALETTE, get_style_manager()._typography))
        probe.ensurePolished()
    finally:
        qInstallMessageHandler(previous)
    assert not [m for m in messages if "parse" in m[1].lower()], messages


def test_resolve_scheme_explicit_and_auto(app, monkeypatch):
    assert resolve_scheme('dark') == 'dark' and resolve_scheme('light') == 'light'
    assert resolve_scheme('LIGHT') == 'light'

    class Hints:
        def __init__(self, scheme):
            self._s = scheme

        def colorScheme(self):
            return self._s

    from PyQt6.QtGui import QGuiApplication
    for reported, expected in ((Qt.ColorScheme.Dark, 'dark'), (Qt.ColorScheme.Light, 'light')):
        monkeypatch.setattr(QGuiApplication, "styleHints", staticmethod(lambda r=reported: Hints(r)))
        assert resolve_scheme('auto') == expected


def test_unknown_scheme_falls_back_to_os_palette_lightness(app, monkeypatch):
    from PyQt6.QtGui import QGuiApplication
    import gui.theme.manager as manager

    class Hints:
        def colorScheme(self):
            return Qt.ColorScheme.Unknown

    monkeypatch.setattr(QGuiApplication, "styleHints", staticmethod(lambda: Hints()))
    dark_os = tokens_to_qpalette(DARK_PALETTE)
    monkeypatch.setattr(manager, "_system_palette", dark_os)
    assert resolve_scheme('auto') == 'dark'
    monkeypatch.setattr(manager, "_system_palette", tokens_to_qpalette(LIGHT_PALETTE))
    assert resolve_scheme('auto') == 'light'


def test_apply_switches_palette_and_emits_signal(app):
    manager = ThemeManager()
    seen = []
    manager.theme_changed.connect(seen.append)
    assert manager.apply(app, 'light') == 'light'
    light_window = app.palette().color(QPalette.ColorRole.Window)
    assert manager.apply(app, 'dark') == 'dark'
    dark_window = app.palette().color(QPalette.ColorRole.Window)
    assert light_window.lightness() > 200 > 80 > dark_window.lightness() - 1
    assert seen == ['light', 'dark']


def test_auto_follows_system_scheme_changes_but_explicit_choice_does_not(app, monkeypatch):
    import gui.theme.manager as manager
    tm = ThemeManager()
    state = {'scheme': 'dark'}
    monkeypatch.setattr(manager, "resolve_scheme",
                        lambda setting: state['scheme'] if setting == 'auto' else setting)
    tm.apply(app, 'auto')
    assert tm.scheme == 'dark'
    state['scheme'] = 'light'
    tm._on_system_scheme_changed()
    assert tm.scheme == 'light'

    tm.apply(app, 'dark')
    state['scheme'] = 'light'
    tm._on_system_scheme_changed()
    assert tm.scheme == 'dark'  # explicit choice is never overridden


def test_variant_property_changes_button_appearance(app):
    ThemeManager().apply(app, 'dark')
    button = QPushButton("Delete")
    button.resize(120, 30)
    plain = button.grab().toImage().pixelColor(60, 15).name()
    button.setProperty("variant", "danger")
    repolish(button)
    danger = button.grab().toImage().pixelColor(60, 15).name()
    assert plain != danger


def test_no_qdarktheme_dependency_left():
    import pathlib
    root = pathlib.Path(__file__).resolve().parent.parent
    for rel in ("gui/main_window.py", "main.py", "requirements.txt", "setup.py", "RPG_Database_Manager.spec"):
        assert "darktheme" not in (root / rel).read_text(encoding="utf-8").lower(), rel


def test_no_hardcoded_colours_in_gui_code():
    """Colours live in gui/theme/tokens.py; widgets use role/variant/state properties."""
    import pathlib
    import re
    gui = pathlib.Path(__file__).resolve().parent.parent / "gui"
    allowed = {("image_gallery_widget.py", "#ff3333")}  # fixed-colour delete overlay shown on top of any image
    pattern = re.compile(r"#[0-9a-fA-F]{3,8}\b|(?:color|background(?:-color)?)\s*:\s*(?:red|green|blue|gray|grey|white|black)\b")
    offenders = []
    for path in gui.rglob("*.py"):
        if "theme" in path.parts or path.name == "styles.py":
            continue
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            for match in pattern.finditer(line):
                if (path.name, match.group(0)) not in allowed:
                    offenders.append(f"{path.name}:{number}: {match.group(0)}")
    assert not offenders, offenders


def test_dropzone_drag_state_is_a_property_and_changes_rendering(app):
    from gui.image_gallery_widget import ImageDropZone
    from gui.theme import set_props
    get_tm = ThemeManager()
    get_tm.apply(app, 'light')
    zone = ImageDropZone()
    assert zone.property("role") == "dropzone" and zone.property("dragActive") is False
    assert zone.styleSheet() == ""  # no per-widget stylesheet any more
    idle = zone.grab().toImage().pixelColor(80, 90).name()
    set_props(zone, dragActive=True)
    active = zone.grab().toImage().pixelColor(80, 90).name()
    assert idle != active
