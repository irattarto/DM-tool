"""Database migration system for RPG Database Manager."""

import sqlite3
from utils.logger import get_logger
from typing import Callable, Dict
from datetime import datetime
from PyQt6.QtWidgets import QTextEdit, QApplication


class DatabaseMigration:
    """Manages database schema migrations."""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self.logger = get_logger('migrations')

        # Migration registry: version -> migration function
        self.migrations: Dict[int, Callable] = {
            5: self.migrate_to_v5_markdown_content,
            6: self.migrate_to_v6_image_columns,
            7: self.migrate_to_v7_fix_schema_inconsistencies,
            8: self.migrate_to_v8_entity_types,
            9: self.migrate_to_v9_discord_channel,
            10: self.migrate_to_v10_discord_guild,
            11: self.migrate_to_v11_document_versions
        }

    def get_current_version(self) -> int:
        """Get current database schema version."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            cursor.execute("SELECT MAX(version) FROM schema_version")
            version = cursor.fetchone()[0]
            return version if version else 0
        except sqlite3.OperationalError:
            return 0
        finally:
            conn.close()

    def migrate_to_version(self, target_version: int) -> bool:
        """Migrate database to target version."""
        current_version = self.get_current_version()

        if current_version >= target_version:
            self.logger.info(f"Database already at version {current_version}")
            return True

        self.logger.info(f"Migrating database from v{current_version} to v{target_version}")

        # One backup of the untouched database before anything is changed
        self._chain_backup = None
        try:
            backup = self.db_path + f".pre_v{current_version}_to_v{target_version}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
            self._backup_database(backup)
            self._chain_backup = backup
            self.logger.info(f"Created pre-migration backup {backup}")
        except Exception as e:
            self.logger.error(f"Could not create the pre-migration backup: {e}")
            return False  # never migrate without a safety copy

        try:
            return self._run_chain(current_version, target_version)
        finally:
            self._chain_backup = None

    def _run_chain(self, current_version: int, target_version: int) -> bool:
        """Run the migration steps in order (the pre-migration backup already exists)."""
        for version in range(current_version + 1, target_version + 1):
            if version not in self.migrations:
                self.logger.error(f"No migration defined for version {version}")
                return False

            self.logger.info(f"Running migration to v{version}...")
            try:
                self.migrations[version]()
                self._update_schema_version(version)

                # Validate migration completed successfully; an unvalidated step must not stay stamped
                if not self._validate_migration(version):
                    self.logger.error(f"Migration to v{version} validation failed")
                    self._update_schema_version(version - 1)
                    return False

                self.logger.info(f"Migration to v{version} completed and validated")
            except Exception as e:
                self.logger.error(f"Migration to v{version} failed: {e}", exc_info=True)
                return False

        return True

    def _validate_migration(self, version: int) -> bool:
        """Validate that migration was applied successfully."""
        try:
            # Verify the schema version was updated
            actual_version = self.get_current_version()
            if actual_version != version:
                self.logger.error(
                    f"Schema version mismatch after migration. "
                    f"Expected {version}, got {actual_version}"
                )
                return False

            # Run basic integrity check
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            try:
                cursor.execute("PRAGMA integrity_check")
                result = cursor.fetchone()
                if result[0] != "ok":
                    self.logger.error(f"Database integrity check failed: {result[0]}")
                    return False
            finally:
                conn.close()

            self.logger.debug(f"Migration v{version} validated successfully")
            return True

        except Exception as e:
            self.logger.error(f"Migration validation failed: {e}", exc_info=True)
            return False

    def _backup_database(self, backup_path: str) -> None:
        """WAL-safe backup using SQLite's online backup API.

        While a whole migration chain runs, one backup taken before the first step covers it, so the
        individual steps do not each write another full copy of the database.
        """
        if getattr(self, '_chain_backup', None):
            self.logger.info(f"Skipping step backup; the pre-migration backup is {self._chain_backup}")
            return
        src = sqlite3.connect(self.db_path)
        try:
            dst = sqlite3.connect(backup_path)
            try:
                src.backup(dst)
            finally:
                dst.close()
        finally:
            src.close()

    def _update_schema_version(self, version: int):
        """Update schema version in database."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            cursor.execute(
                "INSERT OR REPLACE INTO schema_version (version, applied_date) VALUES (?, CURRENT_TIMESTAMP)",
                (version,)
            )
            conn.commit()
        finally:
            conn.close()

    def migrate_to_v5_markdown_content(self):
        """
        Migration v4 → v5: Convert HTML content to Markdown.

        Changes:
        - Converts all document content from HTML to Markdown
        - Converts all game_session content from HTML to Markdown
        - Converts all document_template content from HTML to Markdown
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            # Create backup before migration
            backup_path = self.db_path + f".pre_v5_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
            self.logger.info(f"Creating backup at {backup_path}")
            self._backup_database(backup_path)

            # Migrate documents table
            self.logger.info("Migrating documents table...")
            cursor.execute("SELECT id, content FROM documents")
            documents = cursor.fetchall()

            converted_count = 0
            for doc_id, html_content in documents:
                if html_content:
                    markdown_content = self._convert_html_to_markdown(html_content)
                    cursor.execute(
                        "UPDATE documents SET content = ? WHERE id = ?",
                        (markdown_content, doc_id)
                    )
                    converted_count += 1

            self.logger.info(f"Migrated {converted_count} documents")

            # Migrate game_sessions table
            self.logger.info("Migrating game_sessions table...")
            cursor.execute("SELECT id, content FROM game_sessions")
            sessions = cursor.fetchall()

            converted_count = 0
            for session_id, html_content in sessions:
                if html_content:
                    markdown_content = self._convert_html_to_markdown(html_content)
                    cursor.execute(
                        "UPDATE game_sessions SET content = ? WHERE id = ?",
                        (markdown_content, session_id)
                    )
                    converted_count += 1

            self.logger.info(f"Migrated {converted_count} game sessions")

            # Migrate document_templates table
            self.logger.info("Migrating document_templates table...")
            cursor.execute("SELECT id, template_content FROM document_templates")
            templates = cursor.fetchall()

            converted_count = 0
            for template_id, html_content in templates:
                if html_content:
                    markdown_content = self._convert_html_to_markdown(html_content)
                    cursor.execute(
                        "UPDATE document_templates SET template_content = ? WHERE id = ?",
                        (markdown_content, template_id)
                    )
                    converted_count += 1

            self.logger.info(f"Migrated {converted_count} document templates")

            conn.commit()
            self.logger.info("Migration v5 completed successfully")
            self.logger.info(f"Backup saved to: {backup_path}")

        except Exception as e:
            conn.rollback()
            self.logger.error(f"Migration v5 failed: {e}")
            raise
        finally:
            conn.close()

    def migrate_to_v6_image_columns(self):
        """
        Migration v5 → v6: Add missing columns to images table.

        Changes:
        - Adds 'description' TEXT column to images table
        - Adds 'is_primary' BOOLEAN column to images table (default 0)
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            # Create backup before migration
            backup_path = self.db_path + f".pre_v6_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
            self.logger.info(f"Creating backup at {backup_path}")
            self._backup_database(backup_path)

            # Check if columns already exist
            cursor.execute("PRAGMA table_info(images)")
            columns = {row[1] for row in cursor.fetchall()}

            # Add description column if it doesn't exist
            if 'description' not in columns:
                self.logger.info("Adding 'description' column to images table...")
                cursor.execute("ALTER TABLE images ADD COLUMN description TEXT")
                self.logger.info("Added 'description' column")
            else:
                self.logger.info("Column 'description' already exists, skipping")

            # Add is_primary column if it doesn't exist
            if 'is_primary' not in columns:
                self.logger.info("Adding 'is_primary' column to images table...")
                cursor.execute("ALTER TABLE images ADD COLUMN is_primary BOOLEAN DEFAULT 0")
                self.logger.info("Added 'is_primary' column")
            else:
                self.logger.info("Column 'is_primary' already exists, skipping")

            conn.commit()
            self.logger.info("Migration v6 completed successfully")
            self.logger.info(f"Backup saved to: {backup_path}")

        except Exception as e:
            conn.rollback()
            self.logger.error(f"Migration v6 failed: {e}")
            raise
        finally:
            conn.close()

    def migrate_to_v7_fix_schema_inconsistencies(self):
        """
        Migration v6 → v7: Fix schema inconsistencies.

        Changes:
        - Adds 'status' TEXT column to game_sessions table (default 'planned')
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            # Create backup before migration
            backup_path = self.db_path + f".pre_v7_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
            self.logger.info(f"Creating backup at {backup_path}")
            self._backup_database(backup_path)

            # Check game_sessions columns
            cursor.execute("PRAGMA table_info(game_sessions)")
            game_sessions_cols = {row[1] for row in cursor.fetchall()}

            # Add status column to game_sessions if missing
            if 'status' not in game_sessions_cols:
                self.logger.info("Adding 'status' column to game_sessions table...")
                cursor.execute("ALTER TABLE game_sessions ADD COLUMN status TEXT DEFAULT 'planned'")
                self.logger.info("Added 'status' column to game_sessions")
            else:
                self.logger.info("Column 'status' already exists in game_sessions, skipping")

            # Note: We're NOT removing the legacy columns from documents table yet
            # (abilities, inventory, abilities_content, inventory_content)
            # These may contain data that needs to be migrated first

            conn.commit()
            self.logger.info("Migration v7 completed successfully")
            self.logger.info(f"Backup saved to: {backup_path}")

        except Exception as e:
            conn.rollback()
            self.logger.error(f"Migration v7 failed: {e}")
            raise
        finally:
            conn.close()

    def migrate_to_v8_entity_types(self):
        """
        Migration v7 → v8: entity type customisation.

        Changes:
        - Adds entity_types and app_meta tables
        - Backfills custom types found in existing documents so none become invisible
        - Marks default templates as already seeded (deleted ones must not come back)
        """
        from config.entity_types import builtin_keys, RESERVED_KEYS, is_valid_key

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            backup_path = self.db_path + f".pre_v8_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
            self.logger.info(f"Creating backup at {backup_path}")
            self._backup_database(backup_path)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS entity_types (
                    key TEXT PRIMARY KEY,
                    label_singular TEXT NOT NULL,
                    label_plural TEXT NOT NULL,
                    sort_order INTEGER NOT NULL DEFAULT 0,
                    hidden INTEGER NOT NULL DEFAULT 0,
                    builtin INTEGER NOT NULL DEFAULT 0
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS app_meta (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )
            """)

            known = set(builtin_keys()) | set(RESERVED_KEYS)
            cursor.execute("SELECT DISTINCT entity_type FROM documents WHERE entity_type IS NOT NULL")
            order = 1000
            for (key,) in cursor.fetchall():
                if key in known:
                    continue
                label = key.replace('_', ' ').title()
                cursor.execute(
                    "INSERT OR IGNORE INTO entity_types (key, label_singular, label_plural, sort_order, hidden, builtin) "
                    "VALUES (?, ?, ?, ?, 0, 0)",
                    (key, label, label + 's', order)
                )
                order += 1
                if not is_valid_key(key):
                    self.logger.warning(f"Legacy entity type '{key}' is not a valid slug; kept as is")

            cursor.execute("INSERT OR REPLACE INTO app_meta (key, value) VALUES ('templates_seeded', '1')")

            conn.commit()
            self.logger.info("Migration v8 completed successfully")

        except Exception as e:
            conn.rollback()
            self.logger.error(f"Migration v8 failed: {e}")
            raise
        finally:
            conn.close()

    def migrate_to_v9_discord_channel(self):
        """
        Migration v8 → v9: link modules to a Discord channel.

        Changes:
        - Adds discord_channel_id and discord_channel_name to modules (both nullable)
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            backup_path = self.db_path + f".pre_v9_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
            self.logger.info(f"Creating backup at {backup_path}")
            self._backup_database(backup_path)

            cursor.execute("PRAGMA table_info(modules)")
            columns = {row[1] for row in cursor.fetchall()}
            for column in ('discord_channel_id', 'discord_channel_name'):
                if column not in columns:
                    cursor.execute(f"ALTER TABLE modules ADD COLUMN {column} TEXT")

            conn.commit()
            self.logger.info("Migration v9 completed successfully")

        except Exception as e:
            conn.rollback()
            self.logger.error(f"Migration v9 failed: {e}")
            raise
        finally:
            conn.close()

    def migrate_to_v10_discord_guild(self):
        """
        Migration v9 → v10: Discord server per module.

        Changes:
        - Adds discord_guild_id and discord_guild_name to modules (both nullable)
        - Modules that already link a channel keep working: they get the server that was
          stored globally until now
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            cursor.execute("PRAGMA table_info(modules)")
            columns = {row[1] for row in cursor.fetchall()}
            for column in ('discord_guild_id', 'discord_guild_name'):
                if column not in columns:
                    cursor.execute(f"ALTER TABLE modules ADD COLUMN {column} TEXT")

            try:
                meta = dict(cursor.execute(
                    "SELECT key, value FROM app_meta WHERE key IN ('discord_guild_id', 'discord_guild_name')"
                ).fetchall())
            except sqlite3.OperationalError:  # no app_meta table: Discord was never set up
                meta = {}
            if meta.get('discord_guild_id'):
                cursor.execute(
                    "UPDATE modules SET discord_guild_id = ?, discord_guild_name = ? "
                    "WHERE discord_channel_id IS NOT NULL AND discord_guild_id IS NULL",
                    (meta['discord_guild_id'], meta.get('discord_guild_name')))

            conn.commit()
            self.logger.info("Migration v10 completed successfully")

        except Exception as e:
            conn.rollback()
            self.logger.error(f"Migration v10 failed: {e}")
            raise
        finally:
            conn.close()

    def migrate_to_v11_document_versions(self):
        """
        Migration v10 → v11: earlier versions of entries (History in the editor).

        Changes:
        - Adds the document_versions table (text only, the last 20 versions per entry)
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS document_versions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    document_id INTEGER NOT NULL,
                    title TEXT NOT NULL,
                    content TEXT,
                    saved_date DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (document_id) REFERENCES documents (id) ON DELETE CASCADE
                )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_versions_document ON document_versions(document_id)")
            conn.commit()
            self.logger.info("Migration v11 completed successfully")

        except Exception as e:
            conn.rollback()
            self.logger.error(f"Migration v11 failed: {e}")
            raise
        finally:
            conn.close()

    def _convert_html_to_markdown(self, html_content: str) -> str:
        """Convert HTML content to Markdown using Qt6."""
        if not html_content or not html_content.strip():
            return ""

        # Check if already Markdown (heuristic: no HTML tags)
        if '<' not in html_content:
            return html_content

        try:
            app = QApplication.instance()
            if app is None:
                # Fallback: strip HTML tags
                import re
                text = re.sub(r'<[^>]+>', '', html_content)
                return text.strip()

            # Use QTextEdit for conversion
            temp_editor = QTextEdit()
            temp_editor.setHtml(html_content)
            markdown = temp_editor.toMarkdown()
            temp_editor.deleteLater()

            return markdown.strip()
        except Exception as e:
            self.logger.warning(f"HTML to Markdown conversion failed: {e}")
            # Fallback: strip HTML tags
            import re
            text = re.sub(r'<[^>]+>', '', html_content)
            return text.strip()
