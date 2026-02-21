from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Header, Footer, Static, Label
from textual.containers import VerticalScroll
from textual.binding import Binding

from confoo.day_utils import format_time_range


class SessionDetailScreen(Screen):
    """Detailed view of a single session."""

    BINDINGS = [
        Binding("a", "toggle_attend", "Add/Remove", show=True),
        Binding("escape", "go_back", "Back", show=True),
    ]

    def __init__(self, session_slug: str):
        super().__init__()
        self.session_slug = session_slug
        self._attend_widget: Static | None = None

    def compose(self) -> ComposeResult:
        yield Header()
        yield VerticalScroll(id="detail-container")
        yield Footer()

    def on_mount(self) -> None:
        self._populate()

    def _populate(self):
        """Fill the detail view with session data."""
        container = self.query_one("#detail-container", VerticalScroll)

        session = self.app.data_loader.get_session(self.session_slug)
        if not session:
            container.mount(Static("Session not found."))
            return

        cal = self.app.calendar_manager
        is_attending = cal.is_selected(session.slug)
        attend_text = "[bold green]✓ In your calendar[/]" if is_attending else "[dim]Not in your calendar[/dim]"

        container.mount(Static(f"[bold]{session.title}[/bold]"))

        meta_parts = []
        if session.day:
            meta_parts.append(f"[bold]Day:[/bold] {session.day}")
        if session.start_time:
            time_str = format_time_range(session.start_time, session.end_time, separator=" - ")
            meta_parts.append(f"[bold]Time:[/bold] {time_str}")
        if session.room:
            meta_parts.append(f"[bold]Room:[/bold] {session.room}")
        if session.language:
            meta_parts.append(f"[bold]Language:[/bold] {session.language}")
        if session.level:
            meta_parts.append(f"[bold]Level:[/bold] {session.level}")
        if session.tracks:
            meta_parts.append(f"[bold]Tracks:[/bold] {', '.join(session.tracks)}")
        if session.is_keynote:
            meta_parts.append("[bold yellow]KEYNOTE[/bold yellow]")
        container.mount(Static("\n".join(meta_parts)))

        self._attend_widget = Static(attend_text)
        container.mount(self._attend_widget)

        if session.abstract:
            container.mount(Static(""))
            container.mount(Label("[bold]Abstract[/bold]"))
            container.mount(Static(session.abstract))

        speaker = self.app.data_loader.get_speaker(session.speaker_slug) if session.speaker_slug else None
        if speaker or session.speaker_name:
            container.mount(Static(""))
            name = speaker.name if speaker else session.speaker_name
            container.mount(Static(f"[bold]Speaker: {name}[/bold]"))

            if speaker:
                speaker_meta = []
                if speaker.company:
                    speaker_meta.append(f"[bold]Company:[/bold] {speaker.company}")
                if speaker.country:
                    speaker_meta.append(f"[bold]Country:[/bold] {speaker.country}")
                if speaker.twitter:
                    speaker_meta.append(f"[bold]Twitter:[/bold] {speaker.twitter}")
                if speaker.website:
                    speaker_meta.append(f"[bold]Website:[/bold] {speaker.website}")
                if speaker_meta:
                    container.mount(Static("\n".join(speaker_meta)))

                if speaker.bio:
                    container.mount(Static(""))
                    container.mount(Label("[bold]Bio[/bold]"))
                    container.mount(Static(speaker.bio))

        rating = self.app.speaker_ratings.get(session.speaker_slug)
        if rating:
            rating_text = f"Speaker Rating: {rating.display} ({rating.badge})"
            if rating.note:
                rating_text += f"\n{rating.note}"
            container.mount(Static(""))
            container.mount(Static(rating_text))

    def action_toggle_attend(self) -> None:
        result = self.app.calendar_manager.toggle(self.session_slug)
        self.notify(
            "Added to calendar" if result else "Removed from calendar",
            severity="information",
        )
        if self._attend_widget:
            text = "[bold green]✓ In your calendar[/]" if result else "[dim]Not in your calendar[/dim]"
            self._attend_widget.update(text)

    def action_go_back(self) -> None:
        self.app.pop_screen()
