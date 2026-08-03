# Recruiter Agency - Job Board Service
#
# Scrapes Jobs.ch (Switzerland's largest job board) for listings.
# Uses Playwright (headless Chromium) to render the JS-heavy page.

from __future__ import annotations

import asyncio
import concurrent.futures
import re
from typing import Any, Dict, List, Optional

from playwright.async_api import async_playwright

TIMEOUT = 30000
JOBS_CH_BASE = "https://www.jobs.ch/en/vacancies/"


def _run_async(coro):
    """Run an async coroutine, handling event loop conflicts.

    If we are already inside a running asyncio loop (e.g. Streamlit's
    Tornado server), Playwright's sync API will refuse to run.  This
    helper detects that case and farms the work out to a fresh thread
    with its own event loop so that async_playwright works correctly.
    """
    try:
        asyncio.get_running_loop()
        with concurrent.futures.ThreadPoolExecutor(1) as pool:
            return pool.submit(asyncio.run, coro).result()
    except RuntimeError:
        return asyncio.run(coro)


def _parse_salary(text: str) -> Optional[str]:
    """Extract salary info from text."""
    patterns = [
        r"(CHF\s*\d{2,3}[kK'']?\s*(?:-|–|to)\s*\d{2,3}[kK'']?)",
        r"(\d{2,3}[kK]\s*(?:-|–|to)\s*\d{2,3}[kK])",
        r"(CHF\s*[\d,']+\s*(?:-|–|to)\s*[\d,']+)",
        r"(\$\s*\d{2,3}[kK]\s*(?:-|–|to)\s*\d{2,3}[kK])",
        r"(\d{2,3})\s*(?:-|–|to)\s*(\d{2,3})\s*k",
    ]
    for p in patterns:
        m = re.search(p, text, re.IGNORECASE)
        if m:
            return m.group(0)
    return None


# ── Browser Lifecycle ─────────────────────────────────────────────────


async def _browser_context():
    """Return a (playwright, browser, context, page) tuple (async)."""
    p = await async_playwright().__aenter__()
    browser = await p.chromium.launch(
        headless=True,
        args=["--disable-blink-features=AutomationControlled"],
    )
    context = await browser.new_context(
        user_agent=(
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/131.0.0.0 Safari/537.36"
        ),
        viewport={"width": 1920, "height": 1080},
        locale="en",
    )
    page = await context.new_page()
    await page.add_init_script(
        'Object.defineProperty(navigator, "webdriver", {get: () => undefined})'
    )
    return p, browser, context, page


async def _close_browser(p, browser, context):
    """Safely close the Playwright browser (async)."""
    try:
        await context.close()
    except Exception:
        pass
    try:
        await browser.close()
    except Exception:
        pass
    try:
        await p.__aexit__(None, None, None)
    except Exception:
        pass


# ── Jobs.ch Scraper ──────────────────────────────────────────────────


def _build_url(query: str, region: str = "") -> str:
    """Build search URL for jobs.ch."""
    term = query.strip().lower().replace(" ", "+") or "data+scientist"
    url = f"{JOBS_CH_BASE}?term={term}"
    if region:
        url += f"&region={region}"
    return url


async def _scrape_jobs_ch(
    query: str = "", limit: int = 5, region: str = "zurich"
) -> List[Dict[str, Any]]:
    """Scrape job listings from Jobs.ch using Playwright (headless Chromium)."""
    url = _build_url(query, region)

    last_error = None
    for attempt in range(2):
        p, browser, context, page = await _browser_context()
        try:
            await page.route(
                re.compile(r"\.(png|jpg|jpeg|gif|svg|woff|woff2|ttf|eot)"),
                lambda route: route.abort(),
            )
            await page.goto(url, timeout=TIMEOUT, wait_until="load")
            await page.wait_for_timeout(3000)

            jobs = await page.evaluate(
                """(queryLimit) => {
                    const cards = document.querySelectorAll('[data-cy="vacancy-serp-item"]');
                    const results = [];

                    for (const card of cards) {
                        if (results.length >= queryLimit) break;

                        const link = card.closest('a');
                        const href = link ? link.getAttribute('href') : '';

                        const lines = card.innerText
                            .split('\\n')
                            .map(l => l.trim())
                            .filter(l => l);

                        if (lines.length < 3) continue;

                        let title = '';
                        let company = '';
                        let location = '';
                        let timestamp = '';

                        if (/ago|week|day|month/i.test(lines[0])) {
                            timestamp = lines[0];
                            title = lines[1] || '';
                        } else {
                            title = lines[0];
                        }

                        for (let i = 0; i < lines.length; i++) {
                            const line = lines[i];
                            if (line.startsWith('Place of work:')) {
                                location = lines[i + 1] || '';
                            }
                        }

                        for (let i = 0; i < lines.length; i++) {
                            if (lines[i].startsWith('Contract type:')) {
                                company = lines[i + 2] || '';
                                if (company === 'Promoted' && lines.length > i + 3) {
                                    company = lines[i + 3] || '';
                                }
                                break;
                            }
                        }

                        const fullUrl = href && !href.startsWith('http')
                            ? 'https://www.jobs.ch' + href
                            : (href || '');

                        results.push({
                            title: title,
                            company: company,
                            location: location,
                            url: fullUrl,
                            source: 'jobs_ch',
                            posted_date: timestamp,
                        });
                    }

                    return results;
                }""",
                limit,
            )

            return jobs[:limit]

        except Exception as e:
            last_error = e
            print(f"[scraper] Jobs.ch attempt {attempt + 1} failed: {e}")
        finally:
            await _close_browser(p, browser, context)

    print(f"[scraper] Jobs.ch failed after 2 attempts: {last_error}")
    return []


def scrape_jobs_ch(
    query: str = "", limit: int = 5, region: str = "zurich"
) -> List[Dict[str, Any]]:
    """Sync wrapper — scrape job listings from Jobs.ch."""
    return _run_async(_scrape_jobs_ch(query=query, limit=limit, region=region))


# ── Generic Page Scraper ──────────────────────────────────────────────


async def _fetch_jd_from_url(url: str) -> Dict[str, Any]:
    """Fetch a job posting URL and extract the JD text using Playwright."""
    p, browser, context, page = await _browser_context()

    try:
        await page.goto(url, timeout=TIMEOUT, wait_until="load")
        await page.wait_for_timeout(3000)

        try:
            await page.wait_for_selector(
                "main, article, .job-description, .description, .content",
                timeout=5000,
            )
        except Exception:
            pass

        body = await page.query_selector(
            "main, article, .job-description, .description, .content"
        )
        if not body:
            body = await page.query_selector("body")

        text = await body.inner_text() if body else ""
        raw_title = await page.title() or ""
        salary = _parse_salary(text)

        company = ""
        for sel in [".company", ".employer", "[class*=company]", ".top-card-layout__short-description"]:
            el = await page.query_selector(sel)
            if el:
                company = (await el.inner_text()).strip()[:100]
                break

        # Heuristic Inference from description text if selectors failed
        inferred_title = ""
        inferred_location = ""
        if text:
            lines = [l.strip() for l in text.split("\n") if l.strip()]
            if lines:
                # Often Line 0 is Title, Line 1 is Company + Location
                if not inferred_title and len(lines) > 0:
                    inferred_title = lines[0][:100]

                if not company and len(lines) > 1:
                    # Look for "Company Name  Location" pattern (LinkedIn style)
                    parts = re.split(r"\s{2,}", lines[1])
                    if parts:
                        company = parts[0][:100]
                        if len(parts) > 1:
                            inferred_location = parts[1][:100]

        # Final assembly
        final_title = inferred_title or raw_title or "Unknown"
        if "hiring" in final_title.lower() and "LinkedIn" in final_title:
             # Clean up LinkedIn-style page titles if possible
             if inferred_title:
                 final_title = inferred_title

        return {
            "url": url,
            "description": text[:5000],
            "title": final_title[:100],
            "company": company[:100] or "Unknown",
            "location": inferred_location or None,
            "salary_range": salary,
        }

    except Exception as e:
        print(f"[scraper] Failed to fetch JD from {url}: {e}")
        return {
            "url": url,
            "description": "",
            "title": "Unknown",
            "company": "Unknown",
        }
    finally:
        await _close_browser(p, browser, context)


def fetch_jd_from_url(url: str) -> Dict[str, Any]:
    """Sync wrapper — fetch a job posting URL and extract the JD text."""
    return _run_async(_fetch_jd_from_url(url))


async def _batch_fetch_descriptions(urls: List[str]) -> Dict[str, str]:
    """Fetch descriptions for multiple URLs using a single shared browser.

    Visits each URL sequentially within one browser session, extracts
    the main content text (up to 5000 chars), and returns a dict mapping
    URL -> description text (empty string on failure).

    Limits to 25 URLs per call to keep response time reasonable.
    """
    if not urls:
        return {}

    original_count = len([u for u in urls if u])
    urls = urls[:25]
    if original_count > len(urls):
        print(f"[scraper] Batch fetch limited to first 25 URLs (out of {original_count})")

    p, browser, context, page = await _browser_context()
    try:
        await page.route(
            re.compile(r"\.(png|jpg|jpeg|gif|svg|woff|woff2|ttf|eot)"),
            lambda route: route.abort(),
        )
        results: Dict[str, str] = {}
        for url in urls:
            try:
                await page.goto(url, timeout=20000, wait_until="domcontentloaded")
                await page.wait_for_timeout(1000)
                try:
                    await page.wait_for_selector(
                        "main, article, .job-description, .description, .content",
                        timeout=3000,
                    )
                except Exception:
                    pass
                body = await page.query_selector(
                    "main, article, .job-description, .description, .content"
                )
                if not body:
                    body = await page.query_selector("body")
                text = await body.inner_text() if body else ""
                results[url] = text[:5000]
                print(f"[scraper] Batch fetched description for {url} ({len(text)} chars)")
            except Exception as e:
                print(f"[scraper] Batch fetch failed for {url}: {e}")
                results[url] = ""
        return results
    except Exception as e:
        print(f"[scraper] Batch fetch browser error: {e}")
        return {url: "" for url in urls}
    finally:
        await _close_browser(p, browser, context)


def batch_fetch_descriptions(urls: List[str]) -> Dict[str, str]:
    """Sync wrapper — batch fetch descriptions for multiple URLs."""
    return _run_async(_batch_fetch_descriptions(urls))


# ── Jobindex.dk Scraper (Denmark) ───────────────────────────────────────


JOBINDEX_BASE = "https://jobindex.dk/jobsoegning"


async def _scrape_jobindex_dk(
    query: str = "", limit: int = 5, location: str = ""
) -> List[Dict[str, Any]]:
    """Scrape job listings from Jobindex.dk using Playwright."""
    term = query.strip().lower().replace(" ", "+") or "data+scientist"
    loc = location.strip().lower().replace(" ", "+") if location else ""
    url = f"{JOBINDEX_BASE}?q={term}"
    if loc:
        url += f"&where={loc}"

    last_error = None
    for attempt in range(2):
        p, browser, context, page = await _browser_context()
        try:
            await page.route(
                re.compile(r"\.(png|jpg|jpeg|gif|svg|woff|woff2|ttf|eot)"),
                lambda route: route.abort(),
            )
            await page.goto(url, timeout=TIMEOUT, wait_until="load")
            await page.wait_for_timeout(3000)

            jobs = await page.evaluate(
                """(queryLimit) => {
                    const cards = document.querySelectorAll('article.jobad, .jobsearch-result');
                    const results = [];

                    for (const card of cards) {
                        if (results.length >= queryLimit) break;

                        let title = '';
                        let company = '';
                        let location = '';
                        let fullUrl = '';

                        const companyEl = card.querySelector('.jix-toolbar-top__company a');
                        if (companyEl) company = companyEl.innerText.trim();

                        const titleEl = card.querySelector('.PaidJob-inner h4 a');
                        if (titleEl) {
                            title = titleEl.innerText.trim();
                            fullUrl = titleEl.getAttribute('href') || '';
                        }

                        const areaEl = card.querySelector('.jobad-element-area .jix_robotjob--area');
                        if (areaEl) location = areaEl.innerText.trim();

                        if (!title || !company) {
                            const lines = card.innerText
                                .split('\\n')
                                .map(l => l.trim())
                                .filter(l => l);

                            if (lines.length < 2) continue;

                            if (!company) company = lines[0] || '';
                            if (!title) title = lines[1] || '';
                            if (!location) location = lines[2] || '';
                            if (!fullUrl) {
                                const link = card.querySelector('a[href*="/job/"], a[href*="vis-job"]');
                                fullUrl = link ? link.getAttribute('href') || '' : '';
                            }
                        }

                        if (fullUrl && !fullUrl.startsWith('http')) {
                            fullUrl = 'https://jobindex.dk' + fullUrl;
                        }

                        results.push({
                            title: title,
                            company: company,
                            location: location,
                            url: fullUrl,
                            source: 'jobindex_dk',
                            posted_date: '',
                        });
                    }

                    return results;
                }""",
                limit,
            )

            return jobs[:limit]

        except Exception as e:
            last_error = e
            print(f"[scraper] Jobindex.dk attempt {attempt + 1} failed: {e}")
        finally:
            await _close_browser(p, browser, context)

    print(f"[scraper] Jobindex.dk failed after 2 attempts: {last_error}")
    return []


def scrape_jobindex_dk(
    query: str = "", limit: int = 5, location: str = ""
) -> List[Dict[str, Any]]:
    """Sync wrapper — scrape job listings from Jobindex.dk."""
    return _run_async(_scrape_jobindex_dk(query=query, limit=limit, location=location))


# ── Orchestrator ─────────────────────────────────────────────────────


def _detect_country(location: str) -> str:
    """Detect country from location string."""
    if not location:
        return "switzerland"
    loc_lower = location.lower().strip()
    denmark_keywords = {"denmark", "danmark", "copenhagen", "københavn", "aarhus", "århus", "odense", "aalborg", "aalborg", "esbjerg", "randers", "kolding", "horsens", "vejle", "roskilde", "helsingør", "herning", "silkeborg", "næstved", "fredericia", "viborg", "køge", "holstebro", "taastrup", "hillerød", "slagelse", "holbæk", "næstved", "færøerne", "færø", "grønland"}
    switzerland_keywords = {"switzerland", "schweiz", "suisse", "svizzera", "zurich", "zürich", "geneva", "genève", "basel", "bern", "berne", "lausanne", "winterthur", "lucerne", "luzern", "st. gallen", "st.gallen", "lugano", "biel", "bienne", "thun", "köniz", "la chaux-de-fonds", "fribourg", "freiburg", "schaffhausen", "chur", "vernier", "uffikon", "dübendorf", "wädenswil", "wemllikon", "horgen", "kloten", "meilen", "wetzikon", "richterswil", "altstätten", "frauenfeld", "wil", "kreuzlingen", "weinfelden", "arbon", "ammann", "stein", "gossau", "herisau", "teufen", "speicher", "trogen", "urzach", "wattwil", "wildhaus", "neslau", "wattwil"}

    for kw in denmark_keywords:
        if kw in loc_lower:
            return "denmark"
    for kw in switzerland_keywords:
        if kw in loc_lower:
            return "switzerland"
    return "switzerland"


def search_all_boards(
    query: str = "", limit: int = 5, location: str = ""
) -> List[Dict[str, Any]]:
    """Search all configured job boards based on location/country."""
    listings = []
    country = _detect_country(location)

    if country == "denmark":
        try:
            results = scrape_jobindex_dk(query=query, limit=limit, location=location)
            listings.extend(results)
            print(f"[scraper] jobindex.dk: {len(results)} listings")
        except Exception as e:
            print(f"[scraper] jobindex.dk error: {e}")
    else:
        try:
            region = location.lower().strip() if location else "zurich"
            results = scrape_jobs_ch(query=query, limit=limit, region=region)
            listings.extend(results)
            print(f"[scraper] jobs.ch: {len(results)} listings")
        except Exception as e:
            print(f"[scraper] jobs.ch error: {e}")

    return listings