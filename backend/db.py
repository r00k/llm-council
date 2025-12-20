"""SQLite database initialization and utilities."""

import sqlite3
from pathlib import Path
from .config import DATA_DIR

DB_PATH = Path(DATA_DIR) / "conversations.db"
SCHEMA_PATH = Path(__file__).parent / "schema.sql"


def get_connection() -> sqlite3.Connection:
    """
    Get a connection to the SQLite database.

    Returns:
        SQLite connection with row factory enabled
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # Enable dict-like access
    return conn


def init_db():
    """Initialize the database with schema if it doesn't exist."""
    # Ensure data directory exists
    Path(DATA_DIR).mkdir(parents=True, exist_ok=True)

    # Read schema
    with open(SCHEMA_PATH, 'r') as f:
        schema_sql = f.read()

    # Create tables
    conn = get_connection()
    try:
        conn.executescript(schema_sql)
        conn.commit()
    finally:
        conn.close()


# Initialize database on module import
init_db()
