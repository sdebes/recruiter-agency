# Recruiter Agency - Listing Finder Agent
#
# Discovers job listings from configured job boards.
# Orchestrates the scraper service and deduplicates results.

from __future__ import annotations

import re
import uuid
from typing import Any, Dict, List, Optional

from utils.config_loader import load_profile
from services.tracker_service import get_all_listings, update_listing_fields


def _normalize(text: str) -> str:
    """Normalize text for comparison: lowercase and replace common umlauts."""
    replacements = {"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss", "å": "aa", "ø": "oe", "æ": "ae"}
    result = text.lower()
    for umlaut, ascii_replacement in replacements.items():
        result = result.replace(umlaut, ascii_replacement)
    return result


def _filter_by_location(listings: List[Dict]) -> List[Dict]:
    """Filter listings by city preferences from profile.yml.

    Jobs.ch is Swiss-only, so no country check needed.
    If cities are configured (e.g. \"Zürich\"), only show listings
    in those cities. Otherwise show all listings.
    """
    prefs = load_profile().get("search_preferences", {})
    cities_str = (prefs.get("cities", "") or "").strip()

    if not cities_str:
        return listings

    cities = [c.strip().lower() for c in cities_str.split(",") if c.strip()]
    cities_norm = [_normalize(c) for c in cities]

    filtered = []
    for listing in listings:
        loc = (listing.get("location", "") or "").strip()
        if not loc:
            filtered.append(listing)
            continue

        loc_norm = _normalize(loc)

        if any(c in loc_norm for c in cities_norm):
            filtered.append(listing)

    return filtered


def _deduplicate(new_listings: List[Dict], existing: List[Dict]) -> List[Dict]:
    """Remove listings that already exist in the tracker."""
    existing_urls = {l.get("url", "") for l in existing if l.get("url")}
    existing_titles = {
        (l.get("title", "").lower(), l.get("company", "").lower())
        for l in existing
    }

    deduped = []
    for listing in new_listings:
        url = listing.get("url", "")
        key = (listing.get("title", "").lower(), listing.get("company", "").lower())

        if url and url in existing_urls:
            continue
        if key in existing_titles:
            continue
        deduped.append(listing)

    return deduped


def find_listings(
    query: Optional[str] = None,
    limit: int = 20,
    boards: Optional[List[str]] = None,
    location: Optional[str] = None,
) -> Dict[str, Any]:
    """Search job boards for listings matching the given query.

    Args:
        query: Search query (defaults to profile's primary target roles).
        limit: Max listings per board.
        boards: Specific boards to search (defaults to config's enabled boards).
        location: Location to search in (e.g. "Zurich"). When provided, overrides
                  profile-based location filtering with a direct region search.

    Returns:
        Dict with 'listings' (newly found), 'total_found', and 'sources'.
    """
    if not query:
        profile = load_profile()
        primary = profile.get("target_roles", {}).get("primary", [])
        query = " ".join(primary[:3]) or "data scientist"

    from services.scraper_service import search_all_boards, batch_fetch_descriptions
    from services.llm_service import LLMService
    raw_listings = search_all_boards(query=query, limit=limit, location=location or "")
    total_scraped = len(raw_listings)
    sources = list({l.get("source", "unknown") for l in raw_listings})

    if location:
        total_after_filter = len(raw_listings)
    else:
        raw_listings = _filter_by_location(raw_listings)
        total_after_filter = len(raw_listings)

    existing = get_all_listings()
    deduped = _deduplicate(raw_listings, existing)

    # Heal: existing listings that are missing a description get their JD
    # fetched again and updated in place (stale rows from earlier scrapes).
    heal_targets = [
        l for l in existing
        if l.get("url") and not (l.get("description") or "").strip()
    ]
    if heal_targets:
        print(f"[listing_finder] Backfilling descriptions for {len(heal_targets)} existing listings...")

    # Batch-fetch descriptions for all new listings with URLs (+ heal targets)
    to_fetch = deduped + heal_targets
    urls_to_fetch = [l["url"] for l in to_fetch if l.get("url")]
    if urls_to_fetch:
        print(f"[listing_finder] Batch-fetching descriptions for {len(urls_to_fetch)} listings...")
        descriptions = batch_fetch_descriptions(urls_to_fetch)
        llm = LLMService()
        for listing in to_fetch:
            url = listing.get("url", "")
            desc = descriptions.get(url, "")
            if desc:
                listing["description"] = desc
                if len(desc) > 100:
                    try:
                        enriched = llm.summarize_jd(desc)
                        cleaned = enriched.get("cleaned_description", "")
                        if cleaned and len(cleaned) > 100:
                            listing["description"] = cleaned
                        listing["title"] = _best(enriched.get("position"), listing.get("title", "Unknown"))
                        listing["company"] = _best(enriched.get("company"), listing.get("company", "Unknown"))
                        listing.setdefault("location", enriched.get("location"))
                        listing.setdefault("salary_range", enriched.get("salary"))
                        listing.setdefault("seniority", enriched.get("seniority"))
                        listing.setdefault("employment_type", enriched.get("employment type"))
                        _swap_title_company(listing)
                    except Exception as e:
                        print(f"[listing_finder] LLM enrichment failed for {url}: {e}")

        # Persist healed fields back to the tracker
        healed = {l["id"]: l for l in heal_targets if (l.get("description") or "").strip()}
        for lid, listing in healed.items():
            try:
                update_listing_fields(lid, {
                    "description": listing["description"],
                    "title": listing.get("title"),
                    "company": listing.get("company"),
                    "location": listing.get("location"),
                    "salary_range": listing.get("salary_range"),
                    "seniority": listing.get("seniority"),
                    "employment_type": listing.get("employment_type"),
                })
            except Exception as e:
                print(f"[listing_finder] Failed to persist heal for {lid}: {e}")

    # Assign IDs
    for listing in deduped:
        if "id" not in listing or not listing["id"]:
            listing["id"] = str(uuid.uuid4())

    return {
        "listings": deduped,
        "total_found": total_scraped,
        "filtered_out": total_scraped - total_after_filter,
        "new_count": len(deduped),
        "duplicates": total_after_filter - len(deduped),
        "sources": sources,
    }


def _best(val, fallback):
    if not val or val.lower() in ["unknown", "not specified", "unknown position", "unknown company"]:
        return fallback
    return val


def _swap_title_company(result: Dict[str, Any]) -> Dict[str, Any]:
    """Detect and fix swapped title/company fields using heuristics."""
    title = result.get("title", "") or ""
    company = result.get("company", "") or ""

    company_patterns = [
        r"\bA/S\b", r"\bInc\.?\b", r"\bLLC\b", r"\bCorp\.?\b", r"\bLtd\.?\b",
        r"\bGmbH\b", r"\bAG\b", r"\bSA\b", r"\bPLC\b", r"\bSE\b", r"\b& Co\b",
        r"\bCo\.?\b", r"\bAB\b", r"\bOy\b", r"\bPty\b", r"\bBV\b", r"\bNV\b",
        r"\bKK\b", r"\bLLP\b", r"\bPLLC\b", r"\bPC\b",
    ]
    title_patterns = [
        r"\bEngineer\b", r"\bDeveloper\b", r"\bManager\b", r"\bAnalyst\b",
        r"\bDesigner\b", r"\bArchitect\b", r"\bLead\b", r"\bHead\b",
        r"\bSpecialist\b", r"\bConsultant\b", r"\bCoordinator\b", r"\bOfficer\b",
        r"\bDirector\b", r"\bChief\b", r"\bVP\b", r"\bPresident\b",
        r"\bAssociate\b", r"\bIntern\b", r"\bTechnician\b", r"\bAssistant\b",
        r"\bSupervisor\b", r"\bRepresentative\b", r"\bTrainee\b", r"\bAdvisor\b",
        r"\bResearcher\b", r"\bScientist\b", r"\bProfessor\b", r"\bLecturer\b",
        r"\bNurse\b", r"\bPhysician\b", r"\bAttorney\b",
    ]

    title_looks_like_company = (
        any(re.search(p, title) for p in company_patterns)
        or len(title) > 50
    )
    company_looks_like_title = any(re.search(p, company) for p in title_patterns)

    if title_looks_like_company and company_looks_like_title:
        result["title"] = company
        result["company"] = title

    return result


def enrich_listing(url: str) -> Dict[str, Any]:
    """Fetch and enrich a single listing URL with full JD text and structured metadata."""
    from services.llm_service import LLMService
    from services.scraper_service import fetch_jd_from_url

    # 1. Scrape raw data
    raw_data = fetch_jd_from_url(url)
    desc = raw_data.get("description", "")
    
    # 2. Extract structured metadata using LLM if description is available
    if desc and len(desc) > 100:
        llm = LLMService()
        enriched = llm.summarize_jd(desc)
        
        # Helper to pick the best value
        def best(field, fallback):
            val = enriched.get(field)
            if not val or val.lower() in ["unknown", "not specified", "unknown position", "unknown company"]:
                return fallback
            return val

        cleaned = enriched.get("cleaned_description", "")
        final_desc = cleaned if cleaned and len(cleaned) > 100 else desc

        result = {
            "url": url,
            "description": final_desc,
            "title": best("position", raw_data.get("title", "Unknown")),
            "company": best("company", raw_data.get("company", "Unknown")),
            "location": best("location", raw_data.get("location")),
            "salary_range": best("salary", raw_data.get("salary_range")),
            "seniority": best("seniority", None),
            "start_date": best("start_date", None),
            "employment_duration": best("employment duration", None),
            "employment_type": best("employment type", None),
        }

        return _swap_title_company(result)
    
    return _swap_title_company(raw_data)