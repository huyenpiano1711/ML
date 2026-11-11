"""
connector.py - SQLite connector (same interface as connectors/connector.py in ProjectML,
but SQLite instead of MySQL so the app runs without a database server).
The database file is created automatically: desktop_app/databases/autowise.sqlite

Tables
    users          accounts, role user/admin, lock state after wrong passwords
    login_history  every sign-in attempt (success or not) - lock rule and admin dashboard
    searches       every analysis a user runs (history, admin statistics)
    favorites      cars a user saved from the results (compare side by side)
    audit_log      what admins changed (lock a user, reset a password, activate a model...)
"""
import sqlite3
import traceback
from pathlib import Path

import pandas as pd

DATABASE_PATH = Path(__file__).resolve().parents[1] / "databases" / "autowise.sqlite"

SCHEMA = [
    """CREATE TABLE IF NOT EXISTS users (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        username      TEXT    NOT NULL UNIQUE COLLATE NOCASE,
        password      TEXT    NOT NULL,          -- salt$pbkdf2-sha256 hash, never plain text
        full_name     TEXT    NOT NULL,
        email         TEXT,
        is_banned     INTEGER NOT NULL DEFAULT 0,
        role          TEXT    NOT NULL DEFAULT 'user' CHECK (role IN ('user', 'admin')),
        created_at    TEXT    NOT NULL DEFAULT (datetime('now', 'localtime'))
    )""",
    """CREATE TABLE IF NOT EXISTS login_history (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id     INTEGER REFERENCES users(id) ON DELETE SET NULL,
        username    TEXT    NOT NULL,
        success     INTEGER NOT NULL,
        reason      TEXT,
        created_at  TEXT    NOT NULL DEFAULT (datetime('now', 'localtime'))
    )""",
    """CREATE TABLE IF NOT EXISTS searches (
        id               INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id          INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        created_at       TEXT    NOT NULL DEFAULT (datetime('now', 'localtime')),
        manufacturer     TEXT    NOT NULL,
        model_base       TEXT    NOT NULL,
        year             INTEGER NOT NULL,
        odometer         REAL    NOT NULL,
        budget_max_usd   REAL    NOT NULL,
        predicted_price  REAL,
        price_low        REAL,
        price_high       REAL,
        n_matches        INTEGER NOT NULL DEFAULT 0,
        success          INTEGER NOT NULL DEFAULT 1,
        elapsed_ms       REAL,
        input_json       TEXT    NOT NULL,       -- the form, to open the analysis again
        result_json      TEXT                    -- price + Top 5 + same price range, for the PDF
    )""",
    """CREATE TABLE IF NOT EXISTS favorites (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        listing_id  INTEGER NOT NULL,
        car_json    TEXT    NOT NULL,
        note        TEXT,
        created_at  TEXT    NOT NULL DEFAULT (datetime('now', 'localtime')),
        UNIQUE (user_id, listing_id)
    )""",
    """CREATE TABLE IF NOT EXISTS audit_log (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        admin_id    INTEGER REFERENCES users(id) ON DELETE SET NULL,
        action      TEXT    NOT NULL,
        target      TEXT,
        detail      TEXT,
        created_at  TEXT    NOT NULL DEFAULT (datetime('now', 'localtime'))
    )""",
    "CREATE INDEX IF NOT EXISTS ix_login_user ON login_history(username, created_at)",
    "CREATE INDEX IF NOT EXISTS ix_search_user ON searches(user_id, created_at)",
]

# Columns added after the first release: (table, column, definition). Existing databases get them on connect.
MIGRATIONS = [
    ("users", "failed_count", "INTEGER NOT NULL DEFAULT 0"),
    ("users", "locked_until", "TEXT"),
    ("users", "last_login_at", "TEXT"),
    ("users", "updated_at", "TEXT"),
]


class Connector:
    def __init__(self, database=DATABASE_PATH):
        self.database = Path(database)
        self.conn = None

    def connect(self):
        self.database.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.database)
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.createTables()
        return self.conn

    def disConnect(self):
        if self.conn is not None:
            self.conn.close()
            self.conn = None

    def createTables(self):
        for sql in SCHEMA:
            self.conn.execute(sql)
        for table, column, definition in MIGRATIONS:
            columns = {row[1] for row in self.conn.execute(f"PRAGMA table_info({table})")}
            if column not in columns:
                self.conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
        self.conn.commit()

    def queryDataset(self, sql, val=None):
        """SELECT -> pandas DataFrame (empty DataFrame when there are no rows, None on error)."""
        try:
            cursor = self.conn.cursor()
            cursor.execute(sql, val or ())
            columns = [c[0] for c in cursor.description]
            return pd.DataFrame(cursor.fetchall(), columns=columns)
        except Exception:
            traceback.print_exc()
        return None

    def executeNonQuery(self, sql, val=None):
        """INSERT / UPDATE / DELETE -> id of the inserted row for an INSERT, else the number of changed rows
        (None on error)."""
        try:
            cursor = self.conn.cursor()
            cursor.execute(sql, val or ())
            self.conn.commit()
            return cursor.lastrowid if sql.lstrip().lower().startswith("insert") else cursor.rowcount
        except Exception:
            traceback.print_exc()
            self.conn.rollback()
        return None
