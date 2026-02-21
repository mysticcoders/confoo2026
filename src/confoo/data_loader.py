import json
import logging
from pathlib import Path

from confoo.models import Speaker, Session, SpeakerRating
from confoo.db import ConfooDB, DEFAULT_DB_PATH

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"


def load_speaker_ratings() -> dict[str, SpeakerRating]:
    """Load curated speaker ratings from JSON."""
    ratings_path = DATA_DIR / "speaker_ratings.json"
    if not ratings_path.exists():
        return {}
    try:
        with open(ratings_path) as f:
            data = json.load(f)
        return {
            slug: SpeakerRating(slug=slug, tier=info["tier"], note=info.get("note", ""))
            for slug, info in data.items()
        }
    except (json.JSONDecodeError, KeyError):
        logger.warning("Corrupt speaker ratings file %s, returning empty ratings", ratings_path)
        return {}


def load_sessions_from_json() -> list[Session]:
    """Load sessions from the static JSON snapshot."""
    json_path = DATA_DIR / "confoo2026.json"
    if not json_path.exists():
        return []
    with open(json_path) as f:
        data = json.load(f)
    sessions = []
    for s in data.get("sessions", []):
        raw_tracks = s.get("tracks", [])
        clean_tracks = []
        for t in raw_tracks:
            if "\t" in t:
                clean_tracks.extend(part.strip() for part in t.split("\t") if part.strip())
            else:
                clean_tracks.append(t)
        clean_tracks = list(dict.fromkeys(clean_tracks))
        sessions.append(Session(
            slug=s["slug"],
            title=s["title"],
            abstract=s.get("abstract", ""),
            day=s.get("day", ""),
            start_time=s.get("start_time", ""),
            end_time=s.get("end_time", ""),
            room=s.get("room", ""),
            language=s.get("language", ""),
            level=s.get("level", ""),
            is_keynote=s.get("is_keynote", False),
            speaker_slug=s.get("speaker_slug", ""),
            speaker_name=s.get("speaker_name", ""),
            tracks=clean_tracks,
        ))
    return sessions


def load_speakers_from_json() -> list[Speaker]:
    """Load speakers from the static JSON snapshot."""
    json_path = DATA_DIR / "confoo2026.json"
    if not json_path.exists():
        return []
    with open(json_path) as f:
        data = json.load(f)
    speakers = []
    for s in data.get("speakers", []):
        speakers.append(Speaker(
            slug=s["slug"],
            name=s["name"],
            company=s.get("company", ""),
            country=s.get("country", ""),
            bio=s.get("bio", ""),
            photo_url=s.get("photo_url", ""),
            website=s.get("website", ""),
            twitter=s.get("twitter", ""),
        ))
    return speakers


class DataLoader:
    """SQLite-first data loader with JSON fallback."""

    def __init__(self):
        self._db: ConfooDB | None = None
        self._using_json = False
        self._json_sessions: list[Session] | None = None
        self._json_speakers: list[Speaker] | None = None
        self._init_source()

    def _init_source(self):
        """Try SQLite first, fall back to JSON."""
        try:
            if DEFAULT_DB_PATH.exists():
                db = ConfooDB()
                if db.session_count() > 0:
                    self._db = db
                    return
                db.close()
        except Exception:
            pass

        self._using_json = True
        self._json_sessions = load_sessions_from_json()
        self._json_speakers = load_speakers_from_json()

    @property
    def source_name(self) -> str:
        if self._using_json:
            return "JSON snapshot"
        return "SQLite database"

    def get_all_sessions(self) -> list[Session]:
        if self._db:
            return self._db.get_all_sessions()
        return self._json_sessions or []

    def get_sessions_by_day(self, day: str) -> list[Session]:
        if self._db:
            return self._db.get_sessions_by_day(day)
        return [s for s in (self._json_sessions or []) if s.day == day]

    def get_session(self, slug: str) -> Session | None:
        if self._db:
            return self._db.get_session(slug)
        for s in (self._json_sessions or []):
            if s.slug == slug:
                return s
        return None

    def get_speaker(self, slug: str) -> Speaker | None:
        if self._db:
            return self._db.get_speaker(slug)
        for s in (self._json_speakers or []):
            if s.slug == slug:
                return s
        return None

    def get_all_speakers(self) -> list[Speaker]:
        if self._db:
            return self._db.get_all_speakers()
        return self._json_speakers or []

    def get_all_days(self) -> list[str]:
        if self._db:
            return self._db.get_all_days()
        days = sorted({s.day for s in (self._json_sessions or []) if s.day})
        return days

    def get_all_tracks(self) -> list[str]:
        if self._db:
            return self._db.get_all_tracks()
        tracks = set()
        for s in (self._json_sessions or []):
            tracks.update(s.tracks)
        return sorted(tracks)

    def get_last_sync(self) -> str | None:
        if self._db:
            return self._db.get_sync_meta("last_sync")
        return None

    def session_count(self) -> int:
        if self._db:
            return self._db.session_count()
        return len(self._json_sessions or [])

    def close(self):
        if self._db:
            self._db.close()
