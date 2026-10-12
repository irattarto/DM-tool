# Roadmap

Planned work, in rough priority order. Details live in `docs/`.

## Requested by the owner
- **Discord integration** (version 1 is built; needs a test against the real bot and server) (via the existing bot's REST API): send entity images (captioned with the entity
  name) and selected text to selectable or preselected channels, link each module to a default channel,
  always preview and confirm before sending.
  See [docs/discord_integration.md](docs/discord_integration.md).

## Known gaps / deferred
- Split the rest of `gui/main_window.py` (about 1,300 lines left: menus, campaign dialogs, templates, theme, shutdown). The entity lists, the sidebar/switcher/search and the Home/pins code already moved to `gui/entity_tabs.py`, `gui/shell.py` and `gui/home_and_pins.py`.
- Windows and macOS: the OS keyring and microphone recording have only been tested with fakes / headless.
- Code signing for the Windows executable (SmartScreen warning).
- Not done from the UI redesign: helpful empty states (not wanted for now); a Home agenda, scratch notes and quest status (they would need new stored fields).

## Done recently
UI redesign: sidebar, Home page, campaign switcher, Ctrl+K search, picture lists with sort/group and preview,
pinned "Tonight" tray, Delete with Undo, redesigned editor window.
Security hardening, schema v8 with custom entity types, one theme system with live dark/light,
OS keyring for the API-key encryption key, backup/restore on worker threads, Windows and Linux
downloadable builds via GitHub Actions, PyAudio bundled for speech-to-text.
