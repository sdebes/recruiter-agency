# Recruiter Agency - Input Node
#
# Processes the initial user input (URL, JD text, or command)
# and produces the initial state for the pipeline.

from __future__ import annotations

import re
import uuid
from typing import Any, Dict, Optional

from graph.state import AgentState, JobListing


def is_url(text: str) -> bool:
    """Check if input text looks like a URL."""
    return bool(re.match(r"https?://\S+", text.strip()))


def parse_jd_metadata(text: str) -> dict:
    """Extract basic metadata from raw JD text."""
    metadata = {
        "title": "Unknown",
        "company": "Unknown",
        "location": None,
        "salary_range": None,
    }
    return metadata


def input_node(state: AgentState) -> dict:
    """Process user input and create the initial listing.

    Handles:
    - URL input → placeholder listing (scraping happens in finding_node)
    - Raw JD text → JobListing with extracted metadata
    """
    input_type = state.get("input_type", "jd_text")
    input_data = state.get("input_data", "")

    if not input_data:
        return {
            "errors": ["No input data provided"],
            "pipeline_phase": "done",
        }

    if input_type == "url" or is_url(input_data):
        # URL-based: create a placeholder listing
        listing: JobListing = {
            "id": str(uuid.uuid4()),
            "url": input_data,
            "title": "Unknown (awaiting scrape)",
            "company": "Unknown",
            "description": "",
            "source": "url",
            "location": None,
            "salary_range": None,
        }
        message = f"Processing URL: {input_data[:80]}..."
        next_phase = "finding"
    else:
        # Raw JD text: create listing directly
        lines = input_data.strip().split("\n")
        title = "Unknown Position"
        company = "Unknown Company"

        # Try to guess title and company from first lines
        for line in lines[:10]:
            line = line.strip()
            if not title or title == "Unknown Position":
                if "title" in line.lower() or "position" in line.lower():
                    title = line.split(":", 1)[-1].strip() if ":" in line else line
            if not company or company == "Unknown Company":
                if "company" in line.lower():
                    company = line.split(":", 1)[-1].strip() if ":" in line else company

        listing = {
            "id": str(uuid.uuid4()),
            "url": "",
            "title": title,
            "company": company,
            "description": input_data,
            "raw_text": input_data,
            "source": "manual",
            "location": None,
            "salary_range": None,
        }
        message = f"Analyzing job posting: {title} at {company}"
        next_phase = "evaluating"

    return {
        "listings": [listing],
        "pipeline_phase": next_phase,
        "messages": [message],
    }