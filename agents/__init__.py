# Recruiter Agency — Agents Module
#
# Exports all agent interfaces for the recruiter agency pipeline.

from agents.job_finder_agent import find_jobs, print_shortlist
from agents.cv_tailor_agent import tailor_for_shortlist, load_base_resumejson
from agents.notion_tracker import (
    prepare_notion_entry,
    serialize_notion_properties,
    prepare_shortlist_for_notion,
    update_application_status,
    get_local_applications,
    NOTION_DB_SCHEMA,
)
from agents.orchestrator import run_full_pipeline
from agents.listing_finder import find_listings, enrich_listing

__all__ = [
    # Agent 1 — Job Finder
    "find_jobs",
    "print_shortlist",
    # Agent 2 — CV & Cover Letter Tailor
    "tailor_for_shortlist",
    "load_base_resumejson",
    # Agent 3 — Notion Tracker
    "prepare_notion_entry",
    "serialize_notion_properties",
    "prepare_shortlist_for_notion",
    "update_application_status",
    "get_local_applications",
    "NOTION_DB_SCHEMA",
    # Orchestrator
    "run_full_pipeline",
    # Legacy
    "find_listings",
    "enrich_listing",
]