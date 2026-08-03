# Agent 3 — Notion Tracker
#
# Logs each application as a page in a Notion database.
# Fields: Company, Role, URL, Status, Date Added, CV link, Cover Letter link, Notes.
# Handles status updates (To Apply -> Applied -> Interview -> Rejected).
#
# This agent has two layers:
#   1. Python layer (this file) — structures data, manages local state
#   2. MCP layer — uses the Notion MCP tools (called by the orchestrator/Claude)
#      to create the database and write pages.
#
# Usage (data preparation):
#   from agents.notion_tracker import prepare_notion_entry
#   entry = prepare_notion_entry(listing, cv_url, cl_url)
#
# Usage (orchestrator — run from Claude Code):
#   python agents/notion_tracker.py --prepare apps.json  # prepare data
#   python agents/notion_tracker.py --status              # check status

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from dotenv import load_dotenv

load_dotenv(os.path.join(PROJECT_ROOT, ".env"))


# ── Data Model ───────────────────────────────────────────────────────────

NOTION_DB_TITLE = "Job Applications"
NOTION_DB_SCHEMA = """CREATE TABLE (
    "Company" TITLE,
    "Role" RICH_TEXT,
    "URL" URL,
    "Status" SELECT(
        'To Apply':gray,
        'Applied':blue,
        'Interview':yellow,
        'Offer':green,
        'Rejected':red,
        'Archived':brown
    ),
    "Date Added" DATE,
    "Date Applied" DATE,
    "Score (/10)" NUMBER,
    "CV Link" URL,
    "Cover Letter Link" URL,
    "Notes" RICH_TEXT,
    "Source" SELECT(
        'Indeed':blue,
        'LinkedIn':blue,
        'ZipRecruiter':blue,
        'Jobs.ch':blue,
        'Manual':gray
    )
)"""

APPLICATION_STATUSES = [
    "To Apply",
    "Applied",
    "Interview",
    "Offer",
    "Rejected",
    "Archived",
]


# ── Data Preparation ─────────────────────────────────────────────────────

def prepare_notion_entry(
    listing: Dict[str, Any],
    cv_url: Optional[str] = None,
    cover_letter_url: Optional[str] = None,
    status: str = "To Apply",
    notes: str = "",
) -> Dict[str, Any]:
    """Structure a job listing as a Notion database entry.

    Args:
        listing: Listing dict with title, company, url, source, score, etc.
        cv_url: URL to the tailored CV Google Doc.
        cover_letter_url: URL to the cover letter Google Doc.
        status: Application status from APPLICATION_STATUSES.
        notes: Optional notes about this application.

    Returns:
        Dict ready to be converted to Notion properties.
    """
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # Map source to our enum
    source_raw = (listing.get("source") or "").lower()
    source_map = {
        "indeed": "Indeed",
        "linkedin": "LinkedIn",
        "zip_recruiter": "ZipRecruiter",
        "ziprecruiter": "ZipRecruiter",
        "jobs_ch": "Jobs.ch",
        "jobs.ch": "Jobs.ch",
    }
    source = source_map.get(source_raw, "Manual")

    score = listing.get("score")
    if score is not None:
        score = round(float(score), 1)

    return {
        "company": listing.get("company", "Unknown"),
        "role": listing.get("title", "Unknown Role"),
        "url": listing.get("url", ""),
        "status": status,
        "date_added": today,
        "score": score,
        "cv_url": cv_url or "",
        "cover_letter_url": cover_letter_url or "",
        "notes": notes,
        "source": source,
        "fit_rationale": listing.get("fit_rationale", ""),
    }


def serialize_notion_properties(entry: Dict[str, Any]) -> Dict[str, Any]:
    """Convert a prepared entry to Notion API properties format.

    This produces the JSON structure needed for the Notion MCP create-pages tool.
    """
    notes_text = entry.get("notes", "")
    fit_rationale = entry.get("fit_rationale", "")
    if fit_rationale and not notes_text:
        notes_text = fit_rationale
    elif fit_rationale:
        notes_text += f"\n\nFit: {fit_rationale}"

    properties = {
        "Company": entry.get("company", "Unknown"),
        "Role": entry.get("role", "Unknown Role"),
        "URL": entry.get("url", ""),
        "Status": entry.get("status", "To Apply"),
        "Date Added": entry.get("date_added", ""),
        "Notes": notes_text,
        "Source": entry.get("source", "Manual"),
    }

    score = entry.get("score")
    if score is not None:
        properties["Score (/10)"] = score

    cv_url = entry.get("cv_url", "")
    cl_url = entry.get("cover_letter_url", "")
    if cv_url:
        properties["CV Link"] = cv_url
    if cl_url:
        properties["Cover Letter Link"] = cl_url

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if entry.get("status") == "Applied":
        properties["Date Applied"] = today

    return properties


# ── Local State Persistence ──────────────────────────────────────────────

LOCAL_DB_PATH = os.path.join(PROJECT_ROOT, "agentdb", "notion_apps.json")


def _ensure_local_db():
    """Ensure the local JSON database file exists."""
    os.makedirs(os.path.dirname(LOCAL_DB_PATH), exist_ok=True)
    if not os.path.exists(LOCAL_DB_PATH):
        with open(LOCAL_DB_PATH, "w") as f:
            json.dump({"applications": [], "notion_db_id": None}, f)


def save_local_entry(entry: Dict[str, Any]):
    """Save a prepared entry to the local JSON database."""
    _ensure_local_db()
    with open(LOCAL_DB_PATH, "r") as f:
        data = json.load(f)
    data["applications"].append({
        **entry,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    with open(LOCAL_DB_PATH, "w") as f:
        json.dump(data, f, indent=2, default=str)


def get_local_applications() -> List[Dict[str, Any]]:
    """Get all locally-tracked applications."""
    _ensure_local_db()
    with open(LOCAL_DB_PATH, "r") as f:
        data = json.load(f)
    return data.get("applications", [])


def get_notion_db_id() -> Optional[str]:
    """Get the stored Notion database ID."""
    _ensure_local_db()
    with open(LOCAL_DB_PATH, "r") as f:
        data = json.load(f)
    return data.get("notion_db_id")


def set_notion_db_id(db_id: str):
    """Store the Notion database ID after creation."""
    _ensure_local_db()
    with open(LOCAL_DB_PATH, "r") as f:
        data = json.load(f)
    data["notion_db_id"] = db_id
    with open(LOCAL_DB_PATH, "w") as f:
        json.dump(data, f, indent=2, default=str)


def update_application_status(company: str, role: str, new_status: str) -> bool:
    """Update the status of a tracked application locally.

    Args:
        company: Company name.
        role: Job title.
        new_status: One of APPLICATION_STATUSES.

    Returns:
        True if the application was found and updated.
    """
    if new_status not in APPLICATION_STATUSES:
        return False

    apps = get_local_applications()
    found = False
    for app in apps:
        if (app.get("company", "").lower() == company.lower()
                and app.get("role", "").lower() == role.lower()):
            app["status"] = new_status
            app["updated_at"] = datetime.now(timezone.utc).isoformat()
            if new_status == "Applied" and not app.get("date_applied"):
                app["date_applied"] = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            found = True
            break

    if found:
        _ensure_local_db()
        with open(LOCAL_DB_PATH, "r") as f:
            data = json.load(f)
        data["applications"] = apps
        with open(LOCAL_DB_PATH, "w") as f:
            json.dump(data, f, indent=2, default=str)
    return found


# ── Batch Processing ────────────────────────────────────────────────────

def prepare_shortlist_for_notion(
    tailoring_results: List[Dict[str, Any]],
    status: str = "To Apply",
) -> List[Dict[str, Any]]:
    """Prepare a full shortlist for Notion import.

    Args:
        tailoring_results: The output from cv_tailor_agent.tailor_for_shortlist().
        status: Initial status for all entries.

    Returns:
        List of prepared Notion entries (serialized properties).
    """
    entries = []
    for r in tailoring_results:
        listing = r.get("listing", {})
        cv = r.get("tailored_cv", {})
        cl = r.get("cover_letter", {})

        cv_url = cv.get("google_doc_url") if cv and not cv.get("error") else None
        cl_url = cl.get("google_doc_url") if cl and not cl.get("error") else None

        entry = prepare_notion_entry(
            listing=listing,
            cv_url=cv_url,
            cover_letter_url=cl_url,
            status=status,
            notes="",
        )
        entries.append(entry)
        save_local_entry(entry)

    return entries


# ── MCP Instructions ────────────────────────────────────────────────────
#
# The Notion database is created and pages are added via the Notion MCP tools,
# which are only accessible from this Claude Code session.
#
# To use this agent, the orchestrator should:
#
#   Step 1 — Create the database (one-time):
#     notion-create-database({
#       "parent": {"page_id": "<your-workspace-page-id>"},
#       "title": "Job Applications",
#       "schema": NOTION_DB_SCHEMA (from above)
#     })
#
#   Step 2 — Add pages:
#     For each prepared entry, call:
#     notion-create-pages({
#       "parent": {"data_source_id": "<returned-db-id>"},
#       "pages": [{
#         "properties": serialize_notion_properties(entry),
#         "content": f"# {entry['role']} @ {entry['company']}\n\n{entry['notes']}"
#       }]
#     })
#
#   Step 3 — Update status:
#     notion-update-page({
#       "page_id": "<page-id>",
#       "command": "update_properties",
#       "properties": {"Status": "Applied"}
#     })


# ── CLI Entry Point ──────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Agent 3 — Notion Tracker")
    parser.add_argument("--prepare", help="Path to tailoring results JSON")
    parser.add_argument("--status", action="store_true", help="Show local application status")
    parser.add_argument("--update-status", nargs=3, metavar=("COMPANY", "ROLE", "STATUS"),
                        help="Update application status")
    parser.add_argument("--output", default="", help="Path to write prepared entries JSON")
    args = parser.parse_args()

    if args.prepare:
        with open(args.prepare, "r") as f:
            tailoring_results = json.load(f)
        entries = prepare_shortlist_for_notion(tailoring_results)
        serialized = [serialize_notion_properties(e) for e in entries]

        print(f"\n=== NOTION TRACKER — Prepared {len(entries)} entries ===\n")
        for i, entry in enumerate(serialized, 1):
            print(f"  [{i}] {entry.get('Company', '?')} — {entry.get('Role', '?')} ({entry.get('Status', '?')})")
            if entry.get("CV Link"):
                print(f"      CV: {entry['CV Link']}")
            if entry.get("Cover Letter Link"):
                print(f"      CL: {entry['Cover Letter Link']}")
            print()

        if args.output:
            with open(args.output, "w") as f:
                json.dump(serialized, f, indent=2, default=str)
            print(f"Prepared entries written to {args.output}")
            print(f"\nTo create the Notion database, use the Notion MCP:")
            print(f"  notion-create-database with schema from NOTION_DB_SCHEMA")
            print(f"\nTo add pages, use notion-create-pages with the prepared entries.")

    elif args.status:
        apps = get_local_applications()
        print(f"\n=== NOTION TRACKER — {len(apps)} Applications ===\n")
        by_status: Dict[str, int] = {}
        for app in apps:
            s = app.get("status", "Unknown")
            by_status[s] = by_status.get(s, 0) + 1

        for status, count in sorted(by_status.items()):
            print(f"  {status}: {count}")
        print()

        for i, app in enumerate(apps, 1):
            print(f"  [{i}] {app.get('company', '?')} — {app.get('role', '?')} [{app.get('status', '?')}]")
            if app.get("cv_url"):
                print(f"      CV: {app['cv_url']}")
            if app.get("cover_letter_url"):
                print(f"      CL: {app['cover_letter_url']}")
            print()

    elif args.update_status:
        company, role, status = args.update_status
        success = update_application_status(company, role, status)
        if success:
            print(f"  Updated {company} / {role} → {status}")
            print(f"\n  To also update in Notion, use:")
            print(f"  notion-update-page with Status={status}")
        else:
            print(f"  Application not found for {company} / {role}")