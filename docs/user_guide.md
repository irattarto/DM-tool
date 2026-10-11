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

The application uses a tabbed interface:

- **Documents Tab**: Create, edit, and manage RPG entities (including World Settings for game world configuration)
- **Game Sessions Tab**: Log and analyze game sessions

Application settings can be accessed via the **Preferences** menu under Edit.

### Document Editing

Documents support rich text formatting including:
- **Bold text** for field labels (e.g., **Name:**, **Age:**)
- **Italic** and **underline** formatting
- **Text highlighting** for important sections
- Field placeholders like `[Field Name]` for structured data

The rich text editor provides formatting tools in the document viewer toolbar.

### Creating Documents

#### Using Templates

1. In the Documents tab, click **"New Document"**
2. Select an entity type (NPC, Character, Faction, etc.)
3. Choose a template or use the default
4. Fill in the template fields
5. Enter a title for your document
6. Click **"Create Document"**

#### Manual Creation

1. Create a new document using any template
2. Edit the content in the rich text editor
3. Use field placeholders like `[Name]`, `[Age]`, `[Faction]` for structure
4. Add rich formatting as needed
5. Save and approve when ready

### Document Management

#### Editing Documents
- Double-click any document in the list to open it for editing
- Use the rich text editor with formatting toolbar
- Add field placeholders for structured data

#### Approval Workflow
- **Draft**: Initial document state
- **Approved**: Finalized and ready for use
- **Archived**: Older documents for reference

#### Search and Filtering
- Use the search bar to find documents by content
- Filter by entity type using the dropdown
- Search across full document content for comprehensive results

### Game Session Management

#### Logging Sessions

1. Go to the **Game Sessions** tab
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

Importing the same file again updates the existing documents instead of duplicating them. Documents you edited yourself are shown as "edited here" and are left alone unless you tick them. Details of the format: `docs/html_module_format.md`.

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