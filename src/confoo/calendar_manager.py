import json
import logging
from pathlib import Path
from confoo.models import Session

logger = logging.getLogger(__name__)

CALENDAR_PATH = Path.home() / ".local" / "share" / "confoo2026" / "my_calendar.json"


class CalendarManager:
    """Manages personal session selections with conflict detection."""

    def __init__(self, calendar_path: Path | None = None):
        self.path = calendar_path or CALENDAR_PATH
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._selected_slugs: set[str] = set()
        self._load()

    def _load(self):
        """Load selections from disk."""
        if self.path.exists():
            try:
                with open(self.path) as f:
                    data = json.load(f)
                self._selected_slugs = set(data.get("selected", []))
            except (json.JSONDecodeError, KeyError, OSError) as exc:
                logger.warning("Could not load calendar file %s: %s", self.path, exc)
                self._selected_slugs = set()

    def _save(self):
        """Persist selections to disk via atomic temp-file swap."""
        data = {"selected": sorted(self._selected_slugs)}
        tmp_path = self.path.with_suffix(".tmp")
        with open(tmp_path, "w") as f:
            json.dump(data, f, indent=2)
        tmp_path.replace(self.path)

    def add(self, slug: str):
        """Add a session to the personal calendar."""
        self._selected_slugs.add(slug)
        self._save()

    def remove(self, slug: str):
        """Remove a session from the personal calendar."""
        self._selected_slugs.discard(slug)
        self._save()

    def toggle(self, slug: str) -> bool:
        """Toggle a session. Returns True if now selected."""
        if slug in self._selected_slugs:
            self.remove(slug)
            return False
        self.add(slug)
        return True

    def is_selected(self, slug: str) -> bool:
        return slug in self._selected_slugs

    @property
    def selected_slugs(self) -> set[str]:
        return set(self._selected_slugs)

    def get_selected_sessions(self, all_sessions: list[Session]) -> list[Session]:
        """Get full Session objects for all selections."""
        return [s for s in all_sessions if s.slug in self._selected_slugs]

    def find_conflicts(self, sessions: list[Session]) -> dict[str, list[str]]:
        """Find time conflicts among selected sessions.

        Returns a dict mapping session slug to list of conflicting session slugs.
        """
        selected = self.get_selected_sessions(sessions)
        conflicts: dict[str, list[str]] = {}

        for i, a in enumerate(selected):
            for b in selected[i + 1:]:
                if a.day != b.day or not a.day:
                    continue
                if not a.start_time or not b.start_time:
                    continue
                if self._times_overlap(a.start_time, a.end_time, b.start_time, b.end_time):
                    conflicts.setdefault(a.slug, []).append(b.slug)
                    conflicts.setdefault(b.slug, []).append(a.slug)

        return conflicts

    @staticmethod
    def _times_overlap(start_a: str, end_a: str, start_b: str, end_b: str) -> bool:
        """Check if two time ranges overlap."""
        def to_minutes(t: str) -> int:
            parts = t.split(":")
            return int(parts[0]) * 60 + int(parts[1])

        try:
            sa = to_minutes(start_a)
            ea = to_minutes(end_a) if end_a else sa + 60
            sb = to_minutes(start_b)
            eb = to_minutes(end_b) if end_b else sb + 60
            return sa < eb and sb < ea
        except (ValueError, IndexError):
            return False
