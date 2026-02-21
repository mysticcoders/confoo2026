from functools import partial
from pathlib import Path

from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Header, Footer, DataTable, Static, TabbedContent, TabPane
from textual.containers import Vertical
from textual.binding import Binding

from confoo.models import Session
from confoo.day_utils import day_number, day_sort_key, time_sort_key, format_time_range, DAY_LABELS


class MyCalendarScreen(Screen):
    """Personal calendar screen showing selected sessions."""

    BINDINGS = [
        Binding("r", "remove_session", "Remove", show=True),
        Binding("e", "export_ical", "Export iCal", show=True),
        Binding("enter", "view_detail", "Details", show=True),
        Binding("escape", "go_back", "Back", show=True),
    ]

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(id="calendar-content"):
            yield Static("", id="calendar-header")
            yield TabbedContent(id="cal-tabs")
        yield Footer()

    def on_mount(self) -> None:
        self._load_data()

    def on_screen_resume(self) -> None:
        self._refresh()

    def _get_calendar_data(self) -> tuple[list[Session], dict[str, list[str]]]:
        """Fetch selected sessions and conflicts from the calendar manager."""
        all_sessions = self.app.data_loader.get_all_sessions()
        cal = self.app.calendar_manager
        selected = cal.get_selected_sessions(all_sessions)
        conflicts = cal.find_conflicts(all_sessions)
        return selected, conflicts

    def _update_header(self, count: int, conflict_count: int):
        """Update the calendar header with session and conflict counts."""
        header = self.query_one("#calendar-header", Static)
        header.update(
            f"[bold]My Calendar[/bold] - {count} session{'s' if count != 1 else ''}"
            + (f" - [red]{conflict_count} conflict{'s' if conflict_count != 1 else ''}[/red]" if conflict_count else "")
        )

    def _load_data(self):
        """Build calendar view from selected sessions."""
        selected, conflicts = self._get_calendar_data()
        self._update_header(len(selected), len(conflicts))

        days = sorted({s.day for s in selected if s.day}, key=day_sort_key)
        tabs = self.query_one("#cal-tabs", TabbedContent)

        for pane in list(tabs.query("TabPane")):
            tabs.remove_pane(pane.id)

        for day in days:
            num = day_number(day)
            label = DAY_LABELS.get(num, day[:15])
            tab_id = f"cal-day-{num}"
            pane = TabPane(label, id=tab_id)
            tabs.add_pane(pane)

        if days:
            first_num = day_number(days[0])
            tabs.active = f"cal-day-{first_num}"
            self.call_later(partial(self._populate_tab, selected, conflicts))

    def _refresh(self):
        """Refresh the calendar display."""
        selected, conflicts = self._get_calendar_data()
        self._update_header(len(selected), len(conflicts))
        self._populate_tab(selected, conflicts)

    def on_tabbed_content_tab_activated(self, event: TabbedContent.TabActivated) -> None:
        selected, conflicts = self._get_calendar_data()
        self.call_later(partial(self._populate_tab, selected, conflicts))

    def _populate_tab(self, selected: list[Session], conflicts: dict[str, list[str]]):
        """Populate the DataTable for the active tab."""
        tabs = self.query_one("#cal-tabs", TabbedContent)
        active_id = tabs.active
        if not active_id:
            return

        day_num = active_id.replace("cal-day-", "")
        pane = tabs.query_one(f"#{active_id}", TabPane)

        existing = pane.query("DataTable")
        if existing:
            table = existing.first()
        else:
            table = DataTable(id=f"cal-table-{day_num}")
            pane.mount(table)
            table.add_columns("Time", "Title", "Speaker", "Room", "Status")
            table.cursor_type = "row"

        table.clear()

        day_sessions = sorted(
            [s for s in selected if day_number(s.day) == day_num],
            key=lambda s: time_sort_key(s.start_time),
        )

        for session in day_sessions:
            time_str = format_time_range(session.start_time, session.end_time)

            status = "✓"
            if session.slug in conflicts:
                status = "[CONFLICT]"

            table.add_row(
                time_str, session.title, session.speaker_name,
                session.room, status,
                key=session.slug,
            )

    def action_remove_session(self) -> None:
        table = self._get_active_table()
        if not table or table.row_count == 0:
            return
        row_key, _ = table.coordinate_to_cell_key(table.cursor_coordinate)
        slug = row_key.value
        self.app.calendar_manager.remove(slug)
        self.notify("Session removed from calendar", severity="information")
        self._refresh()

    def action_export_ical(self) -> None:
        from confoo.export import export_ical

        all_sessions = self.app.data_loader.get_all_sessions()
        selected = self.app.calendar_manager.get_selected_sessions(all_sessions)
        if not selected:
            self.notify("No sessions to export", severity="warning")
            return

        output = Path.home() / "Downloads" / "confoo2026.ics"
        export_ical(selected, output)
        self.notify(f"Exported to {output}", severity="information")

    def action_view_detail(self) -> None:
        table = self._get_active_table()
        if not table or table.row_count == 0:
            return
        row_key, _ = table.coordinate_to_cell_key(table.cursor_coordinate)
        slug = row_key.value
        from confoo.screens.session_detail import SessionDetailScreen
        self.app.push_screen(SessionDetailScreen(slug))

    def action_go_back(self) -> None:
        self.app.pop_screen()

    def _get_active_table(self) -> DataTable | None:
        tabs = self.query_one("#cal-tabs", TabbedContent)
        active_id = tabs.active
        if not active_id:
            return None
        pane = tabs.query_one(f"#{active_id}", TabPane)
        tables = pane.query("DataTable")
        return tables.first() if tables else None
