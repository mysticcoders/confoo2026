import asyncio
from typing import Callable

from confoo.models import Speaker, Session, SpecialEvent
from confoo.db import ConfooDB

BASE_URL = "https://confoo.ca"
SCHEDULE_URL = f"{BASE_URL}/en/2026/schedule"
POLITENESS_DELAY = 0.5

GRID_EXTRACTION_JS = """
() => {
  const days = document.querySelectorAll('.schedule-day');
  const allSessions = [];
  const allEvents = [];

  days.forEach((dayEl, dayIdx) => {
    const h2 = dayEl.previousElementSibling;
    const dayText = h2 ? h2.textContent.trim() : 'Day ' + dayIdx;

    const headerRow = dayEl.querySelector('.row:first-child');
    const roomEls = headerRow ? headerRow.querySelectorAll('.room') : [];
    const rooms = Array.from(roomEls).map(r => r.textContent.trim());

    const rows = dayEl.querySelectorAll('.row');
    rows.forEach(row => {
      const timeEl = row.querySelector('.time');
      if (!timeEl) return;

      const timeText = timeEl.textContent.trim();
      const times = timeText.match(/\\d+:\\d+/g) || [];
      const startTime = times[0] || '';
      const endTime = times[1] || '';

      const lunchEl = row.querySelector('.lunch');
      if (lunchEl) {
        allEvents.push({
          day: dayText, start_time: startTime,
          end_time: endTime, name: lunchEl.textContent.trim(),
        });
        return;
      }

      const slots = row.querySelectorAll('.slot');
      slots.forEach((slot, slotIdx) => {
        const sessionEl = slot.querySelector('.session a');
        if (!sessionEl) return;

        const href = sessionEl.getAttribute('href') || '';
        const slugMatch = href.match(/\\/en\\/2026\\/session\\/(.+?)$/);
        const slug = slugMatch ? slugMatch[1] : '';
        const title = sessionEl.textContent.trim();

        const speakerEl = slot.querySelector('.speaker a');
        const speakerHref = speakerEl ? speakerEl.getAttribute('href') || '' : '';
        const speakerSlugMatch = speakerHref.match(/\\/en\\/speaker\\/(.+?)$/);
        const speakerSlug = speakerSlugMatch ? speakerSlugMatch[1] : '';
        const speakerName = speakerEl ? speakerEl.textContent.trim() : '';

        const sessionTypeEl = slot.querySelector('.session-type');
        const sessionType = sessionTypeEl ? sessionTypeEl.textContent.trim() : '';
        const isKeynote = slot.classList.contains('keynote') || sessionType.toLowerCase() === 'keynote';

        const roomSpan = slot.querySelector('.room');
        const room = roomSpan ? roomSpan.textContent.trim() : (rooms[slotIdx] || '');

        const tagEls = slot.querySelectorAll('.tag');
        const tracks = Array.from(tagEls)
          .map(t => t.getAttribute('title') || '')
          .filter(Boolean);

        allSessions.push({
          slug, title, day: dayText, start_time: startTime, end_time: endTime,
          room, speaker_slug: speakerSlug, speaker_name: speakerName,
          is_keynote: isKeynote, tracks,
        });
      });
    });
  });

  return { sessions: allSessions, events: allEvents };
}
"""


class ConFooScraper:
    """Three-phase scraper for the ConFoo 2026 schedule."""

    def __init__(self, db: ConfooDB, log: Callable[[str], None] | None = None):
        self.db = db
        self.log = log or print
        self._speaker_companies: dict[str, str] = {}
        self._speaker_bios: dict[str, str] = {}

    def _session_from_grid(self, slug: str, grid: dict, detail: dict | None = None) -> Session:
        """Build a Session from grid data, optionally enriched with detail-page data."""
        return Session(
            slug=slug,
            title=grid["title"],
            abstract=detail["abstract"] if detail else "",
            day=grid["day"],
            start_time=grid["start_time"],
            end_time=grid["end_time"],
            room=grid["room"],
            language=detail["language"] if detail else "",
            level=detail["level"] if detail else "",
            is_keynote=grid["is_keynote"],
            speaker_slug=grid["speaker_slug"],
            speaker_name=grid["speaker_name"],
            tracks=grid["tracks"],
        )

    async def run_full_sync(self):
        """Execute all three scraping phases."""
        from playwright.async_api import async_playwright

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent="ConFoo2026-TUI-Planner/0.1 (personal schedule tool)"
            )
            page = await context.new_page()

            try:
                grid_sessions, speaker_slugs = await self._phase1_schedule_grid(page)

                if not grid_sessions:
                    self.log("WARNING: No sessions found. Site layout may have changed. Aborting to preserve existing data.")
                    return

                self.db.clear_all()
                await self._phase2_session_details(page, grid_sessions)
                await self._phase3_speaker_profiles(page, speaker_slugs)

                self.db.update_last_sync()
                self.db.commit()
                self.log(f"Sync complete. {self.db.session_count()} sessions in database.")
            finally:
                await browser.close()

    async def _phase1_schedule_grid(self, page) -> tuple[dict[str, dict], set[str]]:
        """Phase 1: Extract all schedule data from the grid via JS evaluation."""
        self.log("Phase 1: Loading schedule grid...")
        await page.goto(SCHEDULE_URL, wait_until="networkidle", timeout=30000)
        await page.wait_for_selector(".schedule-day", timeout=10000)

        result = await page.evaluate(GRID_EXTRACTION_JS)
        raw_sessions = result["sessions"]
        events = result["events"]

        self.log(f"  Found {len(raw_sessions)} session slots, {len(events)} events")

        grid_sessions: dict[str, dict] = {}
        speaker_slugs: set[str] = set()

        for s in raw_sessions:
            slug = s["slug"]
            if not slug:
                continue

            if s.get("speaker_slug"):
                speaker_slugs.add(s["speaker_slug"])

            if slug in grid_sessions:
                existing = grid_sessions[slug]
                if s["start_time"] < existing["start_time"]:
                    existing["start_time"] = s["start_time"]
                if s["end_time"] > existing["end_time"]:
                    existing["end_time"] = s["end_time"]
                for t in s.get("tracks", []):
                    if t not in existing["tracks"]:
                        existing["tracks"].append(t)
            else:
                grid_sessions[slug] = {
                    "slug": slug,
                    "title": s["title"],
                    "day": s["day"],
                    "start_time": s["start_time"],
                    "end_time": s["end_time"],
                    "room": s["room"],
                    "speaker_slug": s.get("speaker_slug", ""),
                    "speaker_name": s.get("speaker_name", ""),
                    "is_keynote": s.get("is_keynote", False),
                    "tracks": list(s.get("tracks", [])),
                }

        for event in events:
            self.db.upsert_special_event(SpecialEvent(
                day=event["day"],
                start_time=event["start_time"],
                end_time=event["end_time"],
                name=event["name"],
            ))

        self.db.commit()
        self.log(f"  {len(grid_sessions)} unique sessions, {len(speaker_slugs)} unique speakers, {len(events)} events")
        return grid_sessions, speaker_slugs

    async def _phase2_session_details(self, page, grid_sessions: dict[str, dict]):
        """Phase 2: Fetch abstracts and language/level from session detail pages."""
        slugs = list(grid_sessions.keys())
        total = len(slugs)
        self.log(f"Phase 2: Scraping {total} session detail pages...")

        for i, slug in enumerate(slugs, 1):
            if i % 20 == 0 or i == 1:
                self.log(f"  Session {i}/{total}...")
            url = f"{BASE_URL}/en/2026/session/{slug}"
            grid = grid_sessions[slug]

            detail = None
            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=15000)
                detail = await self._extract_session_detail(page)

                if grid.get("speaker_slug"):
                    if detail.get("speaker_company"):
                        self._speaker_companies[grid["speaker_slug"]] = detail["speaker_company"]
                    if detail.get("speaker_bio"):
                        self._speaker_bios[grid["speaker_slug"]] = detail["speaker_bio"]
            except Exception as e:
                self.log(f"  Error scraping {url}: {e}")

            self.db.upsert_session(self._session_from_grid(slug, grid, detail))

            if i % 50 == 0:
                self.db.commit()

            await asyncio.sleep(POLITENESS_DELAY)

        self.db.commit()
        self.log(f"  Done. {self.db.session_count()} sessions saved.")

    async def _extract_session_detail(self, page) -> dict:
        """Extract abstract, language, and level from a session detail page."""
        result = await page.evaluate("""
        () => {
            let abstract = '';
            let language = '';
            let level = '';

            // Parse language and level from paragraphs
            const paragraphs = document.querySelectorAll('p');
            for (const p of paragraphs) {
                const text = p.textContent.trim();
                if (text.match(/(English|French)\\s+(session|training)/i)) {
                    const langMatch = text.match(/(English|French)/i);
                    if (langMatch) language = langMatch[1];
                    const levelMatch = text.match(/(Beginner|Intermediate|Advanced)/i);
                    if (levelMatch) level = levelMatch[1];
                    break;
                }
            }

            // Abstract: find content divs nested in the main content area
            const selectors = [
                '.content > div > div > div > div',
                '.col-md-12 > div > div > div > div'
            ];
            for (const sel of selectors) {
                const divs = document.querySelectorAll(sel);
                for (const div of divs) {
                    if (div.querySelector('h2') || div.querySelector('a[href*="share"]')) continue;
                    const text = div.textContent.trim();
                    if (text.length > 50 &&
                        !text.includes('View all') &&
                        !text.includes('Share on') &&
                        !text.includes('Other training')) {
                        abstract = text;
                        break;
                    }
                }
                if (abstract) break;
            }

            // Fallback: search for any substantial text div
            if (!abstract) {
                const content = document.querySelector('.content');
                if (content) {
                    const deepDivs = content.querySelectorAll('div');
                    for (const div of deepDivs) {
                        if (div.children.length > 3) continue;
                        const text = div.textContent.trim();
                        if (text.length > 80 &&
                            !text.includes('View all') &&
                            !text.includes('Share on') &&
                            !text.includes('Home /') &&
                            !text.includes('Sponsored by') &&
                            !text.includes('Other training') &&
                            !div.querySelector('h2')) {
                            abstract = text;
                            break;
                        }
                    }
                }
            }

            // Speaker info from the speaker section on session page
            let speakerCompany = '';
            let speakerBio = '';
            const h2s = document.querySelectorAll('h2');
            for (const h2 of h2s) {
                const parent = h2.parentElement;
                if (!parent) continue;
                const speakerLink = parent.querySelector('a[href*="/speaker/"]');
                if (!speakerLink) continue;
                const paras = parent.querySelectorAll('p');
                for (const p of paras) {
                    const text = p.textContent.trim();
                    if (text.includes('Read More') || text.length < 3) continue;
                    if (!speakerCompany && text.length < 120) {
                        speakerCompany = text;
                    } else if (!speakerBio && text.length > 50) {
                        speakerBio = text;
                    }
                }
                break;
            }

            return { abstract, language, level, speaker_company: speakerCompany, speaker_bio: speakerBio };
        }
        """)

        return {
            "abstract": result.get("abstract", ""),
            "language": result.get("language", ""),
            "level": result.get("level", ""),
            "speaker_company": result.get("speaker_company", ""),
            "speaker_bio": result.get("speaker_bio", ""),
        }

    async def _phase3_speaker_profiles(self, page, speaker_slugs: set[str]):
        """Phase 3: Scrape individual speaker profile pages."""
        slugs = sorted(speaker_slugs)
        total = len(slugs)
        self.log(f"Phase 3: Scraping {total} speaker profiles...")

        for i, slug in enumerate(slugs, 1):
            if i % 20 == 0 or i == 1:
                self.log(f"  Speaker {i}/{total}...")
            url = f"{BASE_URL}/en/speaker/{slug}"
            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=15000)
                speaker = await self._extract_speaker(page, slug)
                company = self._speaker_companies.get(slug, "")
                if company:
                    speaker.company = company
                if not speaker.bio:
                    speaker.bio = self._speaker_bios.get(slug, "")
                self.db.upsert_speaker(speaker)
                if i % 50 == 0:
                    self.db.commit()
            except Exception as e:
                self.log(f"  Error scraping {url}: {e}")

            await asyncio.sleep(POLITENESS_DELAY)

        self.db.commit()
        self.log(f"  Done. Speaker profiles saved.")

    async def _extract_speaker(self, page, slug: str) -> Speaker:
        """Extract speaker profile from a speaker page using JS evaluation."""
        result = await page.evaluate("""
        () => {
            const h1 = document.querySelector('h1');
            const name = h1 ? h1.textContent.trim() : '';

            // Country: look for a span inside a paragraph (flag + country name)
            let country = '';
            const content = document.querySelector('.content') || document.querySelector('main');
            if (content) {
                const paras = content.querySelectorAll('p');
                for (const p of paras) {
                    const span = p.querySelector('span');
                    if (span) {
                        const text = span.textContent.trim();
                        if (text.length > 2 && text.length < 50 &&
                            !text.includes('session') && !text.includes('training')) {
                            country = text;
                            break;
                        }
                    }
                }
            }

            // Bio: find the first substantial paragraph text
            let bio = '';
            if (content) {
                const paras = content.querySelectorAll('p');
                for (const p of paras) {
                    const text = p.textContent.trim();
                    if (text.length > 50 &&
                        !text.match(/session\\s*-|training\\s*-/i) &&
                        !text.includes('Share on') &&
                        !text.includes('Read More') &&
                        !text.includes(country)) {
                        bio = text;
                        break;
                    }
                }
            }

            // Photo: image with speaker name as alt
            let photo_url = '';
            if (name) {
                const img = document.querySelector('img[alt="' + name.replace(/"/g, '\\\\"') + '"]');
                if (img) photo_url = img.src || '';
            }

            // Social links
            let twitter = '';
            const links = document.querySelectorAll('a[href]');
            for (const a of links) {
                const href = a.getAttribute('href') || '';
                if ((href.includes('twitter.com') || href.includes('x.com/')) &&
                    !href.includes('intent/tweet') && !href.includes('confooca')) {
                    twitter = href;
                    break;
                }
            }

            return { name, country, bio, photo_url, twitter };
        }
        """)

        return Speaker(
            slug=slug,
            name=result.get("name", ""),
            country=result.get("country", ""),
            bio=result.get("bio", ""),
            photo_url=result.get("photo_url", ""),
            twitter=result.get("twitter", ""),
        )
