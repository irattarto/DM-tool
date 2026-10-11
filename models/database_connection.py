"""
Database connection manager with proper error handling and transactions.
"""

import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Optional

from utils.logger import get_logger



def _tolerant_date_converter(value: bytes):
    """DATE column converter that never fails a whole query on a malformed value.

    Valid ISO dates are returned as datetime.date (previous behaviour); anything
    else is returned as the raw text so one bad row cannot break get_sessions().
    """
    import datetime
    text = value.decode("utf-8", errors="replace")
    try:
        return datetime.date.fromisoformat(text[:10])
    except ValueError:
        return text


sqlite3.register_converter("DATE", _tolerant_date_converter)


class DatabaseConnection:
    """
    Database connection manager with proper error handling and transactions.
    """

    def __init__(self, db_path: str):
        """
        Initialize database connection.

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path
        self._connection: Optional[sqlite3.Connection] = None
        self._lock = threading.RLock()  # Add thread safety with reentrant lock
        self._depth = 0  # Nesting depth of transaction() on the shared connection
        self.logger = get_logger('database')

    def connect(self) -> sqlite3.Connection:
        """Create and return database connection."""
        with self._lock:
            if self._connection is None:
                # Ensure directory exists
                db_dir = Path(self.db_path).parent
                db_dir.mkdir(parents=True, exist_ok=True)

                # Create connection with proper settings
                self._connection = sqlite3.connect(
                    self.db_path,
                    detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES,
                    check_same_thread=False  # Allow GUI thread access with lock protection
                )

                try:
                    # Enable foreign keys
                    self._connection.execute("PRAGMA foreign_keys = ON")

                    # Optimize for database reliability and performance
                    self._connection.execute("PRAGMA synchronous = FULL")   # Flush every write to disk — prevents corruption on crash
                    self._connection.execute("PRAGMA journal_mode = WAL")   # Write-Ahead Logging for better concurrency
                    self._connection.execute("PRAGMA temp_store = MEMORY")  # Store temp tables in memory
                    self._connection.execute("PRAGMA mmap_size = 268435456") # 256MB memory map for better performance

                    # Merge any WAL file left over from a previous crash.
                    # In PASSIVE mode SQLite checkpoints as many frames as possible
                    # without blocking readers/writers, which is safe at startup.
                    self._connection.execute("PRAGMA wal_checkpoint(PASSIVE)")
                except Exception:
                    # Never keep a half-configured connection cached
                    self._connection.close()
                    self._connection = None
                    raise

                # Set row factory for named columns
                self._connection.row_factory = sqlite3.Row

                self.logger.info(f"Connected to database: {self.db_path}")

            return self._connection

    def checkpoint(self) -> None:
        """
        Force a full WAL checkpoint and truncate the WAL file.

        Call this before a clean shutdown to consolidate all WAL frames into
        the main database file.  TRUNCATE mode resets the WAL to zero bytes,
        so the next open starts with a clean slate even if the process is then
        killed before disconnect() is called.
        """
        with self._lock:
            if self._connection:
                try:
                    self._connection.execute("PRAGMA wal_checkpoint(TRUNCATE)")
                    self.logger.info("WAL checkpoint completed")
                except Exception as e:
                    self.logger.warning(f"WAL checkpoint failed (non-fatal): {e}")

    def disconnect(self) -> None:
        """Close database connection."""
        with self._lock:
            if self._connection:
                self.checkpoint()
                self._connection.close()
                self._connection = None
                self.logger.info("Disconnected from database")

    def is_connected(self) -> bool:
        """Check if database is connected."""
        return self._connection is not None

    @contextmanager
    def transaction(self):
        """
        Context manager for database transactions.

        Thread-safe transaction handling using lock to serialize database access.
        SQLite connections are not thread-safe even with check_same_thread=False,
        so we must serialize all operations.
        """
        # Acquire lock to ensure only one transaction at a time
        self._lock.acquire()
        transaction_acquired = True
        self._depth += 1
        outermost = self._depth == 1

        try:
            conn = self.connect()
            transaction_id = id(conn)  # Unique identifier for this transaction
            self.logger.debug(f"Starting transaction {transaction_id} (thread: {threading.current_thread().name})")

            try:
                # Note: SQLite automatically begins transactions, no explicit BEGIN needed
                self.logger.debug(f"Transaction {transaction_id} - yielding connection")
                yield conn
                # Nested use shares one connection: only the outermost block commits
                if outermost:
                    self.logger.debug(f"Transaction {transaction_id} - committing")
                    conn.commit()
                    self.logger.debug(f"Transaction {transaction_id} - committed successfully")
            except Exception as e:
                self.logger.error(f"Transaction {transaction_id} failed: {e}", exc_info=True)
                if outermost:
                    self.logger.debug(f"Transaction {transaction_id} - rolling back")
                    try:
                        conn.rollback()
                        self.logger.debug(f"Transaction {transaction_id} - rolled back successfully")
                    except Exception as rollback_error:
                        self.logger.error(f"Transaction {transaction_id} rollback also failed: {rollback_error}", exc_info=True)
                raise
            finally:
                # Connection remains open for reuse
                self.logger.debug(f"Transaction {transaction_id} - completed")
        finally:
            # Always release the lock
            self._depth -= 1
            if transaction_acquired:
                self._lock.release()
                self.logger.debug(f"Transaction lock released (thread: {threading.current_thread().name})")
