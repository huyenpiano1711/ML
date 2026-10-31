"""
connector.py - SQLite connector (same interface as connectors/connector.py in ProjectML,
but SQLite instead of MySQL so the app runs without a database server).
The database file is created automatically: desktop_app/databases/autowise.sqlite
"""
import sqlite3
import traceback
from pathlib import Path

import pandas as pd

DATABASE_PATH = Path(__file__).resolve().parents[1] / "databases" / "autowise.sqlite"


class Connector:
    def __init__(self, database=DATABASE_PATH):
        self.database = Path(database)
        self.conn = None

    def connect(self):
        self.database.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.database)
        self.createTables()
        return self.conn

    def disConnect(self):
        if self.conn is not None:
            self.conn.close()
            self.conn = None

    def createTables(self):
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                username      TEXT    NOT NULL UNIQUE COLLATE NOCASE,
                password      TEXT    NOT NULL,          -- salt$pbkdf2-sha256 hash, never plain text
                full_name     TEXT    NOT NULL,
                email         TEXT,
                is_banned     INTEGER NOT NULL DEFAULT 0,
                role          TEXT    NOT NULL DEFAULT 'user',
                created_at    TEXT    NOT NULL DEFAULT (datetime('now', 'localtime'))
            )""")
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
        """INSERT / UPDATE / DELETE -> id of the inserted row (or None on error)."""
        try:
            cursor = self.conn.cursor()
            cursor.execute(sql, val or ())
            self.conn.commit()
            return cursor.lastrowid
        except Exception:
            traceback.print_exc()
            self.conn.rollback()
        return None
