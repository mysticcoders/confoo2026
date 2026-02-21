# ConFoo 2026 Schedule Planner

A terminal UI app for browsing the [ConFoo 2026](https://confoo.ca/en/2026) conference schedule, exploring sessions and speakers, and building your personal calendar with automatic conflict detection.

![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue)
![Textual TUI](https://img.shields.io/badge/TUI-Textual-green)

## Features

- Browse 197 sessions across 5 conference days with tabbed day views
- Search across all days by session title or speaker name
- Filter by any of the 25 tracks (AI, Security, Java, PHP, etc.)
- View full session details: abstract, speaker bio, company, social links
- Build a personal calendar with one-key add/remove
- Automatic conflict detection for overlapping sessions
- Export your schedule to iCal (`.ics`) for import into any calendar app
- Curated speaker ratings (S/A/B/C tiers) with star display
- Works offline with bundled JSON data -- no scraping required
- Optional live sync from confoo.ca for the latest schedule updates

## Prerequisites

- **Python 3.11+**
- **[uv](https://docs.astral.sh/uv/)** package manager

## Installation

### As a uv tool (recommended)

Install globally so the `confoo` command is available everywhere:

```bash
uv tool install git+<repo-url>
```

Or from a local checkout:

```bash
git clone <repo-url>
cd confoo2026
uv tool install .
```

Then run from anywhere:

```bash
confoo
```

To update later:

```bash
uv tool upgrade confoo2026
```

To uninstall:

```bash
uv tool uninstall confoo2026
```

### For development

```bash
git clone <repo-url>
cd confoo2026
uv sync
uv run confoo
```

### Optional: Live Sync

If you want to pull the latest data directly from confoo.ca:

```bash
# Install the browser engine (one-time setup for the tool environment)
uv tool run --from confoo2026 playwright install chromium

# Or if using a local dev checkout
uv run playwright install chromium

# Run a full sync (~4 minutes)
confoo sync
```

## Usage

```bash
confoo
```

### Navigating the App

The app has three main screens, accessible from anywhere via number keys:

| Key | Screen | Description |
|-----|--------|-------------|
| `1` | Schedule | Browse sessions by day, search, and filter |
| `2` | My Calendar | View your selected sessions and conflicts |
| `3` | Sync | Pull fresh data from confoo.ca |
| `q` | | Quit the app |

### Schedule Screen

This is the main view. Sessions are organized in day tabs (Mon-Fri).

| Key | Action |
|-----|--------|
| `/` | Search by title or speaker (searches across all days) |
| `Escape` | Clear search and return to day tabs |
| `t` | Cycle through track filters |
| `a` | Add or remove the selected session from your calendar |
| `Enter` | View full session details |

Sessions in your calendar show a bold green **✓** in the first column.

### Session Detail Screen

Full view of a session including the abstract, speaker bio, and your calendar status.

| Key | Action |
|-----|--------|
| `a` | Add or remove from your calendar |
| `Escape` | Go back |

### My Calendar Screen

Shows all your selected sessions organized by day, with conflict detection.

| Key | Action |
|-----|--------|
| `r` | Remove the selected session |
| `e` | Export calendar to `~/Downloads/confoo2026.ics` |
| `Enter` | View session details |
| `Escape` | Go back |

Sessions with time overlaps are flagged with `[CONFLICT]`.

### Sync Screen

Re-scrape confoo.ca for the latest schedule data. This runs a three-phase scraper that fetches the schedule grid, session details, and speaker profiles. Takes approximately 4 minutes.

## Speaker Ratings

You can curate speaker ratings by editing `data/speaker_ratings.json`:

```json
{
  "speaker-slug": {
    "tier": "S",
    "note": "Amazing live coder, always packed rooms"
  }
}
```

**Tiers:**

| Tier | Label | Display |
|------|-------|---------|
| S | Exceptional | ★★★★★ |
| A | Excellent | ★★★★ |
| B | Good | ★★★ |
| C | Average | ★★ |

Ratings appear in the schedule table and on session detail screens.

## Data Storage

| Location | Contents |
|----------|----------|
| `data/confoo2026.json` | Bundled schedule snapshot (works offline) |
| `data/speaker_ratings.json` | Your curated speaker ratings |
| `~/.local/share/confoo2026/confoo.db` | SQLite database (created by sync) |
| `~/.local/share/confoo2026/my_calendar.json` | Your personal session selections |
| `~/Downloads/confoo2026.ics` | Exported iCal file |

## Conference Info

**ConFoo 2026** -- February 23-27, 2026 -- Montreal, Canada

- Monday & Tuesday: Full-day workshops
- Wednesday through Friday: Main conference (7 time slots per day, 10 parallel sessions)
- 197 sessions, 107 speakers, 25 tracks
- Sessions are 45 minutes, primarily in English (some in French)

## License

MIT
