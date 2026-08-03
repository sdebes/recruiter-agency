# Recruiter Agency - Tracking Node
#
# Records evaluation results and application state in the SQLite database.
# Handles canonical state transitions and deduplication.

from __future__ import annotations

from typing import Any, Dict, Optional

from graph.state import AgentState
from services.tracker_service import (
    init_db,
    insert_listing,
    insert_evaluation,
    insert_application,
    update_application_status,
    get_application,
    get_all_applications,
)


def _resolve_status(user_decision: Optional[str]) -> str:
    """Map user decision to canonical application status."""
    mapping = {
        "apply": "Evaluated",       # User wants to apply next
        "skip": "SKIP",              # Not a fit
        "review_later": "Evaluated", # Undecided, keep evaluated
    }
    return mapping.get(user_decision or "", "Evaluated")


def track_listing_node(state: AgentState) -> dict:
    """Store the listing and evaluation in the database.

    Creates the application tracker entry with the user's decision.
    Returns updated state with application IDs.
    """
    init_db()

    listings = state.get("listings", [])
    idx = state.get("current_listing_index", 0)
    evaluation = state.get("current_evaluation")
    user_decision = state.get("user_decision")

    if not listings or idx >= len(listings) or not evaluation:
        return {
            "errors": state.get("errors", []) + ["No listing or evaluation to track"],
            "pipeline_phase": "done",
        }

    listing = listings[idx]

    # 1. Insert listing
    lid = insert_listing({
        "id": listing.get("id"),
        "title": listing.get("title", "Unknown Title"),
        "company": listing.get("company", "Unknown Company"),
        "url": listing.get("url", ""),
        "description": listing.get("description", listing.get("raw_text", "")),
        "source": listing.get("source", "manual"),
        "location": listing.get("location"),
        "salary_range": listing.get("salary_range"),
        "posted_date": listing.get("posted_date"),
        "archetype": evaluation.get("archetype_detected"),
    })

    # 2. Insert evaluation
    eid = insert_evaluation({
        "listing_id": lid,
        "cv_match_score": evaluation.get("cv_match_score"),
        "north_star_score": evaluation.get("north_star_score"),
        "comp_score": evaluation.get("comp_score"),
        "culture_score": evaluation.get("culture_score"),
        "red_flags": evaluation.get("red_flags", []),
        "global_score": evaluation.get("global_score"),
        "legitimacy": evaluation.get("legitimacy"),
        "archetype_detected": evaluation.get("archetype_detected"),
        "detailed_notes": evaluation.get("detailed_notes"),
        "report_path": evaluation.get("report_path"),
    })

    # 3. Insert or update application
    status = _resolve_status(user_decision)

    aid = insert_application({
        "listing_id": lid,
        "company": listing.get("company", "Unknown"),
        "role": listing.get("title", "Unknown"),
        "status": status,
        "score": evaluation.get("global_score"),
        "notes": f"Score: {evaluation.get('global_score', 'N/A')}/5 — {evaluation.get('legitimacy', '')}",
    })

    message = f"Tracked {listing.get('title', '')} at {listing.get('company', '')} — Status: {status}"

    return {
        "applications": get_all_applications(),
        "pipeline_phase": "tracking",
        "messages": state.get("messages", []) + [message],
    }


def routing_node(state: AgentState) -> dict:
    """Route based on user decision.

    - 'apply' → proceed to tailoring (and eventually reporting)
    - 'skip' → skip to next listing or done
    - 'review_later' → report only
    """
    user_decision = state.get("user_decision")

    if user_decision == "apply":
        return {
            "pipeline_phase": "tailoring",
            "messages": state.get("messages", []) + ["Preparing tailored application materials..."],
        }
    elif user_decision == "skip":
        return {
            "pipeline_phase": "done",
            "messages": state.get("messages", []) + ["Listing skipped."],
        }
    else:
        return {
            "pipeline_phase": "reporting",
        }