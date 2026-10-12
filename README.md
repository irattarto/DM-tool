# RPG Database Manager

A comprehensive desktop application for managing tabletop RPG campaigns with a flexible document-centric approach.

![Version](https://img.shields.io/badge/version-1.7.1-blue.svg)
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
   - Open an entity list in the sidebar (NPCs, Locations, Quests, etc.)
   - Click "New" and choose "From template"
   - Enter a name and fill in the template
   - Click "Save"


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

### Navigation & Daily Use

- **Sidebar and Home page**: jump between Home, Sessions, every entity type and Templates; Home shows what is in the campaign (counts, latest edits, factions, sessions)
- **Picture lists**: every entity list shows the primary picture, race, faction (in its own colour) and module, with sorting, grouping and a preview panel
- **Search everything (Ctrl+K)**: find any entry or run an action from one box
- **Pinned tray "Tonight"**: pin the NPCs, places and items for the next session and open them from any page
- **Campaign switcher**: the open campaign is always visible at the top; switch with one click
- **Delete with Undo**: a deleted entry can be brought back for 10 seconds (Ctrl+Z)

### UI & Customization

- **Modern Design System**: Consistent styling with semantic colors
- **Dark/Light Themes**: Choose your preferred theme
- **Customizable Fonts**: Adjust font family and size
- **Responsive Layout**: Adaptive interface for different screen sizes


## Usage

### Creating Documents

1. Open an entity list in the sidebar (NPCs, Locations, Quests, etc.)
2. Click "New" and choose "From template" (Ctrl+N) or "Blank document" (Ctrl+Shift+N)
3. Enter a name; the editor opens
4. Fill in the template fields and add rich text formatting as needed
5. Save when ready

Find anything with Ctrl+K, and pin the entries you need for tonight's session with the star on a row.

### Managing Sessions

1. Open Sessions in the sidebar
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

Re-importing the same file updates changed documents and skips unchanged ones; documents you edited in the app are only overwritten when you tick them. How to write such a file: **Help > HTML Module Guide...** in the app, or the [HTML Module Guide](docs/html_module_guide.md). Importer details for developers: [docs/html_module_format.md](docs/html_module_format.md).

## HTML Module Creation Manual

The rules for writing an HTML module that the app can import (page skeleton, id prefixes, cards, links, factions, scenes, pictures, audio and maps, the JSON alternative, what the import warnings mean, and a checklist) are in **[docs/html_module_guide.md](docs/html_module_guide.md)**.

In the app it is under **Help > HTML Module Guide...** (F1), and the **Format guide...** button of the Import HTML Module dialog opens it too. The window can save a copy of the guide and a ready-made example module (`tools/html_module/module_template.html`) to any folder. Both files are part of the installation.

The importer reference for developers is [docs/html_module_format.md](docs/html_module_format.md). The complete generation rules and the pipeline scripts live in the separate **module-creator** project.

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
- [HTML Module Guide](docs/html_module_guide.md) - How to write an HTML module the app can import (also in the app: Help > HTML Module Guide)
- [HTML Module Format](docs/html_module_format.md) - What the HTML module importer recognises (reference for developers)
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
- Ubuntu 22.04+, Debian 12+, Linux Mint 21+ or equivalent
- **Install package (.deb)** from the Releases page: `sudo apt install ./rpg-database-manager_<version>_amd64.deb` (it pulls in the libraries it needs and adds a menu entry; remove it with `sudo apt remove rpg-database-manager`). Your data stays in `~/.local/share/RPG Database Manager`.
- Or the AppImage / tar.gz from the same page (no installation needed)
- When running from source, additional packages may be needed:
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
python packaging/linux/build_deb.py                       # -> rpg-database-manager_<version>_amd64.deb (needs only Python, no dpkg)
```

The GitHub Actions workflow `build-executables.yml` builds the Windows and Linux downloads (see below).
New Linux installs store data in `~/.local/share/RPG Database Manager` (an existing `~/Documents/RPG Database Manager` is still used).

## Downloadable test builds (Windows and Linux)

The workflow `.github/workflows/build-executables.yml` builds both platforms with PyInstaller:

| Platform | Download | Run |
|---|---|---|
| Windows 10/11 (x64) | `RPG_Database_Manager-windows-x64.zip` | unzip, run `RPG_Database_Manager\RPG_Database_Manager.exe` |
| Linux (x64), Debian / Ubuntu / Mint | `rpg-database-manager_<version>_amd64.deb` | `sudo apt install ./rpg-database-manager_<version>_amd64.deb`, then start it from the menu or with `rpg-database-manager` |
| Linux (x64), any distribution | `RPG_Database_Manager-x86_64.AppImage` or `RPG_Database_Manager-linux-x64.tar.gz` | `chmod +x` the AppImage and run it, or extract the tar.gz and run `rpg-database-manager/rpg-database-manager` |

Where to get them: GitHub > Actions > "Build executables" > pick a run > Artifacts. Tags starting with `v`
(and manual runs with "publish a pre-release" ticked) also publish them on the Releases page.
Windows may show a SmartScreen warning because the build is not code-signed: "More info" > "Run anyway".
Your data lives in `Documents\RPG Database Manager` on Windows and `~/.local/share/RPG Database Manager` on Linux.
