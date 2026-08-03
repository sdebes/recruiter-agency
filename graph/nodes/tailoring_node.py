# Recruiter Agency - CV Tailoring Node (ResumeBuilder Edition)
#
# Reads the base CV from the ResumeBuilder resumeinfo.json (the master
# reference) and the job description, then produces a tailored version
# in the same structured JSON format — saved alongside the master as a
# separate file so the user can preview it in the ResumeBuilder UI without
# altering the original.
#
# The agent treats resumeinfo.json as an intentionally overfilled reference
# and selects only the entries most relevant to the target role.

from __future__ import annotations

import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from dotenv import load_dotenv

load_dotenv(
    os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))), ".env"
    )
)
load_dotenv()

from services.llm_service import LLMService


# ── Paths ──────────────────────────────────────────────────────────────────

def _project_root() -> Path:
    return Path(__file__).parent.parent.parent.resolve()

_RESUME_BUILDER_JSON = (
    _project_root() / "config" / "resumeinfo.json"
)

_OUTPUT_DIR = _project_root() / "output" / "resumes"


def _load_base_resume_json() -> dict:
    """Load the canonical base CV from the master ResumeBuilder JSON file."""
    path = _RESUME_BUILDER_JSON
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {}


def _slugify(text: str, max_len: int = 40) -> str:
    text = re.sub(r"[^\w\s-]", "", text.lower())
    text = re.sub(r"[\s_-]+", "_", text).strip("_")
    return text[:max_len]


def _save_tailored_md(content: str, company: str, role: str) -> Path:
    """Write the tailored CV markdown to output/resumes/ and return the path."""
    _OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M")
    filename = f"cv_{_slugify(company)}_{_slugify(role)}_{stamp}.md"
    out_path = _OUTPUT_DIR / filename
    out_path.write_text(content, encoding="utf-8")
    return out_path


def _save_tailored_json(data: dict, company: str, role: str) -> Path:
    """Save the tailored resume JSON to output/resumes/ as a new file.

    Naming convention: {company}_{title}_resumeinfo.json
    The master resumeinfo.json is never modified.
    """
    _OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M")
    filename = f"resume_{_slugify(company)}_{_slugify(role)}_{stamp}_resumeinfo.json"
    out_path = _OUTPUT_DIR / filename
    out_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return out_path


# ── Prompt ─────────────────────────────────────────────────────────────────

_SYSTEM = (
    "You are an elite professional CV writer with 15 years of experience "
    "helping data scientists and engineers land jobs at top-tier companies. "
    "You output structured JSON only — no commentary, no markdown."
)

_PROMPT_TEMPLATE = """You are tailoring a candidate's structured CV for a specific job.

The candidate's base CV is intentionally **overfilled** — it contains every
experience, skill, project, course, and reference they have ever accumulated.
Your job is to be **selective**: choose only the entries that strengthen their
candidacy for *this specific role*. A tailored CV should fit on 1-2 pages.

## Rules

1. **Never invent** experience, companies, metrics, dates, skills, education,
   projects, or anything the candidate does not already have.
2. **Do NOT change** the name/email/phone/linkedin/github/location/permit
   contact fields.
3. **Summaries** — Use the candidate's **existing summaries** as the starting
   point. Adapt and rephrase `summaries[0]` using JD keywords, but keep the
   same tone, structure, and level of detail. Do NOT write a generic AI-sounding
   summary from scratch. Drop unused entries from the array.
4. **Skills** — remove entire categories that are totally irrelevant. For kept
   categories, keep **5-8 skills** — do not strip them down to 2-3. Reorder
   remaining categories and skills so the most relevant appear first.
5. **Experience** — keep only the experience entries that are most relevant
   to this role. Drop entire entries that are not relevant. Within kept entries:
   - **Preserve the original bullet point detail and length.** Each bullet
     should be as detailed as the original (same metrics, same level of
     specificity). Rephrase using JD keywords but do NOT shorten or truncate.
   - Reorder bullets so the most relevant ones appear first.
   - You may drop irrelevant bullets from a kept entry, but keep at least 3.
6. **Education** — **Always keep education.** This section is mandatory and
   should never be dropped. Keep all education entries — do not remove any.
   Do not modify the kept entries.
7. **Projects** — keep only projects relevant to this role. Drop the rest.
8. **Courses** — keep only courses relevant to this role. Drop the rest.
9. **References** — you may keep or drop as needed.
10. The result must be a concise, targeted CV. Every entry you include should
    serve the application. Quality over quantity.

Output ONLY valid JSON matching the schema below. No preamble, no code fences,
no commentary.

```json
{{
  "name": "<string>",
  "title": "<string>",
  "email": "<string>",
  "phone": "<string>",
  "linkedin": "<string>",
  "github": "<string>",
  "location": "<string>",
  "permit": "<string>",
  "summaries": ["<primary tailored summary>"],
  "skills": {{
    "RelevantCategory": ["skill1", "skill2"]
  }},
  "experience": [
    {{
      "company": "<string>",
      "role": "<string>",
      "location": "<string>",
      "startDate": "<string>",
      "endDate": "<string>",
      "bulletpoints": ["<rephrased bullet>"]
    }}
  ],
  "education": [ ... ],
  "courses": [ ... ],
  "projects": [ ... ],
  "references": [ ... ]
}}
```

## Target Role
Company: {company}
Role: {role}

## Job Description
{jd_text}

## Candidate's Base CV (overfilled reference — select what fits)
{base_json}

Output ONLY valid JSON. No markdown fences. No commentary."""


# ── Public API ─────────────────────────────────────────────────────────────

class TailoringResult:
    """Holds the output of a CV tailoring run."""

    def __init__(
        self,
        tailored_cv: str,
        commentary: str,
        saved_path: Optional[Path],
        error: Optional[str] = None,
        google_doc_url: Optional[str] = None,
        resume_builder_url: Optional[str] = None,
    ):
        self.tailored_cv = tailored_cv
        self.commentary = commentary
        self.saved_path = saved_path
        self.error = error
        self.google_doc_url = google_doc_url
        self.resume_builder_url = resume_builder_url

    @property
    def ok(self) -> bool:
        return self.error is None


def tailor_cv_for_listing(
    listing: Dict[str, Any],
) -> TailoringResult:
    """Tailor the base CV for a specific job listing.

    The base CV (resumeinfo.json) is treated as an overfilled reference.
    The LLM selects only the most relevant entries and produces a concise,
    targeted resume as a new JSON file in output/resumes/.

    Args:
        listing: A listing dict from the tracker DB (needs 'title', 'company',
                 'description' / 'raw_text').

    Returns:
        TailoringResult with the tailored CV text, commentary, saved file path,
        and resume_builder_url pointing to the specific tailored file.
    """
    try:
        llm = LLMService()
    except ValueError as e:
        return TailoringResult(
            tailored_cv="",
            commentary="",
            saved_path=None,
            error=str(e),
        )

    base_json = _load_base_resume_json()
    if not base_json:
        return TailoringResult(
            tailored_cv="",
            commentary="",
            saved_path=None,
            error=(
                "Could not find your base CV. "
                "Make sure config/resumeinfo.json exists."
            ),
        )

    company = listing.get("company", "Unknown Company")
    role = listing.get("title", "Unknown Role")
    jd_text = listing.get("description") or listing.get("raw_text") or ""

    if not jd_text.strip():
        return TailoringResult(
            tailored_cv="",
            commentary="",
            saved_path=None,
            error="The listing has no job description text to tailor against.",
        )

    prompt = _PROMPT_TEMPLATE.format(
        company=company,
        role=role,
        jd_text=jd_text[:6000],
        base_json=json.dumps(base_json, indent=2),
    )

    try:
        raw = llm._call(
            model="gemini-2.0-flash-lite",
            prompt=prompt,
            system_instruction=_SYSTEM,
            temperature=0.35,
        )
    except Exception as exc:
        return TailoringResult(
            tailored_cv="",
            commentary="",
            saved_path=None,
            error=f"LLM call failed: {exc}",
        )

    # Strip any code fences the LLM might include
    raw = raw.strip()
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)
    raw = raw.strip()

    # Parse the tailored JSON
    try:
        tailored_data = json.loads(raw)
    except json.JSONDecodeError as exc:
        md_path = _save_tailored_md(raw, company, role)
        return TailoringResult(
            tailored_cv=raw,
            commentary="",
            saved_path=md_path,
            error=f"LLM output was not valid JSON: {exc}",
        )

    # Build commentary describing what was selected/removed
    commentary_parts = [
        f"Tailored resume for **{role} @ {company}**",
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "",
        "## Changes Made",
    ]

    # Check what was dropped vs kept
    def _list_names(entries, key="company"):
        return [e.get(key, "") for e in entries if isinstance(e, dict)]

    orig_exp = _list_names(base_json.get("experience", []))
    new_exp = _list_names(tailored_data.get("experience", []))
    dropped_exp = set(orig_exp) - set(new_exp)
    if dropped_exp:
        commentary_parts.append(
            f"- Removed {len(dropped_exp)} irrelevant position(s): {', '.join(dropped_exp)}"
        )

    orig_skills = set(base_json.get("skills", {}).keys())
    new_skills = set(tailored_data.get("skills", {}).keys())
    dropped_skills = orig_skills - new_skills
    if dropped_skills:
        commentary_parts.append(
            f"- Removed skill categories: {', '.join(dropped_skills)}"
        )

    orig_proj = _list_names(base_json.get("projects", []), "name")
    new_proj = _list_names(tailored_data.get("projects", []), "name")
    if set(orig_proj) - set(new_proj):
        commentary_parts.append("- Removed irrelevant projects")

    if base_json.get("summaries") and len(base_json["summaries"]) > len(tailored_data.get("summaries", [])):
        commentary_parts.append("- Condensed summary selection")

    # Convert tailored JSON to a readable markdown version
    md_lines = [
        f"# {tailored_data.get('name', '')}",
        f"**{tailored_data.get('title', '')}**",
        "",
        "---",
        "",
    ]

    if tailored_data.get("summaries"):
        md_lines.append("## Summary")
        md_lines.append(tailored_data["summaries"][0])
        md_lines.append("")

    if tailored_data.get("skills"):
        md_lines.append("## Skills")
        for cat, skills in tailored_data["skills"].items():
            md_lines.append(f"- **{cat}**: {', '.join(skills)}")
        md_lines.append("")

    if tailored_data.get("experience"):
        md_lines.append("## Experience")
        for exp in tailored_data["experience"]:
            md_lines.append(
                f"### {exp.get('role', '')} @ {exp.get('company', '')}"
            )
            md_lines.append(f"*{exp.get('startDate', '')} - {exp.get('endDate', '')}*")
            for bp in exp.get("bulletpoints", []):
                md_lines.append(f"- {bp}")
            md_lines.append("")

    if tailored_data.get("education"):
        md_lines.append("## Education")
        for edu in tailored_data["education"]:
            md_lines.append(
                f"### {edu.get('degree', '')} in {edu.get('major', '')} @ {edu.get('institution', '')}"
            )
            md_lines.append(f"*{edu.get('startDate', '')} - {edu.get('endDate', '')}*")
            md_lines.append("")

    tailored_md = "\n".join(md_lines)
    commentary = "\n".join(commentary_parts)

    # Save the tailored JSON (NOT to resumeinfo.json — to a new file)
    json_path = _save_tailored_json(tailored_data, company, role)

    # Also save a markdown copy for reference
    md_path = _save_tailored_md(tailored_md, company, role)

    # Build the resume-builder URL with a query param pointing to this file
    rel_path = json_path.relative_to(_project_root())
    resume_builder_url = f"/resume-builder?resume={rel_path}"

    return TailoringResult(
        tailored_cv=tailored_md,
        commentary=commentary,
        saved_path=md_path,
        resume_builder_url=resume_builder_url,
    )