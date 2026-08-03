# Agent 2 — CV & Cover Letter Tailor (ResumeBuilder Edition)
#
# Reads the user's base resume from config/resumeinfo.json.
# For each shortlisted job, produces:
#   1. A tailored CV in the same structured JSON format (for ResumeBuilder
#      HTML+CSS preview / PDF export).
#   2. A cover letter tailored to the specific company and role.
#
# The base CV is treated as an intentionally overfilled reference — the LLM
# selects only the entries most relevant to the target role.
#
# Usage:
#   from agents.cv_tailor_agent import tailor_for_shortlist
#   results = tailor_for_shortlist(shortlist)

from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

# Ensure project root is on path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from dotenv import load_dotenv

load_dotenv(os.path.join(PROJECT_ROOT, ".env"))


# ── CV Loading ───────────────────────────────────────────────────────────

_RESUME_BUILDER_JSON = Path(PROJECT_ROOT) / "config" / "resumeinfo.json"


def load_base_resumejson() -> dict:
    """Load the canonical base CV from the ResumeBuilder JSON file."""
    path = _RESUME_BUILDER_JSON
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {}


# ── File-saving helpers ──────────────────────────────────────────────────

def _slugify(text: str, max_len: int = 40) -> str:
    """Turn arbitrary text into a safe filename fragment."""
    text = re.sub(r"[^\w\s-]", "", text.lower())
    text = re.sub(r"[\s_-]+", "_", text).strip("_")
    return text[:max_len]


def _save_markdown(content: str, subdir: str, company: str, role: str, label: str) -> str:
    """Save content as markdown and return the path."""
    out_dir = Path(PROJECT_ROOT) / "output" / subdir
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{label}_{_slugify(company)}_{_slugify(role)}_{stamp}.md"
    out_path = out_dir / filename
    out_path.write_text(content, encoding="utf-8")
    return str(out_path)


def _save_tailored_json(data: dict, company: str, role: str) -> str:
    """Save the tailored resume JSON to output/resumes/ and return the path.

    The master resumeinfo.json is never modified — each tailored CV is
    saved as a separate file so the user can preview it in the ResumeBuilder.
    """
    out_dir = Path(PROJECT_ROOT) / "output" / "resumes"
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M")
    filename = f"resume_{_slugify(company)}_{_slugify(role)}_{stamp}_resumeinfo.json"
    out_path = out_dir / filename
    out_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return str(out_path)


# ── Tailored CV Generation ──────────────────────────────────────────────

_CV_SYSTEM = (
    "You are an elite professional CV writer with 15 years of experience "
    "helping data scientists and engineers land jobs at top-tier companies. "
    "You output structured JSON only — no commentary, no markdown."
)

_CV_PROMPT = """You are tailoring a candidate's structured CV for a specific job.

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
    point. Adapt and rephrase the most relevant one using JD keywords, but keep
    the same tone, structure, and level of detail. Do NOT write a generic
    AI-sounding summary from scratch.
4. **Skills** — Keep ALL categories that are remotely relevant. Each kept
    category MUST retain **at least 5 skills** (ideally all of them). Do NOT
    strip categories down to 2-3 entries — if you keep a category, keep the
    majority of its skills. Remove only entire categories that are totally
    irrelevant. Reorder categories so the most relevant appear first.
5. **Experience** — Keep all experience entries. Do not drop any entries.
   - **Preserve the original bullet point detail and length.** Each bullet
     should be as detailed as the original (same metrics, same specificity).
     Rephrase using JD keywords but do NOT shorten or truncate.
   - Pick the most relevant bullets from the original set. Include at least 3
     bullets per entry.
6. **Education** — **Always keep this section.** It must never be dropped.
    Keep all entries. You may rephrase slightly but preserve all facts and dates.
7. **Projects** — **Always keep this section.** Choose the 2-3 most relevant projects to this role. 
8. **Courses** — keep only courses relevant to this role. Drop the rest.
    This section can be toggled on/off in the builder, so it is safe to drop.
9. **References** — Keep.
10. The result must be a concise, targeted CV. Every entry you include should
    serve the application. Quality over quantity.

Output ONLY valid JSON matching the schema below. No preamble, no code fences,
no commentary.

{{
  "name": "<string>",
  "title": "<string>",
  "email": "<string>",
  "phone": "<string>",
  "linkedin": "<string>",
  "github": "<string>",
  "location": "<string>",
  "portrait": "<string - always 'portrait.jpg'>",
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

## Target Role
Company: {company}
Role: {role}

## Job Description
{jd_text}

## Candidate's Base CV (overfilled reference — select what fits)
{base_json}

Output ONLY valid JSON. No markdown fences. No commentary."""

_COVER_LETTER_SYSTEM = (
    "You are a professional cover letter writer. You write concise, "
    "compelling cover letters that highlight relevant experience."
)

_COVER_LETTER_PROMPT = """Write a professional cover letter for the following job application.

## Rules
1. Keep it to one page (300-400 words).
2. Map specific proof points from the CV to job requirements.
3. Never invent experience, metrics, or skills.
4. Professional but not robotic tone.
5. Avoid em-dashes and other AI-written give-aways.
6. Mention the specific company and role in the first paragraph.
7. Use standard cover letter format (date, salutation, body, sign-off).

## Target
Role: {role} at {company}

## Job Description
{jd_text}

## Candidate's CV (in structured JSON format):
{base_json}

Output the cover letter in clean markdown.
"""


def generate_tailored_cv(
    company: str,
    role: str,
    jd_text: str,
    base_json: dict,
) -> Dict[str, Any]:
    """Generate a tailored CV for a specific job.

    Returns dict with 'tailored_data' (parsed JSON dict), 'saved_path'
    (JSON file path), 'resume_builder_url', 'commentary', and 'error'.
    """
    from services.llm_service import LLMService

    try:
        llm = LLMService()
    except ValueError as e:
        return {"tailored_data": {}, "saved_path": None, "error": str(e)}

    prompt = _CV_PROMPT.format(
        company=company,
        role=role,
        jd_text=jd_text[:8000],
        base_json=json.dumps(base_json, indent=2),
    )

    try:
        raw = llm._call(
            model="deepseek/deepseek-v4-flash",
            prompt=prompt,
            system_instruction=_CV_SYSTEM,
            temperature=0.35,
        )
    except Exception as exc:
        return {"tailored_data": {}, "saved_path": None, "error": str(exc)}

    # Strip any code fences the LLM might include
    raw = raw.strip()
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)
    raw = raw.strip()

    # Parse the tailored JSON
    try:
        tailored_data = json.loads(raw)
    except json.JSONDecodeError as exc:
        return {
            "tailored_data": {},
            "saved_path": None,
            "error": f"LLM output was not valid JSON: {exc}",
        }

    # Build commentary describing what was selected/removed
    commentary_parts = [
        f"Tailored resume for **{role} @ {company}**",
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "",
        "## Changes Made",
    ]

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

    commentary = "\n".join(commentary_parts)

    # Save the tailored JSON
    json_path = _save_tailored_json(tailored_data, company, role)

    # Build the resume-builder URL with a query param
    rel_path = Path(json_path).relative_to(PROJECT_ROOT)
    resume_builder_url = f"/resume-builder?resume={rel_path}"

    return {
        "tailored_data": tailored_data,
        "saved_path": json_path,
        "resume_builder_url": resume_builder_url,
        "commentary": commentary,
        "error": None,
    }


def generate_cover_letter(
    company: str,
    role: str,
    jd_text: str,
    base_json: dict,
) -> Dict[str, Any]:
    """Generate a tailored cover letter for a specific job.

    Returns dict with 'cover_letter_text', 'saved_path', 'resume_builder_url', 'error'.
    """
    from services.llm_service import LLMService

    try:
        llm = LLMService()
    except ValueError as e:
        return {"cover_letter_text": "", "saved_path": None, "resume_builder_url": None, "error": str(e)}

    prompt = _COVER_LETTER_PROMPT.format(
        company=company,
        role=role,
        jd_text=jd_text[:6000],
        base_json=json.dumps(base_json, indent=2),
    )

    try:
        raw = llm._call(
            model="deepseek/deepseek-v4-flash",
            prompt=prompt,
            system_instruction=_COVER_LETTER_SYSTEM,
            temperature=0.5,
        )
    except Exception as exc:
        return {"cover_letter_text": "", "saved_path": None, "resume_builder_url": None, "error": str(exc)}

    cl_text = raw.strip()

    return {
        "cover_letter_text": cl_text,
        "saved_path": None,
        "error": None,
    }


# ── Batch Processing ────────────────────────────────────────────────────

def tailor_for_shortlist(
    shortlist: List[Dict[str, Any]],
    base_resume: Optional[dict] = None,
) -> List[Dict[str, Any]]:
    """Generate tailored CV and cover letter for every listing in the shortlist.

    Args:
        shortlist: List of listing dicts with 'title', 'company', 'url', etc.
        base_resume: Base resume as a dict (matching resumeinfo.json schema).
                     Loaded from config/resumeinfo.json if omitted.

    Returns:
        List of result dicts, one per listing, each with keys:
          'listing', 'tailored_cv', 'cover_letter', 'error'
    """
    if base_resume is None:
        base_resume = load_base_resumejson()

    if not base_resume:
        print("[cv_tailor] No base CV found at config/resumeinfo.json")
        return []

    results = []
    for i, listing in enumerate(shortlist):
        company = listing.get("company", "Unknown")
        role = listing.get("title", "Unknown Role")
        jd_text = listing.get("description", "")
        url = listing.get("url", "")

        print(f"[cv_tailor] [{i+1}/{len(shortlist)}] Processing {role} @ {company}")

        if not jd_text:
            results.append({
                "listing": listing,
                "tailored_cv": {"error": "No job description available."},
                "cover_letter": {"error": "No job description available."},
            })
            continue

        cv_result = generate_tailored_cv(company, role, jd_text, base_resume)
        cl_result = generate_cover_letter(company, role, jd_text, base_resume)

        res = {
            "listing": listing,
            "tailored_cv": cv_result,
            "cover_letter": cl_result,
        }
        results.append(res)

        # Persist to local SQL database
        try:
            from services.tracker_service import (
                init_db, insert_listing, save_tailored_cv, insert_application
            )
            init_db()
            lid = insert_listing(listing)

            cv_path = cv_result.get("saved_path") or ""
            rb_url = cv_result.get("resume_builder_url") or ""
            commentary = cv_result.get("commentary") or ""

            if cv_path:
                save_tailored_cv(
                    listing_id=lid,
                    cv_path=cv_path,
                    commentary=commentary,
                    resume_builder_url=rb_url,
                )

            insert_application({
                "listing_id": lid,
                "company": company,
                "role": role,
                "status": "Evaluated",
                "score": listing.get("score"),
                "tailored_cv_path": cv_path,
                "notes": listing.get("fit_rationale", ""),
            })
        except Exception as db_err:
            print(f"[cv_tailor] Warning: failed to persist tailored CV to SQL DB: {db_err}")

    return results



# ── CLI Entry Point ──────────────────────────────────────────────────────

if __name__ == "__main__":
    import json
    import argparse

    parser = argparse.ArgumentParser(description="Agent 2 — CV & Cover Letter Tailor")
    parser.add_argument("--shortlist", required=True, help="Path to JSON file with shortlist data")
    parser.add_argument("--output", default="", help="Path to write results JSON")
    args = parser.parse_args()

    # Load shortlist from JSON file
    with open(args.shortlist, "r") as f:
        shortlist_data = json.load(f)

    results = tailor_for_shortlist(shortlist_data)

    print(f"\n=== CV TAILOR — RESULTS ({len(results)} listings) ===\n")
    for r in results:
        listing = r["listing"]
        cv = r["tailored_cv"]
        cl = r["cover_letter"]

        print(f"  {listing['title']} @ {listing['company']}")
        if cv.get("error"):
            print(f"    CV Error: {cv['error']}")
        else:
            print(f"    CV JSON: {cv.get('saved_path', 'N/A')}")
            if cv.get("resume_builder_url"):
                print(f"    Resume Builder: {cv['resume_builder_url']}")
        if cl.get("error"):
            print(f"    Cover Letter Error: {cl['error']}")
        else:
            print(f"    Cover Letter: {cl.get('saved_path', 'N/A')}")
        print()

    if args.output:
        with open(args.output, "w") as f:
            json.dump(results, f, indent=2, default=str)
        print(f"Results written to {args.output}")