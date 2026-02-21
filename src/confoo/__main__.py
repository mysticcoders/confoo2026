import sys
import asyncio


def run_sync():
    """Run the scraper from the command line."""
    from confoo.db import ConfooDB
    from confoo.scraper import ConFooScraper
    from confoo.export import export_json_snapshot
    from confoo.data_loader import DATA_DIR

    print("ConFoo 2026 Sync")
    print("=" * 40)

    with ConfooDB() as db:
        scraper = ConFooScraper(db, log=print)
        asyncio.run(scraper.run_full_sync())

        json_path = DATA_DIR / "confoo2026.json"
        export_json_snapshot(db, json_path)
        print(f"JSON snapshot exported to {json_path}")


def run_app():
    """Launch the TUI application."""
    from confoo.app import ConFooApp
    app = ConFooApp()
    app.run()


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "sync":
        run_sync()
    else:
        run_app()


if __name__ == "__main__":
    main()
