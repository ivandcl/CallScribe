import sqlite3
import threading
from pathlib import Path

from db.models import SCHEMA_SQL

_local = threading.local()


class Database:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _get_conn(self) -> sqlite3.Connection:
        if not hasattr(_local, "conn") or _local.conn is None:
            _local.conn = sqlite3.connect(str(self.db_path))
            _local.conn.row_factory = sqlite3.Row
            _local.conn.execute("PRAGMA journal_mode=WAL")
        return _local.conn

    def _init_schema(self):
        conn = self._get_conn()
        conn.executescript(SCHEMA_SQL)
        conn.commit()

    def execute(self, sql: str, params: tuple = ()) -> sqlite3.Cursor:
        conn = self._get_conn()
        cursor = conn.execute(sql, params)
        conn.commit()
        return cursor

    def fetchone(self, sql: str, params: tuple = ()) -> dict | None:
        cursor = self._get_conn().execute(sql, params)
        row = cursor.fetchone()
        return dict(row) if row else None

    def fetchall(self, sql: str, params: tuple = ()) -> list[dict]:
        cursor = self._get_conn().execute(sql, params)
        return [dict(row) for row in cursor.fetchall()]

    def insert_recording(self, recording_id: str, title: str, started_at: str) -> dict:
        self.execute(
            "INSERT INTO recordings (id, title, started_at, status) VALUES (?, ?, ?, 'recording')",
            (recording_id, title, started_at),
        )
        return self.get_recording(recording_id)

    def get_recording(self, recording_id: str) -> dict | None:
        return self.fetchone("SELECT * FROM recordings WHERE id = ?", (recording_id,))

    def list_recordings(self) -> list[dict]:
        return self.fetchall("SELECT * FROM recordings ORDER BY started_at DESC")

    def update_recording(self, recording_id: str, **fields) -> dict | None:
        if not fields:
            return self.get_recording(recording_id)
        set_clause = ", ".join(f"{k} = ?" for k in fields)
        values = list(fields.values()) + [recording_id]
        self.execute(f"UPDATE recordings SET {set_clause} WHERE id = ?", tuple(values))
        return self.get_recording(recording_id)

    def delete_recording(self, recording_id: str) -> bool:
        cursor = self.execute("DELETE FROM recordings WHERE id = ?", (recording_id,))
        return cursor.rowcount > 0
