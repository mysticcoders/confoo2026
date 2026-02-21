from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Header, Footer, DataTable, Input, Label, Static, TabbedContent, TabPane
from textual.containers import Horizontal, Vertical
from textual.binding import Binding
from rich.text import Text

from confoo.models import Session
from confoo.day_utils import day_number, day_sort_key, make_tab_label, time_sort_key, format_time_range, CONFERENCE_DAYS, DAY_LABELS


class ScheduleScreen(Screen):
    """Main schedule browsing screen."""

    BINDINGS = [
        Binding("slash", "focus_search", "Search", show=True),
        Binding("a", "toggle_attend", "Add/Remove", show=True),
        Binding("t", "cycle_track", "Filter Track", show=True),
        Binding("enter", "view_detail", "Details", show=True),
        Binding("escape", "clear_search", "Clear", show=False),
    ]

    def __init__(self):
        super().__init__()
        self._sessions: list[Session] = []
        self._days: list[str] = []
        self._tracks: list[str] = []
        self._current_track_idx: int = -1
        self._search_text: str = ""

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(id="schedule-content"):
            with Horizontal(id="search-bar"):
                yield Label("Search:")
                yield Input(placeholder="Filter by title or speaker...", id="search-input")
                yield Static("All Tracks", id="track-filter")
            yield TabbedContent(id="day-tabs")
            yield DataTable(id="search-results")
        yield Footer()

    def on_mount(self) -> None:
        search_table = self.query_one("#search-results", DataTable)
        search_table.display = False
        search_table.add_columns("Cal", "Day", "Time", "Title", "Speaker", "Track", "Room", "Rating")
        search_table.cursor_type = "row"
        self._load_data()

    def _load_data(self):
        """Load sessions from the data loader."""
        loader = self.app.data_loader
        self._sessions = loader.get_all_sessions()
        self._days = sorted(loader.get_all_days(), key=day_sort_key)
        self._tracks = loader.get_all_tracks()

        tabs = self.query_one("#day-tabs", TabbedContent)
        for day in self._days:
            label = make_tab_label(day)
            tab_id = f"day-{day_number(day)}"
            pane = TabPane(label, id=tab_id)
            tabs.add_pane(pane)

        if self._days:
            first_conf = None
            for day in self._days:
                if day_number(day) in CONFERENCE_DAYS:
                    first_conf = day
                    break
            target = first_conf or self._days[0]
            tab_id = f"day-{day_number(target)}"
            tabs.active = tab_id
            self.call_later(self._populate_active_tab)

    def on_tabbed_content_tab_activated(self, event: TabbedContent.TabActivated) -> None:
        self.call_later(self._populate_active_tab)

    def _build_session_row(self, session: Session) -> tuple:
        """Build the common row fields for a session: (cal, time, title, speaker, track, room, rating)."""
        ratings = self.app.speaker_ratings
        calendar = self.app.calendar_manager

        time_str = format_time_range(session.start_time, session.end_time)
        track = session.tracks[0] if session.tracks else ""
        rating_info = ratings.get(session.speaker_slug)
        rating_display = rating_info.display if rating_info else ""
        cal_mark = Text("✓", style="bold green") if calendar.is_selected(session.slug) else Text("")
        title = f"[KEYNOTE] {session.title}" if session.is_keynote else session.title

        return (cal_mark, time_str, title, session.speaker_name, track, session.room, rating_display)

    def _populate_active_tab(self):
        """Populate the DataTable for the currently active day tab."""
        if self._search_text:
            self._populate_search_results()
            return

        search_table = self.query_one("#search-results", DataTable)
        search_table.display = False
        tabs = self.query_one("#day-tabs", TabbedContent)
        tabs.display = True

        active_id = tabs.active
        if not active_id:
            return

        day_num = active_id.replace("day-", "")
        pane = tabs.query_one(f"#{active_id}", TabPane)

        existing = pane.query("DataTable")
        if existing:
            table = existing.first()
        else:
            table = DataTable(id=f"table-{day_num}")
            pane.mount(table)
            table.add_columns("Cal", "Time", "Title", "Speaker", "Track", "Room", "Rating")
            table.cursor_type = "row"

        table.clear()
        for session in self._get_filtered_sessions(day_num):
            table.add_row(*self._build_session_row(session), key=session.slug)

    def _populate_search_results(self):
        """Populate the cross-day search results table."""
        tabs = self.query_one("#day-tabs", TabbedContent)
        tabs.display = False
        search_table = self.query_one("#search-results", DataTable)
        search_table.display = True
        search_table.clear()

        query = self._search_text.lower()
        sessions = [
            s for s in self._sessions
            if query in s.title.lower() or query in s.speaker_name.lower()
        ]

        if self._current_track_idx >= 0:
            track = self._tracks[self._current_track_idx]
            sessions = [s for s in sessions if track in s.tracks]

        sessions.sort(key=lambda s: (day_sort_key(s.day), time_sort_key(s.start_time)))

        for session in sessions:
            cal, time_str, title, speaker, track, room, rating = self._build_session_row(session)
            day_label = DAY_LABELS.get(day_number(session.day), session.day[:10])
            search_table.add_row(
                cal, day_label, time_str, title, speaker, track, room, rating,
                key=session.slug,
            )

    def _get_filtered_sessions(self, day_num: str) -> list[Session]:
        """Get sessions for a day, applying track filter and sorting by time."""
        sessions = [
            s for s in self._sessions
            if day_number(s.day) == day_num
        ]

        if self._current_track_idx >= 0:
            track = self._tracks[self._current_track_idx]
            sessions = [s for s in sessions if track in s.tracks]

        sessions.sort(key=lambda s: time_sort_key(s.start_time))
        return sessions

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "search-input":
            self._search_text = event.value
            self._populate_active_tab()

    def action_focus_search(self) -> None:
        self.query_one("#search-input", Input).focus()

    def action_clear_search(self) -> None:
        inp = self.query_one("#search-input", Input)
        inp.value = ""
        self._search_text = ""
        self._populate_active_tab()

    def action_cycle_track(self) -> None:
        if not self._tracks:
            return
        self._current_track_idx += 1
        if self._current_track_idx >= len(self._tracks):
            self._current_track_idx = -1

        label = self.query_one("#track-filter", Static)
        if self._current_track_idx < 0:
            label.update("All Tracks")
        else:
            label.update(self._tracks[self._current_track_idx])
        self._populate_active_tab()

    def action_toggle_attend(self) -> None:
        table = self._get_active_table()
        if not table or table.row_count == 0:
            return
        row_key, _ = table.coordinate_to_cell_key(table.cursor_coordinate)
        slug = row_key.value
        self.app.calendar_manager.toggle(slug)
        self._populate_active_tab()

    def action_view_detail(self) -> None:
        table = self._get_active_table()
        if not table or table.row_count == 0:
            return
        row_key, _ = table.coordinate_to_cell_key(table.cursor_coordinate)
        slug = row_key.value
        from confoo.screens.session_detail import SessionDetailScreen
        self.app.push_screen(SessionDetailScreen(slug))

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        slug = event.row_key.value
        from confoo.screens.session_detail import SessionDetailScreen
        self.app.push_screen(SessionDetailScreen(slug))

    def _get_active_table(self) -> DataTable | None:
        """Get the currently visible DataTable (search results or day tab)."""
        search_table = self.query_one("#search-results", DataTable)
        if search_table.display:
            return search_table

        tabs = self.query_one("#day-tabs", TabbedContent)
        active_id = tabs.active
        if not active_id:
            return None
        pane = tabs.query_one(f"#{active_id}", TabPane)
        tables = pane.query("DataTable")
        return tables.first() if tables else None

    def refresh_schedule(self):
        """Called when returning from detail screen or after calendar change."""
        self._populate_active_tab()
