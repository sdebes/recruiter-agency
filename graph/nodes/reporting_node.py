# Recruiter Agency - Reporting Node
#
# Generates a markdown evaluation report for the user.
# Reports are saved to reports/{num}-{company}-{date}.md

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any, Dict, Optional

from graph.state import AgentState


def _slugify(text: str) -> str:
    """Convert text to a filesystem-safe slug."""
    return "".join(c if c.isalnum() or c in "-_" else "-" for c in text.lower()).strip("-")


def _get_report_number() -> int:
    """Determine the next sequential report number."""
    reports_dir = Path("reports")
    reports_dir.mkdir(parents=True, exist_ok=True)
    existing = [f.stem for f in reports_dir.glob("*.md")]
    max_num = 0
    for name in existing:
        parts = name.split("-", 1)
        if parts[0].isdigit():
            max_num = max(max_num, int(parts[0]))
    return max_num + 1


def _score_label(score: float) -> str:
    """Get a human-readable label for a score."""
    if score >= 4.5:
        return "Strong Match — Apply immediately"
    elif score >= 4.0:
        return "Good Match — Worth applying"
    elif score >= 3.5:
        return "Decent — Apply only if specific reason"
    else:
        return "Weak Match — Recommend against applying"


def generate_report(state: AgentState) -> dict:
    """Generate a markdown evaluation report from the current evaluation."""
    evaluation = state.get("current_evaluation")
    listings = state.get("listings", [])
    idx = state.get("current_listing_index", 0)
    profile = state.get("profile", {})

    if not evaluation or not listings or idx >= len(listings):
        return {
            "errors": state.get("errors", []) + ["Cannot generate report: missing data"],
            "pipeline_phase": "done",
        }

    listing = listings[idx]
    company = listing.get("company", "Unknown")
    role = listing.get("title", "Unknown")
    today = date.today().isoformat()
    company_slug = _slugify(company)
    report_num = _get_report_number()

    score = evaluation.get("global_score", 0.0)

    # Build the report
    report = f"""# Evaluation Report: {role} @ {company}

**Date:** {today}
**Score:** {score}/5 — {_score_label(score)}
**Legitimacy:** {evaluation.get('legitimacy', 'Not assessed')}
**Archetype:** {evaluation.get('archetype_detected', 'Not detected')}

---

## Evaluation Details

### CV Match Score: {evaluation.get('cv_match_score', 'N/A')}/5

### North Star Alignment: {evaluation.get('north_star_score', 'N/A')}/5

### Compensation Score: {evaluation.get('comp_score', 'N/A')}/5

### Culture/Fit Score: {evaluation.get('culture_score', 'N/A')}/5

### Red Flags
"""
    flags = evaluation.get("red_flags", [])
    if flags:
        for flag in flags:
            report += f"- {flag}\n"
    else:
        report += "- None identified\n"

    report += f"""
### Detailed Notes

{evaluation.get('detailed_notes', 'No detailed notes available.')}

---

## Scores Breakdown

| Dimension | Score |
|-----------|-------|
| CV Match | {evaluation.get('cv_match_score', 'N/A')}/5 |
| North Star Alignment | {evaluation.get('north_star_score', 'N/A')}/5 |
| Compensation | {evaluation.get('comp_score', 'N/A')}/5 |
| Culture/Fit | {evaluation.get('culture_score', 'N/A')}/5 |
| **Global (weighted)** | **{score}/5** |

## Listing Info

| Field | Value |
|-------|-------|
| Company | {company} |
| Role | {role} |
| URL | {listing.get('url', 'N/A')} |
| Location | {listing.get('location', 'N/A')} |
| Salary Range | {listing.get('salary_range', 'N/A')} |
| Source | {listing.get('source', 'N/A')} |
"""

    # Write the report
    reports_dir = Path("reports")
    reports_dir.mkdir(parents=True, exist_ok=True)
    report_path = reports_dir / f"{report_num:03d}-{company_slug}-{today}.md"
    report_path.write_text(report)

    message = f"Report saved to {report_path}"

    return {
        "report_path": str(report_path),
        "pipeline_phase": "done",
        "messages": state.get("messages", []) + [message],
    }