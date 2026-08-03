# Recruiter Agency - Tracker Service
#
# SQLite-backed CRUD for the application tracker.
# Manages listings, evaluations, applications, interview preps,
# story bank, and scan history.

from __future__ import annotations

import json
import os
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv

load_dotenv()


def _decode_json_field(value: Any, default: Any = None) -> Any:
    """Decode a JSON-encoded string field back to a Python object."""
    if default is None:
        default = []
    if isinstance(value, str):
        try:
            return json.loads(value)
        except (json.JSONDecodeError, TypeError):
            return default
    return value if value is not None else default


def _get_db_path() -> str:
    """Get the applications database path."""
    path = os.getenv("DB_PATH", "agentdb/applications.db")
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    return path


def _conn() -> sqlite3.Connection:
    """Get a connection to the applications database."""
    conn = sqlite3.connect(_get_db_path())
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    """Initialize the database schema. Idempotent — safe to call on startup."""
    conn = _conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS listings (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            company TEXT NOT NULL,
            url TEXT,
            description TEXT NOT NULL,
            source TEXT,
            location TEXT,
            salary_range TEXT,
            posted_date TEXT,
            archetype TEXT,
            seniority TEXT,
            start_date TEXT,
            employment_duration TEXT,
            employment_type TEXT,
            score REAL,
            fit_rationale TEXT,
            is_active INTEGER DEFAULT 1,
            created_at TEXT DEFAULT (datetime('now'))
        );



        CREATE TABLE IF NOT EXISTS evaluations (
            id TEXT PRIMARY KEY,
            listing_id TEXT NOT NULL REFERENCES listings(id) ON DELETE CASCADE,
            cv_match_score REAL,
            north_star_score REAL,
            comp_score REAL,
            culture_score REAL,
            red_flags TEXT,
            global_score REAL,
            legitimacy TEXT,
            archetype_detected TEXT,
            detailed_notes TEXT,
            report_path TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS applications (
            id TEXT PRIMARY KEY,
            listing_id TEXT REFERENCES listings(id) ON DELETE SET NULL,
            company TEXT NOT NULL,
            role TEXT NOT NULL,
            status TEXT DEFAULT 'Evaluated',
            score REAL,
            applied_date TEXT,
            interview_dates TEXT,
            notes TEXT,
            tailored_cv_path TEXT,
            cover_letter_path TEXT,
            report_link TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS interview_preps (
            id TEXT PRIMARY KEY,
            application_id TEXT NOT NULL REFERENCES applications(id) ON DELETE CASCADE,
            company TEXT NOT NULL,
            role TEXT NOT NULL,
            star_stories TEXT,
            company_questions TEXT,
            qa_pairs TEXT,
            prep_doc_path TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS story_bank (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            situation TEXT NOT NULL,
            task TEXT NOT NULL,
            action TEXT NOT NULL,
            result TEXT NOT NULL,
            reflection TEXT,
            tags TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS scan_history (
            url TEXT PRIMARY KEY,
            first_seen TEXT NOT NULL,
            last_seen TEXT,
            title TEXT,
            company TEXT,
            status TEXT,
            portal TEXT,
            seen_count INTEGER DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            updated_at TEXT DEFAULT (datetime('now'))
        );
    """)
    conn.commit()
    conn.close()


def _new_id() -> str:
    return str(uuid.uuid4())


# ── Listings ─────────────────────────────────────────────────────────────

def insert_listing(listing: Dict[str, Any]) -> str:
    lid = listing.get("id", _new_id())
    conn = _conn()
    conn.execute("""
        INSERT OR REPLACE INTO listings
            (id, title, company, url, description, source, location, salary_range, 
             posted_date, archetype, seniority, start_date, employment_duration, employment_type,
             score, fit_rationale)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        lid, listing.get("title", "Unknown Title"), listing.get("company", "Unknown Company"), listing.get("url"),
        listing.get("description") or listing.get("raw_text", ""), listing.get("source"), listing.get("location"),
        listing.get("salary_range") or listing.get("salary"), listing.get("posted_date"), listing.get("archetype"),
        listing.get("seniority"), listing.get("start_date"), 
        listing.get("employment_duration"), listing.get("employment_type"),
        listing.get("score"), listing.get("fit_rationale")
    ))
    conn.commit()
    conn.close()
    return lid


def save_scraped_listings(listings: List[Dict[str, Any]]) -> List[str]:
    """Save a batch of scraped/found listings to the SQLite database."""
    saved_ids = []
    for listing in listings:
        saved_ids.append(insert_listing(listing))
    return saved_ids


def update_listing_fields(listing_id: str, fields: Dict[str, Any]) -> None:
    """Update a subset of fields on an existing listing (e.g. backfilled JD)."""
    if not fields:
        return
    allowed = {
        "title", "company", "url", "description", "source", "location",
        "salary_range", "posted_date", "archetype", "seniority",
        "start_date", "employment_duration", "employment_type",
        "score", "fit_rationale",
    }
    cols = [k for k in fields if k in allowed]
    if not cols:
        return
    conn = _conn()
    conn.execute(
        f"UPDATE listings SET {', '.join(f'{c} = ?' for c in cols)} WHERE id = ?",
        [fields[c] for c in cols] + [listing_id],
    )
    conn.commit()
    conn.close()



def get_listing(listing_id: str) -> Optional[Dict[str, Any]]:
    conn = _conn()
    row = conn.execute("SELECT * FROM listings WHERE id = ?", (listing_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_all_listings() -> List[Dict[str, Any]]:
    conn = _conn()
    rows = conn.execute("SELECT * FROM listings ORDER BY created_at DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def delete_listing(listing_id: str):
    conn = _conn()
    conn.execute("DELETE FROM listings WHERE id = ?", (listing_id,))
    conn.commit()
    conn.close()


# ── Evaluations ──────────────────────────────────────────────────────────

def insert_evaluation(eval_data: Dict[str, Any]) -> str:
    eid = eval_data.get("id", _new_id())
    conn = _conn()
    conn.execute("""
        INSERT INTO evaluations
            (id, listing_id, cv_match_score, north_star_score, comp_score, culture_score,
             red_flags, global_score, legitimacy, archetype_detected, detailed_notes, report_path)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        eid, eval_data["listing_id"],
        eval_data.get("cv_match_score"), eval_data.get("north_star_score"),
        eval_data.get("comp_score"), eval_data.get("culture_score"),
        json.dumps(eval_data.get("red_flags", [])),
        eval_data.get("global_score"), eval_data.get("legitimacy"),
        eval_data.get("archetype_detected"), eval_data.get("detailed_notes"),
        eval_data.get("report_path"),
    ))
    conn.commit()
    conn.close()
    return eid


def get_evaluations_for_listing(listing_id: str) -> List[Dict[str, Any]]:
    conn = _conn()
    rows = conn.execute(
        "SELECT * FROM evaluations WHERE listing_id = ? ORDER BY created_at DESC",
        (listing_id,),
    ).fetchall()
    conn.close()
    results = []
    for r in rows:
        d = dict(r)
        d["red_flags"] = _decode_json_field(d.get("red_flags"))
        results.append(d)
    return results


# ── Tailored CVs ─────────────────────────────────────────────────────────

def save_tailored_cv(listing_id: str, cv_path: str, commentary: str = "", google_doc_url: str = "", resume_builder_url: str = "") -> str:
    """Persist the path of a generated tailored CV for a listing."""
    conn = _conn()
    # Create the table if it doesn't exist yet (safe migration)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS tailored_cvs (
            id TEXT PRIMARY KEY,
            listing_id TEXT NOT NULL,
            cv_path TEXT NOT NULL,
            commentary TEXT,
            google_doc_url TEXT DEFAULT '',
            resume_builder_url TEXT DEFAULT '',
            created_at TEXT DEFAULT (datetime('now'))
        )
    """)
    # Migration: add google_doc_url column if it doesn't exist
    try:
        conn.execute("ALTER TABLE tailored_cvs ADD COLUMN google_doc_url TEXT DEFAULT ''")
    except sqlite3.OperationalError:
        pass
    # Migration: add resume_builder_url column if it doesn't exist
    try:
        conn.execute("ALTER TABLE tailored_cvs ADD COLUMN resume_builder_url TEXT DEFAULT ''")
    except sqlite3.OperationalError:
        pass
    tid = _new_id()
    conn.execute(
        "INSERT INTO tailored_cvs (id, listing_id, cv_path, commentary, google_doc_url, resume_builder_url) VALUES (?, ?, ?, ?, ?, ?)",
        (tid, listing_id, cv_path, commentary, google_doc_url, resume_builder_url),
    )
    conn.commit()
    conn.close()
    return tid


def get_tailored_cvs_for_listing(listing_id: str) -> List[Dict[str, Any]]:
    """Return all tailored CVs for a listing, newest first."""
    conn = _conn()
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS tailored_cvs (
                id TEXT PRIMARY KEY,
                listing_id TEXT NOT NULL,
                cv_path TEXT NOT NULL,
                commentary TEXT,
                google_doc_url TEXT DEFAULT '',
                resume_builder_url TEXT DEFAULT '',
                created_at TEXT DEFAULT (datetime('now'))
            )
        """)
        # Migration: add google_doc_url column if it doesn't exist
        try:
            conn.execute("ALTER TABLE tailored_cvs ADD COLUMN google_doc_url TEXT DEFAULT ''")
        except sqlite3.OperationalError:
            pass
        # Migration: add resume_builder_url column if it doesn't exist
        try:
            conn.execute("ALTER TABLE tailored_cvs ADD COLUMN resume_builder_url TEXT DEFAULT ''")
        except sqlite3.OperationalError:
            pass
        rows = conn.execute(
            "SELECT * FROM tailored_cvs WHERE listing_id = ? ORDER BY created_at DESC",
            (listing_id,),
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except Exception:
        conn.close()
        return []


# ── Applications ─────────────────────────────────────────────────────────

def insert_application(app: Dict[str, Any]) -> str:
    aid = app.get("id", _new_id())
    now = datetime.now().isoformat()
    conn = _conn()
    conn.execute("""
        INSERT INTO applications
            (id, listing_id, company, role, status, score, applied_date,
             interview_dates, notes, tailored_cv_path, cover_letter_path, report_link,
             created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        aid, app.get("listing_id"), app["company"], app["role"],
        app.get("status", "Evaluated"), app.get("score"),
        app.get("applied_date"), json.dumps(app.get("interview_dates", [])),
        app.get("notes", ""), app.get("tailored_cv_path"),
        app.get("cover_letter_path"), app.get("report_link"),
        now, now,
    ))
    conn.commit()
    conn.close()
    return aid


def update_application_status(app_id: str, status: str, notes: Optional[str] = None):
    conn = _conn()
    if notes:
        conn.execute(
            "UPDATE applications SET status = ?, notes = ?, updated_at = datetime('now') WHERE id = ?",
            (status, notes, app_id),
        )
    else:
        conn.execute(
            "UPDATE applications SET status = ?, updated_at = datetime('now') WHERE id = ?",
            (status, app_id),
        )
    conn.commit()
    conn.close()


def get_application(app_id: str) -> Optional[Dict[str, Any]]:
    conn = _conn()
    row = conn.execute("SELECT * FROM applications WHERE id = ?", (app_id,)).fetchone()
    conn.close()
    if row is None:
        return None
    d = dict(row)
    d["interview_dates"] = _decode_json_field(d.get("interview_dates"))
    return d


def get_all_applications() -> List[Dict[str, Any]]:
    conn = _conn()
    rows = conn.execute(
        "SELECT * FROM applications ORDER BY updated_at DESC"
    ).fetchall()
    conn.close()
    return [
        {**dict(r), "interview_dates": _decode_json_field(dict(r).get("interview_dates"))}
        for r in rows
    ]


def get_application_stats() -> Dict[str, Any]:
    """Get aggregate stats about the application pipeline."""
    conn = _conn()
    total = conn.execute("SELECT COUNT(*) FROM applications").fetchone()[0]
    by_status = conn.execute(
        "SELECT status, COUNT(*) as cnt FROM applications GROUP BY status"
    ).fetchall()
    avg_score = conn.execute(
        "SELECT AVG(score) FROM applications WHERE score IS NOT NULL"
    ).fetchone()[0]
    conn.close()
    return {
        "total": total,
        "by_status": {r["status"]: r["cnt"] for r in by_status},
        "avg_score": round(avg_score, 2) if avg_score else 0.0,
    }


# ── Scan History ─────────────────────────────────────────────────────────

def record_scan(url: str, title: str, company: str, portal: str, status: str = "added"):
    conn = _conn()
    existing = conn.execute(
        "SELECT * FROM scan_history WHERE url = ?", (url,)
    ).fetchone()
    now = datetime.now().isoformat()
    if existing:
        conn.execute(
            "UPDATE scan_history SET last_seen = ?, seen_count = seen_count + 1 WHERE url = ?",
            (now, url),
        )
    else:
        conn.execute(
            "INSERT INTO scan_history (url, first_seen, last_seen, title, company, status, portal, seen_count) VALUES (?, ?, ?, ?, ?, ?, ?, 1)",
            (now, now, title, company, status, portal),
        )
    conn.commit()
    conn.close()


# ── Story Bank ───────────────────────────────────────────────────────────

def add_story(story: Dict[str, Any]) -> str:
    sid = story.get("id", _new_id())
    conn = _conn()
    conn.execute("""
        INSERT INTO story_bank (id, title, situation, task, action, result, reflection, tags)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        sid, story["title"], story["situation"], story["task"],
        story["action"], story["result"], story.get("reflection"),
        json.dumps(story.get("tags", [])),
    ))
    conn.commit()
    conn.close()
    return sid


def get_all_stories() -> List[Dict[str, Any]]:
    conn = _conn()
    rows = conn.execute("SELECT * FROM story_bank ORDER BY created_at DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ── Settings ─────────────────────────────────────────────────────────────

def set_setting(key: str, value: Any):
    conn = _conn()
    conn.execute("""
        INSERT INTO settings (key, value, updated_at)
        VALUES (?, ?, datetime('now'))
        ON CONFLICT(key) DO UPDATE SET
            value = excluded.value,
            updated_at = datetime('now')
    """, (key, json.dumps(value)))
    conn.commit()
    conn.close()


def get_setting(key: str, default: Any = None) -> Any:
    conn = _conn()
    row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    conn.close()
    if row:
        return json.loads(row[0])
    return default