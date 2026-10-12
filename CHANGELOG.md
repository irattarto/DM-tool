# Changelog

All notable changes to RPG Database Manager will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.9.0] - 2026-10-12

Adventure modules as filters, entity files (import and export), places inside places, quests in HTML modules, Tab completion and the other helpers below. The database schema is now v11.

### Changed
- **Names found in the text** are now a list where each name can be edited (which part is the link or the title) and set to **Link to: <existing entry>** (one choice per entry it may mean, e.g. "Abernaty" -> "Dr. Walter Abernaty"), **Create new <type>**, Skip (remembered for that entry) or Never. A full existing title is linked by default; "Find Mira Thornwood" is cut down to the known "Mira Thornwood".

### Fixed (since the first beta)
- New names found: a short form of an existing entry ("Abernaty" for "Dr. Walter Abernaty", also with an ending such as "Abernatyval") is no longer offered as a new entry; common words such as "Lásd", "See" or "Meanwhile", labels like **Goal:** and abbreviations (HP, DC) are not offered either, and a single capitalised word must appear inside a sentence at least once.
- The "deleted - Undo" message was an empty white box from the second delete on (it read its own colours back); it is readable every time now.

### Added
- **Quests in HTML modules.** The importer now reads quest cards: ids starting with `q-` become quests and `goal-` becomes a quest with the subtype "goal" (they appear in the Quests list, are linked to the people and places they mention, and show in the import preview). The HTML Module Guide has a new "Quests and goals" part (how to write the goal, who gives it, the reward and the status), a checklist line and an example in the module template. Quests that were only prose in an earlier module are not imported; they need a card.

- **Places inside places.** A location can be **Located in** another location (a street in a district, a district in a city, a road...). Set it in the editor, or select places and right-click > **Set 'Located in'**. The locations list has a **Located in** column (sortable), **Group by: Located in** (headers show the whole path, e.g. "Chicago > Downtown"), a **Located in** filter box (shows everything inside the chosen place, at any depth) and the second line of each row says where the place is. Entity files have a `located_in` property; no database change (a `located_in` relationship).
- **"+ Add new faction..."** at the end of the NPC editor's Faction box, **New faction...** in the right-click Set faction menu, and the entity import creates factions that the entries name but that do not exist yet (a checkbox in the preview). The editor's "Located in" box has "+ Add new place..." too.

### Added
- **Adventure modules as a filter.** An entry can belong to no module, one module or several (the links are the `belongs_to_module` relationships the HTML import already makes; no change for existing data). The **Scope** button in the top bar limits every list, the Sessions page, Home, the counts and Ctrl+K to chosen modules or to "No module"; each list also has its own **Module** box. The editor has a **Modules** field. In a list, select several rows (Ctrl/Shift+click) and right-click: **Add to module**, **Remove from module** (with **New module...**) and, for people, **Set faction**.
- **File > Import Entities...**: NPCs, factions, locations, items, quests, events and sessions from a Markdown file (front matter, `## NPC: Name {#id}` blocks with property lines and text), a JSON file (`dm-entities`) or HTML cards. A preview shows what is new, changed or unchanged, and where the entries go: the modules named in the file, one module you choose, a new module, or none. A re-import recognises entries by `pack` + id (by type and title when there is no id), keeps what you edited in the app, and never overwrites an entry made by hand unasked. `[text](#id)` and `[[Title]]` become real links; pictures come from the file's folder. Pictures, sessions (date, status, participants) and factions work too.
- **File > Export Entities...** (and **Export as entity file...** on selected rows): saves entries as a Markdown or JSON entity file with their faction, tags, modules, session details and links between them, and copies their main pictures to an `images` folder. The file imports again, also into another campaign; into the same campaign the entries are matched by title and never duplicated.
- **Guides** (Help menu, F1): the window now has two tabs, "HTML module" and "Entity file" (`docs/entity_file_guide.md`), with **Save example as...** for Markdown, JSON and HTML. The examples are part of the installation (`tools/entity_files/`).
- **Tab completion of names.** While you type, grey text completes the name of an entry; **Tab** accepts it and makes it a link, **Esc** ignores it, and several matches open a small list. Select text and right-click for **Create entry from selection**.
- **Connections without typing.** The Connections tab shows **Mentioned in** (who links to this entry) and, for a session, **Cast and places**. Lists have a sortable **Last seen** column (the latest session that mentions the entry) and the preview shows it.
- **New names found.** After saving, capitalised names that match no entry are offered as new entries (NPC, location, faction...), linked in the text; "Never" stops asking about a name.
- **Health check** (Tools menu, and "Needs attention" / "Not used for a while" on Home): people without a faction, entries without a picture, entries linked to nothing, possible duplicates (with **Merge**, which moves text, links, pictures and modules to the kept entry), and entries missing from the last sessions.
- **Quick capture (Ctrl+Space)**: one line is added to the current session with the time, and the names in it are linked.
- **Relationship map** (Map... in the editor, or right-click a row): the entry in the middle and what it is connected to around it; click to move around.
- **History**: each save keeps the text it replaces (the last 20 per entry); History... in the editor previews and restores a version. This is stored data: the database schema is now **v11** (a migration with an automatic copy runs on first start; older program versions can no longer open the database).
- **Automatic backup** when the program closes (the last 7 are kept in `auto_backups` next to the database; skipped when a backup is less than 30 minutes old).
- **Tools > Automation** switches name suggestions, new-name offers, the Home attention cards and the backup on or off.

### Changed
- The health check looks at real entries only (not abilities or inventory items), and "Guard 1" / "Guard 2" are not reported as duplicates ("Name (1)" / "Name (2)" are).
- Help > HTML Module Guide is now **Help > Guides (HTML module, entity file)**. The badge in the editor reads "Imported from: ..." (the module file an entry came from); the **Modules** field shows what it belongs to.

### Fixed
- Names that contain numbers sort by the number's value: "1, 2, 3, 9, 10" instead of "1, 10, 2, 3, 9", and "Session 2" before "Session 10". This applies to the entity lists (also their group headings and the faction column), the Sessions page, the factions on Home, the search results and the Discord picker. Sorting also ignores accents now, so names such as "Ágnes" or "Åsa" no longer end up after "Z".

## [1.8.0] - 2026-10-12

### Added
- **HTML Module Guide** (Help menu, F1; also the **Format guide...** button of the Import HTML Module window): the rules for writing an HTML module the app can import, with a quick start, examples for every kind of entry, factions, pictures, a table of what the import warnings mean, and a checklist. The window has a contents list and a find box, and can save a copy of the guide and a ready-made example module (`module_template.html`) to any folder. Both files are now part of the installation (`docs/html_module_guide.md`, `tools/html_module/module_template.html`).

- **Linux install package (.deb)** in every release, next to the AppImage and the tar.gz: `sudo apt install ./rpg-database-manager_<version>_amd64.deb` installs the program into `/opt/rpg-database-manager`, adds the `rpg-database-manager` command and a menu entry with its icon, and pulls in the system libraries it needs. It is built by `packaging/linux/build_deb.py` (Python only, no dpkg needed). The release build checks it with `dpkg-deb`, installs it, starts it and removes it again before attaching it.

### Changed
- The long "HTML Module Creation Manual" moved from the README into the guide (the README links to it). The "No entities or scenes found" warning now points to Help > HTML Module Guide.

## [1.7.1] - 2026-10-12

### Fixed
- Sessions were counted from the wrong place: the sidebar and the campaign status ("N sessions") and the Home page's recent sessions now use the same sessions as the Sessions page (newest game date first).
- Pinned entries: a pinned entry that is deleted (or deleted and then undone) now leaves or returns to the Tonight tray at once, and its pin is removed for good when it is really deleted.
- The Home entry in the sidebar had the wrong icon (a plain square instead of the house).
- Changing an NPC's faction in the editor now counts as an unsaved change (the "Unsaved changes" marker and the question when closing).
- A folded "No faction" / "No module" group stays folded when the list is rebuilt.
- Enter (also the keypad key), Delete and Ctrl+N work right after choosing a page in the sidebar: a click or Enter on a sidebar entry gives the keyboard to its list.
- Saving an entry in the editor refreshes everything that shows it (its list, keeping the filter you typed, the Tonight tray, Home, the sidebar counts, and the NPC lists after a faction is renamed).
- A quick double-click on a row's pin star no longer opens the entry.
- Home faction counts come from the database instead of the lists on screen, so a filter in a list or a delete waiting for Undo no longer changes them.
- A delete waiting for Undo is carried out when you switch to another campaign, instead of following you into it.

### Changed
- Faster: the sidebar counts are refreshed once when a campaign is loaded (not once per list), and Home reads only titles and dates instead of the full text of every entry.

## [1.7.0] - 2026-10-12

### Added
- **Sidebar** replaces the row of tabs: Home, Play (Sessions), World (every visible entity type, custom ones too, each with a small icon and its number of entries) and Library (Templates).
- **Home page** (opens at start): a tile per entity type with its count and the latest pictures, the six latest edits, the factions with the number of NPCs in each, and the latest sessions. It only shows what the app already stores.
- **Campaign switcher** at the top (name, badge with initials, "N sessions · M entries"): switch between campaigns, create one, or open Manage Campaigns.
- **Search everything** (Ctrl+K, Edit menu): finds entries by name or text, with their pictures, and runs actions (New from template, Name Generator, Settings, Manage campaigns, full screen, Go to any page). With nothing typed it lists the recently edited entries.
- **Thumbnail entity lists**: every list shows the entry's primary picture (initials on a colour when there is none), the name, race · faction (each faction name in its own colour, made from the name) and the module. A **preview panel** shows the large picture, race, faction, module, created, modified and the first words of the text; it has Open, Pin for tonight and, where available, Send to Discord.
- **Sort by / Group by** in every list (group by Module, or by Faction where entries have one); click a group header to fold it. The sort choice and grouping are remembered per entity type.
- **Pinned tray "Tonight"** at the bottom: pin entries with the star on a row, the right-click menu or the preview, and open them from any page. Pins are kept per campaign in the database (no schema change).
- **Delete with Undo**: delete (right-click menu or the Delete key) still asks first, then the entry is hidden and can be brought back with Undo or Ctrl+Z for 10 seconds before it is really deleted. Enter opens the selected row.
- **New** is one button with "From template" (Ctrl+N) and "Blank document" (Ctrl+Shift+N). Help > Keyboard Shortcuts lists the shortcuts.
- **Editor window**: the picture, title and faction (or date, status and participants of a session) are on the left, the tabs (Description, Images, Connections, Abilities, Inventory) on the right, and a marker shows unsaved changes.

### Changed
- The list headers no longer sort; use Sort by. The Delete button and the separate "New Blank" button are gone (see above). The Metadata tab of the editor is gone: the faction is now on the left of the window.
- The entity list code moved out of `gui/main_window.py` into `gui/entity_tabs.py`; the sidebar, campaign switcher and search are in `gui/shell.py`, Home and pins in `gui/home_and_pins.py`.

## [1.6.0] - 2026-10-11

### Restored
- **Name Generator** (Tools menu): it was removed together with the AI features, but the embedded name lists never needed AI. It is back as an offline tool (fantasy, English, German, Hungarian, Nordic, Celtic, Asian; any/male/female); the AI option is gone.

### Fixed
- HTML module re-import now updates pictures: a portrait or gear picture that was redrawn replaces the stored one (keeping its caption and primary flag, removing the outdated file), and pictures generated after the first import are added. Cards whose text did not change are no longer skipped for their pictures (the preview notes "Pictures changed").

### Added
- **Send NPCs and locations to Discord**: a "Send to Discord..." button next to the filter on the NPC and Location tabs (and the same entry in the right-click menu of a row) opens a picker with every entry sorted by name. The ticked ones are posted to the chosen channel as embed cards (name as title, primary picture inside), up to ten per message, after the usual preview and confirmation. Entries without a primary picture are listed as skipped.
- **HTML Module Creation Manual** in the README: what a module HTML needs to be importable (page skeleton, id prefixes, card anatomy, links, factions, scenes, pictures/audio/maps, JSON alternative, checklist). New helpers in `tools/html_module/`: `module_template.html` (minimal valid module) and `validate_module.py` (lists unknown links, missing pictures, NPCs without faction).
- HTML module import, faction choice: NPCs the module leaves without a faction are listed in the preview with a drop-down to pick one (monsters and minor NPCs are not asked; a faction set earlier is kept and never asked again). Optional **automatic factions**: NPCs without a faction join "Unaffiliated", monsters join "Monsters" ("Függetlenek" / "Szörnyek" in Hungarian modules), created as ordinary faction documents only when used. `data-faction="f-id"` sets an NPC's faction explicitly, `data-faction="none"` keeps it deliberately without one.
- HTML module import, faction table: **+ New faction...** in the drop-down lets you type a new faction, which every other NPC can then pick as well (created only when used; an existing name is reused). Hovering over an NPC in the faction table (and over NPC rows in the preview tree) shows a short description of the NPC to help decide.
- HTML module import, faction line and states: an NPC card may carry a visible `.npc-faction` line (`data-faction` = a faction id, `none`, `unknown` or `undecided`). Every NPC without a real faction, minor NPCs and monsters included, is listed in the preview's faction table with the stated state preselected; the drop-down now also offers "Unknown faction" and "Undecided yet" (recorded as a tag, nothing linked). Changing a faction choice on a re-import now updates an otherwise unchanged NPC.
- HTML module import, groups: `data-count="N"` marks one NPC entry that stands for N identical extras (tag `×N`).
- The generation rules, a full module template and the pipeline scripts moved into the separate **module-creator** project; `tools/html_module/validate_module.py` now also warns about NPCs without a faction line and about cards that look like several people.
- HTML module import, gear: each line of an NPC's `.gear` list becomes an inventory item in the NPC's Inventory tab (option, on by default). A re-import updates the text but keeps the item type, quantity and equipped flag you changed. The gear picture (`gen-item`) is attached as a secondary image with the caption "Gear".
- HTML module import, audio and maps: audio players become a link to the file in the module folder (Ctrl+click plays it in the default player, after a confirmation; only existing local `.mp3 .wav .ogg .m4a .flac` files open, never network paths or other file types). Inline SVG maps (base image and linked locations) and `.svg-legend` are kept as text instead of being dropped, `data-character` on a `hook-` box is shown as the character, the `.warn` notice is kept as a quote, and a file with no recognised entity or scene shows a warning pointing to the manual.

### Removed
- All AI features: the AI Generation, AI Analyse and AI Database Assistant tabs, the AI text assistant and summary in the editors' context menus, the Name Generator, the AI Settings and AI timeouts in Preferences, and the OpenAI/Ollama provider code. The stored provider list (`ai_providers.json`, with its encrypted API keys) and the old `AI/*` settings are deleted at startup. The encryption key itself is kept because the Discord token uses it. The `ai_suggestions` table stays in the schema (unused) so older versions can still open the database; new backups no longer carry AI suggestions, and old backups that do are still restorable (the suggestions are ignored).
- Online speech-to-text through the OpenAI Whisper API: it used the API key from AI Settings. A stored "openai" speech-to-text provider falls back to local Whisper.

### Security
- Text from documents, campaigns and backup files is shown as plain text in message boxes and the restore dialog, and network paths (UNC, `file://server`) are not loaded as document resources: an `<img src="//server/share/x.png">` could make Windows send the user's credentials to that server.
- The build workflow no longer leaves its write token in the checkout; CUDA DLLs are extracted atomically; HTML module files over 50 MB are refused.
- Without a system keyring, the fallback encryption-key file is now protected with Windows DPAPI (usable only by your Windows account, works the same for the EXE and Store Python); an older plain key file is upgraded in place after a verified round trip.
- Release builds install from hashed lock files (`pip install --require-hashes`), so a tampered or replaced package is rejected.

### Changed
- Closing a document with unsaved changes now offers Save / Discard changes / Cancel (there was no way back before).
- Links (`rpg://`) only open entries of the open campaign.
- Recording with the Google provider stops after 60 seconds (Google does not accept longer audio); other providers use the Preferences limit.
- Titles are no longer rejected for SQL-like text such as "; update"; every query is parameterised anyway.
- The 🎤 Record button is now a toggle: click to start recording, click again to stop and transcribe (it was push-to-talk). The recording stops by itself after the "maximum recording duration" from Preferences and then plays a short two-tone sound (bundled, independent of the Windows sound scheme). That duration is now 30–480 seconds (default 120; it was a fixed 30 seconds).
- HTML module import: each scene (`j-…`) is now an event (subtype `scene`) instead of its own session; the campaign gets one first session, and the scene texts can be copied into it, into an existing session of your choice, or nowhere. Character hooks (`hook-…`, "Karakterhorgok") are imported as character documents instead of events. Earlier imports are not changed.

### Fixed
- Restoring a backup as a new campaign now remaps `parent_document_id`: inventory and ability items kept pointing at the original campaign's NPC and were orphaned.
- HTML module import: the main picture of a card is the one with `data-gen-id` equal to the card id (or `gen-portrait`/`gen-room`/`gen-creature`), not simply the first `<img>`; belongings pictures (`gen-item`) no longer replace it and the image prompt is the one that follows the main picture (Raton Pass's Marsh, Baines and Abernathy got their item picture as portrait). Tables are real markdown tables and convoy-style rows are no longer glued together.
- Local Whisper on an NVIDIA graphics card: the build lacks NVIDIA's CUDA libraries, so large models silently ran on the CPU (very slow) and retried the GPU on every recording. The app now offers once to download the libraries (about 1 GB, SHA-256 verified) and then uses the GPU; a failed GPU run is not retried in the same session, the model loads while you hold Record, and the status text says whether the model is downloading or only loading.
- Local Whisper failed with "open() got an unexpected keyword argument 'metadata_errors'": PyAV 19 removed that argument, which faster-whisper 1.2.x still passes. The app now decodes the audio itself when that happens, and `requirements.txt` keeps `av` below 19.
- Discord: the server is now stored per campaign (schema v10) instead of once for the whole app, so each campaign can post to its own server. Existing campaign links keep the server that was set before; the server in Preferences is only the default for campaigns without their own. Changing it no longer clears campaign links.
- HTML module import: image paths are resolved before the containment check (no `../` escape).
- Backups: `module_data.json`, `metadata.json` and images are read with a hard byte cap, whatever the zip header claims.
- `check_database.py`: recovery dump is flushed before it is read; `-wal`/`-shm` move with a renamed database.
- Module names with `?` or `"` no longer produce an invalid database file name.
- `GameSession.to_dict` now stores `status`; template import counts only templates that were really saved.
- Retired worker threads disconnect their signals (no slots on destroyed dialogs).
- OpenAI provider: real throttle, retries with exponential backoff on 429/5xx; configurable AI rate limit; entity worker honours the generation-timeout setting.
- Migration/settings/AI-config loggers go through the application logger (visible in the windowed build).
- Backups: `.tiff` images are restored; a restore-as-new reports images that could not be restored; a nested snapshot no longer drops the progress callback; deleting an image keeps a thumbnail another campaign still uses.
- HTML import: a shared `module-export.json` only applies to its own module (`<name>.module-export.json` is preferred).
- `validate_json_input` really parses the JSON; unguarded sort-preference parsing; multi-word NPC interaction indicators; `update_image_description` reports a missing image; `integrity_check` runs once; silent `except: pass` handlers now log.
- Discord: retries on 5xx and unreachable-network errors; a failed metadata strip is logged.
- Speech-to-text: the real cause of a failed transcription is shown (not a generic message); Whisper continues without the silence filter if it cannot load; the Windows/Linux builds now bundle `onnxruntime`, `av` and `tokenizers`.
- `setup.py` reads `requirements.txt`; constants de-duplicated; entity-context tables follow renamed/hidden/added types; worker classes moved to `gui/workers/`; CI runs on pushes to `main` and pull requests only; `check_schema_consistency.py` finds the real database and parses columns correctly.
- Removed about 130 unused methods/functions and 49 unused constants.
- README version badge fixed; `gui/styles.py` moved to `gui/theme/style_manager.py`.

## [1.6.0-beta.1] - 2026-10-03

First pre-release with downloadable builds (Windows installer and zip, Linux AppImage and tarball). Please report problems.

### Added

- **Windows installer** (per-user, Start-menu entry, uninstaller that keeps your campaigns) and **Linux AppImage**, built by GitHub Actions.
- **Entity types you control** (Preferences > Entity Types): add, rename, reorder and hide types; custom types are stored in the database and included in backups.
- **One theme system** with a real automatic dark/light mode that follows the operating system.
- **Send to Discord** (bot token entered in Preferences): send images (with the entity name) and selected text to a channel after a preview and confirmation; every campaign can have a default channel.
- **Offline speech-to-text** (Whisper) is now the default for session recording; the cloud option must be chosen explicitly. Transcription runs in the background, so the window no longer freezes.
- **Fullscreen** (View > Full Screen, F11), remembered across restarts.
- Backup and restore run in the background with progress; the API-key encryption key is kept in the system keyring when available.

### Changed

- Hidden entity types stay in the AI context and in internal links; window position and maximised state restore safely.

### Fixed

- Many crash and data-safety fixes from a full code review: errors in a handler no longer close the app, stopping the AI assistant mid-analysis, closing dialogs while work runs, restoring backups (images and rollback), migrations (a newer database is refused untouched; one backup before the chain), API keys no longer wiped after a failed decrypt, settings load key by key, strict image file names in backups, and more.
- Microphone errors now explain what is wrong (missing PyAudio, no microphone, Windows privacy settings).

### Known limits

- Untested on real hardware: GPU transcription (CUDA libraries are not bundled; it falls back to the CPU), Discord sending against a live server.
- Builds are not code-signed, so Windows SmartScreen shows an "unknown publisher" warning.
- `gui/main_window.py` is still one large file.

### Added (carried over from before the first pre-release)


- **Import HTML Module** (`File` menu): imports a Temple Dungeons style HTML adventure module into the current campaign as a `module` document with one session per scene and linked NPCs, factions, locations, items and events. A preview dialog shows what will be created or updated; re-imports update by HTML id and leave documents you edited alone unless you tick them. See `docs/html_module_format.md`.
  - New `module` entity type; links are stored in `document_relationships` (`belongs_to_module`, `appears_in_session`, `member_of`, `references`) and as `rpg://` links in the notes.
  - Entity lists get a **Module** column; the document window shows a module badge and a **Connections** tab.
  - `python -m services.html_module_parser file.html [--export]` checks a file and can write a `module-export.json` (`dm-module` format) that the importer prefers over scraping.

### Changed

- **Naming**: what the app called a "Module" is now a **Campaign** everywhere in the UI, menus, dialogs and AI prompts (database tables and backup files keep their names). "Module" now means an adventure inside a campaign and "Session" a sitting of play within it.

### Fixed

- **Saving an NPC or session in the document window dropped other metadata** (`gui/dialogs/document_viewer.py`): the form replaced the stored metadata with only its own fields. It now merges, and choosing "(None)" as an NPC's faction really clears it.
- **Backup restore kept stale document ids** (`services/backup_service.py`): `faction_id`, `module_doc_id` and `rpg://` links in restored documents are remapped to the restored documents.

## [1.5.5] - 2026-05-10

### Security

- **JSON response validation in AI search** (`services/ai/provider_openai.py`): `search_content()` now validates that the AI response is a JSON object (not an array or primitive) and that the `explanations` field is a dict before accessing it. Added a specific `json.JSONDecodeError` handler with a descriptive warning log instead of silently falling through the generic exception handler.

### Fixed

- **Test database initialization crash** (`models/database_migrations.py`): `get_current_version()` now catches `sqlite3.OperationalError` and returns `0` when the `schema_version` table does not yet exist, instead of raising an unhandled exception.
- **In-memory database migration skip** (`models/database.py`): `_apply_migrations()` now returns immediately for `:memory:` databases. Each new SQLite connection to `:memory:` is an isolated empty database, so migrations were incorrectly failing when tests used in-memory databases.
- **`is_primary` missing from image query** (`models/database.py`): `get_document_images()` was omitting `is_primary` from its explicit column SELECT and result dict despite the column existing in the schema.

### Updated

- **All dependencies upgraded** (`requirements.txt`, `setup.py`):
  - PyQt6: 6.9.1 → 6.11.0
  - PyQt6-WebEngine: 6.9.0 → 6.11.0
  - Pillow: 11.3.0 → 12.2.0
  - cryptography: 46.0.3 → 48.0.0
  - aiohttp: 3.13.1 → 3.13.5
  - requests: 2.32.5 → 2.33.1
  - SpeechRecognition: 3.14.3 → 3.16.1
  - pytest: 8.4.2 → 9.0.3
  - pytest-asyncio: 1.2.0 → 1.3.0
  - `pip-audit` found no CVEs before or after upgrade
- **`setup.py` core dependencies cleaned**: Removed `PyQt6-Qt6` and `PyQt6-WebEngine-Qt6` from `install_requires` — they are auto-installed transitive dependencies; listing them explicitly can cause version conflicts on some platforms.

### Technical Details
- `models/database_migrations.py`: `get_current_version()` catches `sqlite3.OperationalError` → returns `0`
- `models/database.py`: `_apply_migrations()` early-return for `":memory:"`; `get_document_images()` adds `is_primary` to SELECT and result dict
- `services/ai/provider_openai.py`: `search_content()` adds `isinstance` guards + `json.JSONDecodeError` handler
- `tests/test_models/test_crud.py`: field names, method signatures, and session ordering updated to match current API
- `tests/test_models/test_image_management.py`: absolute image paths replaced with relative paths

## [1.5.4] - 2026-03-16

### Fixed

- **Duplicate log entries**: `logging.basicConfig()` added a handler to the root logger while `setup_logging()` added handlers to the `rpg_database_manager` child logger. Since child loggers propagate to the root by default, every message was logged twice. Fixed by setting `logger.propagate = False` in `setup_logging()`.
- **Settings OK button showing redundant popup**: Pressing OK after already saving via Apply showed a "Settings saved successfully" popup. OK now silently saves and closes (the dialog closing is itself the confirmation).
- **Settings Apply popup suppressed by Qt signal**: The `clicked` signal passes a boolean (checked state = `False`) as the first argument. After adding the `show_confirmation` parameter to `_on_apply`, this boolean was silently received as `show_confirmation=False`, suppressing the Apply popup. Fixed by connecting via `lambda: self._on_apply()`.
- **Unimplemented "Change Database Location" button**: Removed the button and its stub handler from the Database Management dialog — it opened a file picker then immediately showed "not yet implemented".

### Technical Details
- `utils/logger.py`: `logger.propagate = False` added after `logger.handlers.clear()`
- `gui/settings_dialog.py`: `_on_apply(show_confirmation=True)`; `_on_ok` calls `_on_apply(show_confirmation=False)`; Apply button connected via `lambda`
- `gui/database_dialog.py`: `change_location_btn` and `_on_change_db_location()` removed

## [1.5.2] - 2026-03-15

### Fixed

- **EXE vs Python database path mismatch**: `setup_logging()` was called before `QApplication` was created and its identity (org/app name) was set. Qt falls back to the executable filename when `QStandardPaths` is called without a proper application identity — meaning the compiled EXE (`RPG_Database_Manager`) resolved a different `AppData` folder than Python (`python`). Fixed by moving `setup_logging()` to after `QApplication` creation and `setApplicationName`/`setOrganizationName` calls. Both Python and EXE now always use `AppData\Roaming\RPG Database Manager\RPG Database Manager\`
- **Log file in wrong location**: As a consequence of the above, log files were written to a path based on the executable name instead of the application name. After this fix, log files are always at `AppData\Roaming\RPG Database Manager\RPG Database Manager\logs\rpg_database_manager.log`
- **Windowed EXE console logger crash risk**: `setup_logging()` was adding a `StreamHandler(sys.stdout)` even when `sys.stdout is None` (PyInstaller `console=False` mode). Now guarded with `if sys.stdout is not None`
- **Database path now logged at startup**: `DatabaseManager.__init__()` logs `Database path: <path>` at INFO level so you can always verify which file is being used by checking the log
- **`check_database.py` used wrong path**: The recovery tool called `QStandardPaths` without a `QApplication` setup, so it pointed to the wrong database. Fixed by creating a `QApplication` with correct identity before any path resolution

### Technical Details
- `main.py`: temporary `logging.basicConfig` for pre-QApp console output; `setup_logging()` moved to after line 59 (`setOrganizationDomain`)
- `utils/logger.py`: console handler guarded with `sys.stdout is not None`
- `models/database.py`: `self.logger.info(f"Database path: {self.db_path}")` added to `__init__`
- `check_database.py`: `QApplication` + `setApplicationName`/`setOrganizationName` added before first `QStandardPaths` call

## [1.5.1] - 2026-03-15

### Fixed

- **Crash-safe database**: Changed `synchronous` pragma from `NORMAL` to `FULL` so every write is flushed to disk before confirming; added `PRAGMA wal_checkpoint(PASSIVE)` on startup to recover any WAL left by a previous crash; added `PRAGMA wal_checkpoint(TRUNCATE)` + clean disconnect on normal shutdown so the next open starts with no WAL file
- **Silent backup warning**: If image files are missing from disk during a module backup, a warning dialog now appears after the backup completes listing the count of missing files — previously only a status-bar message was shown
- **Thumbnail regeneration on restore**: After restoring a module from a backup ZIP, the 200×200 thumbnail cache is now automatically regenerated for all restored images; previously thumbnails were absent until the app was restarted or images were re-uploaded
- **Safe overwrite restore**: When restoring in overwrite mode, images are now extracted to a temporary directory first; the existing module data is only deleted after confirming the ZIP is fully readable — previously a corrupt or incomplete ZIP could cause the target module to be deleted with nothing to replace it
- **Backup return-value bug**: Two early-exit paths in `backup_module()` returned a 2-tuple instead of the required 3-tuple, causing a `ValueError` when the module was not found or data export failed

### Technical Details
- `models/database_connection.py`: `synchronous = FULL`; `PRAGMA wal_checkpoint(PASSIVE)` after connect; new `checkpoint()` method; `disconnect()` now calls checkpoint before closing
- `gui/main_window.py`: `closeEvent()` now calls `db_manager.connection.disconnect()` to trigger WAL flush on clean exit
- `services/backup_service.py`: `backup_module()` / `_create_zip_backup()` return `Tuple[bool, str, int]`; `_restore_overwrite_module()` rewrites to temp-first approach; thumbnail regeneration added to both restore paths
- `services/image_service.py`: New `regenerate_thumbnails_for_module(module_id)` public method
- `gui/database_dialog.py`: `_on_backup_module()` unpacks 3-tuple and shows `show_warning` dialog when images were missing

## [1.5.0] - 2026-03-15

### Added
- **German Name Style**: Added German naming style to the name generator, expanding language options for NPC and character name generation

## [1.4.9] - 2026-01-10

### Added
- **Module Backup and Restore functionality**: Create and restore complete module backups with all data and images
  - Backup modules to ZIP files containing database data (JSON export) and all images
  - Restore backups either as new modules or by overwriting existing modules
  - Integrated into Database Management dialog as new "Module Backup & Restore" section
  - Module selection dialog showing statistics (documents, images, sessions)
  - Restore options dialog with overwrite confirmation and warnings
  - Metadata tracking (module name, backup date, image count, backup version)
  - Proper ID remapping for documents, sessions, and relationships during restore
  - Windows-compatible ZIP handling with forward slash paths

### Fixed
- **AI suggestions import**: Fixed column name mismatch and missing session ID remapping
  - Fixed INSERT statement to use correct column names (session_id, original_content, suggested_content, reasoning)
  - Added session_id_mapping to properly remap session foreign keys
  - Fixed module ID validation to use `is None` instead of `not` operator
  - Ensures data integrity when restoring modules with AI suggestions

### Technical Details
- Created `services/backup_service.py`: Core backup/restore service using JSON export/import approach
- Created `gui/dialogs/module_backup_dialogs.py`: ModuleSelectionDialog and RestoreOptionsDialog
- Modified `gui/database_dialog.py`: Added backup/restore UI section with handlers (lines 95-111, 389-529)
- BackupService uses JSON export to extract all module data from main database
- Backup format: module_data.json (all records), metadata.json (backup info), images/ (physical files)
- Restore process creates new module records and imports data with proper ID remapping
- Session IDs remapped before AI suggestions to maintain foreign key integrity
- ZIP files use forward slashes for cross-platform compatibility
- Backup version: 2.0 (JSON-based format)

## [1.4.7] - 2026-01-10

### Fixed
- **Critical: Images not imported when restoring module from backup**
  - Fixed `_import_images_from_zip()`: Now properly extracts images to module directory
  - Fixed `_import_images_from_directory()`: Now copies images with correct paths
  - Fixed module ID passing: Import functions now use the actual created/target module ID
  - Images are now copied to the correct module directory with original filenames preserved
  - Thumbnails are automatically generated during import if missing
  - Added proper error handling and logging for image import operations

### Changed
- **Improved module import/restore process**
  - Image files are extracted directly to module directory (no temp files left behind)
  - Thumbnail subdirectories are properly excluded during import
  - Better validation: warns if no module ID is available for image import
  - Enhanced logging for debugging image import issues

### Technical Details
- Modified `services/export_service.py`:
  - `_import_images_from_zip()`: Complete rewrite to properly copy images (lines 695-743)
  - `_import_images_from_directory()`: Complete rewrite to properly copy images (lines 745-790)
  - `_import_from_zip()`: Pass actual module ID to image import (lines 483-489)
  - `_import_from_directory()`: Pass actual module ID to image import (lines 547-553)
- Images are now preserved with original UUID filenames as stored in database
- Fixes incomplete implementation that was only counting files but not actually copying them

## [1.4.6] - 2026-01-10

### Removed
- **Cleanup: Removed manual test scripts**
  - Removed `tests/test_markdown.py` - manual PyQt6 markdown support test
  - Removed `tests/test_backup_verification.py` - manual backup verification script
  - Removed `tests/test_abilities_inventory_backup.py` - manual abilities/inventory test script
  - Kept proper pytest unit tests in `tests/test_models/` and `tests/test_services/`

### Technical Details
- Cleaned up tests directory to contain only automated pytest unit tests
- Manual test scripts were development/debugging tools not needed in production

## [1.4.5] - 2026-01-10

### Fixed
- **Critical: ZIP export/import path separator issues on Windows (Python 3.13)**
  - Fixed module export ZIP error: "File name in directory and header differ"
  - Fixed escape sequence corruption in image filenames containing backslashes
  - Fixed Path object handling in zipfile operations for Python 3.13 compatibility
  - Fixed ZIP file reading using ZipInfo objects to avoid validation errors
  - Applied defensive fixes to handle both clean and corrupted filename data

### Changed
- **Improved ZIP file handling across all operations**
  - All `zipfile.ZipFile()` calls now convert Path objects to strings
  - All `zipf.write()` calls use explicit `arcname=` parameter with forward slashes
  - Filename normalization: backslashes converted to forward slashes before Path operations
  - Enhanced error handling for ZIP operations with try-except blocks

### Technical Details
- Modified `services/export_service.py`:
  - `export_module()`: Convert Path to string for ZIP creation (line 74)
  - `_export_images_to_zip()`: Normalize filenames and use explicit arcname (lines 295-296, 305, 312)
  - `_import_from_zip()`: Convert Path to string for ZIP reading (line 440)
  - `create_backup()`: Convert Path to string and normalize image filenames (lines 827, 872-873, 879, 894)
  - `_validate_zip_export()`: Convert Path to string (line 1023)
  - `_create_manifest()`: Use ZipInfo objects for reading files (line 1160)
- Modified `gui/settings_dialog.py`:
  - `_restore_from_zip_backup()`: Convert Path to string for ZIP extraction (lines 888-889)
- Modified `tests/test_abilities_inventory_backup.py`:
  - Test ZIP operations use string conversion (line 141)
- Tested and verified on Windows with Python 3.13.9

## [1.4.3] - 2025-12-29

### Fixed
- **Code quality improvements**: Fixed error handling and cleaned up orphaned files
  - Fixed bare `except:` clause in `gui/dialogs/document_viewer.py` → `except Exception:`
  - Better error handling, won't hide unexpected exceptions
  - Deleted orphaned `gui/__pycache__/document_widget.cpython-313.pyc` (22.5 KB)
  - Removed compiled file from deleted source (v1.3.14 cleanup)

### Changed
- **Test file organization**: Moved test scripts to proper location
  - Moved `test_markdown.py` → `tests/test_markdown.py`
  - Moved `test_backup_verification.py` → `tests/test_backup_verification.py`
  - Moved `test_abilities_inventory_backup.py` → `tests/test_abilities_inventory_backup.py`
  - All test files now properly organized in `tests/` directory

### Technical Details
- Modified `gui/dialogs/document_viewer.py` (line 738): Improved exception handling
- All Python files compile successfully with no errors
- No security vulnerabilities detected
- No deprecated dependencies found
- Codebase follows Python best practices

## [1.3.14] - 2025-12-28

### Fixed
- **Template deletion functionality**: Connected GUI to existing `template_service.delete_template()` method
  - Template deletion now works properly from Templates tab
  - Added check to prevent deletion of default templates
  - Displays appropriate success/error messages
  - Auto-refreshes template list after deletion
- **Database integrity check error**: Fixed KeyError when checking database integrity
  - Removed references to `fts_check` key that was removed with FTS5 cleanup
  - Integrity check dialog now displays correctly in main window and settings
  - Shows database status, integrity check, foreign key check, and errors

### Removed
- **Unused DocumentWidget**: Deleted legacy document editor widget (415 lines)
  - Removed `gui/document_widget.py` - standalone widget that was never used
  - Removed broken "AI Assist" button showing "not available in this version"
  - Application uses DocumentViewerWindow which has full working AI features
  - Cleaned up `gui/__init__.py` exports

### Technical Details
- Fixed template deletion in `gui/main_window.py` (lines 1334-1379)
- Removed FTS check display from `gui/main_window.py` (lines 2423-2435)
- Removed FTS check display from `gui/settings_dialog.py` (lines 1629-1641)
- Total code removed: 441 lines (415 DocumentWidget + 26 FTS display code)
- All Python files compile successfully, no syntax errors

## [1.3.13] - 2025-12-28

### Removed
- **Unused repository pattern package**: Removed entire `models/repositories/` directory (173 lines)
  - Deleted broken imports to 5 non-existent repository files
  - Removed unused `base_repository.py`, `session_repository.py`, and `template_repository.py`
  - Package was never imported anywhere in production code
- **Unused dependencies**: Cleaned up requirements.txt from 36 to 8 packages (78% reduction)
  - Removed 28 unused packages including: beautifulsoup4, lxml, python-docx, bcrypt, python-dotenv, PyYAML, openai, ollama, tiktoken, PyAudio, openai-whisper, reportlab, PyMuPDF, pypdf, pandas, openpyxl, qrcode, plyer, Whoosh, keyboard, pynput, pytest-asyncio, black, flake8, mypy
  - Application uses direct HTTP calls to AI APIs instead of official SDKs for better control
- **Orphaned compiled files**: Removed 7 orphaned .pyc files from deleted source files
- **Mysterious directory**: Removed empty `-p` directory from project root

### Changed
- **Updated requirements.txt**: Now contains only packages actually used in codebase
  - Added comprehensive documentation explaining removed packages
  - Fixed pyqtdarktheme version constraint from >=2.1.0 to >=0.1.7 (correct latest version)
  - Added installation notes for minimal vs full installation
  - Documented that faster-whisper is used instead of openai-whisper

### Technical Details
- Total code reduction: 173 lines (repository pattern dead code)
- Dependency reduction: 78% (36 packages → 8 packages)
- No functional changes - only removed unused code and dependencies
- All imports verified, no broken references
- No syntax errors or circular imports detected

## [1.3.10] - 2025-11-27

### Added
- **AI context menu in Abilities and Inventory tabs**: Right-click menu now available in Abilities and Inventory tabs for Characters and NPCs
  - Added "AI Assistant" option to help edit or generate ability/inventory descriptions
  - Added "AI Summary" option to summarize selected text
  - Added "Paste Without Formatting" option (Ctrl+Shift+V)
  - Includes all standard text editing options (Cut, Copy, Paste, Select All)
  - Matches functionality previously only available in Description tab

### Technical Details
- Modified `gui/ability_widget.py`:
  - Implemented `_show_context_menu()` to display context menu with AI features
  - Added `_open_ai_assistant()` for AI text assistance
  - Added `_open_ai_summary()` for AI text summarization
  - Added `_apply_ai_edit()` to apply AI-generated edits
  - Added `_get_ai_service()` to retrieve AI service from parent hierarchy
- Modified `gui/inventory_widget.py`:
  - Implemented identical context menu functionality as abilities tab
  - All AI assistant features now available for inventory item descriptions

## [1.3.5] - 2025-11-26

### Fixed
- **Rich text editor list formatting bugs**: Fixed critical errors in bullet and numbered list toggle functionality
  - Fixed `AttributeError: 'QTextBlockFormat' object has no attribute 'setNumberSuffix'` in `_remove_all_list_formatting()`
  - Fixed `TypeError: removeItem(self, i: int): argument 1 has unexpected type 'QTextBlock'` by using proper `itemNumber()` and `removeItem(index)` methods
  - List formatting now correctly removes blocks from lists and resets indentation
- **Clear formatting preserves text color**: Clear formatting now preserves existing text colors instead of resetting to theme default
- **Normal text button preserves formatting**: Normal text button now preserves text color and uses widget's default font size instead of changing them

### Technical Details
- Modified `gui/widgets/formatted_text_edit.py`:
  - Updated `_remove_all_list_formatting()` to properly remove blocks from QTextList objects
  - Modified `clear_formatting()` to preserve foreground color
  - Updated `apply_heading()` for normal text to preserve color and use default font size

## [1.3.2] - 2025-11-25

### Added
- **Comprehensive backup verification testing**: Created automated test suites to verify all data types are properly backed up and restored
  - Added `test_backup_verification.py` - Tests core backup/export functionality for all entity types
  - Added `test_abilities_inventory_backup.py` - Specifically tests abilities and inventory backup/restore
  - Added `BACKUP_VERIFICATION_REPORT.md` - Comprehensive documentation of backup capabilities
  - All tests pass successfully - all data types confirmed backed up and restorable

### Verified
- **Abilities backup confirmed**: Character/NPC abilities (skills, spells, feats, traits) are fully backed up and restored
  - Stored as documents with `entity_type='ability_item'`
  - Includes all metadata (ability type, parent character/NPC, descriptions)
  - Automatically included in all backup and export operations
- **Inventory backup confirmed**: Character/NPC inventory items are fully backed up and restored
  - Stored as documents with `entity_type='inventory_item'`
  - Includes all metadata (item type, quantities, parent character/NPC, descriptions)
  - Quantities preserved on import/export
  - Automatically included in all backup and export operations

### Documentation
- **Backup capabilities fully documented**: Complete documentation of all backup/export features
  - Full database backup functionality
  - Module export to ZIP and directory formats
  - Import/restore capabilities
  - Data type coverage (10 entity types + sessions + templates + images + abilities + inventory)
  - User interface integration (File → Import/Export)
  - Recommended backup strategies

## [1.3.1] - 2025-11-25

### Fixed
- **Session tab blank on first start**: Fixed issue where the Sessions tab appeared empty when first opening the application. Session widget is now initialized immediately rather than lazily loaded when tab is first accessed.
  - Modified `gui/main_window.py`: Changed `_setup_sessions_tab()` to create SessionWidget during initialization
  - Modified `gui/main_window.py`: Simplified `_on_tab_changed()` to refresh data instead of creating widget

### Added
- **Resizable columns with persistence**: All columns in entity tabs (Characters, NPCs, Locations, etc.) and Sessions tab are now horizontally resizable by dragging column dividers. Column widths are automatically saved and restored across application restarts.
  - Session columns: Title, Date, Status, Participants
  - Entity columns: Name, Created Date, Modified Date (plus Race and Faction for NPCs)
  - Default widths set for first-time use, then user preferences are remembered
  - Column widths stored per widget type (sessions, entity_npc, entity_location, etc.)
  - Added `config/settings.py`: `get_column_widths()` and `set_column_widths()` methods
  - Modified `gui/session_widget.py`: Added Settings parameter, column resize handler, and width persistence
  - Modified `gui/main_window.py`: Added column resize handlers and width persistence for all entity tabs

### Technical Details
- Changed column resize mode from `Stretch`/`ResizeToContents` to `Interactive` for user control
- Column widths saved to settings file on each resize event
- Settings format: `column_widths_<widget_name>` stores comma-separated width values
- Backward compatible: Falls back to sensible defaults if no saved widths exist

## [1.2.6] - 2025-11-22

### Fixed
- **Critical: HTML content sent to AI**: Fixed issue where entity content was sent to AI with HTML formatting tags instead of plain text, making it difficult for AI to process properly.
  - AI Database Assistant: Now strips HTML from world settings and entity summaries
  - AI Analyse: Now strips HTML from all module entity content
  - AI Generate: Now strips HTML from all module entity content
  - AI Context Helper: Safety layer strips HTML from all entity context building
  - Affects all entity types including sessions, NPCs, locations, quests, etc.
  - AI now receives clean, readable text: "Session description" instead of "<p>Session description</p>"

### Technical Details
- Modified `gui/ai_database_assistant_tab.py`: Added `TextUtils.remove_html_tags()` to `_build_context_data()` method
- Modified `gui/main_window.py`: Added HTML stripping to `_gather_module_data()` method
- Modified `utils/ai_context_helper.py`: Added HTML stripping to `build_entity_context()` function
- Uses existing `TextUtils.remove_html_tags()` utility which handles HTML tag removal and entity decoding (&amp;, &nbsp;, etc.)
- HTML formatting is preserved in UI display, only stripped when sending to AI

## [1.2.5] - 2025-11-22

### Added
- **Session context support in AI features**: All three AI tabs (AI Database Assistant, AI Analyse, AI Generate) now include session checkbox options and send session information as context for AI requests.
  - Added 'Sessions' to entity type names and context profiles
  - AI Analyse tab: Session checkbox added (checked by default)
  - AI Generate tab: Session checkbox appears based on entity context profiles (suggested for NPCs, Characters, Quests, Events)
  - AI Database Assistant tab: New "Context Settings" section with session checkbox (checked by default)
  - Session context includes narrative content, dates, participants, and status
  - Token estimation accounts for session content (~200 tokens per session)

### Changed
- **Entity context profiles updated**: Modified context profiles for all entity types to appropriately include sessions:
  - Suggested for: NPCs, Characters, Quests, Events (session history provides valuable temporal/narrative context)
  - Optional for: Locations, Items, Factions, Settings
- **Checkbox ordering**: Sessions now appear second in context checkbox lists (after Settings, before Characters)

### Technical Details
- Modified `config/entity_context_profiles.py`: Added session to ENTITY_TYPE_NAMES, updated all context profiles, added session token estimate
- Modified `gui/main_window.py`: Added session to entity_types dictionary, updated fixed order arrays for context checkboxes
- Modified `gui/ai_database_assistant_tab.py`: Added context settings widget with session support, updated context building logic

## [1.2.4] - 2025-11-22

### Removed
- **Legacy abilities/inventory column references**: Removed all code referencing non-existent `abilities` and `inventory` columns in the documents table. These columns were never added to the table schema but had remnant references in various code paths.
  - Removed `abilities` and `inventory` parameters from `update_document()` method signature
  - Removed validation code for abilities/inventory parameters (~11 lines)
  - Updated SQL UPDATE query to remove non-existent columns
  - Removed `abilities` and `inventory` fields from Document dataclass
  - Fixed two `update_document()` callers in document_viewer.py that were passing these parameters
  - Deleted 8 orphaned UI methods for legacy ability/inventory editors (~230 lines)
  - Deleted migration code `_migrate_legacy_data()` method (~75 lines)
  - Total cleanup: ~340 lines of dead code removed

### Technical Details
- Modified `models/database.py`: Cleaned up update_document() method
- Modified `models/document.py`: Removed abilities/inventory from dataclass and serialization methods
- Modified `gui/dialogs/document_viewer.py`: Fixed callers and removed orphaned methods
- The modern system stores abilities/inventory as separate documents with entity_type='ability_item'/'inventory_item', which are properly indexed by FTS5 and work correctly

## [1.2.3] - 2025-11-22

### Fixed
- **Critical: FTS5 trigger schema mismatch**: Fixed FTS5 virtual table and triggers that referenced non-existent `abilities` and `inventory` columns. The triggers were attempting to index columns that were removed from the documents table schema in commit 44f2ba0, causing potential database errors on INSERT/UPDATE/DELETE operations.
  - Updated FTS5 virtual table definition to only include: `title`, `content`, `entity_type`
  - Fixed all three triggers (INSERT, UPDATE, DELETE) to match the current schema
  - Ensures consistency between `_create_indexes()` and `_recreate_fts_triggers()` methods

### Technical Details
- Modified `models/database.py`:
  - Line 201-205: Updated FTS5 virtual table schema
  - Line 211-214: Fixed INSERT trigger (documents_ai)
  - Line 218-221: Fixed DELETE trigger (documents_ad)
  - Line 225-230: Fixed UPDATE trigger (documents_au)
- All changes maintain consistency with existing `_recreate_fts_triggers()` and `_rebuild_fts5_index()` methods

## [1.0.1] - 2025-11-21

### Fixed
- **Entity list sort order persistence**: Sort order is now preserved when saving entities, searching, or refreshing lists. Previously, the list would reset to default (Name, ascending) after any save operation.
- **Cross-session sort preferences**: Sort preferences are now saved between application sessions. Each entity type (NPC, Location, Quest, etc.) maintains its own independent sort preference.

### Changed
- Repository cleanup: Removed build artifacts (build/, dist/ directories) from git history, reducing repository size from 744MB to 985KB
- Updated .gitignore to properly exclude build artifacts while tracking the PyInstaller spec file
- Created comprehensive PyInstaller build configuration (RPG_Database_Manager.spec)

### Technical Details
- Added sort state tracking in MainWindow class
- Implemented sort preference persistence in Settings class
- Connected to QTreeWidget sort indicator signals to capture user preferences
- Updated _load_entity_documents() and _on_entity_search() to preserve sort state

## [1.0.0] - 2024-11-20

### Added
- Initial release of RPG Database Manager
- Document-centric design for storing all RPG entities as rich text documents
- Multi-AI provider support (OpenAI GPT, Ollama local models, Mock provider)
- Session management with progress tracking and analysis
- Speech-to-text recording for session notes (multiple languages)
- Rich text editor with formatting toolbar
- Template system for NPCs, Characters, Factions, Quests, Locations, and more
- Module system for organizing campaigns
- Image management and attachment to documents
- Import/Export functionality for modules (ZIP and directory formats)
- Search and filter across all documents
- Dark and Light theme support
- AI Text Assistant with diff highlighting for text editing
- Approval workflow (Draft, Approved, Archived)
- Comprehensive settings and configuration system
- User guide and documentation
- Design system with consistent styling
- PyQt6-based modern GUI
- SQLite database backend
- Security features (encryption, password protection)
- Test suite with pytest
- PyInstaller build configuration

### Features by Category

#### Document Management
- Rich text editing with bold, italic, underline, and highlighting
- Multiple entity types (NPC, Character, Faction, Location, Quest, Item, World Settings)
- Template-based document creation
- Image attachments with preview
- Document approval workflow
- Full-text search

#### AI Integration
- OpenAI GPT integration (GPT-4, GPT-3.5)
- Ollama local model support (Llama 2, Mistral, etc.)
- Mock provider for testing
- AI-powered content generation
- Natural language search
- AI Text Assistant with diff highlighting

#### Session Management
- Session logging with date, participants, and duration
- Speech-to-text recording
- Multi-language support (Hungarian, English, German, French, Spanish, Italian, Portuguese, Russian, Japanese, Korean, Chinese)
- Session content analysis
- Progress tracking

#### Module System
- Separate databases per campaign
- Module creation, selection, and deletion
- Import/Export (ZIP and directory formats)
- Backup and restore functionality

#### User Interface
- Modern PyQt6-based interface
- Dark and Light themes
- Customizable fonts
- Responsive layout
- Consistent design system
- Icon integration

### Technical Details
- Python 3.8+ support
- PyQt6 6.9.0+ GUI framework
- SQLite database with FTS5 full-text search
- Cryptography for security features
- Cross-platform support (Windows, Linux, macOS)
- Comprehensive test coverage
- Type hints throughout codebase
- Black code formatting
- Flake8 and mypy code quality checks

### Documentation
- Comprehensive README with installation and usage instructions
- User guide with detailed feature documentation
- Quick Style Reference for developers
- API documentation (inline docstrings)
- Setup script for easy installation
- PyInstaller spec for building executables

### Known Issues
- None at initial release

### Dependencies
See [requirements.txt](requirements.txt) for complete list of dependencies.

## [Unreleased]

### Removed
- All AI features: the AI Generation, AI Analyse and AI Database Assistant tabs, the AI text assistant and summary in the editors' context menus, the Name Generator, the AI Settings and AI timeouts in Preferences, and the OpenAI/Ollama provider code. The stored provider list (`ai_providers.json`, with its encrypted API keys) and the old `AI/*` settings are deleted at startup. The encryption key itself is kept because the Discord token uses it. The `ai_suggestions` table stays in the schema (unused) so older versions can still open the database; new backups no longer carry AI suggestions, and old backups that do are still restorable (the suggestions are ignored).
- Online speech-to-text through the OpenAI Whisper API: it used the API key from AI Settings. A stored "openai" speech-to-text provider falls back to local Whisper.

### Planned Features
- Cloud synchronization
- Mobile companion app
- Advanced relationship mapping
- Combat encounter management
- Dice roller integration
- Multi-user collaboration
- Custom plugin system
- Enhanced AI features
- More export formats (PDF, HTML)
- Import from other RPG tools

---

## Version History Legend

### Types of Changes
- **Added** - New features
- **Changed** - Changes in existing functionality
- **Deprecated** - Soon-to-be removed features
- **Removed** - Removed features
- **Fixed** - Bug fixes
- **Security** - Vulnerability fixes

### Version Numbering
- **Major** (X.0.0) - Breaking changes
- **Minor** (0.X.0) - New features, backward compatible
- **Patch** (0.0.X) - Bug fixes, backward compatible
