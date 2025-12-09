"""Database configuration and connection management.

Uses aiosqlite with connection pooling for optimal performance.
Following 2025 best practices for async SQLite operations.
"""

import asyncio
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator, Optional

import aiosqlite

from ..common.exceptions import (
    DatabaseException,
    JobNotFoundException,
    JobStateException,
    ValidationException
)

logger = logging.getLogger(__name__)

# SQLite configuration for concurrent access
SQLITE_PRAGMAS = [
    "PRAGMA journal_mode = WAL",          # Write-Ahead Logging for concurrency
    "PRAGMA busy_timeout = 5000",         # 5 second timeout for locks
    "PRAGMA synchronous = NORMAL",        # Balance safety/speed
    "PRAGMA cache_size = -64000",         # 64MB cache
    "PRAGMA foreign_keys = ON",           # Enable FK constraints
    "PRAGMA temp_store = MEMORY",         # Use memory for temp tables
]


class DatabasePool:
    """SQLite connection pool for async operations.

    Manages a pool of connections to avoid connection overhead
    and maintain hot caches for better performance.
    """

    def __init__(
        self,
        database_path: str,
        max_connections: int = 5,
        min_connections: int = 1
    ):
        self.database_path = Path(database_path)
        self.max_connections = max_connections
        self.min_connections = min_connections
        self._pool: list[aiosqlite.Connection] = []
        self._semaphore = asyncio.Semaphore(max_connections)
        self._lock = asyncio.Lock()
        self._closed = False

    async def initialize(self) -> None:
        """Initialize the connection pool and create schema."""
        try:
            logger.info(
                f"Initializing database: path={self.database_path}, "
                f"exists={self.database_path.exists()}, "
                f"parent_exists={self.database_path.parent.exists()}"
            )

            # Ensure database directory exists
            logger.info("Creating database directory if needed")
            try:
                self.database_path.parent.mkdir(parents=True, exist_ok=True)
                logger.info(f"Database directory ready: {self.database_path.parent}")
            except Exception as dir_error:
                logger.error(f"Failed to create database directory: {dir_error}")
                raise DatabaseException(
                    f"Cannot create database directory {self.database_path.parent}: {dir_error}"
                )

            # Create initial connections
            logger.info(f"Creating {self.min_connections} initial database connections")
            for i in range(self.min_connections):
                try:
                    conn = await self._create_connection()
                    self._pool.append(conn)
                    logger.debug(f"Created connection {i+1}/{self.min_connections}")
                except Exception as conn_error:
                    logger.error(f"Failed to create connection {i+1}: {conn_error}")
                    raise
            logger.info(f"Database connections initialized: {len(self._pool)} connections ready")

            # Create schema using first connection
            logger.info("Creating database schema")
            async with self.acquire() as conn:
                await self._create_schema(conn)
            logger.info("Database schema created/verified")

            logger.info(
                f"Database pool initialization complete: {len(self._pool)} connections "
                f"at {self.database_path}"
            )

        except Exception as e:
            logger.error(f"Failed to initialize database: {e}", exc_info=True)
            raise DatabaseException(f"Database initialization failed: {e}")

    async def _create_connection(self) -> aiosqlite.Connection:
        """Create a new database connection with optimized settings."""
        conn = await aiosqlite.connect(
            self.database_path,
            timeout=30.0,
            isolation_level=None  # Autocommit mode
        )

        # Apply performance pragmas
        for pragma in SQLITE_PRAGMAS:
            await conn.execute(pragma)

        # Enable row factory for dict-like access
        conn.row_factory = aiosqlite.Row

        return conn

    @asynccontextmanager
    async def acquire(self) -> AsyncGenerator[aiosqlite.Connection, None]:
        """Acquire a connection from the pool."""
        if self._closed:
            raise DatabaseException("Database pool is closed")

        async with self._semaphore:
            conn = None
            try:
                async with self._lock:
                    if self._pool:
                        conn = self._pool.pop()
                    elif len(self._pool) < self.max_connections:
                        conn = await self._create_connection()

                if conn is None:
                    # Wait for available connection
                    await asyncio.sleep(0.1)
                    async with self.acquire() as retry_conn:
                        yield retry_conn
                        return

                # Verify connection is still valid
                try:
                    await conn.execute("SELECT 1")
                except (aiosqlite.Error, AttributeError):
                    await conn.close()
                    conn = await self._create_connection()

                yield conn

            except Exception as e:
                if isinstance(e, (JobNotFoundException, JobStateException, ValidationException)):
                    raise
                logger.error(f"Connection error: {e}")
                raise DatabaseException(f"Failed to acquire connection: {e}")

            finally:
                if conn and not self._closed:
                    async with self._lock:
                        self._pool.append(conn)

    async def close(self) -> None:
        """Close all connections in the pool."""
        self._closed = True
        async with self._lock:
            for conn in self._pool:
                try:
                    await conn.close()
                except Exception as e:
                    logger.error(f"Error closing connection: {e}")
            self._pool.clear()
        logger.info("Database pool closed")

    async def _create_schema(self, conn: aiosqlite.Connection) -> None:
        """Create database schema if not exists."""
        schema = """
        CREATE TABLE IF NOT EXISTS jobs (
            id TEXT PRIMARY KEY,
            filename TEXT NOT NULL,
            file_size INTEGER NOT NULL,
            mime_type TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            pdf_path TEXT NOT NULL,
            msf_path TEXT,
            progress INTEGER DEFAULT 0,
            current_stage TEXT DEFAULT 'queued',
            error TEXT,
            metadata TEXT DEFAULT '{}',
            source_pages TEXT DEFAULT '[]',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            started_at TIMESTAMP,
            completed_at TIMESTAMP,
            output_formats TEXT DEFAULT '["msf"]',
            acc_paths TEXT DEFAULT '{}',
            CHECK (progress >= 0 AND progress <= 100),
            CHECK (status IN ('pending', 'processing', 'completed', 'failed', 'cancelled'))
        );

        CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
        CREATE INDEX IF NOT EXISTS idx_jobs_created_at ON jobs(created_at);
        CREATE INDEX IF NOT EXISTS idx_jobs_status_created ON jobs(status, created_at);

        CREATE TABLE IF NOT EXISTS job_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id TEXT NOT NULL,
            event_type TEXT NOT NULL,
            message TEXT,
            details TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (job_id) REFERENCES jobs(id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_events_job_id ON job_events(job_id);
        CREATE INDEX IF NOT EXISTS idx_events_created_at ON job_events(created_at);
        """

        try:
            await conn.executescript(schema)
            await conn.commit()
            logger.info("Database schema created/verified")

            # Add multi-format columns if not present (for existing databases)
            await self._migrate_add_multiformat_columns(conn)

        except aiosqlite.Error as e:
            logger.error(f"Schema creation failed: {e}")
            raise DatabaseException(f"Failed to create schema: {e}")

    async def _migrate_add_multiformat_columns(
        self,
        conn: aiosqlite.Connection
    ) -> None:
        """Add multi-format output columns if they don't exist.

        Supports databases created before multi-format support was added.
        """
        # Check if columns exist by querying table info
        cursor = await conn.execute("PRAGMA table_info(jobs)")
        columns = await cursor.fetchall()
        column_names = {col[1] for col in columns}

        migrations_needed = []

        if "output_formats" not in column_names:
            migrations_needed.append(
                "ALTER TABLE jobs ADD COLUMN output_formats TEXT DEFAULT '[\"msf\"]'"
            )

        if "acc_paths" not in column_names:
            migrations_needed.append(
                "ALTER TABLE jobs ADD COLUMN acc_paths TEXT DEFAULT '{}'"
            )

        for migration in migrations_needed:
            try:
                await conn.execute(migration)
                logger.info(f"Applied migration: {migration}")
            except aiosqlite.Error as e:
                # Column might already exist in some edge cases
                logger.warning(f"Migration skipped or failed: {e}")


class Database:
    """Database manager singleton."""

    _instance: Optional[DatabasePool] = None

    @classmethod
    async def initialize(
        cls,
        database_path: str | None = None,
        max_connections: int = 5
    ) -> DatabasePool:
        """Initialize the database singleton.

        Args:
            database_path: Path to database file. If None, uses DATA_DIR env var
                          with default "Data/web.db"
            max_connections: Maximum number of database connections in pool
        """
        if cls._instance is None:
            # Respect DATA_DIR environment variable for Railway volume mounts
            if database_path is None:
                base_dir = Path(os.getenv("DATA_DIR", "Data"))
                database_path = str(base_dir / "web.db")

            cls._instance = DatabasePool(database_path, max_connections)
            await cls._instance.initialize()
        return cls._instance

    @classmethod
    def get_pool(cls) -> DatabasePool:
        """Get the database pool instance."""
        if cls._instance is None:
            raise DatabaseException("Database not initialized")
        return cls._instance

    @classmethod
    async def close(cls) -> None:
        """Close the database pool."""
        if cls._instance:
            await cls._instance.close()
            cls._instance = None


# Transaction helper
@asynccontextmanager
async def transaction(conn: aiosqlite.Connection):
    """Transaction context manager for atomic operations."""
    try:
        await conn.execute("BEGIN")
        yield conn
        await conn.execute("COMMIT")
    except Exception:
        await conn.execute("ROLLBACK")
        raise