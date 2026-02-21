import sqlite3
from pathlib import Path
from datetime import datetime

from confoo.models import Speaker, Session, SpecialEvent

DEFAULT_DB_PATH = Path.home() / ".local" / "share" / "confoo2026" / "confoo.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS speakers (
    slug TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    company TEXT DEFAULT '',
    country TEXT DEFAULT '',
    bio TEXT DEFAULT '',
    photo_url TEXT DEFAULT '',
    website TEXT DEFAULT '',
    twitter TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS sessions (
    slug TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    abstract TEXT DEFAULT '',
    day TEXT DEFAULT '',
    start_time TEXT DEFAULT '',
    end_time TEXT DEFAULT '',
    room TEXT DEFAULT '',
    language TEXT DEFAULT '',
    level TEXT DEFAULT '',
    is_keynote INTEGER DEFAULT 0,
    speaker_slug TEXT DEFAULT '',
    speaker_name TEXT DEFAULT '',
    FOREIGN KEY (speaker_slug) REFERENCES speakers(slug)
);

CREATE TABLE IF NOT EXISTS session_tracks (
    session_slug TEXT NOT NULL,
    track TEXT NOT NULL,
    PRIMARY KEY (session_slug, track),
    FOREIGN KEY (session_slug) REFERENCES sessions(slug)
);

CREATE TABLE IF NOT EXISTS special_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    day TEXT DEFAULT '',
    start_time TEXT DEFAULT '',
    end_time TEXT DEFAULT '',
    name TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS sync_meta (
    key TEXT PRIMARY KEY,
    value TEXT
);
"""


class ConfooDB:
    """SQLite database for ConFoo 2026 schedule data."""

    def __init__(self, db_path: Path | None = None):
        self.db_path = db_path or DEFAULT_DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.db_path))
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self._init_schema()

    def _init_schema(self):
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def close(self):
        self.conn.close()

    def upsert_speaker(self, speaker: Speaker):
        """Insert or update a speaker."""
        self.conn.execute(
            """INSERT INTO speakers (slug, name, company, country, bio, photo_url, website, twitter)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(slug) DO UPDATE SET
                 name=excluded.name, company=excluded.company, country=excluded.country,
                 bio=excluded.bio, photo_url=excluded.photo_url,
                 website=excluded.website, twitter=excluded.twitter""",
            (speaker.slug, speaker.name, speaker.company, speaker.country,
             speaker.bio, speaker.photo_url, speaker.website, speaker.twitter),
        )

    def upsert_session(self, session: Session):
        """Insert or update a session and its tracks."""
        self.conn.execute(
            """INSERT INTO sessions (slug, title, abstract, day, start_time, end_time,
                 room, language, level, is_keynote, speaker_slug, speaker_name)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(slug) DO UPDATE SET
                 title=excluded.title, abstract=excluded.abstract, day=excluded.day,
                 start_time=excluded.start_time, end_time=excluded.end_time,
                 room=excluded.room, language=excluded.language, level=excluded.level,
                 is_keynote=excluded.is_keynote, speaker_slug=excluded.speaker_slug,
                 speaker_name=excluded.speaker_name""",
            (session.slug, session.title, session.abstract, session.day,
             session.start_time, session.end_time, session.room, session.language,
             session.level, int(session.is_keynote), session.speaker_slug,
             session.speaker_name),
        )
        self.conn.execute(
            "DELETE FROM session_tracks WHERE session_slug = ?", (session.slug,)
        )
        for track in session.tracks:
            self.conn.execute(
                "INSERT INTO session_tracks (session_slug, track) VALUES (?, ?)",
                (session.slug, track),
            )

    def upsert_special_event(self, event: SpecialEvent):
        """Insert a special event."""
        self.conn.execute(
            """INSERT INTO special_events (day, start_time, end_time, name)
               VALUES (?, ?, ?, ?)""",
            (event.day, event.start_time, event.end_time, event.name),
        )

    def set_sync_meta(self, key: str, value: str):
        """Set a sync metadata value."""
        self.conn.execute(
            "INSERT INTO sync_meta (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, value),
        )

    def get_sync_meta(self, key: str) -> str | None:
        """Get a sync metadata value."""
        row = self.conn.execute(
            "SELECT value FROM sync_meta WHERE key = ?", (key,)
        ).fetchone()
        return row["value"] if row else None

    def commit(self):
        self.conn.commit()

    def clear_all(self):
        """Clear all data for a fresh sync."""
        self.conn.execute("DELETE FROM session_tracks")
        self.conn.execute("DELETE FROM sessions")
        self.conn.execute("DELETE FROM speakers")
        self.conn.execute("DELETE FROM special_events")
        self.conn.commit()

    def _row_to_session(self, row, tracks: list[str] | None = None) -> Session:
        """Build a Session from a database row."""
        if tracks is None:
            tracks_rows = self.conn.execute(
                "SELECT track FROM session_tracks WHERE session_slug = ?",
                (row["slug"],),
            ).fetchall()
            tracks = [t["track"] for t in tracks_rows]
        return Session(
            slug=row["slug"],
            title=row["title"],
            abstract=row["abstract"],
            day=row["day"],
            start_time=row["start_time"],
            end_time=row["end_time"],
            room=row["room"],
            language=row["language"],
            level=row["level"],
            is_keynote=bool(row["is_keynote"]),
            speaker_slug=row["speaker_slug"],
            speaker_name=row["speaker_name"],
            tracks=tracks,
        )

    def _row_to_speaker(self, row) -> Speaker:
        """Build a Speaker from a database row."""
        return Speaker(
            slug=row["slug"],
            name=row["name"],
            company=row["company"],
            country=row["country"],
            bio=row["bio"],
            photo_url=row["photo_url"],
            website=row["website"],
            twitter=row["twitter"],
        )

    def _fetch_tracks(self, slugs: list[str] | None = None) -> dict[str, list[str]]:
        """Pre-fetch session tracks in a single query, optionally scoped to specific slugs."""
        if slugs is not None:
            if not slugs:
                return {}
            placeholders = ",".join("?" * len(slugs))
            rows = self.conn.execute(
                f"SELECT session_slug, track FROM session_tracks WHERE session_slug IN ({placeholders})",
                slugs,
            ).fetchall()
        else:
            rows = self.conn.execute(
                "SELECT session_slug, track FROM session_tracks"
            ).fetchall()
        tracks_map: dict[str, list[str]] = {}
        for row in rows:
            tracks_map.setdefault(row["session_slug"], []).append(row["track"])
        return tracks_map

    def get_all_sessions(self) -> list[Session]:
        """Get all sessions with their tracks."""
        rows = self.conn.execute(
            "SELECT * FROM sessions ORDER BY day, start_time, room"
        ).fetchall()
        tracks_map = self._fetch_tracks()
        return [
            self._row_to_session(row, tracks_map.get(row["slug"], []))
            for row in rows
        ]

    def get_sessions_by_day(self, day: str) -> list[Session]:
        """Get sessions for a specific day."""
        rows = self.conn.execute(
            "SELECT * FROM sessions WHERE day = ? ORDER BY start_time, room",
            (day,),
        ).fetchall()
        slugs = [row["slug"] for row in rows]
        tracks_map = self._fetch_tracks(slugs)
        return [
            self._row_to_session(row, tracks_map.get(row["slug"], []))
            for row in rows
        ]

    def get_session(self, slug: str) -> Session | None:
        """Get a single session by slug."""
        row = self.conn.execute(
            "SELECT * FROM sessions WHERE slug = ?", (slug,)
        ).fetchone()
        if not row:
            return None
        return self._row_to_session(row)

    def get_speaker(self, slug: str) -> Speaker | None:
        """Get a single speaker by slug."""
        row = self.conn.execute(
            "SELECT * FROM speakers WHERE slug = ?", (slug,)
        ).fetchone()
        if not row:
            return None
        return self._row_to_speaker(row)

    def get_all_speakers(self) -> list[Speaker]:
        """Get all speakers."""
        rows = self.conn.execute(
            "SELECT * FROM speakers ORDER BY name"
        ).fetchall()
        return [self._row_to_speaker(row) for row in rows]

    def get_all_days(self) -> list[str]:
        """Get all unique days in the schedule."""
        rows = self.conn.execute(
            "SELECT DISTINCT day FROM sessions WHERE day != '' ORDER BY day"
        ).fetchall()
        return [row["day"] for row in rows]

    def get_all_tracks(self) -> list[str]:
        """Get all unique tracks."""
        rows = self.conn.execute(
            "SELECT DISTINCT track FROM session_tracks ORDER BY track"
        ).fetchall()
        return [row["track"] for row in rows]

    def get_special_events(self) -> list[SpecialEvent]:
        """Get all special events."""
        rows = self.conn.execute(
            "SELECT * FROM special_events ORDER BY day, start_time"
        ).fetchall()
        return [
            SpecialEvent(
                id=row["id"],
                day=row["day"],
                start_time=row["start_time"],
                end_time=row["end_time"],
                name=row["name"],
            )
            for row in rows
        ]

    def session_count(self) -> int:
        """Get total number of sessions."""
        row = self.conn.execute("SELECT COUNT(*) as cnt FROM sessions").fetchone()
        return row["cnt"]

    def update_last_sync(self):
        """Record the current time as last sync."""
        self.set_sync_meta("last_sync", datetime.now().isoformat())
