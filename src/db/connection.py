"""
FACT System Database Connection Management

This module handles SQLite database connections, query execution,
and database initialization with sample data.
"""

import aiosqlite
import sqlite3
import os
import time
import asyncio
from typing import Dict, List, Any, Optional, Tuple
from contextlib import asynccontextmanager
import structlog

try:
    # Try relative imports first (when used as package)
    from ..core.errors import DatabaseError, SecurityError, InvalidSQLError
    from .models import (
        DATABASE_SCHEMA,
        SAMPLE_COMPANIES,
        SAMPLE_FINANCIAL_RECORDS,
        QueryResult,
        validate_schema_integrity,
    )
except ImportError:
    # Fall back to absolute imports (when run as script)
    import sys
    from pathlib import Path

    # Add src to path if not already there
    src_path = str(Path(__file__).parent.parent)
    if src_path not in sys.path:
        sys.path.insert(0, src_path)

    from core.errors import DatabaseError, SecurityError, InvalidSQLError
    from db.models import (
        DATABASE_SCHEMA,
        SAMPLE_COMPANIES,
        SAMPLE_FINANCIAL_RECORDS,
        QueryResult,
        validate_schema_integrity,
    )


logger = structlog.get_logger(__name__)


class AsyncConnectionPool:
    """
    Async connection pool for SQLite database connections.

    Provides connection reuse and management to reduce connection overhead.
    """

    def __init__(self, database_path: str, pool_size: int = 10):
        """
        Initialize connection pool.

        Args:
            database_path: Path to SQLite database
            pool_size: Maximum number of connections in pool
        """
        self.database_path = database_path
        self.pool_size = pool_size
        self.pool: asyncio.Queue = asyncio.Queue(maxsize=pool_size)
        self.created_connections = 0
        self._lock = asyncio.Lock()

    async def get_connection(self) -> aiosqlite.Connection:
        """Get a connection from the pool or create a new one."""
        try:
            # Try to get existing connection
            conn = self.pool.get_nowait()
            logger.debug("Reused pooled connection")
            return conn
        except asyncio.QueueEmpty:
            # Create new connection if pool is empty and we haven't hit limit
            async with self._lock:
                if self.created_connections < self.pool_size:
                    conn = await aiosqlite.connect(self.database_path)
                    self.created_connections += 1
                    logger.debug(
                        "Created new pooled connection",
                        total_connections=self.created_connections,
                    )
                    return conn
                else:
                    # Wait for a connection to become available
                    conn = await self.pool.get()
                    logger.debug("Retrieved connection from pool after wait")
                    return conn

    async def return_connection(self, conn: aiosqlite.Connection):
        """Return a connection to the pool."""
        try:
            self.pool.put_nowait(conn)
            logger.debug("Returned connection to pool")
        except asyncio.QueueFull:
            # Pool is full, close the connection
            await conn.close()
            async with self._lock:
                self.created_connections -= 1
            logger.debug(
                "Closed excess connection", total_connections=self.created_connections
            )

    async def close_all(self):
        """Close all connections in the pool."""
        connections_closed = 0
        while not self.pool.empty():
            try:
                conn = self.pool.get_nowait()
                await conn.close()
                connections_closed += 1
            except asyncio.QueueEmpty:
                break

        async with self._lock:
            self.created_connections = 0

        logger.info(
            "Closed all pooled connections", connections_closed=connections_closed
        )


class DatabaseManager:
    """
    Manages SQLite database connections and operations for the FACT system.

    Provides secure database access with read-only query validation,
    connection pooling, and performance monitoring.
    """

    def __init__(self, database_path: str, pool_size: int = 10):
        """
        Initialize database manager with connection pooling.

        Args:
            database_path: Path to SQLite database file
            pool_size: Maximum number of connections in pool
        """
        self.database_path = database_path
        self.pool_size = pool_size
        self.connection_pool = AsyncConnectionPool(database_path, pool_size)
        self._ensure_directory_exists()
        self._query_plan_cache = {}  # Cache for validated queries
        self._cache_max_size = 1000

    def _ensure_directory_exists(self) -> None:
        """Ensure the database directory exists."""
        db_dir = os.path.dirname(self.database_path)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir, exist_ok=True)
            logger.info("Created database directory", path=db_dir)

    async def initialize_database(self) -> None:
        """
        Initialize database with schema and sample data.

        Raises:
            DatabaseError: If database initialization fails
        """
        try:
            async with aiosqlite.connect(self.database_path) as db:
                # Execute schema creation
                await db.executescript(DATABASE_SCHEMA)
                await db.commit()

                # Check if data already exists
                cursor = await db.execute("SELECT COUNT(*) FROM companies")
                company_count = (await cursor.fetchone())[0]
                await cursor.close()

                # Check if financial_data table has data
                cursor = await db.execute("SELECT COUNT(*) FROM financial_data")
                financial_data_count = (await cursor.fetchone())[0]
                await cursor.close()

                # Check if benchmarks table has data
                cursor = await db.execute("SELECT COUNT(*) FROM benchmarks")
                benchmarks_count = (await cursor.fetchone())[0]
                await cursor.close()

                if company_count == 0:
                    # Batch insert sample companies for better performance
                    await db.executemany(
                        """
                        INSERT INTO companies (name, symbol, sector, founded_year, employees, market_cap)
                        VALUES (:name, :symbol, :sector, :founded_year, :employees, :market_cap)
                    """,
                        SAMPLE_COMPANIES,
                    )

                    # Batch insert sample financial records
                    await db.executemany(
                        """
                        INSERT INTO financial_records (company_id, quarter, year, revenue, profit, expenses)
                        VALUES (:company_id, :quarter, :year, :revenue, :profit, :expenses)
                    """,
                        SAMPLE_FINANCIAL_RECORDS,
                    )

                    # Batch insert into financial_data table for validation compatibility
                    await db.executemany(
                        """
                        INSERT INTO financial_data (company_id, quarter, year, revenue, profit, expenses)
                        VALUES (:company_id, :quarter, :year, :revenue, :profit, :expenses)
                    """,
                        SAMPLE_FINANCIAL_RECORDS,
                    )

                    # Insert sample benchmark data
                    sample_benchmarks = [
                        {
                            "test_name": "system_initialization",
                            "duration_ms": 250.5,
                            "queries_executed": 0,
                            "cache_hit_rate": 0.0,
                            "average_response_time_ms": 0.0,
                            "success_rate": 1.0,
                            "notes": "Initial system setup benchmark",
                        },
                        {
                            "test_name": "cache_warming",
                            "duration_ms": 180.2,
                            "queries_executed": 10,
                            "cache_hit_rate": 0.0,
                            "average_response_time_ms": 18.02,
                            "success_rate": 1.0,
                            "notes": "Cache warming performance test",
                        },
                    ]

                    for benchmark in sample_benchmarks:
                        await db.execute(
                            """
                            INSERT INTO benchmarks (test_name, duration_ms, queries_executed, cache_hit_rate,
                                                  average_response_time_ms, success_rate, notes)
                            VALUES (:test_name, :duration_ms, :queries_executed, :cache_hit_rate,
                                   :average_response_time_ms, :success_rate, :notes)
                        """,
                            benchmark,
                        )

                    await db.commit()
                    logger.info("Database initialized with sample data")

                # Handle the case where companies exist but other tables don't
                elif financial_data_count == 0:
                    logger.info("Adding missing financial_data records")
                    # Insert sample financial records into financial_data table
                    for record in SAMPLE_FINANCIAL_RECORDS:
                        await db.execute(
                            """
                            INSERT INTO financial_data (company_id, quarter, year, revenue, profit, expenses)
                            VALUES (:company_id, :quarter, :year, :revenue, :profit, :expenses)
                        """,
                            record,
                        )
                    await db.commit()
                    logger.info("Financial data populated")

                if benchmarks_count == 0:
                    logger.info("Adding missing benchmark records")
                    # Insert sample benchmark data
                    sample_benchmarks = [
                        {
                            "test_name": "system_initialization",
                            "duration_ms": 250.5,
                            "queries_executed": 0,
                            "cache_hit_rate": 0.0,
                            "average_response_time_ms": 0.0,
                            "success_rate": 1.0,
                            "notes": "Initial system setup benchmark",
                        },
                        {
                            "test_name": "cache_warming",
                            "duration_ms": 180.2,
                            "queries_executed": 10,
                            "cache_hit_rate": 0.0,
                            "average_response_time_ms": 18.02,
                            "success_rate": 1.0,
                            "notes": "Cache warming performance test",
                        },
                    ]

                    for benchmark in sample_benchmarks:
                        await db.execute(
                            """
                            INSERT INTO benchmarks (test_name, duration_ms, queries_executed, cache_hit_rate,
                                                  average_response_time_ms, success_rate, notes)
                            VALUES (:test_name, :duration_ms, :queries_executed, :cache_hit_rate,
                                   :average_response_time_ms, :success_rate, :notes)
                        """,
                            benchmark,
                        )
                    await db.commit()
                    logger.info("Benchmark data populated")
                else:
                    logger.info(
                        "Database already contains data, skipping sample data insertion"
                    )

                # Validate schema integrity
                cursor = await db.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                )
                tables = await cursor.fetchall()
                await cursor.close()

                tables_info = [{"name": table[0]} for table in tables]
                if not validate_schema_integrity(tables_info):
                    raise DatabaseError("Database schema validation failed")

        except Exception as e:
            logger.error("Database initialization failed", error=str(e))
            raise DatabaseError(f"Failed to initialize database: {e}")

    def validate_sql_query(self, statement: str) -> None:
        """
        Validate SQL query for security and syntax with caching.

        Args:
            statement: SQL statement to validate

        Raises:
            SecurityError: If statement contains dangerous operations
            InvalidSQLError: If statement has syntax errors
        """
        # Generate cache key for query validation
        import hashlib

        query_hash = hashlib.md5(statement.encode()).hexdigest()

        # Check cache first
        if query_hash in self._query_plan_cache:
            logger.debug("Query validation cache hit", statement=statement[:100])
            return

        normalized_statement = statement.lower().strip()

        # Security check: allow SELECT statements and safe PRAGMA queries
        is_select = normalized_statement.startswith("select")
        is_safe_pragma = normalized_statement.startswith("pragma table_info")

        if not (is_select or is_safe_pragma):
            raise SecurityError(
                "Only SELECT statements and PRAGMA table_info queries are allowed"
            )

        # Enhanced dangerous keyword detection (excluding safe pragma)
        dangerous_keywords = [
            "drop",
            "delete",
            "update",
            "insert",
            "alter",
            "create",
            "truncate",
            "replace",
            "merge",
            "exec",
            "execute",
            "attach",
            "detach",
            "vacuum",
            "reindex",
            "analyze",
        ]

        # For PRAGMA queries, only allow table_info
        if normalized_statement.startswith(
            "pragma"
        ) and not normalized_statement.startswith("pragma table_info"):
            raise SecurityError("Only PRAGMA table_info queries are allowed")

        # Check for dangerous keywords with word boundaries
        import re

        for keyword in dangerous_keywords:
            pattern = r"\b" + re.escape(keyword) + r"\b"
            if re.search(pattern, normalized_statement, re.IGNORECASE):
                raise SecurityError(f"Dangerous SQL keyword detected: {keyword}")

        # Check for SQL injection patterns
        # Check for SQL injection patterns (skip for safe PRAGMA queries)
        if not normalized_statement.startswith("pragma table_info"):
            injection_patterns = [
                r"--",  # SQL comments
                r"/\*.*?\*/",  # Multi-line comments
                r";\s*\w+",  # Multiple statements
                r"\bunion\s+select\b",  # Union injection
                r"\bor\s+1\s*=\s*1\b",  # Always true conditions
                r"\band\s+1\s*=\s*1\b",  # Always true conditions
                r"\bor\s+\'.*?\'\s*=\s*\'.*?\'",  # Suspicious OR with string comparisons
                r"\'.*?\'\s*or\s*\'.*?\'",  # Injection with OR between quotes
                r"\\x[0-9a-f]{2}",  # Hex encoding
            ]

            for pattern in injection_patterns:
                if re.search(pattern, normalized_statement, re.IGNORECASE):
                    raise SecurityError(
                        f"Potential SQL injection pattern detected: {pattern} in query: {normalized_statement[:100]}"
                    )
        # Limit query complexity
        if len(statement) > 5000:
            raise SecurityError("Query too long - potential DoS attack")

        # Count nested subqueries to prevent complex injection attacks
        subquery_count = normalized_statement.count("select")
        if subquery_count > 5:
            raise SecurityError(
                "Too many nested subqueries - potential injection attack"
            )

        # Basic syntax validation using actual database connection
        try:
            # Parse SQL to check syntax (without executing)
            with sqlite3.connect(self.database_path) as conn:
                conn.execute(f"EXPLAIN QUERY PLAN {statement}")
        except sqlite3.Error as e:
            raise InvalidSQLError(f"SQL syntax error: {e}")

        # Cache successful validation
        if len(self._query_plan_cache) >= self._cache_max_size:
            # Simple eviction: remove oldest entries
            oldest_keys = list(self._query_plan_cache.keys())[:100]
            for key in oldest_keys:
                del self._query_plan_cache[key]

        self._query_plan_cache[query_hash] = time.time()
        logger.debug(
            "SQL query validation passed and cached", statement=statement[:100]
        )

    def _is_valid_table_name(self, table_name: str) -> bool:
        """
        Validate table name to prevent SQL injection.

        Args:
            table_name: Table name to validate

        Returns:
            True if table name is valid
        """
        import re

        # Table name should only contain alphanumeric characters and underscores
        if not re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", table_name):
            return False

        # Reasonable length limit
        if len(table_name) > 64:
            return False

        # Check against known system tables that should not be accessed
        forbidden_tables = {
            "sqlite_master",
            "sqlite_temp_master",
            "sqlite_sequence",
            "sqlite_stat1",
            "sqlite_stat2",
            "sqlite_stat3",
            "sqlite_stat4",
        }

        if table_name.lower() in forbidden_tables:
            return False

        return True

    async def execute_query(self, statement: str) -> QueryResult:
        """
        Execute a validated SQL query using connection pool.

        Args:
            statement: SQL SELECT statement to execute

        Returns:
            QueryResult containing rows, metadata, and timing

        Raises:
            DatabaseError: If query execution fails
            SecurityError: If statement violates security rules
            InvalidSQLError: If statement has syntax errors
        """
        # Validate query first (with caching)
        self.validate_sql_query(statement)

        start_time = time.time()

        try:
            # Get connection from pool
            db = await self.connection_pool.get_connection()

            try:
                # Enable row factory for dictionary-like access
                db.row_factory = aiosqlite.Row

                cursor = await db.execute(statement)
                rows = await cursor.fetchall()

                # Convert rows to dictionaries
                structured_results = []
                columns = []

                if rows:
                    # Get column names from first row
                    columns = list(rows[0].keys())

                    # Convert each row to dictionary
                    for row in rows:
                        row_dict = {col: row[col] for col in columns}
                        structured_results.append(row_dict)

                await cursor.close()

                end_time = time.time()
                execution_time_ms = (end_time - start_time) * 1000

                result = QueryResult(
                    rows=structured_results,
                    row_count=len(structured_results),
                    columns=columns,
                    execution_time_ms=execution_time_ms,
                )

                logger.info(
                    "Query executed successfully",
                    statement=statement[:100],
                    row_count=result.row_count,
                    execution_time_ms=execution_time_ms,
                )

                return result

            finally:
                # Always return connection to pool
                await self.connection_pool.return_connection(db)

        except Exception as e:
            end_time = time.time()
            execution_time_ms = (end_time - start_time) * 1000

            logger.error(
                "Query execution failed",
                statement=statement[:100],
                error=str(e),
                execution_time_ms=execution_time_ms,
            )

            raise DatabaseError(f"Query execution failed: {e}")

    async def get_database_info(self) -> Dict[str, Any]:
        """
        Get database metadata and statistics.

        Returns:
            Dictionary containing database information
        """
        try:
            async with aiosqlite.connect(self.database_path) as db:
                # Get table information
                cursor = await db.execute("""
                    SELECT name FROM sqlite_master
                    WHERE type='table' AND name NOT LIKE 'sqlite_%'
                """)
                tables = await cursor.fetchall()
                await cursor.close()

                table_info = {}
                for (table_name,) in tables:
                    # Validate table name to prevent injection
                    if not self._is_valid_table_name(table_name):
                        logger.warning(
                            "Invalid table name detected", table_name=table_name
                        )
                        continue

                    # Get row count for each table using parameterized query
                    # Note: Table names cannot be parameterized, so we validate them first
                    cursor = await db.execute(f'SELECT COUNT(*) FROM "{table_name}"')
                    count = (await cursor.fetchone())[0]
                    await cursor.close()
                    table_info[table_name] = {"row_count": count}

                # Get database file size
                file_size = (
                    os.path.getsize(self.database_path)
                    if os.path.exists(self.database_path)
                    else 0
                )

                return {
                    "database_path": self.database_path,
                    "file_size_bytes": file_size,
                    "tables": table_info,
                    "total_tables": len(tables),
                }

        except Exception as e:
            logger.error("Failed to get database info", error=str(e))
            raise DatabaseError(f"Failed to get database info: {e}")

    async def cleanup(self):
        """
        Cleanup database resources including connection pool.
        """
        try:
            await self.connection_pool.close_all()
            logger.info("Database manager cleanup completed")
        except Exception as e:
            logger.error("Database cleanup failed", error=str(e))

    @asynccontextmanager
    async def get_connection(self):
        """
        Get an async database connection context manager.

        Yields:
            aiosqlite.Connection: Database connection
        """
        # Use connection pool instead of creating new connections
        conn = await self.connection_pool.get_connection()
        try:
            yield conn
        except Exception as e:
            logger.error("Database connection error", error=str(e))
            raise DatabaseError(f"Database connection error: {e}")
        finally:
            await self.connection_pool.return_connection(conn)


def create_database_manager(database_path: str) -> DatabaseManager:
    """
    Create and initialize a database manager instance.

    Args:
        database_path: Path to SQLite database file

    Returns:
        Configured DatabaseManager instance
    """
    return DatabaseManager(database_path)
