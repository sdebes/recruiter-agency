# Recruiter Agency — FastAPI Server
#
# Replaces the Streamlit frontend with a FastAPI server serving
# Jinja2 HTML templates + REST API endpoints.
#
# Run with: uvicorn server.main:app --reload

import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

# Ensure project root is on sys.path
_project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_project_root))

load_dotenv(_project_root / ".env")
load_dotenv()

import json
import yaml
import uuid

from services.tracker_service import (
    init_db, get_all_listings, get_listing, insert_listing, delete_listing,
    get_evaluations_for_listing, insert_evaluation,
    get_all_applications, get_application, get_application_stats,
    update_application_status,
    get_tailored_cvs_for_listing, save_tailored_cv,
    get_setting, set_setting,
)
from utils.config_loader import load_profile, load_archetypes, PROJECT_ROOT

from jinja2 import Environment, FileSystemLoader
from fastapi.middleware.cors import CORSMiddleware

# ── FastAPI App Setup ─────────────────────────────────────────────────────

app = FastAPI(title="Recruiter Agency")

import traceback

@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    traceback.print_exc()
    return JSONResponse(
        status_code=500,
        content={"detail": f"Internal server error: {exc}"},
    )

# Configure CORS for decoupled frontend development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins in local dev; can restrict to localhost:3000 later
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_here = Path(__file__).parent
_tpl_env = Environment(
    loader=FileSystemLoader(str(_here / "templates")),
    cache_size=0,  # disable caching in development
)
templates = Jinja2Templates(env=_tpl_env)
app.mount("/static", StaticFiles(directory=str(_here / "static")), name="static")

init_db()

# ── Pydantic Models ──────────────────────────────────────────────────────

class ListingPayload(BaseModel):
    url: Optional[str] = None
    title: Optional[str] = None
    company: Optional[str] = None
    description: Optional[str] = None
    location: Optional[str] = None

class FindListingsPayload(BaseModel):
    location: str
    query: Optional[str] = None

class StatusUpdate(BaseModel):
    status: str
    notes: Optional[str] = None

class SettingPayload(BaseModel):
    key: str
    value: Any

# ── Page Routes ──────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    return templates.TemplateResponse(request, "index.html")

@app.get("/tracker", response_class=HTMLResponse)
async def tracker_page(request: Request):
    return templates.TemplateResponse(request, "tracker.html")

@app.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request):
    profile = load_profile()
    archetypes = load_archetypes()
    return templates.TemplateResponse(request, "settings.html", {
        "profile": profile,
        "archetypes": archetypes["archetypes"],
        "PROJECT_ROOT": str(PROJECT_ROOT),
    })

@app.get("/resume-builder", response_class=HTMLResponse)
async def resume_builder_page(request: Request):
    return templates.TemplateResponse(request, "resume_builder.html")

# ── API — Stats ──────────────────────────────────────────────────────────

@app.get("/api/stats")
async def stats():
    return get_application_stats()

# ── API — Listings ───────────────────────────────────────────────────────

@app.get("/api/listings")
async def list_listings(source: Optional[str] = None, search: Optional[str] = None):
    listings = get_all_listings()
    if source:
        if source == "scan":
            listings = [l for l in listings if l.get("source") != "manual"]
        else:
            listings = [l for l in listings if l.get("source") == source]
    if search:
        sl = search.lower()
        listings = [
            l for l in listings
            if sl in (l.get("company", "") or "").lower()
            or sl in (l.get("title", "") or "").lower()
        ]
    return listings

@app.post("/api/listings/find")
async def find_listings(payload: FindListingsPayload):
    """Search job boards for listings in the given location and save them."""
    from agents.listing_finder import find_listings as run_find_listings
    from services.tracker_service import save_scraped_listings

    try:
        result = run_find_listings(
            query=payload.query,
            location=payload.location,
            limit=20,
        )
        new_listings = result["listings"]
        saved_ids = save_scraped_listings(new_listings) if new_listings else []

        return {
            "ok": True,
            "listings": new_listings,
            "saved_ids": saved_ids,
            "total_found": result["total_found"],
            "new_count": result["new_count"],
            "duplicates": result["duplicates"],
            "sources": result["sources"],
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/listings")
async def add_listing(payload: ListingPayload):
    try:
        if payload.url and payload.url.startswith("http"):
            from agents.listing_finder import enrich_listing
            enriched = enrich_listing(payload.url)
            title = enriched.get("title") or "Unknown Position"
            company = enriched.get("company") or "Unknown Company"
            desc = enriched.get("description") or ""
            listing = {
                "id": str(uuid.uuid4()),
                "title": title,
                "company": company,
                "url": payload.url,
                "description": desc,
                "source": "manual",
                "location": enriched.get("location"),
                "salary_range": enriched.get("salary_range"),
                "seniority": enriched.get("seniority"),
                "start_date": enriched.get("start_date"),
                "employment_duration": enriched.get("employment_duration"),
                "employment_type": enriched.get("employment_type"),
            }
        else:
            if not payload.title or not payload.company:
                raise HTTPException(status_code=400, detail="Title and company required for manual entry")

            from agents.listing_finder import _swap_title_company
            raw = {
                "title": payload.title,
                "company": payload.company,
            }
            swapped = _swap_title_company(raw)

            listing = {
                "id": str(uuid.uuid4()),
                "title": swapped["title"],
                "company": swapped["company"],
                "url": payload.url or "",
                "description": payload.description or "",
                "source": "manual",
                "location": payload.location,
            }

        existing = get_all_listings()
        for ex in existing:
            if listing.get("url") and ex.get("url") == listing["url"]:
                raise HTTPException(status_code=409, detail=f"Duplicate: {listing['title']} at {listing['company']} already exists")
            if ex.get("title") == listing["title"] and ex.get("company") == listing["company"]:
                raise HTTPException(status_code=409, detail=f"Duplicate: {listing['title']} at {listing['company']} already exists")

        insert_listing(listing)
        return listing
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/api/listings/{listing_id}")
async def get_listing_detail(listing_id: str):
    listing = get_listing(listing_id)
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")
    return listing

@app.delete("/api/listings/{listing_id}")
async def remove_listing(listing_id: str):
    delete_listing(listing_id)
    return {"ok": True}

# ── API — Evaluations ────────────────────────────────────────────────────

@app.get("/api/listings/{listing_id}/evaluations")
async def list_evaluations(listing_id: str):
    return get_evaluations_for_listing(listing_id)

@app.post("/api/listings/{listing_id}/evaluate")
async def evaluate_listing(listing_id: str):
    listing = get_listing(listing_id)
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")

    from services.llm_service import LLMService
    from utils.config_loader import load_all_config, get_cv_text
    from graph.nodes.evaluation_node import _parse_evaluation_result, _get_archetype_weights

    try:
        config = load_all_config()
        profile = config.get("profile", {})
        cv_text = get_cv_text()
        profile["_cv_text"] = cv_text
        archetypes_config = config.get("archetypes", {})

        jd_text = listing.get("description") or listing.get("raw_text", "")
        if not jd_text:
            raise HTTPException(status_code=400, detail="Listing has no description to evaluate")

        llm = LLMService()

        # 1. Detect archetype
        archetype_result = llm.detect_archetype(jd_text, archetypes_config)
        import re
        arch_match = re.search(r"ARCHETYPE:\s*(.+)", archetype_result)
        archetype_name = arch_match.group(1).strip() if arch_match else "Data Scientist"

        # 2. Get scoring weights
        weights = _get_archetype_weights(archetype_name, archetypes_config)

        # 3. Run evaluation
        eval_text = llm.evaluate_listing(
            jd_text=jd_text,
            cv_text=cv_text,
            profile=profile,
            archetype=archetype_name,
            archetype_weights=weights,
        )

        # 4. Parse results
        evaluation = _parse_evaluation_result(eval_text)
        evaluation["listing_id"] = listing_id
        evaluation["archetype_detected"] = archetype_name

        # 5. Calculate global score if not in LLM output
        if evaluation["global_score"] == 0.0:
            weighted = (
                weights.get("cv_match", 0.25) * evaluation["cv_match_score"]
                + weights.get("north_star", 0.20) * evaluation["north_star_score"]
                + weights.get("compensation", 0.20) * evaluation["comp_score"]
                + weights.get("culture", 0.20) * evaluation["culture_score"]
            )
            flag_penalty = min(len(evaluation.get("red_flags", [])) * 0.2, 1.0)
            evaluation["global_score"] = round(max(weighted - flag_penalty, 1.0), 1)

        # 6. Save to database
        insert_evaluation(evaluation)

        return {"ok": True, "result": evaluation}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ── API — Tailored CVs ───────────────────────────────────────────────────

@app.get("/api/listings/{listing_id}/tailored-cvs")
async def list_tailored_cvs(listing_id: str):
    return get_tailored_cvs_for_listing(listing_id)

@app.post("/api/listings/{listing_id}/tailor-cv")
async def tailor_cv(listing_id: str):
    listing = get_listing(listing_id)
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")

    from graph.nodes.tailoring_node import tailor_cv_for_listing as tailor

    try:
        result = tailor(listing)
        if not result.ok:
            raise HTTPException(status_code=500, detail=f"Tailoring failed: {result.error}")

        save_tailored_cv(
            listing_id=listing["id"],
            cv_path=str(result.saved_path),
            commentary=result.commentary,
            google_doc_url="",
            resume_builder_url=result.resume_builder_url or "/resume-builder",
        )
        return {
            "ok": True,
            "cv_path": str(result.saved_path),
            "commentary": result.commentary,
            "resume_builder_url": result.resume_builder_url or "/resume-builder",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/listings/{listing_id}/critique")
async def critique_listing_cv(listing_id: str):
    listing = get_listing(listing_id)
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")

    # Load candidate's base CV text
    try:
        from utils.config_loader import get_cv_text
        cv_text = get_cv_text()
    except Exception:
        cv_text = ""

    if not cv_text:
        # Fallback to reading the resumeinfo.json directly if master md isn't generated
        if _RESUME_DATA_PATH.exists():
            try:
                cv_text = _RESUME_DATA_PATH.read_text(encoding="utf-8")
            except Exception:
                pass
        
        if not cv_text:
            raise HTTPException(status_code=400, detail="Base resume data is missing or unreadable")

    from services.llm_service import LLMService
    try:
        llm = LLMService()
        critique = llm.critique_cv(
            jd_text=listing.get("description") or listing.get("raw_text") or "",
            cv_text=cv_text,
            company=listing.get("company") or "Unknown Company",
            role=listing.get("title") or "Unknown Role",
        )
        return {"ok": True, "critique": critique}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ── API — Applications ───────────────────────────────────────────────────

@app.get("/api/applications")
async def list_applications(
    status: Optional[str] = None,
    min_score: Optional[float] = Query(None, ge=0.0, le=5.0),
):
    apps = get_all_applications()
    if status and status != "All":
        apps = [a for a in apps if a.get("status") == status]
    if min_score and min_score > 0:
        apps = [a for a in apps if a.get("score") is not None and a["score"] >= min_score]
    return apps

@app.get("/api/applications/{app_id}")
async def get_application_detail(app_id: str):
    app_data = get_application(app_id)
    if not app_data:
        raise HTTPException(status_code=404, detail="Application not found")
    return app_data

@app.patch("/api/applications/{app_id}/status")
async def update_status(app_id: str, payload: StatusUpdate):
    update_application_status(app_id, payload.status, payload.notes)
    return {"ok": True}

# ── API — Config (Profile & Archetypes) ─────────────────────────────────

@app.get("/api/config/profile")
async def get_profile():
    return load_profile()

@app.post("/api/config/profile")
async def save_profile(payload: Dict[str, Any]):
    profile_path = PROJECT_ROOT / "config" / "profile.yml"
    with open(profile_path, "w") as f:
        yaml.dump(payload, f, default_flow_style=False, allow_unicode=True)
    return {"ok": True}

@app.get("/api/config/archetypes")
async def get_archetypes():
    return load_archetypes()

@app.post("/api/config/archetypes")
async def save_archetypes(payload: Dict[str, Any]):
    arch_path = PROJECT_ROOT / "config" / "archetypes.yml"
    with open(arch_path, "w") as f:
        yaml.dump(payload, f, default_flow_style=False, allow_unicode=True)
    return {"ok": True}

# ── API — Resume Builder ────────────────────────────────────────────────

_RESUME_DATA_PATH = _project_root / "config" / "resumeinfo.json"

@app.get("/api/resume-builder/data")
async def get_resume_data(resume: Optional[str] = Query(None, description="Relative path to a tailored resume JSON in output/resumes/")):
    if resume:
        resume_path = _project_root / resume
        if resume_path.exists() and resume_path.suffix == ".json":
            try:
                return JSONResponse(content=json.loads(resume_path.read_text(encoding="utf-8")))
            except (json.JSONDecodeError, OSError):
                raise HTTPException(status_code=400, detail="Invalid resume file")
        raise HTTPException(status_code=404, detail=f"Resume file not found: {resume}")
    if _RESUME_DATA_PATH.exists():
        return JSONResponse(content=json.loads(_RESUME_DATA_PATH.read_text(encoding="utf-8")))
    return {"name": "", "title": "", "email": ""}

@app.post("/api/resume-builder/data")
async def save_resume_data(data: Dict[str, Any]):
    _RESUME_DATA_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return {"ok": True}

# ── API — Settings ───────────────────────────────────────────────────────

@app.get("/api/settings/{key}")
async def get_setting_endpoint(key: str):
    return {"key": key, "value": get_setting(key)}

@app.post("/api/settings")
async def save_setting_endpoint(payload: SettingPayload):
    set_setting(payload.key, payload.value)
    return {"ok": True}