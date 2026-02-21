from pathlib import Path

from textual.app import App
from textual.binding import Binding

from confoo.data_loader import DataLoader, load_speaker_ratings
from confoo.calendar_manager import CalendarManager
from confoo.models import SpeakerRating


CSS_PATH = Path(__file__).parent / "styles" / "app.tcss"


class ConFooApp(App):
    """ConFoo 2026 TUI Schedule Planner."""

    TITLE = "ConFoo 2026"
    SUB_TITLE = "Schedule Planner"
    CSS_PATH = CSS_PATH

    BINDINGS = [
        Binding("1", "show_schedule", "Schedule", show=True, priority=True),
        Binding("2", "show_calendar", "My Calendar", show=True, priority=True),
        Binding("3", "show_sync", "Sync", show=True, priority=True),
        Binding("q", "quit", "Quit", show=True, priority=True),
    ]

    def __init__(self):
        super().__init__()
        self.data_loader: DataLoader = DataLoader()
        self.calendar_manager: CalendarManager = CalendarManager()
        self.speaker_ratings: dict[str, SpeakerRating] = load_speaker_ratings()

    def on_mount(self) -> None:
        from confoo.screens.schedule import ScheduleScreen
        self.install_screen(ScheduleScreen(), "schedule")

        count = self.data_loader.session_count()
        source = self.data_loader.source_name
        if count > 0:
            self.notify(f"Loaded {count} sessions from {source}", severity="information")
        else:
            self.notify(
                "No data found. Run 'confoo sync' or add data/confoo2026.json",
                severity="warning",
            )
        self.push_screen("schedule")

    def action_show_schedule(self) -> None:
        self.switch_screen("schedule")

    def action_show_calendar(self) -> None:
        from confoo.screens.my_calendar import MyCalendarScreen
        self.push_screen(MyCalendarScreen())

    def action_show_sync(self) -> None:
        from confoo.screens.sync import SyncScreen
        self.push_screen(SyncScreen())

    def action_quit(self) -> None:
        self.data_loader.close()
        self.exit()
