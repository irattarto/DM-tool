# RPG Database Manager

A comprehensive desktop application for managing tabletop RPG campaigns with a flexible document-centric approach.

![Version](https://img.shields.io/badge/version-1.6.0-blue.svg)
![Python](https://img.shields.io/badge/python-3.10+-blue.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)
![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20Linux%20%7C%20macOS-lightgrey.svg)

## Overview

RPG Database Manager is a powerful tool for Dungeon Masters and Game Masters to organize, create, and manage their tabletop RPG campaigns. Built with PyQt6, it offers a modern, intuitive interface with advanced features including session management, speech-to-text recording and comprehensive document organization.

### Key Features

- **Document-Centric Design**: Store all RPG entities (NPCs, locations, quests, etc.) as rich text documents with embedded structure
- **Session Management**: Track game sessions with progress analysis and speech-to-text recording
- **Module System**: Organize campaigns in separate modules with full import/export capabilities
- **Rich Text Editing**: Full formatting support with templates for consistent document creation
- **Image Management**: Attach and manage images for characters, locations, and other entities
- **Search & Filter**: Powerful search across all content with filtering by entity type
- **Template System**: Customizable templates for NPCs, quests, locations, and more
- **Dark/Light Themes**: Modern, customizable UI with dark and light theme support

### Recent Features (v1.4.0 - v1.5.1)

- **Crash-Safe Database**: WAL checkpoint on startup/shutdown and FULL sync mode prevent database corruption on hard crashes
- **Backup Image Warning**: A warning dialog now appears if images were missing from disk during backup (instead of silently skipping)
- **Thumbnail Regeneration on Restore**: Thumbnail cache is automatically rebuilt after restoring a module backup
- **Safe Overwrite Restore**: Images are now extracted to a temp location before deleting the target module, preventing data loss if the ZIP is unreadable
- **Module Backup & Restore**: Create and restore complete module backups (ZIP files with all data and images)
- **Database Tools Window**: Dedicated database management window with integrity checks and repair tools
- **Session Sort Preferences**: Sort preferences are now persisted between sessions

## Table of Contents

- [Installation](#installation)
- [Quick Start](#quick-start)
- [Features](#features)
- [Usage](#usage)
- [HTML Module Creation Manual](#html-module-creation-manual)
- [Building from Source](#building-from-source)
- [Documentation](#documentation)
- [Contributing](#contributing)
- [License](#license)

## Installation

### Prerequisites

- Python 3.10 or higher
- pip (Python package installer)

### Option 1: Install from Source

```bash
# Clone the repository (or download the source code)
cd "DM tool"

# Install dependencies
pip install -r requirements.txt

# Run the application
python main.py
```

### Option 2: Minimal Installation (Core Features Only)

If you only need core functionality without the speech-to-text features:

```bash
pip install PyQt6 Pillow cryptography aiohttp requests
python main.py
```

### Option 3: Use Pre-built Executable

Download the pre-built executable for your platform from the releases page (if available).

## Quick Start

1. **Launch the Application**
   ```bash
   python main.py
   ```

2. **Create Your First Module**
   - Click "New Module" in the File menu
   - Enter a name for your campaign
   - Click "Create Module"

3. **Create Your First Document**
   - Go to the Documents tab
   - Click "New Document"
   - Select an entity type (NPC, Location, Quest, etc.)
   - Fill in the template
   - Click "Create Document"


## Features

### Document Management

- **Rich Text Editor**: Full formatting with bold, italic, underline, and highlighting
- **Entity Types**: Pre-configured types including:
  - NPCs (Non-Player Characters)
  - Player Characters
  - Factions/Organizations
  - Locations
  - Quests
  - Items
  - World Settings
  - Custom types
- **Templates**: Reusable templates for consistent document creation
- **Approval Workflow**: Draft, Approved, and Archived states
- **Image Attachments**: Link images to documents with preview support


### Session Management

- **Session Logging**: Record game sessions with dates, participants, and duration
- **Speech-to-Text**: Voice recording for hands-free session notes (multiple languages supported)
- **Progress Tracking**: Monitor quest progression and character development

### Module System

- **Separate Campaigns**: Each campaign/module has its own database
- **Import/Export**: Share modules with other users
- **Backup & Restore**: Create backups of your campaign data
- **Module Selection**: Easily switch between different campaigns

### UI & Customization

- **Modern Design System**: Consistent styling with semantic colors
- **Dark/Light Themes**: Choose your preferred theme
- **Customizable Fonts**: Adjust font family and size
- **Responsive Layout**: Adaptive interface for different screen sizes


## Usage

### Creating Documents

1. Click "New Document" in the Documents tab
2. Select entity type (NPC, Location, Quest, etc.)
3. Choose a template or use default
4. Fill in the template fields
5. Add rich text formatting as needed
6. Save and approve when ready

### Managing Sessions

1. Go to the Game Sessions tab
2. Click "New Session"
3. Enter session details (title, date, participants)
4. Record session content (text or voice)
5. Click "Create Session"


### Importing/Exporting Modules

**Export:**
1. File > Export > Export Module
2. Choose export format (ZIP or directory)
3. Select destination
4. Click "Export"

**Import:**
1. File > Import > Import Module
2. Select module file or directory
3. Enter module name
4. Click "Import"

### Importing an HTML Module

1. File > Import HTML Module...
2. Pick the module `.html` file (keep its `images/` folder next to it)
3. Review the preview (new / changed / unchanged / "edited here" documents) and the options:
   - pictures, image prompts, and where the scene texts go;
   - **Gear lists become inventory items** (on by default): every line of an NPC's gear list becomes an item in the NPC's Inventory tab;
   - **Faction table**: NPCs the module leaves without a faction are listed with a drop-down, so you can pick one. Hover over an NPC (name or drop-down) to read a short description of them. Choose **+ New faction...** to type a new faction name: it then appears in the drop-down of every other NPC too, and is created as a faction document when at least one NPC uses it (typing the name of an existing faction just selects that one);
   - **Automatic factions** (off by default): NPCs without a faction join an automatic "Unaffiliated" faction and monsters a "Monsters" faction (named "Függetlenek" / "Szörnyek" in Hungarian modules). They are real faction documents you can rename or delete.
4. Click "Import"

Re-importing the same file updates changed documents and skips unchanged ones; documents you edited in the app are only overwritten when you tick them. Importer details: [docs/html_module_format.md](docs/html_module_format.md). How to write such a file: see the [HTML Module Creation Manual](#html-module-creation-manual).

## HTML Module Creation Manual

This manual is for whoever (or whatever script) *writes* the module HTML. The complete generation rules, the full module template and the pipeline scripts live in the separate **module-creator** project (`D:D-DataRPGAPPSVSCODEmodule-creator`); this section is the importer-side summary. A single `.html` file is enough; a module folder may also hold `images/`, `audio/` and a `module-export.json`. The importer recognises content by **element ids and a few class names**; styling, scripts and layout are free.

Check a file at any time (without opening the app):

```bash
python -m services.html_module_parser "Module.html"            # counts + warnings
python tools/html_module/validate_module.py "Module.html"      # broken links, missing pictures, NPCs without faction
```

A minimal, valid example is [tools/html_module/module_template.html](tools/html_module/module_template.html); start from it.

### 1. Page skeleton

| Element | Used for |
|---|---|
| `<html lang="hu">` | module language |
| `.eyebrow` | line `Rule system · Campaign · Part`; the text before the first `·` is the **rule system** |
| `h1` | module title (first one on the page) |
| `.sub` | subtitle / pitch |
| `.warn` | optional notice, kept as a quote at the top of the module document |
| `.toc` or `nav` with `<a href="#section-id">` | readable section titles |
| `<section id="...">` with `.section-header h2` | one `## Heading` block of the module document per section |

Everything that is not an entity or a scene (prose, boxes, tables, lists, read-aloud text `.readaloud`) ends up in the **module document**, grouped by section (max. 60,000 characters per section).

### 2. Entities: the id prefix decides the document type

Every entity needs a **unique id** with one of these prefixes. Ids are the identity used for re-import and links, so never rename them later.

| Prefix | Becomes | Markup |
|---|---|---|
| `c-` | NPC | `details.npc-card` (any `*-card` class works), or a table row |
| `g-` | NPC (minor) | table `tr` (first cell = name; a `Courier` cell or a column headed "prompt" = image prompt) |
| `m-` | NPC (monster) | `details.creature-card` |
| `f-` | Faction | `div.card` with an `h4` title |
| `l-` | Location | `details.room` with an `h4` title |
| `item-`, `gift-`, `pw-` | Item (normal / gift / spell) | `details.card` or `div.card` with an `h4` |
| `h-` | Item (handout) | `details.room` |
| `hook-` | Character (hook) | `div.hook-box`, optionally `data-character="Name"` (one per player character) |
| `j-` | Event (scene) | `div.scene` with `.scene-no` and `h4` |

Ids on `h2`, `h3`, `a` and `span` are anchors only and do **not** create documents.

### 3. Anatomy of a card

```html
<details class="npc-card" id="c-boss" data-faction="f-guild">
  <summary class="card-summary">
    <div class="npc-name">Big Boss</div>                 <!-- title (else first h4/h3/h2/strong, else the id) -->
    <div class="npc-epithet">The head of the guild</div> <!-- shown in italics at the top of the notes -->
    <div class="npc-meta"><span class="tag">Human</span><span class="badge b-strong">Strong</span></div>
  </summary>
  <div class="card-body"> ... paragraphs, lists, tables, <a class="xref" href="#l-yard">links</a> ... </div>
  <img class="gen-image gen-portrait" data-gen-id="c-boss" src="images/portraits/c-boss.jpg">
  <details class="prompt-toggle"><div class="imgprompt">image prompt text</div></details>
</details>
```

- **Tags** = text of `.tag`, `.room-tag`, `.rank`, `.badge` inside the summary (a `span.badge` in the body of a non-`details` card counts too). They become the document tags and a `**Tags:**` line. The badge colour class (`b-ally`, `b-foe`, ...) is not interpreted, only its text.
- **Body** = `.card-body`; without it, everything except `summary`, `h3`, `h4`.
- **Labelled fields**: `<div class="gear"><span class="lbl">Gear</span> ...</div>` becomes `**Gear:** ...` (same for `.loot`, `.foes`, `.appearance`, `.haven-note`, `.disc-list`). They stay text lines in the notes. In addition, each `<li>` of a `.gear` list on an NPC card becomes an **inventory item** of that NPC (title = the first `<b>`, text = the whole line incl. price tiers such as `.val`; item type "misc"). Put one notable item per `<li>`; common things (ammunition, a plain knife, food, money, consumables) may share one `<li>`; `.loot` on locations stays text because locations have no inventory.
- **Read-aloud**: `.readaloud` becomes a quote block.
- **Tables** become markdown tables (use `<th>` cells in the first row for a header). Table rows with an id with a `c-`/`g-` prefix become NPC documents; rows without an id stay text.
- **One card = one person.** Named or specific people (escorts, bodyguards, soldiers with a role) each get their own card and id. Generic extras with no story role (thugs, minions) are **one** `g-` card with `data-count="N"`: in the DM tool it is one minor NPC with the tag `×N`. A named minor character may be a compact card or a table row `<tr id="g-...">`.

### 4. Links

- `<a href="#c-boss">` (any entity id) becomes a link between the documents (`rpg://type/id`) and a `references` relationship. Link only to ids that exist (the validator lists unknown ones). Links to plain section anchors become links to the module document.
- External `http(s)` links are kept; other relative links keep their text only.

### 5. Factions

**Every NPC, minor NPC and creature card carries a visible faction line** with `data-faction` (the generation rule; see the [module-creator guide](../module-creator/docs/MODULE_GENERATION_GUIDE.md)):

```html
<div class="npc-faction" data-faction="f-alfa">Frakció: <a class="xref" href="#f-alfa">Alfa Társaság</a></div>
```

| `data-faction` | Meaning | At import |
|---|---|---|
| `f-xxx` | member of that faction card | linked, no question |
| `none` | deliberately in no faction | in the faction table, "(no faction)" preselected |
| `unknown` | the faction is not known (yet) | preselected "Unknown faction"; tag `faction: unknown`, nothing linked |
| `undecided` | the author has not decided yet | preselected "Undecided yet"; tag `faction: undecided`, nothing linked |

The line can also sit as a `span.npc-faction` in a table-row cell, or just be a `data-faction` attribute on the card; a `#f-...` link inside the `.npc-faction` line names the faction when the attribute is missing.
Older modules without the line are still handled: the importer looks for a `#f-...` link in the card, a faction name in the tags/epithet, or a faction card that links to the NPC.

The faction table of the preview lists every NPC without a real faction (hover shows a description): the drop-down offers the faction cards, "(no faction)", "Unknown faction", "Undecided yet", the automatic factions (if ticked) and **+ New faction...**. A faction already set on an earlier import or by hand is kept and never asked again; changing a choice on a re-import updates that NPC.

**For creators:** define catch-all faction cards yourself (for example `f-fuggetlen` "Függetlenek" and `f-szornyek` "Szörnyek") so that nearly every NPC and creature belongs somewhere.

### 6. Scenes and sessions

`<div class="scene" id="j-1"><span class="scene-no">1. scene · Place</span><h4>Title</h4> ... </div>` becomes an **event** document titled "1. Title". Entities nested inside or linked from the scene are attached to it. The import creates one first session; the scenes are listed in it (option in the preview).

### 7. Pictures, audio and maps

- **Pictures** live under `images/` next to the HTML, as relative paths that stay inside the module folder. The main picture of a card is, in this order: the `<img>` with `data-gen-id="<card id>"`; an `<img>` with class `gen-portrait`, `gen-room` or `gen-creature`; the first `<img>` that is not `gen-item`; or the file `images/{portraits,rooms,items,creatures}/<id>.{jpg,jpeg,png,webp}`. It is attached as the document's primary image.
- Other pictures of the card (for example `gen-item`, the belongings) are attached to the same document as **secondary images** (Images tab, caption "Gear" for `gen-item`); the main picture stays the primary one.
- **Image prompt**: the `.imgprompt` that follows the main picture. It is stored in the notes only when "Import image prompts" is ticked.
- **Audio**: `<audio src="audio/x.mp3">` becomes a link `🔊 Audio: audio/x.mp3` to the file in the module folder. **Ctrl+click** it in a document to play it in your default audio player (after a confirmation; only existing local `.mp3 .wav .ogg .m4a .flac` files open). The file itself is not copied into the database: keep the module folder where it is, and import again if you move it. Put a short label before the player.
- **Maps**: an inline `<svg>` becomes `🗺 Map image: <path of the <image> inside the svg>` plus a list of the `#l-...` locations linked from the svg. Keep the base picture as `<image href="images/maps/x.jpg">` inside the svg and wrap place labels in `<a href="#l-id">`. A `.svg-legend` of coloured spans is kept as a text legend.

### 8. What is ignored

`<script>`, `<style>`, `<head>`, `<button>`, `<noscript>`, the `<img>` tags themselves (pictures are handled as above), regenerate buttons and prompt toggles. CSS variables, colours and emoji icons are not imported.

### 9. Alternative: a JSON data block

Instead of relying on the markup, the generator can write the data itself, either inside the page (`<script type="application/json" id="dm-module-data">`) or as `<file>.module-export.json` / `module-export.json` next to it. The importer prefers it over the markup. Format (`formatVersion` 1; a newer version is rejected):

```json
{ "format": "dm-module", "formatVersion": 1,
  "module":   { "key": "raton-pass", "title": "", "eyebrow": "", "subtitle": "", "ruleSystem": "", "language": "", "content": "markdown" },
  "sessions": [ { "id": "j-1", "title": "", "label": "", "content": "markdown", "refs": ["c-boss"] } ],
  "entities": [ { "id": "c-boss", "type": "npc", "subtype": "", "title": "", "content": "markdown",
                  "tags": [], "factionRef": "f-guild", "factionHint": "", "imagePrompt": "",
                  "image": "images/portraits/c-boss.jpg", "extraImages": [], "extraImageCaptions": {},
                  "noFaction": false, "gear": [ { "title": "Rusty key", "content": "markdown" } ], "refs": [] } ] }
```

`type` is `npc`, `faction`, `location`, `item`, `character` or `event`. Generate a starting file from any module with `python -m services.html_module_parser "Module.html" --export`.

### 10. Known limitations and open points

- **Gear**: a `<li>` that lists several items joined by "·" becomes one inventory item (split it into several `<li>` in the HTML). The item type is always "misc", quantity 1, because the HTML carries no such data; change them in the app (a re-import keeps your changes).
- **Gear scope**: only NPC cards (`c-`) and character hooks get inventory items. `.loot` blocks on locations stay text, because locations have no inventory.
- **Audio** is linked, not stored: the link points to the file in the module folder, so it breaks when the folder moves (import again to refresh it), and it needs Ctrl+click. Copying audio into the database would need new storage, backup support and a player, and is not done.
- **Maps** are kept as text: the base image path and the list of linked locations. The SVG drawing itself is not imported.
- **Extra pictures** are attached to their own card only as secondary images; there is no separate item document for them.
- **Automatic factions** use only two fixed names per language (Hungarian and English; any other language gets the English names). Real affiliation is never guessed from the story text, so the creator's `data-faction` stays the reliable way.
- **Several NPCs on one card** (older modules) still import as one NPC document; the validator warns about titles like "X and her escorts".
- **Existing modules** such as Raton Pass have no `data-faction` on their NPCs yet; until they are added, use the faction table or the automatic factions in the preview.
- The faction table and the audio click are covered by automated tests; they have not been exercised by hand in the running app.

### 11. Creator checklist

- [ ] One `h1`, an `.eyebrow` starting with the rule system, `<html lang>` set
- [ ] Every entity has a unique id with a recognised prefix and a title (`.npc-name` or `h4`)
- [ ] All `href="#..."` point to existing ids (validator: no `ERROR` lines)
- [ ] Every NPC, minor NPC and creature has the visible `.npc-faction` line (`f-...`, `none`, `unknown` or `undecided`) and the module has catch-all faction cards
- [ ] Gear is a `.gear` list with one `<li>` per item, the item name in `<b>`
- [ ] Every picture exists under `images/` and is referenced relatively; the main picture has `data-gen-id` = card id
- [ ] Scenes are `div.scene` with `.scene-no` and `h4`
- [ ] `python tools/html_module/validate_module.py Module.html` reports 0 errors, and the parser counts match what you expect

## Building from Source

### Building Executable with PyInstaller

```bash
# Install PyInstaller
pip install pyinstaller

# Build the executable
pyinstaller --noconfirm RPG_Database_Manager.spec

# The executable will be in the dist/ folder
```

### Development Setup

```bash
# Install development dependencies
pip install -r requirements.txt

# Run tests
pytest

# Format code
black .

# Check code quality
flake8 .
mypy .
```

## Project Structure

```
.
├── main.py                 # Application entry point
├── requirements.txt        # Python dependencies
├── RPG_Database_Manager.spec  # PyInstaller configuration (Windows + Linux)
├── config/                 # Configuration modules
│   ├── settings.py
│   ├── ai_config.py
│   └── constants.py
├── gui/                    # GUI components
│   ├── main_window.py
│   ├── components/
│   ├── dialogs/
│   ├── widgets/
│   └── workers/
├── models/                 # Data models
│   ├── database.py
│   ├── document.py
│   └── session.py
├── services/               # Business logic
│   ├── export_service.py
├── utils/                  # Utility modules
│   ├── logger.py
│   ├── image_utils.py
│   └── text_utils.py
├── tests/                  # Test suite
│   └── test_models/
└── docs/                   # Documentation
    └── user_guide.md
```

## Documentation

- [User Guide](docs/user_guide.md) - Comprehensive guide for using the application
- [HTML Module Format](docs/html_module_format.md) - What the HTML module importer recognises ([creation manual](#html-module-creation-manual))
- [Quick Style Reference](QUICK_STYLE_REFERENCE.md) - Design system and styling guide

## Requirements

### Core Dependencies

- PyQt6 >= 6.9.0 (GUI framework)
- SQLite (included with Python)
- Pillow >= 10.0.0 (Image processing)
- cryptography >= 42.0.0 (Security)
- aiohttp >= 3.9.0 (Async HTTP for the Discord integration)
- requests >= 2.31.0 (HTTP client)

### Optional Dependencies

- SpeechRecognition >= 3.10.0 (Voice recording)
- faster-whisper >= 1.0.0 (Whisper transcription)
- PyAudio >= 0.2.14 (Audio processing)
- pandas >= 2.0.0 (Data export)
- reportlab >= 4.0.0 (PDF generation)

See [requirements.txt](requirements.txt) for complete list.

## Platform Support

### Windows
- Windows 10 or later
- Fully tested and supported
- Pre-built executables available

### Linux
- Ubuntu 20.04+ or equivalent
- Additional packages may be needed:
  ```bash
  sudo apt-get install portaudio19-dev  # For speech recognition
  ```

### macOS
- macOS 10.14 (Mojave) or later
- Most features work out of the box

## Troubleshooting

### Common Issues

**Application won't start:**
- Ensure Python 3.10+ is installed
- Verify all dependencies are installed: `pip install -r requirements.txt`
- Check file permissions for the data directory


**Speech recognition issues:**
- Windows: Install Visual C++ Build Tools
- Linux: Install portaudio19-dev
- Check microphone permissions
- Verify language settings

**Import/export errors:**
- Ensure sufficient disk space
- Verify file permissions
- Check file format compatibility

## Contributing

Contributions are welcome! Please feel free to submit pull requests or open issues for bugs and feature requests.

### Development Guidelines

1. Follow PEP 8 style guidelines
2. Use type hints where applicable
3. Add tests for new features
4. Update documentation as needed
5. Use the design system for UI components

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- Built with [PyQt6](https://www.riverbankcomputing.com/software/pyqt/)
- Icons and design inspired by modern desktop applications
- Thanks to the tabletop RPG community for inspiration and feedback

## Support

For questions, issues, or feature requests:
- Check the [User Guide](docs/user_guide.md)
- Review application logs in the data directory
- Create regular backups before major operations

## Roadmap

Future features under consideration:
- Cloud synchronization
- Mobile companion app
- Advanced relationship mapping
- Combat encounter management
- Dice roller integration
- Multi-user collaboration
- Custom plugin system

---

**Made with ♥ for Dungeon Masters and Game Masters everywhere**

## Linux build

```bash
sudo apt install libegl1 libgl1 libxkbcommon-x11-0 libxcb-cursor0 portaudio19-dev
pip install --require-hashes -r requirements-linux.lock   # the exact, hash-checked versions the releases use
# (on Windows: requirements-windows.lock; regenerate both with tools/update-locks.sh after editing requirements.txt)
pyinstaller --noconfirm RPG_Database_Manager.spec   # -> dist/rpg-database-manager/ (Windows: dist\RPG_Database_Manager\)
packaging/linux/build_appimage.sh                         # -> RPG_Database_Manager-x86_64.AppImage
```

The GitHub Actions workflow `build-executables.yml` builds the Windows and Linux downloads (see below).
New Linux installs store data in `~/.local/share/RPG Database Manager` (an existing `~/Documents/RPG Database Manager` is still used).

## Downloadable test builds (Windows and Linux)

The workflow `.github/workflows/build-executables.yml` builds both platforms with PyInstaller:

| Platform | Download | Run |
|---|---|---|
| Windows 10/11 (x64) | `RPG_Database_Manager-windows-x64.zip` | unzip, run `RPG_Database_Manager\RPG_Database_Manager.exe` |
| Linux (x64) | `RPG_Database_Manager-x86_64.AppImage` or `RPG_Database_Manager-linux-x64.tar.gz` | `chmod +x` the AppImage and run it, or extract the tar.gz and run `rpg-database-manager/rpg-database-manager` |

Where to get them: GitHub > Actions > "Build executables" > pick a run > Artifacts. Tags starting with `v`
(and manual runs with "publish a pre-release" ticked) also publish them on the Releases page.
Windows may show a SmartScreen warning because the build is not code-signed: "More info" > "Run anyway".
Your data lives in `Documents\RPG Database Manager` on Windows and `~/.local/share/RPG Database Manager` on Linux.
