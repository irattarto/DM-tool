# Quick Style Reference

All colours live in **`gui/theme/tokens.py`** (one dictionary per scheme). The application
palette and stylesheet are generated from them by `gui/theme/manager.py` and
`gui/theme/qss.py`. Widgets never contain colours; they declare *what they are* with
dynamic properties and the stylesheet decides how that looks in dark and light.

## Use properties, not `setStyleSheet`

```python
from gui.theme import set_props

set_props(save_btn,   variant="primary")      # primary | secondary | success | danger | flat
set_props(title,      role="heading")         # heading | h1 | strong | accent
set_props(hint,       role="muted")           # muted | hint | caption
set_props(status,     role="status", state="ok")      # state: ok | warning | error
set_props(preview,    role="card")            # card | dropzone | code
set_props(zone,       dragActive=True)        # dropzone drag-over state
set_props(box,        variant="warning")      # QPlainTextEdit warning box
```

`set_props` re-polishes the widget, so it also works after the widget is shown
(drag state, status changes).

## Theme-aware colours in code

```python
from gui.theme import get_theme_manager, to_qcolor
tokens = get_theme_manager().tokens()          # concrete dark/light dictionary
brush = QBrush(to_qcolor(tokens['success']))

from gui.theme.diff import diff_span            # HTML spans for diffs
html = diff_span('added', escaped_text)         # 'added' | 'removed' | 'changed'
```

Token values use CSS notation; `to_qcolor` handles `#RRGGBBAA` (alpha last) and
`rgba(r, g, b, a)`. Do not pass them straight to `QColor`.

## Adding a style

1. Add the token(s) to **both** palettes in `gui/theme/tokens.py` (a test checks the key sets match).
2. Add a selector in `gui/theme/qss.py` (`QLabel[role="x"]`, `QPushButton[variant="x"]`, ...).
3. Use `set_props(widget, role="x")` in the widget.

`tests/test_theme.py` fails if a hex colour or a named colour (`red`, `gray`, ...) appears in
`gui/` outside the theme package, so styles cannot drift back into widgets.

## Theme and typography

- Theme setting: `auto` (follows the OS and switches live), `dark`, `light`.
- Typography sizes come from the scale in `gui/styles.py` (Preferences > Typography Scale) and
  feed the stylesheet, so headings and captions follow the user's choice.
- Applying: `get_theme_manager().apply(app, setting)` (done at startup and from Preferences).

## Known limits

Colours already baked into rich text (user-picked text colours, inserted link colour) do not
change on a live scheme switch. Diff views take their colours when they are rendered.
