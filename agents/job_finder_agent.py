# Agent 1 — Job Finder
#
# Uses jobspy to query Indeed + LinkedIn (+ ZipRecruiter as fallback).
# Filters results by role, location, recency.
# Scores each listing for fit against the user's profile.
# Outputs a shortlist of 5–10 listings with title, company, URL, and fit rationale.
#
# Usage:
#   from agents.job_finder_agent import find_jobs
#   shortlist = find_jobs(search_term="data scientist", location="Zurich", hours_old=72)

from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

# Ensure project root is on path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from dotenv import load_dotenv
import pandas as pd

load_dotenv(os.path.join(PROJECT_ROOT, ".env"))

from services.llm_service import LLMService


# ── Scoring ──────────────────────────────────────────────────────────────

def _load_profile() -> Dict[str, Any]:
    """Load user profile from config."""
    from utils.config_loader import load_profile, get_cv_text
    profile = load_profile()
    profile["_cv_text"] = get_cv_text()
    return profile


def _score_listing(llm: LLMService, row: dict, profile: Dict[str, Any]) -> Dict[str, Any]:
    """Score a single listing for fit against the user's profile using the LLM.

    Returns the listing with added score and rationale fields.
    """
    title = str(row.get("title", ""))
    company = str(row.get("company", ""))
    description = str(row.get("description", ""))
    location = str(row.get("location", ""))
    job_url = str(row.get("job_url", ""))
    salary = str(row.get("salary", ""))
    source = str(row.get("site", ""))

    # Skip listings with no description — can't evaluate
    if not description or len(description.strip()) < 50:
        listing = {
            "title": title,
            "company": company,
            "url": job_url,
            "location": location,
            "salary": salary,
            "source": source,
            "score": 0.0,
            "fit_rationale": "No description available to evaluate.",
        }
        return listing

    target_roles = profile.get("target_roles", {})
    primary = ", ".join(target_roles.get("primary", []))
    secondary = ", ".join(target_roles.get("secondary", []))
    cv_text = profile.get("_cv_text", "")[:2000]

    prompt = f"""You are a job fit evaluator. Score this job listing against the candidate's profile.

## Candidate Profile
- Target roles (primary): {primary}
- Target roles (secondary): {secondary}

## Job Listing
- Title: {title}
- Company: {company}
- Location: {location}
- Salary: {salary}

## Job Description (first 2000 chars):
{description[:2000]}

## Candidate CV (first 2000 chars):
{cv_text[:2000]}

Provide your evaluation in this exact format:
SCORE: <number between 1-10>
RATIONALE: <2-3 sentence explanation of fit/direction, mentioning specific skills or list any knockout factors>

Rules:
- 8-10: Strong match — candidate's CV directly matches most requirements
- 5-7: Decent match — some overlap, worth considering
- 1-4: Weak match — significant mismatch in role, seniority, or tech stack
- Score 0 if: location is infeasible, massively over/under-qualified field mismatch
"""

    try:
        result = llm._call(
            model="gemini-2.0-flash-lite",
            prompt=prompt,
            temperature=0.2,
        )
    except Exception as e:
        print(f"[job_finder] LLM scoring failed for {title} @ {company}: {e}")
        result = "SCORE: 5\nRATIONALE: Unable to evaluate due to LLM error."

    score = 5.0
    rationale = result
    for line in result.split("\n"):
        line = line.strip()
        if line.upper().startswith("SCORE:"):
            try:
                score = float(line.split(":", 1)[1].strip())
            except ValueError:
                score = 5.0
        elif line.upper().startswith("RATIONALE:"):
            rationale = line.split(":", 1)[1].strip()

    listing = {
        "title": title,
        "company": company,
        "url": job_url,
        "location": location,
        "salary": salary,
        "description": description,
        "source": source,
        "score": score,
        "fit_rationale": rationale,
    }
    return listing


# ── Danish Job Board Scrapers ────────────────────────────────────────────

def _scrape_jobindex_apify(
    search_term: str,
    limit: int = 20,
) -> List[Dict[str, Any]]:
    """Scrape Jobindex.dk and IT-Jobbank.dk via Apify web-scraper actor.

    Requires APIFY_API_TOKEN in .env.  Falls back to direct HTTP if
    the token is not set or the actor call fails.
    """
    api_token = os.getenv("APIFY_API_TOKEN", "")
    if not api_token:
        print("[job_finder] APIFY_API_TOKEN not set — skipping Apify path")
        return []

    try:
        from apify_client import ApifyClient
    except ImportError:
        print("[job_finder] apify-client not installed — skipping Apify path")
        return []

    client = ApifyClient(api_token)
    all_listings: List[Dict[str, Any]] = []
    term = search_term.strip().replace(" ", "+")

    boards: list[tuple[str, str]] = [
        ("jobindex", f"https://www.jobindex.dk/jobsoegning?q={term}&land=1"),
        ("it-jobbank", f"https://www.it-jobbank.dk/jobsoegning?q={term}"),
    ]

    page_function = """
        async function pageFunction(context) {
            const { request, log, jQuery } = context;
            const $ = jQuery;
            const items = [];
            const selectors = '.PaidJob, .jobsearch-result-item, .job-result-item, [class*=result-item]';
            $(selectors).each(function() {
                const $card = $(this);
                const $link = $card.find('a').first();
                const href = $link.attr('href') || '';
                const url = href.startsWith('http') ? href : 'https://www.jobindex.dk' + href;
                const title = $link.text().trim() || $card.find('h4, h3').text().trim();
                if (!title) return;
                const company = $card.find('.company, [class*=company], .PaidJob-company').first().text().trim();
                items.push({
                    title: title,
                    url: url,
                    company: company || 'Unknown',
                    description: $card.text().trim().substring(0, 2000),
                    location: 'Denmark',
                });
            });
            return items;
        }
    """

    for name, url in boards:
        try:
            print(f"[job_finder] Apify scraping {name}...")
            run = client.actor("apify/web-scraper").call(
                run_input={
                    "startUrls": [{"url": url}],
                    "pageFunction": page_function,
                    "maxPagesPerCrawl": 1,
                    "maxResults": limit,
                },
                wait_until="FINISHED",
            )
            dataset_id = run.get("defaultDatasetId")
            if dataset_id:
                items = client.dataset(dataset_id).list_items().items
                for item in items:
                    if item.get("title"):
                        item["source"] = name
                        item["site"] = name
                        all_listings.append(item)
                print(f"[job_finder] Apify got {len(items)} listings from {name}")
        except Exception as e:
            print(f"[job_finder] Apify scrape failed for {name}: {e}")

    return all_listings[:limit]


def _scrape_jobindex_direct(
    search_term: str,
    limit: int = 20,
) -> List[Dict[str, Any]]:
    """Scrape Jobindex.dk and IT-Jobbank.dk directly via HTTP + BeautifulSoup.

    Uses httpx (already in requirements) and parses the server-rendered HTML.
    Works without any API keys.
    """
    import httpx
    from bs4 import BeautifulSoup

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/131.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "da-DK,da;q=0.9,en;q=0.8",
    }

    boards: list[tuple[str, str, dict[str, str]]] = [
        ("jobindex", "https://www.jobindex.dk/jobsoegning", {"q": search_term, "land": "1"}),
        ("it-jobbank", "https://www.it-jobbank.dk/jobsoegning", {"q": search_term}),
    ]

    all_listings: List[Dict[str, Any]] = []

    with httpx.Client(headers=headers, follow_redirects=True, timeout=30) as client:
        for source, base_url, params in boards:
            try:
                print(f"[job_finder] Direct-scraping {source}...")
                resp = client.get(base_url, params=params)
                resp.raise_for_status()
                soup = BeautifulSoup(resp.text, "html.parser")

                cards = (
                    soup.select(".PaidJob")
                    or soup.select(".jobsearch-result-item")
                    or soup.select("[class*=result-item]")
                    or soup.select("article")
                )

                count = 0
                for card in cards:
                    if count >= limit:
                        break

                    title_el = (
                        card.select_one("a.job-title")
                        or card.select_one("h4 a, h3 a")
                        or card.select_one("a[href*='/job/']")
                        or card.select_one("a")
                    )
                    if not title_el:
                        continue

                    title = title_el.get_text(strip=True)
                    if not title or len(title) < 2:
                        continue

                    href = title_el.get("href", "")
                    url = href if href.startswith("http") else f"https://www.jobindex.dk{href}"

                    company = "Unknown"
                    for sel in [".company", "[class*=company]", ".PaidJob-company", ".job-location"]:
                        el = card.select_one(sel)
                        if el:
                            txt = el.get_text(strip=True)
                            if txt:
                                company = txt.split("|")[0].split("\n")[0].strip()
                                break

                    location = "Denmark"
                    for sel in [".location", "[class*=location]"]:
                        el = card.select_one(sel)
                        if el:
                            loc = el.get_text(strip=True)
                            if loc:
                                location = loc
                                break

                    # Build a usable description from card text
                    card_text = card.get_text("\n", strip=True)

                    all_listings.append({
                        "title": title,
                        "company": company,
                        "url": url,
                        "location": location,
                        "source": source,
                        "site": source,
                        "description": card_text[:2000],
                        "salary": None,
                    })
                    count += 1

                print(f"[job_finder] Direct scrape got {count} listings from {source}")

            except Exception as e:
                print(f"[job_finder] Direct scrape failed for {source}: {e}")

    return all_listings[:limit]


def _scrape_danish_jobs(
    search_term: str,
    limit: int = 20,
) -> List[Dict[str, Any]]:
    """Scrape Danish job boards (Jobindex + IT-Jobbank).

    Uses direct HTTP scraping with httpx + BeautifulSoup by default (fast,
    no API key needed). Falls back to Apify web-scraper if direct fails
    and APIFY_API_TOKEN is available.
    """
    listings = _scrape_jobindex_direct(search_term, limit)
    if listings:
        return listings

    api_token = os.getenv("APIFY_API_TOKEN", "")
    if api_token:
        try:
            from apify_client import ApifyClient
            _ = ApifyClient
            return _scrape_jobindex_apify(search_term, limit)
        except ImportError:
            pass

    return []


# ── Main Search ──────────────────────────────────────────────────────────

def find_jobs(
    search_term: str = "data scientist",
    location: str = "Zurich, Switzerland",
    hours_old: int = 72,
    results_wanted: int = 20,
    sites: Optional[List[str]] = None,
    min_score: float = 5.0,
    shortlist_size: int = 10,
) -> Dict[str, Any]:
    """Search job boards and return a scored shortlist.

    Args:
        search_term: Job title or keywords to search for.
        location: Location string (e.g. "Zurich, Switzerland").
        hours_old: Only show listings posted within this many hours.
        results_wanted: Max raw results to pull per site.
        sites: Job sites to search. Defaults to [indeed, linkedin, zip_recruiter].
        min_score: Minimum LLM score to include in shortlist (1-10).
        shortlist_size: Max number of listings in the final shortlist.

    Returns:
        Dict with keys:
          - 'shortlist': list of scored listings (sorted desc by score)
          - 'total_raw': total raw results from all sites
          - 'errors': any errors encountered
    """
    from jobspy import scrape_jobs

    if location is None:
        location = "Zurich, Switzerland"

    is_danish = location and (
        "copenhagen" in location.lower()
        or "denmark" in location.lower()
        or "københavn" in location.lower()
        or "danmark" in location.lower()
    )

    profile = _load_profile()
    llm = LLMService()
    errors: List[str] = []
    all_listings: List[Dict[str, Any]] = []

    if is_danish:
        print(f"[job_finder] Searching Danish boards for '{search_term}' in '{location}'")
        raw_listings = _scrape_danish_jobs(search_term, limit=results_wanted)
        print(f"[job_finder] Got {len(raw_listings)} raw results from Danish boards")

        for raw in raw_listings:
            try:
                row = {
                    "title": raw.get("title", ""),
                    "company": raw.get("company", ""),
                    "description": raw.get("description", ""),
                    "location": raw.get("location", ""),
                    "job_url": raw.get("url", raw.get("job_url", "")),
                    "salary": raw.get("salary", ""),
                    "site": raw.get("site", raw.get("source", "jobindex")),
                }
                scored = _score_listing(llm, row, profile)
                all_listings.append(scored)
            except Exception as e:
                title = raw.get("title", "Unknown")
                company = raw.get("company", "Unknown")
                print(f"[job_finder] Error scoring {title} @ {company}: {e}")
                errors.append(f"Scoring error for {title}: {e}")
                continue
    else:
        sites = sites or ["indeed", "linkedin", "zip_recruiter"]

        print(f"[job_finder] Searching {', '.join(sites)} for '{search_term}' in '{location}' (past {hours_old}h)")

        try:
            jobs_df: pd.DataFrame = scrape_jobs(
                site_name=sites,
                search_term=search_term,
                location=location,
                results_wanted=results_wanted,
                hours_old=hours_old,
                country_indeed="Denmark" if is_danish else "Switzerland",
            )

            if jobs_df.empty:
                print("[job_finder] No results found.")
                return {
                    "shortlist": [],
                    "total_raw": 0,
                    "errors": ["No listings found from any source."],
                }

            print(f"[job_finder] Got {len(jobs_df)} raw results from jobspy")

            for idx, row in jobs_df.iterrows():
                try:
                    scored = _score_listing(llm, row.to_dict(), profile)
                    all_listings.append(scored)
                except Exception as e:
                    title = row.get("title", "Unknown")
                    company = row.get("company", "Unknown")
                    print(f"[job_finder] Error scoring {title} @ {company}: {e}")
                    errors.append(f"Scoring error for {title}: {e}")
                    continue

        except Exception as e:
            print(f"[job_finder] jobspy search failed: {e}")
            return {
                "shortlist": [],
                "total_raw": 0,
                "errors": [f"Search failed: {e}"],
            }

    # Sort by score descending, filter by min_score
    all_listings.sort(key=lambda x: x.get("score", 0), reverse=True)
    shortlist = [l for l in all_listings if l.get("score", 0) >= min_score][:shortlist_size]

    print(f"[job_finder] Scored {len(all_listings)} listings, shortlisted {len(shortlist)} (min_score={min_score})")

    # Persist all scraped listings into the local SQL database
    try:
        from services.tracker_service import save_scraped_listings, init_db
        init_db()
        save_scraped_listings(all_listings)
        print(f"[job_finder] Saved {len(all_listings)} scraped listings to local SQL database")
    except Exception as db_err:
        print(f"[job_finder] Warning: failed to persist listings to SQL DB: {db_err}")
        errors.append(f"DB save error: {db_err}")

    return {
        "shortlist": shortlist,
        "all_scored": all_listings,
        "total_raw": len(all_listings),
        "errors": errors,
    }



# ── CLI Entry Point ──────────────────────────────────────────────────────

def print_shortlist(result: Dict[str, Any]) -> None:
    """Pretty-print the shortlist to stdout."""
    shortlist = result.get("shortlist", [])
    errors = result.get("errors", [])

    print("\n" + "=" * 80)
    print("=" * 72)
    print(f"  JOB FINDER — SHORTLIST ({len(shortlist)} listings)")
    print("=" * 72)

    if not shortlist:
        print("  No listings met the minimum score threshold.")
        if errors:
            print(f"\n  Encountered {len(errors)} errors:")
            for e in errors[:3]:
                print(f"    - {e}")
        return

    for i, listing in enumerate(shortlist, 1):
        print(f"\n  [{i}] {listing['title']}")
        print(f"      Company: {listing['company']}")
        print(f"      Location: {listing['location']}")
        print(f"      Score: {listing['score']}/10")
        print(f"      URL: {listing['url']}")
        print(f"      Rationale: {listing['fit_rationale']}")
        print(f"      Source: {listing['source']}")
        print()

    if errors:
        print(f"  ({len(errors)} errors encountered during scoring)")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Agent 1 — Job Finder")
    parser.add_argument("--search", default="data scientist", help="Search term")
    parser.add_argument("--location", default="Zurich, Switzerland", help="Location")
    parser.add_argument("--hours", type=int, default=72, help="Hours old (recency)")
    parser.add_argument("--results", type=int, default=20, help="Max results per site")
    parser.add_argument("--min-score", type=float, default=5.0, help="Min score to shortlist (1-10)")
    parser.add_argument("--shortlist", type=int, default=10, help="Max shortlist size")
    args = parser.parse_args()

    result = find_jobs(
        search_term=args.search,
        location=args.location,
        hours_old=args.hours,
        results_wanted=args.results,
        min_score=args.min_score,
        shortlist_size=args.shortlist,
    )
    print_shortlist(result)
