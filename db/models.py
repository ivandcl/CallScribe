SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS recordings (
    id              TEXT PRIMARY KEY,
    title           TEXT NOT NULL,
    started_at      TEXT NOT NULL,
    ended_at        TEXT,
    duration_secs   INTEGER,
    audio_path      TEXT,
    transcript_path TEXT,
    summary_path    TEXT,
    status          TEXT NOT NULL DEFAULT 'recording',
    error_message   TEXT,
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);
"""
