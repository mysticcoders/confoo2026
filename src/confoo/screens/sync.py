from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Header, Footer, Static, Button, RichLog
from textual.containers import Vertical
from textual.binding import Binding


class SyncScreen(Screen):
    """Screen to trigger and monitor a full scrape sync."""

    BINDINGS = [
        Binding("escape", "go_back", "Back", show=True),
    ]

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(id="sync-container"):
            yield Static("", id="sync-status")
            yield Button("Start Full Sync", id="sync-button", variant="primary")
            yield RichLog(id="sync-log", highlight=True, markup=True)
        yield Footer()

    def on_mount(self) -> None:
        self._update_status()

    def _update_status(self):
        """Show last sync time."""
        last_sync = self.app.data_loader.get_last_sync()
        status = self.query_one("#sync-status", Static)
        source = self.app.data_loader.source_name
        if last_sync:
            status.update(f"[bold]Data source:[/bold] {source}\n[bold]Last sync:[/bold] {last_sync}")
        else:
            status.update(f"[bold]Data source:[/bold] {source}\n[bold]Last sync:[/bold] Never")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "sync-button":
            event.button.disabled = True
            event.button.label = "Syncing..."
            self._run_sync()

    def _run_sync(self):
        """Run the sync in a worker thread."""
        self.run_worker(self._do_sync(), exclusive=True)

    async def _do_sync(self):
        """Execute the full sync process."""
        log = self.query_one("#sync-log", RichLog)
        log.clear()

        def log_msg(msg: str):
            self.call_from_thread(log.write, msg)

        try:
            from confoo.db import ConfooDB
            from confoo.scraper import ConFooScraper
            from confoo.export import export_json_snapshot
            from confoo.data_loader import DATA_DIR

            log_msg("Initializing database...")
            with ConfooDB() as db:
                scraper = ConFooScraper(db, log=log_msg)

                log_msg("Starting full sync...")
                await scraper.run_full_sync()

                json_path = DATA_DIR / "confoo2026.json"
                export_json_snapshot(db, json_path)
                log_msg(f"JSON snapshot exported to {json_path}")

            log_msg("")
            log_msg("[bold green]Sync complete! Restart the app to see updated data.[/bold green]")
        except Exception as e:
            log_msg(f"[bold red]Error: {e}[/bold red]")
        finally:
            button = self.query_one("#sync-button", Button)
            button.disabled = False
            button.label = "Start Full Sync"
            self._update_status()

    def action_go_back(self) -> None:
        self.app.pop_screen()
