"""
Database management for RPG Database Manager.
"""

import re
import sqlite3
import json
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime

from config.paths import get_data_dir

from utils.logger import get_logger, log_database_operation
from models.database_connection import DatabaseConnection



class DatabaseManager:
    """
    High-level database manager for RPG Database Manager.

    Handles database initialization, schema management, and provides
    convenient methods for common database operations.
    """

    SCHEMA_VERSION = 11

    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize database manager.

        Args:
            db_path: Optional custom database path. If None, uses default location.
        """
        if db_path is None:
            # Use default database location
            data_dir = get_data_dir()
            db_path = str(data_dir / "rpg_database_manager.db")

        self.db_path = db_path
        self.connection = DatabaseConnection(db_path)
        self.logger = get_logger('database')
        self.logger.info(f"Database path: {self.db_path}")

    def initialize_database(self) -> None:
        """Initialize database with schema and default data."""
        try:
            # Existing databases must be migrated BEFORE tables/indexes are
            # (re)created and before the version is stamped; otherwise the
            # stamp hides the pending migrations forever.
            existing = self._has_existing_schema()
            if existing:
                self._apply_migrations()

            with self.connection.transaction() as conn:
                self._create_tables(conn)
                self._create_indexes(conn)
                # Default templates are seeded exactly once, so templates a user
                # deleted or renamed are not re-created on every start.
                if conn.execute("SELECT 1 FROM app_meta WHERE key = 'templates_seeded'").fetchone() is None:
                    self._insert_default_templates(conn)
                    conn.execute("INSERT OR REPLACE INTO app_meta (key, value) VALUES ('templates_seeded', '1')")
                if not existing:
                    self._update_schema_version(conn)

            self.logger.info("Database initialized successfully")

            # Check database integrity after initialization (non-fatal)
            try:
                integrity_results = self.check_database_integrity()

                if not integrity_results.get('is_healthy', True):
                    self.logger.warning(
                        f"Database integrity issues detected: {len(integrity_results.get('errors', []))} errors"
                    )

                    # Only attempt repair if we have critical errors
                    critical_errors = integrity_results.get('errors', [])

                    if critical_errors:
                        self.logger.warning(f"Critical database errors found: {critical_errors}")

                        # Attempt automatic repair
                        repair_results = self.repair_database()

                        if not repair_results['success']:
                            self.logger.error(
                                "Database corruption detected and repair failed. "
                                "Application may not function correctly."
                            )
                            # Don't raise exception - let the app try to continue
                        else:
                            self.logger.info("Database repaired successfully during initialization")
                    else:
                        self.logger.info("Non-critical integrity issues detected, continuing initialization")

            except Exception as e:
                # Log integrity check failures but don't prevent initialization
                self.logger.warning(
                    f"Integrity check failed during initialization: {e}. "
                    f"This may be a transient issue. Continuing initialization..."
                )

        except (sqlite3.Error, OSError, IOError) as e:
            self.logger.error(f"Failed to initialize database: {e}")
            raise

    def _has_existing_schema(self) -> bool:
        """Return True if this is a pre-existing (non-empty) file database."""
        if self.db_path == ":memory:":
            return False
        # Errors (locked or unreadable file) must surface instead of looking like a new database
        row = self.connection.connect().execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='documents'"
        ).fetchone()
        return row is not None

    def _apply_migrations(self) -> None:
        """Apply database migrations if needed."""
        if self.db_path == ":memory:":
            return

        try:
            from models.database_migrations import DatabaseMigration

            migrator = DatabaseMigration(self.db_path)
            current_version = migrator.get_current_version()
            if current_version == 0:
                # Pre-versioning database: v4 is the baseline of the migrator
                migrator._update_schema_version(4)
                current_version = 4

            if current_version > self.SCHEMA_VERSION:
                raise RuntimeError(
                    f"This database was created by a newer version of the application "
                    f"(schema v{current_version}, this version understands v{self.SCHEMA_VERSION}). "
                    f"Update the application; the database has not been changed.")

            if current_version < self.SCHEMA_VERSION:
                self.logger.info(f"Database schema needs migration from v{current_version} to v{self.SCHEMA_VERSION}")
                success = migrator.migrate_to_version(self.SCHEMA_VERSION)

                if success:
                    self.logger.info("Database migration completed successfully")
                else:
                    error_msg = (
                        f"Database migration from v{current_version} to v{self.SCHEMA_VERSION} failed. "
                        f"The database may be in an inconsistent state. "
                        f"Please restore from backup if available."
                    )
                    self.logger.error(error_msg)
                    raise RuntimeError(error_msg)
            else:
                self.logger.debug(f"Database schema is up-to-date (v{current_version})")

        except Exception as e:
            self.logger.error(f"Error during migration: {e}", exc_info=True)
            raise

    def _create_tables(self, conn: sqlite3.Connection) -> None:
        """Create database tables."""

        # Modules table - stores campaign/module information
        conn.execute("""
            CREATE TABLE IF NOT EXISTS modules (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                description TEXT,
                created_date DATETIME DEFAULT CURRENT_TIMESTAMP,
                database_path TEXT NOT NULL UNIQUE,
                is_active BOOLEAN DEFAULT 1,
                discord_channel_id TEXT,
                discord_channel_name TEXT,
                discord_guild_id TEXT,
                discord_guild_name TEXT
            )
        """)

        # Document templates table - editable templates for entity types
        conn.execute("""
            CREATE TABLE IF NOT EXISTS document_templates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                template_name TEXT NOT NULL,
                entity_type TEXT NOT NULL,
                template_content TEXT NOT NULL,
                is_default BOOLEAN DEFAULT 0,
                created_date DATETIME DEFAULT CURRENT_TIMESTAMP,
                modified_date DATETIME DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(entity_type, template_name)
            )
        """)

        # Documents table - main content storage
        conn.execute("""
            CREATE TABLE IF NOT EXISTS documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                module_id INTEGER,
                entity_type TEXT NOT NULL,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                metadata TEXT, -- JSON metadata for additional fields
                created_date DATETIME DEFAULT CURRENT_TIMESTAMP,
                modified_date DATETIME DEFAULT CURRENT_TIMESTAMP,
                created_by TEXT DEFAULT 'user', -- 'user' or 'ai'
                status TEXT DEFAULT 'draft', -- 'draft', 'approved', 'archived'
                FOREIGN KEY (module_id) REFERENCES modules (id) ON DELETE CASCADE
            )
        """)

        # Game sessions table - session logs and progress tracking
        conn.execute("""
            CREATE TABLE IF NOT EXISTS game_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                module_id INTEGER,
                session_date DATE NOT NULL,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                participants TEXT, -- JSON array of participant names
                duration_minutes INTEGER,
                created_date DATETIME DEFAULT CURRENT_TIMESTAMP,
                status TEXT DEFAULT 'planned',
                FOREIGN KEY (module_id) REFERENCES modules (id) ON DELETE CASCADE
            )
        """)


        # Document relationships table - entity connections
        conn.execute("""
            CREATE TABLE IF NOT EXISTS document_relationships (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                from_document_id INTEGER NOT NULL,
                to_document_id INTEGER NOT NULL,
                relationship_type TEXT NOT NULL,
                description TEXT,
                created_date DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (from_document_id) REFERENCES documents (id) ON DELETE CASCADE,
                FOREIGN KEY (to_document_id) REFERENCES documents (id) ON DELETE CASCADE,
                UNIQUE(from_document_id, to_document_id, relationship_type)
            )
        """)

        # Earlier versions of an entry (the last few, text only): History in the editor
        conn.execute("""
            CREATE TABLE IF NOT EXISTS document_versions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                document_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                content TEXT,
                saved_date DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (document_id) REFERENCES documents (id) ON DELETE CASCADE
            )
        """)

        # Images table - image storage and metadata
        conn.execute("""
            CREATE TABLE IF NOT EXISTS images (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                module_id INTEGER,
                document_id INTEGER,
                filename TEXT NOT NULL,
                original_name TEXT NOT NULL,
                file_path TEXT NOT NULL,
                file_size INTEGER,
                mime_type TEXT,
                description TEXT,
                is_primary BOOLEAN DEFAULT 0,
                uploaded_date DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (module_id) REFERENCES modules (id) ON DELETE CASCADE,
                FOREIGN KEY (document_id) REFERENCES documents (id) ON DELETE CASCADE
            )
        """)

        # Legacy table of the removed AI features: unused, kept so the schema stays compatible with older versions
        conn.execute("""
            CREATE TABLE IF NOT EXISTS ai_suggestions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER,
                document_id INTEGER,
                suggestion_type TEXT NOT NULL,
                original_content TEXT,
                suggested_content TEXT,
                reasoning TEXT,
                status TEXT DEFAULT 'pending',
                created_date DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (session_id) REFERENCES game_sessions (id) ON DELETE CASCADE,
                FOREIGN KEY (document_id) REFERENCES documents (id) ON DELETE CASCADE
            )
        """)

        # Schema version table - for database migrations
        conn.execute("""
            CREATE TABLE IF NOT EXISTS schema_version (
                version INTEGER PRIMARY KEY,
                applied_date DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Entity type customisation (labels, order, visibility, custom types)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS entity_types (
                key TEXT PRIMARY KEY,
                label_singular TEXT NOT NULL,
                label_plural TEXT NOT NULL,
                sort_order INTEGER NOT NULL DEFAULT 0,
                hidden INTEGER NOT NULL DEFAULT 0,
                builtin INTEGER NOT NULL DEFAULT 0
            )
        """)

        # Small key/value table for one-time application markers
        conn.execute("""
            CREATE TABLE IF NOT EXISTS app_meta (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)

        self.logger.info("Database tables created")

    def _create_indexes(self, conn: sqlite3.Connection) -> None:
        """Create database indexes for performance."""

        indexes = [
            # Documents indexes
            "CREATE INDEX IF NOT EXISTS idx_documents_module_id ON documents(module_id)",
            "CREATE INDEX IF NOT EXISTS idx_documents_entity_type ON documents(entity_type)",
            "CREATE INDEX IF NOT EXISTS idx_documents_status ON documents(status)",
            "CREATE INDEX IF NOT EXISTS idx_documents_created_by ON documents(created_by)",

            # Game sessions indexes
            "CREATE INDEX IF NOT EXISTS idx_game_sessions_module_id ON game_sessions(module_id)",
            "CREATE INDEX IF NOT EXISTS idx_game_sessions_date ON game_sessions(session_date)",


            # Document relationships indexes
            "CREATE INDEX IF NOT EXISTS idx_relationships_from ON document_relationships(from_document_id)",
            "CREATE INDEX IF NOT EXISTS idx_relationships_to ON document_relationships(to_document_id)",
            "CREATE INDEX IF NOT EXISTS idx_relationships_type ON document_relationships(relationship_type)",
            "CREATE INDEX IF NOT EXISTS idx_versions_document ON document_versions(document_id)",

            # Images indexes
            "CREATE INDEX IF NOT EXISTS idx_images_module_id ON images(module_id)",
            "CREATE INDEX IF NOT EXISTS idx_images_document_id ON images(document_id)",
        ]

        for index_sql in indexes:
            conn.execute(index_sql)

        self.logger.info("Database indexes created")

    def _insert_default_templates(self, conn: sqlite3.Connection) -> None:
        """Insert default document templates."""

        default_templates = [
            {
                "template_name": "NPC Template",
                "entity_type": "npc",
                "template_content": """NPC: [Character Name]

Basic Information:
Name: [Full Name]
Age: [Age]
Gender: [Gender]
Race/Species: [Race or Species]
Occupation: [Job or Role]

Appearance:
Physical Description: [Height, build, distinctive features]
Clothing/Armor: [Typical attire and equipment]

Background:
Origin: [Where they come from]
History: [Brief background story]
Motivations: [What drives them]

Personality:
Traits: [Personality characteristics]
Flaws: [Weaknesses or negative traits]
Ideals: [What they believe in]

Relationships:
Allies: [Friends, allies, or associates]
Enemies: [Rivals or enemies]
Faction: [Organization or group affiliation]

Notes:
[Additional notes, plot hooks, or special abilities]
""",
                "is_default": True
            },
            {
                "template_name": "Character Template",
                "entity_type": "character",
                "template_content": """Character: [Character Name]

Basic Information:
Name: [Full Name]
Player: [Player Name]
Level: [Character Level]
Class: [Character Class]
Race: [Character Race]
Background: [Character Background]

Ability Scores:
Strength: [STR]
Dexterity: [DEX]
Constitution: [CON]
Intelligence: [INT]
Wisdom: [WIS]
Charisma: [CHA]

Combat Stats:
Hit Points: [Current/Max HP]
Armor Class: [AC]
Speed: [Movement Speed]
Initiative: [Initiative Bonus]

Equipment:
Weapons: [List of weapons]
Armor: [Armor and shield]
Other Items: [Important possessions]

Backstory:
Origin: [Where the character comes from]
History: [Character's personal history]
Goals: [Character's objectives and motivations]

Notes:
[Additional notes, plot hooks, or special abilities]
""",
                "is_default": True
            },
            {
                "template_name": "Faction Template",
                "entity_type": "faction",
                "template_content": """Faction: [Faction Name]

Overview:
Type: [Guild, Order, Clan, etc.]
Primary Race: [Predominant species, or "Mixed" for diverse factions]
Leader: [Leader's name and title]
Headquarters: [Main base location]
Founded: [When and by whom]

Structure:
Hierarchy: [Organizational structure]
Members: [Number and types of members]
Allies: [Allied factions or groups]
Enemies: [Rival or enemy factions]

Goals:
Primary Objective: [Main goal or purpose]
Methods: [How they achieve their goals]
Reputation: [How others view them]

Resources:
Assets: [Important resources or holdings]
Influence: [Areas of influence or control]

Notes:
[Additional information, plot hooks, or special characteristics]
""",
                "is_default": True
            },
            {
                "template_name": "Quest Template",
                "entity_type": "quest",
                "template_content": """Quest: [Quest Title]

Overview:
Type: [Main Quest, Side Quest, etc.]
Status: [Not Started, In Progress, Completed, Failed]
Quest Giver: [Who gave this quest]

Description:
[Brief description of the quest]

Objectives:
1. [Primary objective]
2. [Secondary objectives]
3. [Optional objectives]

Rewards:
Experience: [XP reward]
Items: [Item rewards]
Other: [Additional rewards]

Notes:
[Additional quest details, complications, or plot information]
""",
                "is_default": True
            },
            {
                "template_name": "Session Template",
                "entity_type": "session",
                "template_content": """Session: [Session Title]

Session Information:
Date: [Session Date - YYYY-MM-DD]
Duration: [Duration in minutes]
Participants: [List of players/participants]

Session Log:
[What happened during this game session]

Key Events:
• [Major events, encounters, or plot developments]

NPC Interactions:
• [Important NPC conversations or encounters]

Quest Progress:
• [Quest updates or progress made]

Location Visits:
• [Places visited or explored]

Combat Encounters:
• [Battles, conflicts, or challenges]

Loot and Rewards:
• [Items found, experience gained, or other rewards]

Notes:
[Additional notes, player feedback, or things to remember for next session]
""",
                "is_default": True
            },
            {
                "template_name": "Event Template",
                "entity_type": "event",
                "template_content": """Event: [Event Name]

Overview:
Type: [Festival, Battle, Ceremony, Plot Event, etc.]
Date/Time: [When this event occurs or is scheduled]
Location: [Where the event takes place]
Duration: [How long the event lasts]

Description:
[Detailed description of what happens during this event]

Participants:
Key Figures: [Important NPCs or characters involved]
Attendees: [Who typically attends or participates]
Antagonists: [Opposing forces or obstacles]

Objectives:
Primary Goal: [Main purpose or outcome of the event]
Secondary Goals: [Additional objectives or side activities]
Player Involvement: [How players can participate or influence]

Triggers:
Start Condition: [What causes this event to begin]
Prerequisites: [What must happen before this event]
Consequences: [What happens as a result of this event]

Rewards and Outcomes:
Success: [What happens if the event succeeds]
Failure: [What happens if the event fails]
Neutral: [What happens regardless of outcome]

Notes:
[Additional information, plot hooks, or complications]
""",
                "is_default": True
            },
            {
                "template_name": "Location Template",
                "entity_type": "location",
                "template_content": """Location: [Location Name]

Overview:
Type: [City, Town, Village, Dungeon, Wilderness, Building, etc.]
Region: [Geographic region or area]
Size: [Population or physical dimensions]
Climate: [Weather and environmental conditions]

Description:
Appearance: [What the location looks like]
Atmosphere: [Mood, sounds, smells, general feel]
Notable Features: [Landmarks, distinctive characteristics]

Layout:
Key Areas: [Important places within this location]
• [Area 1: Description]
• [Area 2: Description]
• [Area 3: Description]

Access: [How to get there, entrances, exits]

Inhabitants:
Population: [Number and types of inhabitants]
Leadership: [Who rules or manages this place]
Factions: [Groups or organizations present]
Notable NPCs: [Important characters found here]

History:
Founded: [When and how it was established]
Major Events: [Significant historical moments]
Current Status: [Present-day situation]

Resources and Services:
Available: [Shops, inns, temples, services]
Trade: [Common goods, specialties]
Cost of Living: [Relative prices for goods and lodging]

Dangers and Hooks:
Threats: [Monsters, hazards, conflicts]
Secrets: [Hidden information or mysteries]
Quests: [Adventure opportunities available here]

Notes:
[Additional information, rumors, or plot connections]
""",
                "is_default": True
            },
            {
                "template_name": "Item Template",
                "entity_type": "item",
                "template_content": """Item: [Item Name]

Basic Information:
Type: [Weapon, Armor, Potion, Magic Item, Treasure, Tool, etc.]
Rarity: [Common, Uncommon, Rare, Very Rare, Legendary, Artifact]
Value: [Gold piece value or approximate worth]
Weight: [Weight in pounds or kg]

Appearance:
Description: [What the item looks like]
Materials: [What it's made from]
Distinctive Features: [Special markings, decorations, or characteristics]

Properties:
Mechanical Effects: [Game statistics, bonuses, abilities]
Requirements: [Attunement, class restrictions, proficiency needed]
Charges/Uses: [Limited uses, recharge conditions]

History:
Origin: [Where or how it was created]
Creator: [Who made it, if known]
Previous Owners: [Notable past possessors]
Legend: [Stories or myths about the item]

Identification:
Known Properties: [What is obvious or easily discovered]
Hidden Properties: [Secrets that require investigation]
Curses/Drawbacks: [Negative effects or dangers]

Acquisition:
Location: [Where it can be found or purchased]
Quest Hook: [How players might obtain it]
Price: [Cost if available for purchase]

Notes:
[Additional information, plot connections, or special conditions]
""",
                "is_default": True
            },
            {
                "template_name": "Setting Template",
                "entity_type": "setting",
                "template_content": """Setting: [Setting/World Element Name]

Overview:
Category: [Cosmology, Geography, History, Culture, Magic System, Technology, etc.]
Scope: [Local, Regional, Continental, Global, Planar]
Importance: [How central this is to the campaign]

Description:
Summary: [Brief overview of this world element]
Details: [In-depth explanation]

Key Concepts:
• [Concept 1: Description]
• [Concept 2: Description]
• [Concept 3: Description]

History and Development:
Origin: [How this element came to be]
Evolution: [How it has changed over time]
Current State: [Present-day status]

Rules and Mechanics:
Game Impact: [How this affects gameplay]
Limitations: [What doesn't work or isn't allowed]
Special Rules: [Unique mechanics or exceptions]

Cultural Significance:
Beliefs: [What people think or know about this]
Practices: [How people interact with this element]
Taboos: [What is forbidden or frowned upon]

Geographic Distribution:
Where Found: [Locations where this is relevant]
Regional Variations: [How it differs by area]

Related Elements:
Connections: [How this relates to other world elements]
Dependencies: [What this relies on or affects]
Conflicts: [Contradictions or tensions with other elements]

Story Hooks:
Plot Potential: [How this can drive adventures]
Mysteries: [Unanswered questions or secrets]
Complications: [Problems or challenges this creates]

Notes:
[Additional information, campaign-specific details, or house rules]
""",
                "is_default": True
            }
        ]

        for template in default_templates:
            try:
                conn.execute("""
                    INSERT OR IGNORE INTO document_templates
                    (template_name, entity_type, template_content, is_default, created_date)
                    VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                """, (
                    template["template_name"],
                    template["entity_type"],
                    template["template_content"],
                    template["is_default"]
                ))
            except sqlite3.Error as e:
                self.logger.warning(f"Failed to insert template {template['template_name']}: {e}")

        self.logger.info("Default templates inserted")

    def _update_schema_version(self, conn: sqlite3.Connection) -> None:
        """Update schema version in database."""
        conn.execute("""
            INSERT OR REPLACE INTO schema_version (version, applied_date)
            VALUES (?, CURRENT_TIMESTAMP)
        """, (self.SCHEMA_VERSION,))

    # Entity type management
    def get_entity_types(self) -> List[Dict[str, Any]]:
        """Return stored entity type customisations ordered by sort_order."""
        with self.connection.transaction() as conn:
            rows = conn.execute(
                "SELECT key, label_singular, label_plural, sort_order, hidden, builtin "
                "FROM entity_types ORDER BY sort_order, key"
            ).fetchall()
            return [dict(r) for r in rows]

    def save_entity_types(self, types: List[Dict[str, Any]]) -> None:
        """Replace the stored entity type list (labels, order, visibility, custom types).

        Keys are immutable and must be unique; labels are validated like other names.
        Newly created custom types get a generic default template.
        """
        from utils.text_utils import TextUtils
        from config.entity_types import is_valid_key, RESERVED_KEYS

        with self.connection.transaction() as conn:
            stored_keys = {r[0] for r in conn.execute("SELECT key FROM entity_types")}
        seen = set()
        for position, t in enumerate(types):
            key = t['key']
            if key in seen:
                raise ValueError(f"Duplicate entity type key: {key}")
            seen.add(key)
            # Only NEW keys must be valid slugs; legacy keys already stored must not block every save
            if key in RESERVED_KEYS or (not t.get('builtin') and key not in stored_keys
                                        and not is_valid_key(key)):
                raise ValueError(f"Invalid entity type key: {key}")
            for field_name in ('label_singular', 'label_plural'):
                check = TextUtils.validate_entity_name(t[field_name], max_length=50)
                if not check['valid']:
                    raise ValueError(f"Invalid {field_name}: {', '.join(check['issues'])}")

        with self.connection.transaction() as conn:
            existing = {r[0] for r in conn.execute("SELECT key FROM entity_types")}
            removed = existing - seen
            for key in removed:
                if conn.execute("SELECT 1 FROM documents WHERE entity_type = ? LIMIT 1", (key,)).fetchone():
                    raise ValueError(f"Cannot remove entity type '{key}': documents still use it")
                conn.execute("DELETE FROM document_templates WHERE entity_type = ?", (key,))
            conn.execute("DELETE FROM entity_types")
            for position, t in enumerate(types):
                conn.execute(
                    "INSERT INTO entity_types (key, label_singular, label_plural, sort_order, hidden, builtin) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (t['key'], t['label_singular'], t['label_plural'], position,
                     int(bool(t.get('hidden'))), int(bool(t.get('builtin'))))
                )
                if not t.get('builtin') and t['key'] not in existing:
                    conn.execute(
                        "INSERT OR IGNORE INTO document_templates "
                        "(template_name, entity_type, template_content, is_default) VALUES (?, ?, ?, 1)",
                        (f"{t['label_singular']} Template", t['key'],
                         f"{t['label_singular']}: [Name]\n\nDescription:\n[Description]\n\nNotes:\n[Notes]\n")
                    )

    def count_documents_of_type(self, entity_type: str) -> int:
        """Number of documents (all modules) of an entity type."""
        with self.connection.transaction() as conn:
            return conn.execute(
                "SELECT COUNT(*) FROM documents WHERE entity_type = ?", (entity_type,)
            ).fetchone()[0]

    def delete_entity_type(self, key: str) -> bool:
        """Delete a custom entity type that no document uses. Built-ins cannot be deleted."""
        with self.connection.transaction() as conn:
            row = conn.execute("SELECT builtin FROM entity_types WHERE key = ?", (key,)).fetchone()
            if row is None or row[0]:
                return False
            if conn.execute("SELECT 1 FROM documents WHERE entity_type = ? LIMIT 1", (key,)).fetchone():
                return False
            conn.execute("DELETE FROM document_templates WHERE entity_type = ?", (key,))
            conn.execute("DELETE FROM entity_types WHERE key = ?", (key,))
            return True

    # Application-level key/value storage (app_meta)
    def get_app_meta(self, key: str, default: Optional[str] = None) -> Optional[str]:
        with self.connection.transaction() as conn:
            row = conn.execute("SELECT value FROM app_meta WHERE key = ?", (key,)).fetchone()
            return row[0] if row else default

    def set_app_meta(self, key: str, value: Optional[str]) -> None:
        """Store a value; None removes the key."""
        with self.connection.transaction() as conn:
            if value is None:
                conn.execute("DELETE FROM app_meta WHERE key = ?", (key,))
            else:
                conn.execute("INSERT OR REPLACE INTO app_meta (key, value) VALUES (?, ?)", (key, value))

    # Discord server + channel link per module
    def set_module_discord_channel(self, module_id: int, channel_id: Optional[str],
                                   channel_name: Optional[str] = None,
                                   guild_id: Optional[str] = None,
                                   guild_name: Optional[str] = None) -> bool:
        """Link a module to a Discord channel on a server (None clears the link)."""
        if channel_id is not None and not re.fullmatch(r'[0-9]{15,25}', str(channel_id)):
            raise ValueError("A Discord channel id is a number.")
        if guild_id is not None and not re.fullmatch(r'[0-9]{15,25}', str(guild_id)):
            raise ValueError("A Discord server id is a number.")
        linked = channel_id is not None
        with self.connection.transaction() as conn:
            cursor = conn.execute(
                "UPDATE modules SET discord_channel_id = ?, discord_channel_name = ?, "
                "discord_guild_id = ?, discord_guild_name = ? WHERE id = ?",
                (str(channel_id) if linked else None,
                 (channel_name or None) if linked else None,
                 str(guild_id) if linked and guild_id is not None else None,
                 (guild_name or None) if linked and guild_id is not None else None,
                 module_id))
            return cursor.rowcount > 0

    # Module management methods
    def create_module(self, name: str, description: str = "",
                      database_path: Optional[str] = None) -> int:
        """Create a new RPG module."""
        # Import security utilities
        from utils.text_utils import TextUtils
        from utils.security_utils import get_security_validator

        # Validate module name
        name_validation = TextUtils.validate_entity_name(name, max_length=255)
        if not name_validation['valid']:
            raise ValueError(f"Invalid module name: {', '.join(name_validation['issues'])}")

        # Validate description if provided
        if description:
            desc_validation = get_security_validator().validate_text_content(description)
            if not desc_validation['valid']:
                raise ValueError(f"Invalid description: {', '.join(desc_validation['issues'])}")

        if database_path is None:
            # Generate unique database path for the module
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            # Sanitize name for filename
            safe_name = re.sub(r'[^\w\-]+', '_', TextUtils.sanitize_entity_name(name, max_length=50)).strip('_') or 'module'
            module_db_name = f"module_{safe_name}_{timestamp}.db"

            data_dir = get_data_dir()
            database_path = str(data_dir / "modules" / module_db_name)

        # Validate database path
        if database_path:
            path_validation = TextUtils.validate_file_path(database_path, allowed_extensions=['.db'], allow_absolute=True)
            if not path_validation['valid']:
                raise ValueError(f"Invalid database path: {', '.join(path_validation['issues'])}")

        with self.connection.transaction() as conn:
            cursor = conn.execute("""
                INSERT INTO modules (name, description, database_path)
                VALUES (?, ?, ?)
            """, (name, description, database_path))

            log_database_operation("INSERT", "modules", cursor.lastrowid)
            return cursor.lastrowid

    def get_modules(self) -> List[Dict[str, Any]]:
        """Get all modules."""
        with self.connection.transaction() as conn:
            cursor = conn.execute("""
                SELECT * FROM modules WHERE is_active = 1
                ORDER BY created_date DESC
            """)

            return [dict(row) for row in cursor.fetchall()]

    def get_module_counts(self, module_id: int) -> Dict[str, Any]:
        """Entries per entity type and number of sessions of a module, for the sidebar and campaign switcher."""
        with self.connection.transaction() as conn:
            per_type = {row['entity_type']: row['count'] for row in conn.execute(
                "SELECT entity_type, COUNT(*) AS count FROM documents WHERE module_id = ? GROUP BY entity_type",
                (module_id,))}
        # Sessions are documents of type 'session' (that is what the Sessions page lists)
        return {'documents': per_type, 'sessions': per_type.get('session', 0)}

    def get_module(self, module_id: int) -> Optional[Dict[str, Any]]:
        """Get a specific module by ID."""
        with self.connection.transaction() as conn:
            cursor = conn.execute("SELECT * FROM modules WHERE id = ?", (module_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_all_modules_with_statistics(self) -> List[Dict[str, Any]]:
        """
        Get all modules (active and inactive) with their statistics in a single optimized query.

        Returns:
            List of module dictionaries with statistics
        """
        try:
            with self.connection.transaction() as conn:
                # Single query using LEFT JOINs and GROUP BY for optimal performance
                cursor = conn.execute("""
                    SELECT
                        m.*,
                        COUNT(DISTINCT d.id) as document_count,
                        COUNT(DISTINCT i.id) as image_count,
                        COUNT(DISTINCT s.id) as session_count
                    FROM modules m
                    LEFT JOIN documents d ON d.module_id = m.id
                    LEFT JOIN images i ON i.module_id = m.id
                    LEFT JOIN game_sessions s ON s.module_id = m.id
                    GROUP BY m.id
                    ORDER BY m.is_active DESC, m.created_date DESC
                """)

                modules = []
                for row in cursor.fetchall():
                    module = dict(row)

                    # Get database file size (can't be done in SQL)
                    db_path_str = module.get('database_path', '')
                    if db_path_str:
                        db_path = Path(db_path_str)
                        module['database_size'] = db_path.stat().st_size if db_path.exists() else 0
                    else:
                        module['database_size'] = 0

                    modules.append(module)

                self.logger.info(f"Loaded {len(modules)} modules with statistics in single query")
                return modules

        except sqlite3.Error as e:
            self.logger.error(f"Error getting all modules with statistics: {e}", exc_info=True)
            return []

    def rename_module(self, module_id: int, new_name: str) -> bool:
        """
        Rename a module (updates display name only, no file operations).

        Args:
            module_id: ID of the module to rename
            new_name: New name for the module

        Returns:
            True if successful, False otherwise
        """
        try:
            # Import security utilities
            from utils.text_utils import TextUtils

            # Validate input
            name_validation = TextUtils.validate_entity_name(new_name, max_length=255)
            if not name_validation['valid']:
                self.logger.error(f"Invalid module name: {', '.join(name_validation['issues'])}")
                return False

            with self.connection.transaction() as conn:
                # Check for duplicate names
                existing = conn.execute(
                    "SELECT id FROM modules WHERE name = ? AND id != ?",
                    (new_name, module_id)
                ).fetchone()

                if existing:
                    self.logger.error(f"Module name '{new_name}' already exists (module ID: {existing['id']})")
                    return False

                # Perform rename
                cursor = conn.execute("""
                    UPDATE modules
                    SET name = ?
                    WHERE id = ?
                """, (new_name, module_id))

                if cursor.rowcount > 0:
                    log_database_operation("UPDATE", "modules", module_id)
                    self.logger.info(f"Renamed module {module_id} to '{new_name}'")
                    return True
                else:
                    self.logger.warning(f"No module found with id {module_id}")
                    return False

        except Exception as e:
            self.logger.error(f"Error renaming module {module_id}: {e}", exc_info=True)
            return False

    def soft_delete_module(self, module_id: int) -> bool:
        """
        Soft delete a module (sets is_active = 0, preserves all data).

        Args:
            module_id: ID of the module to soft delete

        Returns:
            True if successful, False otherwise
        """
        try:
            with self.connection.transaction() as conn:
                cursor = conn.execute("""
                    UPDATE modules
                    SET is_active = 0
                    WHERE id = ?
                """, (module_id,))

                if cursor.rowcount > 0:
                    log_database_operation("UPDATE", "modules", module_id)
                    self.logger.info(f"Soft deleted module {module_id}")
                    return True
                else:
                    self.logger.warning(f"No module found with id {module_id}")
                    return False

        except Exception as e:
            self.logger.error(f"Error soft deleting module {module_id}: {e}", exc_info=True)
            return False

    def restore_module(self, module_id: int) -> bool:
        """
        Restore a soft-deleted module (sets is_active = 1).

        Args:
            module_id: ID of the module to restore

        Returns:
            True if successful, False otherwise
        """
        try:
            with self.connection.transaction() as conn:
                cursor = conn.execute("""
                    UPDATE modules
                    SET is_active = 1
                    WHERE id = ?
                """, (module_id,))

                if cursor.rowcount > 0:
                    log_database_operation("UPDATE", "modules", module_id)
                    self.logger.info(f"Restored module {module_id}")
                    return True
                else:
                    self.logger.warning(f"No module found with id {module_id}")
                    return False

        except Exception as e:
            self.logger.error(f"Error restoring module {module_id}: {e}", exc_info=True)
            return False

    def get_module_statistics(self, module_id: int) -> Optional[Dict[str, Any]]:
        """
        Get statistics for a module.

        Args:
            module_id: ID of the module

        Returns:
            Dictionary with module statistics or None if module not found
        """
        try:
            with self.connection.transaction() as conn:
                # Get module info
                module_row = conn.execute("SELECT * FROM modules WHERE id = ?", (module_id,)).fetchone()
                if not module_row:
                    return None

                module = dict(module_row)

                # Count documents
                doc_count = conn.execute(
                    "SELECT COUNT(*) as count FROM documents WHERE module_id = ?",
                    (module_id,)
                ).fetchone()['count']

                # Count images
                img_count = conn.execute(
                    "SELECT COUNT(*) as count FROM images WHERE module_id = ?",
                    (module_id,)
                ).fetchone()['count']

                # Count sessions
                session_count = conn.execute(
                    "SELECT COUNT(*) as count FROM game_sessions WHERE module_id = ?",
                    (module_id,)
                ).fetchone()['count']

                # Get database file size
                db_path = Path(module.get('database_path', ''))
                db_size = db_path.stat().st_size if db_path.exists() else 0

                return {
                    **module,
                    'document_count': doc_count,
                    'image_count': img_count,
                    'session_count': session_count,
                    'database_size': db_size
                }

        except Exception as e:
            self.logger.error(f"Error getting statistics for module {module_id}: {e}", exc_info=True)
            return None

    def get_inactive_modules(self) -> List[Dict[str, Any]]:
        """
        Get all inactive (soft-deleted) modules with statistics in a single optimized query.

        Returns:
            List of inactive module dictionaries with statistics
        """
        try:
            with self.connection.transaction() as conn:
                # Single query using LEFT JOINs and GROUP BY for optimal performance
                cursor = conn.execute("""
                    SELECT
                        m.*,
                        COUNT(DISTINCT d.id) as document_count,
                        COUNT(DISTINCT i.id) as image_count,
                        COUNT(DISTINCT s.id) as session_count
                    FROM modules m
                    LEFT JOIN documents d ON d.module_id = m.id
                    LEFT JOIN images i ON i.module_id = m.id
                    LEFT JOIN game_sessions s ON s.module_id = m.id
                    WHERE m.is_active = 0
                    GROUP BY m.id
                    ORDER BY m.created_date DESC
                """)

                modules = []
                for row in cursor.fetchall():
                    module = dict(row)

                    # Get database file size (can't be done in SQL)
                    db_path_str = module.get('database_path', '')
                    if db_path_str:
                        db_path = Path(db_path_str)
                        module['database_size'] = db_path.stat().st_size if db_path.exists() else 0
                    else:
                        module['database_size'] = 0

                    modules.append(module)

                self.logger.info(f"Loaded {len(modules)} inactive modules with statistics")
                return modules

        except Exception as e:
            self.logger.error(f"Error getting inactive modules: {e}", exc_info=True)
            return []

    def hard_delete_module(self, module_id: int, delete_files: bool = False) -> bool:
        """
        Hard delete a module (permanently removes from database).
        Optionally deletes associated database file.

        Args:
            module_id: ID of the module to delete
            delete_files: If True, also delete the database file

        Returns:
            True if successful, False otherwise
        """
        try:
            # Get module info before deleting
            module = self.get_module(module_id)
            if not module:
                self.logger.warning(f"No module found with id {module_id}")
                return False

            db_path = module.get('database_path', '')

            with self.connection.transaction() as conn:
                # Delete module (CASCADE will delete related documents, images, sessions)
                cursor = conn.execute("DELETE FROM modules WHERE id = ?", (module_id,))
                deleted = cursor.rowcount > 0

            if not deleted:
                return False

            log_database_operation("DELETE", "modules", module_id)
            self.logger.info(f"Hard deleted module {module_id}")

            # Delete files only after the DB change is committed, and only
            # inside the application data directory.
            if delete_files and db_path:
                try:
                    data_dir = get_data_dir().resolve()
                    db_file = Path(db_path).resolve()
                    main_db = Path(self.db_path).resolve() if self.db_path != ":memory:" else None
                    if db_file == main_db:
                        self.logger.warning("Refusing to delete the main application database")
                    elif data_dir in db_file.parents:
                        for suffix in ('', '-wal', '-shm'):
                            f = Path(str(db_file) + suffix)
                            if f.exists():
                                f.unlink()
                        self.logger.info(f"Deleted database file: {db_path}")
                    else:
                        self.logger.warning(f"Refusing to delete file outside data dir: {db_path}")
                except Exception as e:
                    self.logger.error(f"Error deleting database file {db_path}: {e}")

            return True

        except Exception as e:
            self.logger.error(f"Error hard deleting module {module_id}: {e}", exc_info=True)
            return False

    # Template management methods
    def get_templates(self, entity_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get all templates or templates for a specific entity type."""
        with self.connection.transaction() as conn:
            if entity_type:
                self.logger.debug(f"Getting templates for entity_type: {entity_type}")
                cursor = conn.execute("""
                    SELECT * FROM document_templates
                    WHERE entity_type = ?
                    ORDER BY is_default DESC, template_name
                """, (entity_type,))
            else:
                self.logger.debug("Getting all templates")
                cursor = conn.execute("""
                    SELECT * FROM document_templates
                    ORDER BY entity_type, is_default DESC, template_name
                """)

            results = cursor.fetchall()
            self.logger.debug(f"Database query returned {len(results)} template records")

            return [dict(row) for row in results]

    def get_default_template(self, entity_type: str) -> Optional[Dict[str, Any]]:
        """Get the default template for an entity type."""
        with self.connection.transaction() as conn:
            cursor = conn.execute("""
                SELECT * FROM document_templates
                WHERE entity_type = ? AND is_default = 1
            """, (entity_type,))

            row = cursor.fetchone()
            return dict(row) if row else None

    def save_template(self, template_name: str, entity_type: str,
                      template_content: str, is_default: bool = False) -> int:
        """Save or update a document template."""
        # Import security utilities
        from utils.text_utils import TextUtils
        from utils.security_utils import get_security_validator

        # Validate template name
        name_validation = TextUtils.validate_entity_name(template_name, max_length=100)
        if not name_validation['valid']:
            raise ValueError(f"Invalid template name: {', '.join(name_validation['issues'])}")

        # Validate entity type
        entity_validation = TextUtils.validate_entity_name(entity_type, max_length=50)
        if not entity_validation['valid']:
            raise ValueError(f"Invalid entity type: {', '.join(entity_validation['issues'])}")

        # Validate template content
        content_validation = get_security_validator().validate_text_content(template_content)
        if not content_validation['valid']:
            raise ValueError(f"Invalid template content: {', '.join(content_validation['issues'])}")

        with self.connection.transaction() as conn:
            # If setting as default, remove default flag from other templates of same type
            if is_default:
                conn.execute("""
                    UPDATE document_templates
                    SET is_default = 0
                    WHERE entity_type = ?
                """, (entity_type,))

            # Real upsert: keeps the row id and never silently clears an existing default flag
            conn.execute("""
                INSERT INTO document_templates
                (template_name, entity_type, template_content, is_default, modified_date)
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(entity_type, template_name) DO UPDATE SET
                    template_content = excluded.template_content,
                    is_default = CASE WHEN excluded.is_default = 1 THEN 1 ELSE is_default END,
                    modified_date = CURRENT_TIMESTAMP
            """, (template_name, entity_type, template_content, int(bool(is_default))))

            row = conn.execute(
                "SELECT id FROM document_templates WHERE entity_type = ? AND template_name = ?",
                (entity_type, template_name)
            ).fetchone()
            return row[0]

    # Document management methods
    def create_document(self, module_id: int, entity_type: str, title: str,
                        content: str, created_by: str = "user",
                        status: str = "draft", metadata: Optional[str] = None) -> int:
        """Create a new document."""
        # Import security utilities
        from utils.text_utils import TextUtils
        from utils.security_utils import get_security_validator

        # Validate inputs
        validator = get_security_validator()

        # Validate entity type
        entity_validation = TextUtils.validate_entity_name(entity_type, max_length=50)
        if not entity_validation['valid']:
            raise ValueError(f"Invalid entity type: {', '.join(entity_validation['issues'])}")

        # Validate title
        title_validation = TextUtils.validate_entity_name(title, max_length=255)
        if not title_validation['valid']:
            raise ValueError(f"Invalid title: {', '.join(title_validation['issues'])}")

        # Validate content
        content_validation = validator.validate_text_content(content)
        if not content_validation['valid']:
            raise ValueError(f"Invalid content: {', '.join(content_validation['issues'])}")

        # Validate metadata if provided
        if metadata:
            metadata_validation = validator.validate_json_input(metadata)
            if not metadata_validation['valid']:
                raise ValueError(f"Invalid metadata: {', '.join(metadata_validation['issues'])}")

        with self.connection.transaction() as conn:
            cursor = conn.execute("""
                INSERT INTO documents (module_id, entity_type, title, content, metadata, created_by, status)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (module_id, entity_type, title, content, metadata, created_by, status))

            log_database_operation("INSERT", "documents", cursor.lastrowid)
            return cursor.lastrowid

    def get_documents(self, module_id: Optional[int] = None,
                      entity_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get documents with optional filtering."""
        with self.connection.transaction() as conn:
            query = "SELECT * FROM documents WHERE 1=1"
            params = []

            if module_id is not None:
                query += " AND module_id = ?"
                params.append(module_id)

            if entity_type is not None:
                query += " AND entity_type = ?"
                params.append(entity_type)

            query += " ORDER BY modified_date DESC"

            cursor = conn.execute(query, params)
            results = cursor.fetchall()

            self.logger.debug(f"Query found {len(results)} documents")

            return [dict(row) for row in results]

    def get_document_summaries(self, module_id: int) -> List[Dict[str, Any]]:
        """Documents of a module without their text, newest first: enough for overviews and cheap on big campaigns."""
        with self.connection.transaction() as conn:
            cursor = conn.execute("""
                SELECT id, module_id, entity_type, title, metadata, created_date, modified_date, status
                FROM documents WHERE module_id = ? ORDER BY modified_date DESC
            """, (module_id,))
            return [dict(row) for row in cursor.fetchall()]

    def get_document(self, document_id: int) -> Optional[Dict[str, Any]]:
        """Get a specific document by ID."""
        with self.connection.transaction() as conn:
            cursor = conn.execute("SELECT * FROM documents WHERE id = ?", (document_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    HISTORY_KEEP = 20       # earlier versions kept per entry

    def update_document(self, document_id: int, title: str, content: str,
                          metadata: Optional[str] = None, record_history: bool = True) -> bool:
        """Update an existing document. The text it had before is kept as an earlier version (see get_document_versions)."""
        # Import security utilities
        from utils.text_utils import TextUtils
        from utils.security_utils import get_security_validator

        # Validate document_id
        if not isinstance(document_id, int) or document_id <= 0:
            raise ValueError(f"Invalid document_id: must be a positive integer, got {document_id}")

        # Validate inputs
        validator = get_security_validator()

        # Validate title
        title_validation = TextUtils.validate_entity_name(title, max_length=255)
        if not title_validation['valid']:
            raise ValueError(f"Invalid title: {', '.join(title_validation['issues'])}")

        # Validate content
        content_validation = validator.validate_text_content(content)
        if not content_validation['valid']:
            raise ValueError(f"Invalid content: {', '.join(content_validation['issues'])}")

        # Validate metadata if provided
        if metadata:
            metadata_validation = validator.validate_json_input(metadata)
            if not metadata_validation['valid']:
                raise ValueError(f"Invalid metadata: {', '.join(metadata_validation['issues'])}")

        self.logger.debug(f"Updating document {document_id}: title='{title}', content_length={len(content)}")
        with self.connection.transaction() as conn:
            if record_history:
                before = conn.execute("SELECT title, content FROM documents WHERE id = ?", (document_id,)).fetchone()
                if before is not None and (before[0] != title or (before[1] or '') != (content or '')) and (before[1] or '').strip():
                    conn.execute("INSERT INTO document_versions (document_id, title, content) VALUES (?, ?, ?)",
                                 (document_id, before[0], before[1]))
                    conn.execute("""
                        DELETE FROM document_versions WHERE document_id = ? AND id NOT IN (
                            SELECT id FROM document_versions WHERE document_id = ? ORDER BY id DESC LIMIT ?)
                    """, (document_id, document_id, self.HISTORY_KEEP))
            cursor = conn.execute("""
                UPDATE documents
                SET title = ?, content = ?, metadata = COALESCE(?, metadata),
                    modified_date = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (title, content, metadata, document_id))

            success = cursor.rowcount > 0
            self.logger.debug(f"Update affected {cursor.rowcount} rows, success: {success}")
            if success:
                log_database_operation("UPDATE", "documents", document_id)

            return success

    def delete_document(self, document_id: int) -> bool:
        """Delete a document."""
        self.logger.info(f"Starting document deletion - ID: {document_id}")

        try:
            with self.connection.transaction() as conn:
                self.logger.debug(f"Executing DELETE query for document ID: {document_id}")

                # First, check if document exists and log its details
                cursor = conn.execute("SELECT id, title, entity_type FROM documents WHERE id = ?", (document_id,))
                existing_doc = cursor.fetchone()

                if existing_doc:
                    self.logger.info(f"Found document to delete: {dict(existing_doc)}")
                else:
                    self.logger.warning(f"Document with ID {document_id} not found")
                    return False

                # Check for related records that might be affected
                related_counts = {}

                # Check relationships
                try:
                    cursor = conn.execute("SELECT COUNT(*) as count FROM document_relationships WHERE from_document_id = ? OR to_document_id = ?", (document_id, document_id))
                    rel_count = cursor.fetchone()
                    related_counts['relationships'] = rel_count['count'] if rel_count else 0
                except Exception as e:
                    self.logger.warning(f"Could not check relationships: {e}")

                # Check images
                try:
                    cursor = conn.execute("SELECT COUNT(*) as count FROM images WHERE document_id = ?", (document_id,))
                    img_count = cursor.fetchone()
                    related_counts['images'] = img_count['count'] if img_count else 0
                except Exception as e:
                    self.logger.warning(f"Could not check images: {e}")

                self.logger.info(f"Related records for document {document_id}: {related_counts}")

                # Delete the document (foreign key constraints will handle related records)
                cursor = conn.execute("DELETE FROM documents WHERE id = ?", (document_id,))
                success = cursor.rowcount > 0

                if success:
                    self.logger.info(f"Successfully deleted document {document_id}")
                    log_database_operation("DELETE", "documents", document_id)
                    # Log that related records should be cleaned up by foreign key constraints
                    self.logger.debug(f"Foreign key constraints should handle cleanup of {related_counts}")
                else:
                    self.logger.error(f"DELETE query affected 0 rows for document ID: {document_id}")

                return success

        except Exception as e:
            self.logger.error(f"Error during document deletion (ID: {document_id}): {e}", exc_info=True)
            raise

    def create_session(self, module_id: int, session_date: str, title: str,
                       content: str, participants: Optional[List[str]] = None,
                       duration_minutes: Optional[int] = None) -> int:
        """Create a new game session."""
        # Import security utilities
        from utils.text_utils import TextUtils
        from utils.security_utils import get_security_validator

        # Validate title
        title_validation = TextUtils.validate_entity_name(title, max_length=255)
        if not title_validation['valid']:
            raise ValueError(f"Invalid session title: {', '.join(title_validation['issues'])}")

        # Validate content
        content_validation = get_security_validator().validate_text_content(content)
        if not content_validation['valid']:
            raise ValueError(f"Invalid session content: {', '.join(content_validation['issues'])}")

        # Validate participants if provided
        if participants:
            for participant in participants:
                part_validation = TextUtils.validate_entity_name(participant, max_length=100)
                if not part_validation['valid']:
                    raise ValueError(f"Invalid participant name '{participant}': {', '.join(part_validation['issues'])}")

        # Validate duration
        if duration_minutes is not None and (duration_minutes < 0 or duration_minutes > 1440):  # Max 24 hours
            raise ValueError("Invalid duration: must be between 0 and 1440 minutes")

        participants_json = json.dumps(participants or [])

        with self.connection.transaction() as conn:
            cursor = conn.execute("""
                INSERT INTO game_sessions (module_id, session_date, title, content, participants, duration_minutes)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (module_id, session_date, title, content, participants_json, duration_minutes))

            log_database_operation("INSERT", "game_sessions", cursor.lastrowid)
            return cursor.lastrowid

    def get_sessions(self, module_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """Get game sessions."""
        with self.connection.transaction() as conn:
            if module_id:
                cursor = conn.execute("""
                    SELECT * FROM game_sessions
                    WHERE module_id = ?
                    ORDER BY session_date DESC
                """, (module_id,))
            else:
                cursor = conn.execute("""
                    SELECT * FROM game_sessions
                    ORDER BY session_date DESC
                """)

            return [dict(row) for row in cursor.fetchall()]

    def get_document_relationships(self, module_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Get document relationships for a module or all relationships.

        Args:
            module_id: Optional module ID to filter by

        Returns:
            List of relationship dictionaries
        """
        with self.connection.transaction() as conn:
            if module_id:
                # Get relationships for documents in this module
                cursor = conn.execute("""
                    SELECT dr.* FROM document_relationships dr
                    INNER JOIN documents d ON dr.from_document_id = d.id
                    WHERE d.module_id = ?
                    ORDER BY dr.created_date DESC
                """, (module_id,))
            else:
                cursor = conn.execute("""
                    SELECT * FROM document_relationships
                    ORDER BY created_date DESC
                """)

            return [dict(row) for row in cursor.fetchall()]

    def get_relationships_for_document(self, document_id: int) -> List[Dict[str, Any]]:
        """
        All relationships touching a document, in both directions.

        Each row has ``direction`` ('out' when the document is the source, 'in' when it is the
        target), the relationship_type, and the other document's id, title and entity_type.
        """
        with self.connection.transaction() as conn:
            cursor = conn.execute("""
                SELECT 'out' AS direction, dr.relationship_type, dr.description,
                       d.id AS other_id, d.title AS other_title, d.entity_type AS other_type
                FROM document_relationships dr
                JOIN documents d ON d.id = dr.to_document_id
                WHERE dr.from_document_id = ?
                UNION ALL
                SELECT 'in' AS direction, dr.relationship_type, dr.description,
                       d.id, d.title, d.entity_type
                FROM document_relationships dr
                JOIN documents d ON d.id = dr.from_document_id
                WHERE dr.to_document_id = ?
                ORDER BY 2, 5
            """, (document_id, document_id))
            return [dict(row) for row in cursor.fetchall()]

    def create_document_relationship(self, from_document_id: int, to_document_id: int,
                                     relationship_type: str, description: Optional[str] = None) -> int:
        """
        Create a relationship between two documents.

        Args:
            from_document_id: Source document ID
            to_document_id: Target document ID
            relationship_type: Type of relationship (e.g., "ally", "enemy", "located_in", "owns")
            description: Optional description of the relationship

        Returns:
            ID of created relationship

        Raises:
            ValueError: If validation fails
        """
        # Validate relationship type
        if not relationship_type or len(relationship_type) > 50:
            raise ValueError("Invalid relationship type")

        with self.connection.transaction() as conn:
            cursor = conn.execute("""
                INSERT INTO document_relationships
                (from_document_id, to_document_id, relationship_type, description)
                VALUES (?, ?, ?, ?)
            """, (from_document_id, to_document_id, relationship_type, description))

            log_database_operation("INSERT", "document_relationships", cursor.lastrowid)
            return cursor.lastrowid

    def get_document_versions(self, document_id: int) -> List[Dict[str, Any]]:
        """Earlier versions of an entry, newest first (id, title, content, saved_date)."""
        with self.connection.transaction() as conn:
            cursor = conn.execute("""
                SELECT id, document_id, title, content, saved_date FROM document_versions
                WHERE document_id = ? ORDER BY id DESC
            """, (document_id,))
            return [dict(row) for row in cursor.fetchall()]

    # --- adventure modules: which entries belong to which module (relationship 'belongs_to_module') -----------

    def get_module_links(self, campaign_id: int) -> Dict[int, List[int]]:
        """For every entry of a campaign: the ids of the module documents it belongs to (entries with none are absent)."""
        with self.connection.transaction() as conn:
            cursor = conn.execute("""
                SELECT dr.from_document_id, dr.to_document_id
                FROM document_relationships dr
                JOIN documents d ON d.id = dr.from_document_id
                WHERE dr.relationship_type = 'belongs_to_module' AND d.module_id = ?
            """, (campaign_id,))
            links: Dict[int, List[int]] = {}
            for row in cursor.fetchall():
                links.setdefault(row[0], []).append(row[1])
            return links

    def set_module_membership(self, document_ids: List[int], module_doc_id: int, member: bool) -> int:
        """Add the entries to a module (member=True) or remove them from it. Returns how many entries changed."""
        changed = 0
        with self.connection.transaction() as conn:
            for document_id in document_ids:
                if document_id == module_doc_id:
                    continue
                if member:
                    cursor = conn.execute("""
                        INSERT OR IGNORE INTO document_relationships
                        (from_document_id, to_document_id, relationship_type) VALUES (?, ?, 'belongs_to_module')
                    """, (document_id, module_doc_id))
                else:
                    cursor = conn.execute("""
                        DELETE FROM document_relationships
                        WHERE from_document_id = ? AND to_document_id = ? AND relationship_type = 'belongs_to_module'
                    """, (document_id, module_doc_id))
                changed += cursor.rowcount if cursor.rowcount > 0 else 0
        return changed

    def set_document_modules(self, document_id: int, module_doc_ids: List[int]) -> None:
        """Make an entry belong to exactly these modules."""
        wanted = {int(m) for m in module_doc_ids if int(m) != document_id}
        with self.connection.transaction() as conn:
            current = {row[0] for row in conn.execute("""
                SELECT to_document_id FROM document_relationships
                WHERE from_document_id = ? AND relationship_type = 'belongs_to_module'
            """, (document_id,)).fetchall()}
            for module_doc_id in current - wanted:
                conn.execute("""
                    DELETE FROM document_relationships
                    WHERE from_document_id = ? AND to_document_id = ? AND relationship_type = 'belongs_to_module'
                """, (document_id, module_doc_id))
            for module_doc_id in wanted - current:
                conn.execute("""
                    INSERT OR IGNORE INTO document_relationships
                    (from_document_id, to_document_id, relationship_type) VALUES (?, ?, 'belongs_to_module')
                """, (document_id, module_doc_id))

    def set_documents_faction(self, document_ids: List[int], faction_id: Optional[int]) -> int:
        """Give several entries the same faction (None clears it). Other metadata is kept. Returns how many changed."""
        changed = 0
        with self.connection.transaction() as conn:
            for document_id in document_ids:
                row = conn.execute("SELECT metadata FROM documents WHERE id = ?", (document_id,)).fetchone()
                if row is None:
                    continue
                try:
                    metadata = json.loads(row[0]) if row[0] else {}
                    if not isinstance(metadata, dict):
                        metadata = {}
                except (TypeError, ValueError):
                    metadata = {}
                if faction_id is None:
                    metadata.pop('faction_id', None)
                else:
                    metadata['faction_id'] = faction_id
                conn.execute("UPDATE documents SET metadata = ?, modified_date = CURRENT_TIMESTAMP WHERE id = ?",
                             (json.dumps(metadata), document_id))
                changed += 1
        return changed

    def check_database_integrity(self) -> Dict[str, Any]:
        """Check database integrity and return status."""
        self.logger.info("Checking database integrity...")

        integrity_results = {
            'database_path': self.db_path,
            'is_connected': self.connection.is_connected(),
            'integrity_check': None,
            'foreign_key_check': None,
            'pragma_info': {},
            'errors': []
        }

        try:
            with self.connection.transaction() as conn:
                # Basic integrity check
                self.logger.debug("Running PRAGMA integrity_check")
                try:
                    cursor = conn.execute("PRAGMA integrity_check")
                    integrity_result = cursor.fetchone()
                    integrity_results['integrity_check'] = integrity_result[0] if integrity_result else None

                    if integrity_result and integrity_result[0] != 'ok':
                        integrity_results['errors'].append(f"Integrity check failed: {integrity_result[0]}")
                        self.logger.error(f"Database integrity check failed: {integrity_result[0]}")
                except sqlite3.DatabaseError as e:
                    # Severe corruption - can't even run integrity check
                    error_msg = f"Cannot run integrity check (severe corruption): {e}"
                    integrity_results['errors'].append(error_msg)
                    integrity_results['integrity_check'] = 'FAILED'
                    integrity_results['is_healthy'] = False
                    self.logger.error(error_msg)
                    return integrity_results

                # Foreign key constraints check
                self.logger.debug("Running PRAGMA foreign_key_check")
                cursor = conn.execute("PRAGMA foreign_key_check")
                fk_results = cursor.fetchall()
                integrity_results['foreign_key_check'] = [dict(row) for row in fk_results]

                if fk_results:
                    integrity_results['errors'].append(f"Foreign key violations found: {len(fk_results)}")
                    self.logger.warning(f"Foreign key violations: {fk_results}")

                # Get database info
                pragma_checks = [
                    'PRAGMA page_size',
                    'PRAGMA page_count',
                    'PRAGMA freelist_count',
                    'PRAGMA schema_version',
                    'PRAGMA user_version',
                ]
                # reuse the result above instead of running the (slow) check a second time
                integrity_results['pragma_info']['PRAGMA integrity_check'] = integrity_results['integrity_check']

                for pragma in pragma_checks:
                    try:
                        cursor = conn.execute(pragma)
                        result = cursor.fetchone()
                        integrity_results['pragma_info'][pragma] = result[0] if result else None
                    except Exception as e:
                        integrity_results['pragma_info'][pragma] = f"Error: {e}"
                        self.logger.warning(f"Could not get {pragma}: {e}")

                # Overall status
                integrity_results['is_healthy'] = len(integrity_results['errors']) == 0

                if integrity_results['is_healthy']:
                    self.logger.info("Database integrity check passed")
                else:
                    self.logger.error(f"Database integrity check failed with {len(integrity_results['errors'])} errors")

                return integrity_results

        except sqlite3.DatabaseError as e:
            # Handle transaction-level corruption
            error_msg = f"Database corruption detected: {e}"
            integrity_results['errors'].append(error_msg)
            integrity_results['is_healthy'] = False
            self.logger.error(error_msg, exc_info=True)
            return integrity_results
        except Exception as e:
            error_msg = f"Database integrity check failed: {e}"
            integrity_results['errors'].append(error_msg)
            integrity_results['is_healthy'] = False
            self.logger.error(error_msg, exc_info=True)
            return integrity_results

    def repair_database(self) -> Dict[str, Any]:
        """Attempt to repair database corruption."""
        self.logger.warning("Attempting database repair...")

        repair_results = {
            'success': False,
            'actions_taken': [],
            'errors': []
        }

        try:
            # First check current state
            integrity_results = self.check_database_integrity()

            if integrity_results['is_healthy']:
                self.logger.info("Database is already healthy, no repair needed")
                repair_results['success'] = True
                return repair_results

            # Try VACUUM to rebuild database
            self.logger.info("Running VACUUM to rebuild database...")
            try:
                with self.connection.transaction() as conn:
                    conn.execute("VACUUM")
                    repair_results['actions_taken'].append("Database vacuumed")
                    self.logger.info("Database vacuumed successfully")
            except Exception as e:
                error_msg = f"VACUUM failed: {e}"
                repair_results['errors'].append(error_msg)
                self.logger.error(error_msg, exc_info=True)

            # Check if repair was successful
            final_integrity = self.check_database_integrity()
            if final_integrity['is_healthy']:
                repair_results['success'] = True
                self.logger.info("Database repair completed successfully")
            else:
                repair_results['errors'].extend(final_integrity['errors'])
                self.logger.error("Database repair failed")

            return repair_results

        except Exception as e:
            error_msg = f"Database repair failed: {e}"
            repair_results['errors'].append(error_msg)
            self.logger.error(error_msg, exc_info=True)
            return repair_results


    # Image management methods
    def save_image_record(self, module_id: int, document_id: Optional[int],
                         filename: str, original_name: str, file_path: str,
                         file_size: int, mime_type: str, description: Optional[str] = None) -> int:
        """
        Save image metadata to database.

        Args:
            module_id: ID of the module this image belongs to
            document_id: Optional ID of the document/entity this image is attached to
            filename: Unique filename (UUID-based)
            original_name: Original filename from user
            file_path: Full path to the image file
            file_size: Size of the file in bytes
            mime_type: MIME type of the image
            description: Optional description/caption for the image

        Returns:
            ID of the created image record
        """
        try:
            # Import security utilities
            from utils.text_utils import TextUtils
            from utils.security_utils import get_security_validator

            # Validate filename
            filename_validation = TextUtils.validate_entity_name(filename, max_length=255)
            if not filename_validation['valid']:
                raise ValueError(f"Invalid filename: {', '.join(filename_validation['issues'])}")

            # Validate original name
            original_validation = TextUtils.validate_entity_name(original_name, max_length=255)
            if not original_validation['valid']:
                raise ValueError(f"Invalid original name: {', '.join(original_validation['issues'])}")

            # Validate file path
            allowed_image_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.webp']
            path_validation = TextUtils.validate_file_path(file_path, allowed_extensions=allowed_image_extensions, allow_absolute=True)
            if not path_validation['valid']:
                raise ValueError(f"Invalid file path: {', '.join(path_validation['issues'])}")

            # Validate description if provided
            if description:
                desc_validation = get_security_validator().validate_text_content(description)
                if not desc_validation['valid']:
                    raise ValueError(f"Invalid description: {', '.join(desc_validation['issues'])}")

            # Validate file size (reasonable limits)
            if file_size < 0 or file_size > 50 * 1024 * 1024:  # 50MB max
                raise ValueError("Invalid file size")

            # Validate MIME type
            allowed_mime_types = ['image/jpeg', 'image/png', 'image/gif', 'image/bmp', 'image/tiff', 'image/webp']
            if mime_type not in allowed_mime_types:
                raise ValueError(f"Invalid MIME type: {mime_type}")

            with self.connection.transaction() as conn:
                cursor = conn.execute("""
                    INSERT INTO images (module_id, document_id, filename, original_name,
                                      file_path, file_size, mime_type, description)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (module_id, document_id, filename, original_name, file_path,
                      file_size, mime_type, description))

                image_id = cursor.lastrowid
                self.logger.info(f"Saved image record: {filename} (ID: {image_id})")
                log_database_operation("INSERT", "images", image_id)
                return image_id

        except Exception as e:
            self.logger.error(f"Failed to save image record: {e}", exc_info=True)
            raise

    def get_document_images(self, document_id: int) -> List[Dict[str, Any]]:
        """
        Get all images for a specific document.

        Args:
            document_id: ID of the document

        Returns:
            List of image records as dictionaries
        """
        try:
            with self.connection.transaction() as conn:
                cursor = conn.execute("""
                    SELECT id, module_id, document_id, filename, original_name,
                           file_path, file_size, mime_type, description, is_primary, uploaded_date
                    FROM images
                    WHERE document_id = ?
                    ORDER BY uploaded_date ASC
                """, (document_id,))

                images = []
                for row in cursor.fetchall():
                    images.append({
                        'id': row['id'],
                        'module_id': row['module_id'],
                        'document_id': row['document_id'],
                        'filename': row['filename'],
                        'original_name': row['original_name'],
                        'file_path': row['file_path'],
                        'file_size': row['file_size'],
                        'mime_type': row['mime_type'],
                        'description': row['description'],
                        'is_primary': row['is_primary'],
                        'uploaded_date': row['uploaded_date']
                    })

                return images

        except Exception as e:
            self.logger.error(f"Failed to get document images: {e}", exc_info=True)
            return []

    def update_image_description(self, image_id: int, description: str) -> bool:
        """
        Update the description/caption for an image.

        Args:
            image_id: ID of the image
            description: New description text

        Returns:
            True if successful, False otherwise
        """
        try:
            # Import security utilities
            from utils.security_utils import get_security_validator

            # Validate description
            desc_validation = get_security_validator().validate_text_content(description)
            if not desc_validation['valid']:
                raise ValueError(f"Invalid description: {', '.join(desc_validation['issues'])}")

            with self.connection.transaction() as conn:
                cursor = conn.execute("""
                    UPDATE images
                    SET description = ?
                    WHERE id = ?
                """, (description, image_id))

                if cursor.rowcount == 0:
                    return False
                self.logger.info(f"Updated description for image {image_id}")
                log_database_operation("UPDATE", "images", image_id)
                return True

        except Exception as e:
            self.logger.error(f"Failed to update image description: {e}", exc_info=True)
            return False

    def delete_image_record(self, image_id: int) -> bool:
        """
        Delete an image record from the database.
        Note: This does not delete the physical file.

        Args:
            image_id: ID of the image to delete

        Returns:
            True if successful, False otherwise
        """
        try:
            with self.connection.transaction() as conn:
                cursor = conn.execute("DELETE FROM images WHERE id = ?", (image_id,))

                if cursor.rowcount > 0:
                    self.logger.info(f"Deleted image record {image_id}")
                    log_database_operation("DELETE", "images", image_id)
                    return True
                else:
                    self.logger.warning(f"No image found with ID {image_id}")
                    return False

        except Exception as e:
            self.logger.error(f"Failed to delete image record: {e}", exc_info=True)
            return False

    def get_image_by_id(self, image_id: int) -> Optional[Dict[str, Any]]:
        """
        Get a single image record by ID.

        Args:
            image_id: ID of the image

        Returns:
            Image record as dictionary, or None if not found
        """
        try:
            with self.connection.transaction() as conn:
                cursor = conn.execute("""
                    SELECT id, module_id, document_id, filename, original_name,
                           file_path, file_size, mime_type, description, uploaded_date
                    FROM images
                    WHERE id = ?
                """, (image_id,))

                row = cursor.fetchone()
                if row:
                    return {
                        'id': row['id'],
                        'module_id': row['module_id'],
                        'document_id': row['document_id'],
                        'filename': row['filename'],
                        'original_name': row['original_name'],
                        'file_path': row['file_path'],
                        'file_size': row['file_size'],
                        'mime_type': row['mime_type'],
                        'description': row['description'],
                        'uploaded_date': row['uploaded_date']
                    }
                return None

        except Exception as e:
            self.logger.error(f"Failed to get image by ID: {e}", exc_info=True)
            return None

    def set_primary_image(self, document_id: int, image_id: int) -> bool:
        """
        Set an image as the primary image for a document.
        Clears any existing primary image for the document.

        Args:
            document_id: ID of the document
            image_id: ID of the image to set as primary

        Returns:
            True if successful, False otherwise
        """
        try:
            with self.connection.transaction() as conn:
                # First, clear all primary flags for this document
                conn.execute("""
                    UPDATE images
                    SET is_primary = 0
                    WHERE document_id = ?
                """, (document_id,))

                # Then set the specified image as primary
                cursor = conn.execute("""
                    UPDATE images
                    SET is_primary = 1
                    WHERE id = ? AND document_id = ?
                """, (image_id, document_id))

                if cursor.rowcount == 0:
                    # Roll back the cleared flags instead of committing a half-change
                    raise LookupError(f"No image {image_id} for document {document_id}")

                self.logger.info(f"Set image {image_id} as primary for document {document_id}")
                log_database_operation("UPDATE", "images", image_id)
                return True

        except LookupError as e:
            self.logger.warning(str(e))
            return False

        except Exception as e:
            self.logger.error(f"Failed to set primary image: {e}", exc_info=True)
            return False

    def get_primary_image(self, document_id: int) -> Optional[Dict[str, Any]]:
        """
        Get the primary image for a document.

        Args:
            document_id: ID of the document

        Returns:
            Image record as dictionary, or None if no primary image
        """
        try:
            with self.connection.transaction() as conn:
                cursor = conn.execute("""
                    SELECT id, module_id, document_id, filename, original_name,
                           file_path, file_size, mime_type, description, uploaded_date, is_primary
                    FROM images
                    WHERE document_id = ? AND is_primary = 1
                    LIMIT 1
                """, (document_id,))

                row = cursor.fetchone()
                if row:
                    return {
                        'id': row['id'],
                        'module_id': row['module_id'],
                        'document_id': row['document_id'],
                        'filename': row['filename'],
                        'original_name': row['original_name'],
                        'file_path': row['file_path'],
                        'file_size': row['file_size'],
                        'mime_type': row['mime_type'],
                        'description': row['description'],
                        'uploaded_date': row['uploaded_date'],
                        'is_primary': row['is_primary']
                    }
                return None

        except Exception as e:
            self.logger.error(f"Failed to get primary image: {e}", exc_info=True)
            return None

    def get_primary_images_for_documents(self, document_ids) -> Dict[int, Dict[str, Any]]:
        """
        Get the primary image of every given document in as few queries as possible.

        Used by the entity lists to show thumbnails without one query per row.

        Args:
            document_ids: IDs of the documents

        Returns:
            Dict of document ID -> image record; documents without a primary image are absent
        """
        ids = [int(doc_id) for doc_id in document_ids]
        result: Dict[int, Dict[str, Any]] = {}
        if not ids:
            return result

        try:
            with self.connection.transaction() as conn:
                for start in range(0, len(ids), 500):  # stay well below SQLite's variable limit
                    chunk = ids[start:start + 500]
                    marks = ",".join("?" * len(chunk))
                    cursor = conn.execute(f"""
                        SELECT id, module_id, document_id, filename, file_path
                        FROM images
                        WHERE is_primary = 1 AND document_id IN ({marks})
                    """, chunk)
                    for row in cursor.fetchall():
                        result[row['document_id']] = {
                            'id': row['id'],
                            'module_id': row['module_id'],
                            'document_id': row['document_id'],
                            'filename': row['filename'],
                            'file_path': row['file_path'],
                        }
        except Exception as e:
            self.logger.error(f"Failed to get primary images for documents: {e}", exc_info=True)

        return result

    def auto_set_primary_if_needed(self, document_id: int) -> bool:
        """
        Automatically set the first image as primary if no primary image exists.

        Args:
            document_id: ID of the document

        Returns:
            True if a primary was set, False otherwise
        """
        try:
            with self.connection.transaction() as conn:
                # Check if there's already a primary image
                cursor = conn.execute("""
                    SELECT id FROM images
                    WHERE document_id = ? AND is_primary = 1
                    LIMIT 1
                """, (document_id,))

                if cursor.fetchone():
                    # Primary already exists
                    return False

                # Get the first image (by upload date)
                cursor = conn.execute("""
                    SELECT id FROM images
                    WHERE document_id = ?
                    ORDER BY uploaded_date ASC
                    LIMIT 1
                """, (document_id,))

                row = cursor.fetchone()
                if row:
                    image_id = row['id']
                    # Set it as primary
                    conn.execute("""
                        UPDATE images
                        SET is_primary = 1
                        WHERE id = ?
                    """, (image_id,))
                    self.logger.info(f"Auto-set image {image_id} as primary for document {document_id}")
                    log_database_operation("UPDATE", "images", image_id)
                    return True

                return False

        except Exception as e:
            self.logger.error(f"Failed to auto-set primary image: {e}", exc_info=True)
            return False

    def close(self) -> None:
        """Close database connection."""
        self.connection.disconnect()