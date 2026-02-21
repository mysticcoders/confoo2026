import json
from pathlib import Path
from datetime import datetime, timedelta

from confoo.models import Session, Speaker
from confoo.db import ConfooDB
from confoo.day_utils import parse_day_date, parse_time


def export_json_snapshot(db: ConfooDB, output_path: Path):
    """Export the full database to a JSON snapshot file."""
    sessions = db.get_all_sessions()
    speakers = db.get_all_speakers()
    events = db.get_special_events()

    data = {
        "exported_at": datetime.now().isoformat(),
        "sessions": [
            {
                "slug": s.slug,
                "title": s.title,
                "abstract": s.abstract,
                "day": s.day,
                "start_time": s.start_time,
                "end_time": s.end_time,
                "room": s.room,
                "language": s.language,
                "level": s.level,
                "is_keynote": s.is_keynote,
                "speaker_slug": s.speaker_slug,
                "speaker_name": s.speaker_name,
                "tracks": s.tracks,
            }
            for s in sessions
        ],
        "speakers": [
            {
                "slug": sp.slug,
                "name": sp.name,
                "company": sp.company,
                "country": sp.country,
                "bio": sp.bio,
                "photo_url": sp.photo_url,
                "website": sp.website,
                "twitter": sp.twitter,
            }
            for sp in speakers
        ],
        "special_events": [
            {
                "day": e.day,
                "start_time": e.start_time,
                "end_time": e.end_time,
                "name": e.name,
            }
            for e in events
        ],
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def export_ical(sessions: list[Session], output_path: Path):
    """Export selected sessions to an iCal file."""
    from icalendar import Calendar, Event

    cal = Calendar()
    cal.add("prodid", "-//ConFoo 2026 TUI Planner//EN")
    cal.add("version", "2.0")
    cal.add("calscale", "GREGORIAN")
    cal.add("x-wr-calname", "ConFoo 2026")

    for session in sessions:
        base_date = parse_day_date(session.day)
        if not base_date:
            continue
        start = parse_time(session.start_time, base_date)
        end = parse_time(session.end_time, base_date)
        if not start:
            continue
        if not end:
            end = start + timedelta(hours=1)

        event = Event()
        event.add("summary", session.title)
        event.add("dtstart", start)
        event.add("dtend", end)
        if session.room:
            event.add("location", session.room)
        description_parts = []
        if session.speaker_name:
            description_parts.append(f"Speaker: {session.speaker_name}")
        if session.tracks:
            description_parts.append(f"Tracks: {', '.join(session.tracks)}")
        if session.abstract:
            description_parts.append(f"\n{session.abstract}")
        event.add("description", "\n".join(description_parts))
        event.add("uid", f"{session.slug}@confoo2026")
        cal.add_component(event)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "wb") as f:
        f.write(cal.to_ical())
