# RPG Database Manager - User Guide

## Overview

RPG Database Manager is a comprehensive desktop application for managing roleplaying game content using a document-centric approach. The system stores all RPG elements (NPCs, factions, locations, quests, characters, etc.) as rich text documents with embedded structure, making it highly flexible and adaptable to any RPG system.

## Key Features

### Document-Centric Design
- **Unified Storage**: All RPG entities stored as rich text documents
- **Embedded Structure**: Information like "Name: Johnny" embedded in document text
- **Flexible Templates**: Customizable templates for consistent document creation
- **Rich Text Editing**: Full formatting support for document content


### Campaign Management
- **Module System**: Organize content by campaigns or game modules
- **Session Logging**: Record and track game sessions with progress analysis
- **Progress Tracking**: Monitor quest completion and character development
- **Relationship Mapping**: Track connections between entities

## Getting Started

### Installation

1. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Run the Application**:
   ```bash
   python main.py
   ```

3. **Initial Setup**:
   - Create a new RPG module for your campaign
   - Start creating documents using templates

### Creating Your First Module

1. Click **"New Module"** in the File menu or main toolbar
2. Enter a name for your campaign/module
3. Optionally add a description
4. Choose a database location (default is recommended for beginners)
5. Click **"Create Module"**

## Using the Application

### Main Interface

The window has a **sidebar** on the left, a bar at the top, and the page you chose in the middle:

- **Home**: an overview of the open campaign: how many entries each type has, the latest edits, the factions with their NPCs, and the latest sessions. Click a tile or a row to go there.
- **Play > Sessions**: log and review game sessions.
- **World**: one list per entity type (NPCs, Factions, Locations, Items, Quests, ... and your own types). Each shows the number of entries.
- **Library > Templates**: manage the templates used for new entries.

The **top bar** shows the open campaign (name, sessions and entries). Click it to switch to another campaign, create a new one, or open Manage Campaigns. Next to it is **Search everything**.

Application settings can be accessed via the **Preferences** menu under Edit.

#### Search everything (Ctrl+K)

Press **Ctrl+K** (or Edit > Search Everything...) and type to find any entry of the campaign by name or text, shown with its picture. Use Up/Down and Enter to open one. The same box runs actions such as New from template, the Name Generator, Settings, Manage campaigns, full screen and "Go to ..." any page. With nothing typed it lists the entries edited most recently. **Help > Keyboard Shortcuts** lists all shortcuts.

#### Working in a list

- Each row shows the entry's picture (its initials on a colour if it has none), the name, race and faction (every faction has its own colour) and the module.
- **Sort by** and the arrow button order the list; **Group by** groups it by module or, for people, by faction (click a group header to fold it). Your choice is remembered for each type.
- Hover or select a row to see it in the **preview panel** on the right: large picture, race, faction, module, created, modified and the first words of the text.
- **Filter** searches names and text. **Enter** or a double-click opens the entry.
- Right-click a row for Open, Pin for tonight, Send to Discord (NPCs and locations) and Delete.

#### Pinning entries for tonight

Click the star at the right of a row (or use "Pin for tonight" in the right-click menu or the preview) to pin an entry. Pinned entries stay in the **Tonight** strip at the bottom of the window on every page: click one to open it, or the × to unpin. Pins belong to the campaign.

#### Adventure modules and the scope

An entry can belong to **no module, one module or several**. Put it in modules with the **Modules** field of the editor, or select several rows in a list (Ctrl+click, Shift+click), right-click and choose **Add to module** (also **New module...**) or **Remove from module**. People can be given the same faction at once with **Set faction**.

The **Scope** button in the top bar (next to the campaign) shows the whole campaign, or only the entries of the modules you tick, or those with **No module**. It applies to every list, the Sessions page, Home, the counts and Ctrl+K. Each list also has a **Module** box for that list only. Modules themselves are the entries of the **Modules** page.

#### Links, suggestions and connections

- While you type in an entry, grey text completes the name of another entry. **Tab** accepts it and turns it into a link, **Esc** ignores it; with several matches a small list opens (Up/Down, then Tab or Enter). Select text, right-click and choose **Create entry from selection** to make a new entry of that name and link it.
- After you save, names that match no entry yet are offered as **new entries**; choose a type or Skip, or Never.
- The **Connections** tab shows **Mentioned in** (everything that links to this entry) and, for a session, **Cast and places**. The **Last seen** column of a list is the latest session that mentions the entry.
- **Map...** (editor) or right-click > **Relationship map...** draws what an entry is connected to; click a node to move around.
- **History...** shows the earlier versions of an entry (each save keeps the last 20) and restores one.
- Turn these helpers on or off in **Tools > Automation**.
- **Places inside places:** a location can be *Located in* another location (a street in a district, a district in a city). Set it in the editor, or select places and right-click > **Set 'Located in'**. The list can be sorted, grouped and filtered by it, and a filter on a city shows everything inside it.
- The Faction box of an NPC ends with **+ Add new faction...**; **New faction...** is also in the right-click Set faction menu.

#### Quick capture and health check

- **Ctrl+Space** opens a one-line box: what you type is added to the current session (the active one, else the latest) with the time, and the names in it are linked.
- **Tools > Health Check** (and the cards on Home) lists people without a faction, entries without a picture, entries linked to nothing and possible duplicates (**Merge...** folds one into the other), and entries not mentioned in the last sessions.
- When you close the program a **backup** of the campaign is written to the `auto_backups` folder next to the database (the last 7 are kept).

### Document Editing

Documents support rich text formatting including:
- **Bold text** for field labels (e.g., **Name:**, **Age:**)
- **Italic** and **underline** formatting
- **Text highlighting** for important sections
- Field placeholders like `[Field Name]` for structured data

The rich text editor provides formatting tools in the document viewer toolbar.

### Creating Documents

#### Using Templates

1. Open the list of the entity type in the sidebar (NPCs, Factions, ...)
2. Click **New** and choose **From template** (Ctrl+N)
3. Enter a name for the new entry
4. The editor opens with the type's default template; fill in the fields
5. Click **Save** (or **Save & Close**)

#### Blank Documents

1. Click **New** and choose **Blank document** (Ctrl+Shift+N)
2. Enter a name; the editor opens empty
3. Use field placeholders like `[Name]`, `[Age]`, `[Faction]` for structure and add rich formatting as needed
4. Save when ready

### Document Management

#### Editing Documents
- Double-click any document in the list (or press Enter) to open it in the editor window
- On the left: the primary picture (click to enlarge, right-click for options), the title, and the faction of a person; for a session its date, status and participants
- On the right, the tabs: **Description** (the text, with a formatting toolbar), **Images**, **Connections**, and for people **Abilities** and **Inventory**
- A marker at the top says "Unsaved changes"; closing the window asks whether to save them
- Add field placeholders for structured data

#### Deleting and Undo
- Select an entry and press **Delete**, or use Delete in the right-click menu
- The program asks first; afterwards the entry is hidden and a message offers **Undo** (or press Ctrl+Z) for 10 seconds, after which it is really deleted

#### Approval Workflow
- **Draft**: Initial document state
- **Approved**: Finalized and ready for use
- **Archived**: Older documents for reference

#### Search and Filtering
- Use the Filter box above a list to find entries by name or content
- Use **Ctrl+K** to find any entry of the campaign, whatever its type
- Sort and group a list with **Sort by** and **Group by**

### Game Session Management

#### Logging Sessions

1. Open **Sessions** in the sidebar
2. Click **"New Session"**
3. Enter session title and date
4. Add participant names
5. Set duration (optional)
6. Record what happened in the session content area
7. Click **"Create Session"**

#### Speech-to-Text Recording

The session content area includes a speech-to-text feature for hands-free session logging:

1. Click the **🎤 Record** button in the session form
2. Speak clearly in your configured language (default: Hungarian)
3. The system will automatically transcribe your speech and append it to the session content
4. The recording stops automatically after the configured timeout or when you stop speaking

**Speech-to-Text Settings:**
- Configure language in **Edit > Preferences > Speech-to-Text**
- Supported languages: Hungarian, English, German, French, Spanish, Italian, Portuguese, Russian, Japanese, Korean, Chinese
- Select microphone device from available system microphones
- Adjust listening timeout and maximum recording duration
- Uses Google Speech Recognition (requires internet connection)


#### Campaign Progress

- View overall campaign statistics
- Track quest progression across sessions
- Monitor character development
- Review recent activity and events


## Template System

### Using Templates

Templates provide structured starting points for different entity types:

- **NPC Template**: Character information, background, personality
- **Character Template**: Player character stats and details
- **Faction Template**: Organization structure and goals
- **Quest Template**: Objectives, rewards, and progress
- **Location Template**: Description, features, and points of interest

### Customizing Templates

1. Create documents using existing templates
2. Modify the content structure as needed
3. Extract new templates from edited documents
4. Share templates between modules

## Importing Adventure Modules (HTML)

A **campaign** is the top-level container you choose at startup. A **module** is an adventure inside it, made of one or more **sessions**.

1. Open the campaign, then `File > Import HTML Module...` and pick the module's `.html` file.
2. The preview lists the module, its sessions, NPCs, factions, locations, items and events. Untick anything you do not want; options let you skip pictures or image prompts.
3. Click **Import**. Everything is tagged with its module (Module column in the lists, badge and **Connections** tab in each document), NPCs are linked to their factions and to the sessions they appear in, and cross references in the text become clickable links.

Importing the same file again updates the existing documents instead of duplicating them. Documents you edited yourself are shown as "edited here" and are left alone unless you tick them. How to write a module file the app can import: **Help > Guides...** (F1), or the **Format guide...** button in the import window. The guide window can also save a copy of the guide and a ready-made example module. Importer reference for developers: `docs/html_module_format.md`.

## Importing Entity Files

(To save entries as such a file, select rows in a list and use **File > Export Entities...** or right-click > **Export as entity file...**.)

**File > Import Entities...** reads a Markdown, JSON or HTML file that holds only entries (NPCs, factions, locations, items, quests, events, sessions). The preview shows what is new, changed or unchanged and lets you choose where the entries go: the modules named in the file, one module, a new module, or none. Importing the same file again updates the entries; entries you edited in the program are left alone unless you tick them. The format, with an example file you can save, is in **Help > Guides**, tab "Entity file" (also `docs/entity_file_guide.md`).

## Module Management

### Creating Modules

Each RPG campaign should have its own module:

- **Separate Database**: Each module has its own database file
- **Organized Content**: Keep campaign content separate
- **Easy Sharing**: Export modules for sharing with other players
- **Backup Safety**: Independent backup and restore

### Module Operations

- **Create**: Start new campaigns
- **Select**: Switch between active modules
- **Delete**: Remove unwanted modules (with confirmation)
- **Backup**: Create backups of module data
- **Export**: Share modules with other users

Note: All document content and relationships are preserved during export/import operations.

## Data Management

### Export and Import

#### Exporting Modules
- Export complete modules as ZIP files or directories
- Include all documents, sessions, templates, and images
- Share campaigns with other players
- Create backups for safety

#### Importing Modules
- Import modules from ZIP files or directories
- Create new modules from exported data
- Preserve all relationships and document content
- Option to rename imported modules

#### Backup and Restore
- Automatic backups (configurable)
- Manual backup creation
- Complete database restoration
- Export search results and reports

### Data Validation

- Validate exported files before sharing
- Check data integrity and completeness
- Verify image and file references
- Ensure compatibility between versions

## Settings and Configuration

Application settings are accessed via the **Preferences** dialog in the Edit menu.

### Application Settings

- **Theme**: Choose UI appearance (default, dark, light)
- **Font Size**: Adjust text size for comfort
- **Auto-save**: Configure automatic saving intervals
- **Backup Settings**: Set backup frequency and retention


### Database Settings

- **Location**: Choose where to store database files
- **Backup**: Configure automatic backup settings
- **Performance**: Adjust cache and memory settings

## Tips and Best Practices

### Document Organization

1. **Use Consistent Naming**: Establish naming conventions for entities
2. **Leverage Templates**: Use templates for consistency
3. **Regular Approval**: Approve finalized documents to track progress
4. **Cross-Reference**: Link related entities using relationships

### Session Logging

1. **Regular Logging**: Log sessions after each game
2. **Detail Level**: Include key events, decisions, and outcomes
3. **Participant Tracking**: Record who played each session
4. **Progress Updates**: Note quest and character advancements


### Performance Optimization

1. **Regular Backups**: Keep backup frequency appropriate for your needs
2. **Archive Old Content**: Archive completed quests and old NPCs
3. **Image Management**: Optimize large images for better performance
4. **Database Maintenance**: Regular cleanup of unused data

## Troubleshooting

### Common Issues

#### Application Won't Start
- Check Python version (3.8+ required)
- Verify all dependencies are installed
- Check file permissions for data directory

#### Database Errors
- Ensure database file is not corrupted
- Check available disk space
- Verify file permissions


#### Import/Export Problems
- Validate export files before importing
- Check file formats and versions
- Ensure sufficient disk space for operations

### Getting Help

- Check the application logs in the data directory
- Review error messages for specific guidance
- Create backups before major operations

## Advanced Features

### Custom Entity Types

While the system comes with common entity types, you can:

1. Create custom templates for new entity types
2. Define custom field structures
3. Set up specialized approval workflows

### API Integration

For advanced users:

- Access services programmatically
- Create custom import/export formats
- Integrate with other tools
- Automate repetitive tasks

### Plugin System

The architecture supports:

- Additional export formats
- Specialized parsing rules
- Extended GUI components

## Version History

### Current Version (1.3.10)
- Complete document-centric RPG management system
- Speech-to-text session recording
- Comprehensive session analysis with sort preference persistence
- Rich template and export systems
- Full desktop GUI application with enhanced rich text editing
- Improved list formatting in rich text editor

## Support and Feedback

For support, feature requests, or bug reports:

- Check the application logs for detailed error information
- Test with simplified configurations to isolate issues
- Create regular backups before making major changes

---

*This user guide covers the core functionality of RPG Database Manager. The system is designed to be intuitive while providing powerful features for comprehensive RPG campaign management.*