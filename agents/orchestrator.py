# Recruiter Agency — Orchestrator
#
# Ties together all three agents end-to-end:
#   1. Job Finder — search job boards, score, shortlist
#   2. CV Tailor — generate tailored CV + cover letter for each shortlisted job
#   3. Notion Tracker — prepare entries for Notion database
#
# Usage:
#   python agents/orchestrator.py --search "machine learning engineer" --location "Zurich, Switzerland"
#   python agents/orchestrator.py --from-shortlist output/shortlist.json  # resume from saved shortlist
#
# The orchestrator outputs:
#   - Shortlist JSON to output/shortlist.json
#   - Tailored CVs to output/resumes/
#   - Cover letters to output/cover_letters/
#   - Notion-ready entries to output/notion_entries.json
#   - A summary to stdout

from __future__ import annotations

import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

# Ensure project root is on path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from dotenv import load_dotenv

load_dotenv(os.path.join(PROJECT_ROOT, ".env"))


def _ensure_output_dir(subdir: str) -> Path:
    p = Path(PROJECT_ROOT) / "output" / subdir
    p.mkdir(parents=True, exist_ok=True)
    return p


def _timestamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def run_full_pipeline(
    search_term: str = "data scientist",
    location: str = "Zurich, Switzerland",
    hours_old: int = 72,
    results_wanted: int = 20,
    min_score: float = 5.0,
    shortlist_size: int = 10,
    skip_search: bool = False,
    shortlist_path: Optional[str] = None,
) -> Dict[str, Any]:
    """Run the full recruiter agency pipeline end-to-end.

    Args:
        search_term: Job search query.
        location: Location string.
        hours_old: Recency filter in hours.
        results_wanted: Max raw results per site.
        min_score: Minimum LLM score (1-10) to shortlist.
        shortlist_size: Max shortlist size.
        skip_search: If True, load shortlist from file instead of searching.
        shortlist_path: Path to existing shortlist JSON.

    Returns:
        Dict with keys: 'shortlist', 'tailoring_results', 'notion_entries',
        'summary', 'errors'
    """
    errors: List[str] = []
    summary: Dict[str, Any] = {
        "search_term": search_term,
        "location": location,
        "timestamp": _timestamp(),
    }

    # ── Step 1: Find Jobs ────────────────────────────────────────────
    if skip_search and shortlist_path:
        print("\n" + "=" * 72)
        print("  STEP 1 — Loading shortlist from file")
        print("=" * 72)
        with open(shortlist_path, "r") as f:
            finder_result = json.load(f)
        shortlist = finder_result.get("shortlist", [])
        summary["source"] = f"loaded from {shortlist_path}"
    else:
        print("\n" + "=" * 72)
        print(f"  STEP 1 — Job Finder: '{search_term}' in '{location}' (past {hours_old}h)")
        print("=" * 72)
        from agents.job_finder_agent import find_jobs, print_shortlist

        finder_result = find_jobs(
            search_term=search_term,
            location=location,
            hours_old=hours_old,
            results_wanted=results_wanted,
            min_score=min_score,
            shortlist_size=shortlist_size,
        )
        shortlist = finder_result.get("shortlist", [])
        summary["source"] = "live_search"
        summary["total_raw"] = finder_result.get("total_raw", 0)
        errors.extend(finder_result.get("errors", []))

        print_shortlist(finder_result)

        # Save shortlist
        out_dir = _ensure_output_dir("shortlists")
        ts = _timestamp()
        shortlist_path = str(out_dir / f"shortlist_{ts}.json")
        with open(shortlist_path, "w") as f:
            json.dump(finder_result, f, indent=2, default=str)
        print(f"\n[orchestrator] Shortlist saved to {shortlist_path}")

    if not shortlist:
        print("\n[orchestrator] No jobs to process. Exiting.")
        return {
            "shortlist": [],
            "tailoring_results": [],
            "notion_entries": [],
            "summary": {**summary, "status": "no_jobs"},
            "errors": errors,
        }

    summary["shortlist_count"] = len(shortlist)

    # ── Step 2: Tailor CVs & Cover Letters ────────────────────────────
    print("\n" + "=" * 72)
    print(f"  STEP 2 — CV & Cover Letter Tailor ({len(shortlist)} listings)")
    print("=" * 72)

    from agents.cv_tailor_agent import tailor_for_shortlist, load_base_resumejson

    base_resume = load_base_resumejson()
    if not base_resume:
        err_msg = "No base CV found at config/resumeinfo.json"
        print(f"[orchestrator] {err_msg}")
        return {
            "shortlist": shortlist,
            "tailoring_results": [],
            "notion_entries": [],
            "summary": {**summary, "status": "no_cv"},
            "errors": errors + [err_msg],
        }

    tailoring_results = tailor_for_shortlist(shortlist, base_resume)

    successful_cvs = sum(
        1 for r in tailoring_results
        if r.get("tailored_cv", {}).get("saved_path")
    )
    successful_cls = sum(
        1 for r in tailoring_results
        if r.get("cover_letter", {}).get("saved_path")
    )

    print(f"\n[orchestrator] Generated {successful_cvs} tailored CVs, {successful_cls} cover letters")

    summary["tailored_cvs"] = successful_cvs
    summary["cover_letters"] = successful_cls

    # Save tailoring results
    out_dir = _ensure_output_dir("tailoring_results")
    ts = _timestamp()
    tailoring_path = str(out_dir / f"tailoring_{ts}.json")
    with open(tailoring_path, "w") as f:
        json.dump(tailoring_results, f, indent=2, default=str)
    print(f"[orchestrator] Tailoring results saved to {tailoring_path}")

    # ── Step 3: Persist to Local SQL Database ───────────────────────────
    print("\n" + "=" * 72)
    print("  STEP 3 — Local SQL Database Persistence")
    print("=" * 72)

    from services.tracker_service import (
        init_db, insert_listing, save_tailored_cv, insert_application, get_all_applications
    )

    init_db()
    saved_count = 0
    for r in tailoring_results:
        listing = r.get("listing", {})
        cv = r.get("tailored_cv", {})

        company = listing.get("company", "Unknown")
        role = listing.get("title", "Unknown Role")
        lid = insert_listing(listing)

        cv_path = cv.get("saved_path") or ""
        rb_url = cv.get("resume_builder_url") or ""
        commentary = cv.get("commentary") or ""

        if cv_path:
            save_tailored_cv(
                listing_id=lid,
                cv_path=cv_path,
                commentary=commentary,
                resume_builder_url=rb_url,
            )

        insert_application({
            "listing_id": lid,
            "company": company,
            "role": role,
            "status": "Evaluated",
            "score": listing.get("score"),
            "tailored_cv_path": cv_path,
            "notes": listing.get("fit_rationale", ""),
        })
        saved_count += 1

    print(f"[orchestrator] Successfully persisted {saved_count} listings, scores, & tailored CVs to SQL database")

    summary["db_entries"] = saved_count
    summary["status"] = "complete"
    summary["shortlist_path"] = shortlist_path
    summary["tailoring_path"] = tailoring_path

    _print_db_summary(saved_count)

    return {
        "shortlist": shortlist,
        "tailoring_results": tailoring_results,
        "summary": summary,
        "errors": errors,
    }


def _print_db_summary(saved_count: int) -> None:
    """Print SQL database status summary."""
    from services.tracker_service import get_application_stats
    stats = get_application_stats()

    print("\n" + "=" * 72)
    print("  SQL DATABASE TRACKER STATUS")
    print("=" * 72)
    print(f"  Saved {saved_count} applications to local SQLite database (agentdb/applications.db)")
    print(f"  Total Applications in DB: {stats.get('total', 0)}")
    print(f"  Average Fit Score:        {stats.get('avg_score', 0.0)}")
    print("  Breakdown by Status:")
    for status, count in stats.get("by_status", {}).items():
        print(f"    - {status}: {count}")
    print()



# ── CLI Entry Point ──────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Recruiter Agency — Full Pipeline")
    parser.add_argument("--search", default="data scientist",
                        help="Job search term (default: data scientist)")
    parser.add_argument("--location", default="Zurich, Switzerland",
                        help="Location (default: Zurich, Switzerland)")
    parser.add_argument("--hours", type=int, default=72,
                        help="Hours old / recency filter (default: 72)")
    parser.add_argument("--results", type=int, default=20,
                        help="Max results per site (default: 20)")
    parser.add_argument("--min-score", type=float, default=5.0,
                        help="Minimum LLM score 1-10 (default: 5.0)")
    parser.add_argument("--shortlist-size", type=int, default=10,
                        help="Max shortlist size (default: 10)")
    parser.add_argument("--from-shortlist",
                        help="Skip search, load shortlist from JSON file")
    parser.add_argument("--quick", action="store_true",
                        help="Quick mode: fewer results, smaller shortlist")
    args = parser.parse_args()

    if args.quick:
        args.results = 5
        args.shortlist_size = 5

    result = run_full_pipeline(
        search_term=args.search,
        location=args.location,
        hours_old=args.hours,
        results_wanted=args.results,
        min_score=args.min_score,
        shortlist_size=args.shortlist_size,
        skip_search=bool(args.from_shortlist),
        shortlist_path=args.from_shortlist,
    )

    summary = result.get("summary", {})

    print("\n" + "=" * 72)
    print("  PIPELINE COMPLETE")
    print("=" * 72)
    print(f"  Status:  {summary.get('status', 'unknown')}")
    print(f"  Search:  {summary.get('search_term')} / {summary.get('location')}")
    print(f"  Shortlisted: {summary.get('shortlist_count', 0)} jobs")
    print(f"  CVs generated:  {summary.get('tailored_cvs', 0)}")
    print(f"  Cover letters:  {summary.get('cover_letters', 0)}")
    print(f"  SQL DB entries: {summary.get('db_entries', 0)}")

    if result.get("errors"):
        print(f"\n  Errors ({len(result['errors'])}):")
        for e in result["errors"][:5]:
            print(f"    - {e}")

    print("\n  Output files:")
    if summary.get("shortlist_path"):
        print(f"    Shortlist:        {summary['shortlist_path']}")
    if summary.get("tailoring_path"):
        print(f"    Tailoring results: {summary['tailoring_path']}")
    print(f"    SQLite database:   agentdb/applications.db")
    print()