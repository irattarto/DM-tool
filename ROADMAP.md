# Roadmap

Planned work, in rough priority order. Details live in `docs/`.

## Requested by the owner
- **Discord integration** (version 1 is built; needs a test against the real bot and server) (via the existing bot's REST API): send entity images (captioned with the entity
  name) and selected text to selectable or preselected channels, link each module to a default channel,
  always preview and confirm before sending.
  See [docs/discord_integration.md](docs/discord_integration.md).

## Known gaps / deferred
- Split `gui/main_window.py` (about 2,700 lines) into controllers: tabs, theme, shutdown.
- Windows and macOS: the OS keyring and microphone recording have only been tested with fakes / headless.
- Code signing for the Windows executable (SmartScreen warning).
- Sidebar navigation, a Ctrl+K command palette and icons (UI modernisation ideas).

## Done recently
Security hardening, schema v8 with custom entity types, one theme system with live dark/light,
OS keyring for the API-key encryption key, backup/restore on worker threads, Windows and Linux
downloadable builds via GitHub Actions, PyAudio bundled for speech-to-text.
