from dataclasses import dataclass, field


@dataclass
class Speaker:
    """A conference speaker."""

    slug: str
    name: str
    company: str = ""
    country: str = ""
    bio: str = ""
    photo_url: str = ""
    website: str = ""
    twitter: str = ""


@dataclass
class Session:
    """A conference session."""

    slug: str
    title: str
    abstract: str = ""
    day: str = ""
    start_time: str = ""
    end_time: str = ""
    room: str = ""
    language: str = ""
    level: str = ""
    is_keynote: bool = False
    speaker_slug: str = ""
    speaker_name: str = ""
    tracks: list[str] = field(default_factory=list)


TIER_STARS = {"S": "★★★★★", "A": "★★★★", "B": "★★★", "C": "★★"}
TIER_BADGES = {"S": "Exceptional", "A": "Excellent", "B": "Good", "C": "Average"}


@dataclass
class SpeakerRating:
    """Curated speaker quality rating."""

    slug: str
    tier: str  # "S", "A", "B", "C"
    note: str = ""

    @property
    def display(self) -> str:
        """Formatted rating string like 'S ★★★★★'."""
        stars = TIER_STARS.get(self.tier, "")
        return f"{self.tier} {stars}"

    @property
    def badge(self) -> str:
        """Human-readable tier label like 'Exceptional'."""
        return TIER_BADGES.get(self.tier, "")


@dataclass
class SpecialEvent:
    """Non-session schedule event (lunch, networking, etc.)."""

    id: int = 0
    day: str = ""
    start_time: str = ""
    end_time: str = ""
    name: str = ""
