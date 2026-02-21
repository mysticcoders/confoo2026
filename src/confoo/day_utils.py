import logging
import re
from datetime import datetime

logger = logging.getLogger(__name__)

DAY_LABELS = {
    "23": "Mon 23",
    "24": "Tue 24",
    "25": "Wed 25",
    "26": "Thu 26",
    "27": "Fri 27",
}

CONFERENCE_DAYS = {"25", "26", "27"}

DAY_NAME_TO_NUM = {
    "monday": "23",
    "tuesday": "24",
    "wednesday": "25",
    "thursday": "26",
    "friday": "27",
}


def day_number(day: str) -> str:
    """Extract the February day number from a day string.

    Handles formats like:
    - "Wednesday      (2026-02-25)"
    - "Wednesday, February 25"
    - "2026-02-25"
    - "25"
    """
    iso_match = re.search(r"2026-02-(\d{2})", day)
    if iso_match:
        return str(int(iso_match.group(1)))

    feb_match = re.search(r"February\s+(\d+)", day)
    if feb_match:
        return feb_match.group(1)

    for name, num in DAY_NAME_TO_NUM.items():
        if name in day.lower():
            return num

    simple_match = re.match(r"^(\d{1,2})$", day.strip())
    if simple_match:
        return simple_match.group(1)

    logger.warning("Unrecognized day format: %r", day)
    return day


def day_sort_key(day: str) -> str:
    """Sort key for day strings."""
    return day_number(day).zfill(2)


def make_tab_label(day: str) -> str:
    """Create a short tab label from a day string."""
    num = day_number(day)
    return DAY_LABELS.get(num, day[:15])


def day_display(day: str) -> str:
    """Format a day string for display."""
    num = day_number(day)
    label = DAY_LABELS.get(num)
    if label:
        return f"{label} Feb 2026"
    return day


def time_sort_key(time_str: str) -> str:
    """Zero-pad a time string for proper lexicographic sorting."""
    parts = time_str.split(":")
    if len(parts) == 2:
        return f"{int(parts[0]):02d}:{parts[1]}"
    return time_str


def format_time_range(start: str, end: str, separator: str = "-") -> str:
    """Format a start/end time pair into a display string."""
    if end:
        return f"{start}{separator}{end}"
    return start


def parse_day_date(day_str: str) -> datetime | None:
    """Parse a day string into a datetime date."""
    iso_match = re.search(r"2026-02-(\d{2})", day_str)
    if iso_match:
        return datetime(2026, 2, int(iso_match.group(1)))
    feb_match = re.search(r"February\s+(\d+)", day_str)
    if feb_match:
        return datetime(2026, 2, int(feb_match.group(1)))
    for name, num in DAY_NAME_TO_NUM.items():
        if name in day_str.lower():
            return datetime(2026, 2, int(num))
    return None


def parse_time(time_str: str, base_date: datetime) -> datetime | None:
    """Parse a time like '10:00' into a datetime."""
    if not time_str:
        return None
    match = re.match(r"(\d{1,2}):(\d{2})", time_str)
    if match:
        return base_date.replace(hour=int(match.group(1)), minute=int(match.group(2)), second=0)
    return None
