# Recruiter Agency - Finding Node
#
# Orchestrates the listing finder agent to discover job listings
# from configured job boards. Supports both scanning and URL enrichment.

from __future__ import annotations

from typing import Any, Dict, List

from graph.state import AgentState
from agents.listing_finder import find_listings, enrich_listing
from services.tracker_service import record_scan


def scan_listings_node(state: AgentState) -> dict:
    """Search job boards for new listings matching the user's profile."""
    profile = state.get("profile", {})
    primary = profile.get("target_roles", {}).get("primary", [])
    query = " ".join(primary[:3]) if primary else "data scientist"

    result = find_listings(query=query, limit=15)

    new_listings = result.get("listings", [])
    total = result.get("total_found", 0)
    new_count = result.get("new_count", 0)

    # Record in scan history
    for listing in new_listings:
        record_scan(
            url=listing.get("url", ""),
            title=listing.get("title", "Unknown"),
            company=listing.get("company", "Unknown"),
            portal=listing.get("source", "unknown"),
            status="added" if listing else "skipped",
        )

    message = (
        f"Scanned job boards — found {total} total, "
        f"{new_count} new listings"
    )

    return {
        "listings": new_listings,
        "pipeline_phase": "finding",
        "messages": state.get("messages", []) + [message],
    }


def enrich_url_node(state: AgentState) -> dict:
    """Enrich a URL-based listing by fetching the full page content."""
    listings = state.get("listings", [])
    if not listings:
        return {"errors": state.get("errors", []) + ["No listing to enrich"]}

    listing = listings[0]
    url = listing.get("url", "")
    if not url:
        return {"pipeline_phase": "evaluating"}

    enriched = enrich_listing(url)

    # Update the listing with fetched content
    updated = {
        **listing,
        "title": enriched.get("title", listing.get("title", "Unknown")),
        "company": enriched.get("company", listing.get("company", "Unknown")),
        "description": enriched.get("description", listing.get("description", "")),
        "salary_range": enriched.get("salary_range", listing.get("salary_range")),
    }

    return {
        "listings": [updated],
        "pipeline_phase": "evaluating",
        "messages": state.get("messages", []) + [
            f"Fetched JD from {url[:60]}..."
        ],
    }