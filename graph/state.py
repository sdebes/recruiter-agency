# Recruiter Agency - Central Graph State
#
# This module defines the AgentState TypedDict that flows through
# every node in the LangGraph pipeline. All nodes read from and
# write to this shared state.

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from typing_extensions import TypedDict


# ── Data Models ──────────────────────────────────────────────────────────

class JobListing(TypedDict, total=False):
    """A job listing discovered from a job board or entered manually."""
    id: str
    title: str
    company: str
    url: str
    description: str
    source: str                          # "jobs_ch" | "manual" | etc.
    location: Optional[str]
    salary_range: Optional[str]
    posted_date: Optional[str]
    archetype: Optional[str]             # Set after archetype detection
    raw_text: Optional[str]              # Full JD text


class Evaluation(TypedDict, total=False):
    """A-F evaluation results for a single job listing."""
    listing_id: str
    cv_match_score: float                # 1.0-5.0
    north_star_score: float              # 1.0-5.0
    comp_score: float                    # 1.0-5.0
    culture_score: float                 # 1.0-5.0
    red_flags: List[str]                 # Each red flag subtracts from global
    global_score: float                  # Weighted average of above
    legitimacy: str                      # "High Confidence" | "Proceed with Caution" | "Suspicious"
    archetype_detected: Optional[str]
    report_path: Optional[str]
    detailed_notes: Optional[str]


class Application(TypedDict, total=False):
    """A tracked application in the pipeline."""
    id: str
    listing_id: str
    company: str
    role: str
    status: str                          # Canonical: Evaluated|Applied|Responded|Interview|Offer|Rejected|Discarded|SKIP
    score: Optional[float]
    applied_date: Optional[str]
    interview_dates: List[str]
    notes: str
    tailored_cv_path: Optional[str]
    cover_letter_path: Optional[str]
    report_link: Optional[str]


class InterviewPrep(TypedDict, total=False):
    """Interview preparation materials for an application."""
    application_id: str
    company: str
    role: str
    star_stories: List[Dict[str, str]]   # [{situation, task, action, result, reflection}]
    company_questions: List[str]
    generated_qas: List[Dict[str, str]]  # [{question, answer}]
    prep_doc_path: Optional[str]


class STARStory(TypedDict, total=False):
    """A single STAR+R story from the story bank."""
    id: str
    title: str
    situation: str
    task: str
    action: str
    result: str
    reflection: Optional[str]
    tags: List[str]


# ── Graph State ──────────────────────────────────────────────────────────

class AgentState(TypedDict, total=False):
    """Complete state flowing through the LangGraph pipeline.

    All graph nodes read from this state and write updates to it.
    """
    # ── Input ──
    input_type: str                      # "url" | "jd_text" | "scan" | "batch"
    input_data: str                      # URL, JD text, or command

    # ── User Profile (loaded once at start) ──
    profile: Dict[str, Any]             # From config/profile.yml
    archetypes_config: Dict[str, Any]   # From config/archetypes.yml

    # ── Job Listings in Flight ──
    listings: List[JobListing]
    current_listing_index: int           # Which listing we're evaluating

    # ── Evaluation Results ──
    evaluations: List[Evaluation]
    current_evaluation: Optional[Evaluation]

    # ── Applications ──
    applications: List[Application]

    # ── Interview Prep ──
    interview_preps: List[InterviewPrep]

    # ── Pipeline Phase ──
    pipeline_phase: str                  # "input" | "finding" | "evaluating" | "tailoring" | "tracking" | "prep" | "reporting" | "done"
    pending_urls: List[str]

    # ── Human-in-the-Loop ──
    user_decision: Optional[str]         # "apply" | "skip" | "review_later"
    user_approval_required: bool
    interrupt_reason: Optional[str]      # Why we paused
    messages: List[str]                  # Streaming messages for the user

    # ── Errors ──
    errors: List[str]

    # ── Output Paths ──
    report_path: Optional[str]
    output_paths: List[str]


# ── Default State Factory ────────────────────────────────────────────────

def create_initial_state(
    input_type: str = "",
    input_data: str = "",
    profile: Optional[Dict[str, Any]] = None,
    archetypes_config: Optional[Dict[str, Any]] = None,
) -> AgentState:
    """Create a fresh AgentState with defaults."""
    return {
        # Input
        "input_type": input_type,
        "input_data": input_data,

        # User profile
        "profile": profile or {},
        "archetypes_config": archetypes_config or {},

        # Job listings
        "listings": [],
        "current_listing_index": 0,

        # Evaluations
        "evaluations": [],
        "current_evaluation": None,

        # Applications
        "applications": [],

        # Interview prep
        "interview_preps": [],

        # Pipeline phase
        "pipeline_phase": "input",
        "pending_urls": [],

        # HITL
        "user_decision": None,
        "user_approval_required": False,
        "interrupt_reason": None,
        "messages": [],

        # Errors
        "errors": [],

        # Output paths
        "report_path": None,
        "output_paths": [],
    }