
# Recruiter Agency — Product Requirements Document

 1. Product Vision

 Recruiter Agency is a multi-agent job search system that helps candidates discover,
 evaluate, tailor, and track job applications. Built as a Python reimagining of the
 career-ops concept, it uses LangGraph for the core orchestration engine (with
 human-in-the-loop pauses and persistent memory), wrapped in Google ADK as the
 interface layer, with a NextJS dashboard.

 This is also a CV showcase project — demonstrating production-quality Python
 engineering, agentic AI architecture, and real-world utility.

 2. Persona

The personal data is retrieved from the config folder
 - CV and cover letters
 - Location
 - Target roles
 - Needs: automated job discovery, structured evaluation, tailored CVs, application tracking, interview prep

 3. Tech Stack

 ┌─────────────┬────────────────────┬─────────────────────────────────────────────┐
 │    Layer    │     Technology     │                  Rationale                  │
 ├─────────────┼────────────────────┼─────────────────────────────────────────────┤
 │ Agent       │ LangGraph          │ Stateful graphs with built-in HITL,         │
 │ framework   │                    │ checkpointing, Send API for parallelism     │
 ├─────────────┼────────────────────┼─────────────────────────────────────────────┤
 │ Interface   │ Google ADK         │ Natural language orchestration wrapping the │
 │ layer       │                    │  LangGraph engine                           │
 ├─────────────┼────────────────────┼─────────────────────────────────────────────┤
 │ Frontend    │ NextJS             │                                             │
 ├─────────────┼────────────────────┼─────────────────────────────────────────────┤
 │ Database    │ SQLite             │ Zero-config, local-first, matches           │
 │             │                    │ data-sovereignty philosophy                 │
 ├─────────────┼────────────────────┼─────────────────────────────────────────────┤
 │ LLM         │ Depends on Task    │                                             │
 ├─────────────┼────────────────────┼─────────────────────────────────────────────┤
 │ Scraping    │ httpx +            │ Lightweight HTTP scraping; Playwright added │
 │             │ BeautifulSoup      │  where JS rendering is needed               │
 ├─────────────┼────────────────────┼─────────────────────────────────────────────┤
 │ PDF         │ WeasyPrint         │ HTML+CSS → PDF, pure Python, ATS-optimized  │
 │             │                    │ output                                      │
 ├─────────────┼────────────────────┼─────────────────────────────────────────────┤
 │ Config      │ YAML               │ Human-readable, matches career-ops          │
 │             │                    │ conventions                                 │
 ├─────────────┼────────────────────┼─────────────────────────────────────────────┤
 │ Packaging   │ uv +               │ Simple, universal Python setup              │
 │             │ requirements.txt   │                                             │
 └─────────────┴────────────────────┴─────────────────────────────────────────────┘

 4. Architecture

 User (NextJS Interface or CLI)
     │
     ▼
 ┌──────────────────────────────────────────┐
 │  Google ADK Agent (RecruiterAgency)      │
 │  ─ Natural language interface            │
 │  ─ Routes intent to LangGraph pipeline   │
 │  ─ Handles conversation state            │
 │                                          │
 │  ┌────────────────────────────────────┐  │
 │  │  LangGraph Engine                  │  │
 │  │  ─ Stateful graph with HITL        │  │
 │  │  ─ Interrupt_before evaluation     │  │
 │  │  ─ Conditional edges by decision   │  │
 │  │  ─ SQLite checkpointing            │  │
 │  │  ─ Persistent memory (preferences) │  │
 │  │                                    │  │
 │  │  Node: Input → Find → Eval →       │  │
 │  │         Tailor → Track → Prep →    │  │
 │  │         Report                     │  │
 │  └────────────────────────────────────┘  │
 └──────────────────────────────────────────┘

 LangGraph Nodes

 ┌────────────┬───────────────────────────────┬────────────┬───────────────────────┐
 │    Node    │           Function            │    LLM?    │         HITL?         │
 ├────────────┼───────────────────────────────┼────────────┼───────────────────────┤
 │ Finding    │ Scrape job boards, detect     │ flash-lite │ No                    │
 │            │ archetype                     │            │                       │
 ├────────────┼───────────────────────────────┼────────────┼───────────────────────┤
 │            │ A-F scoring blocks (CV match, │            │ Yes — pauses to show  │
 │ Evaluation │  north star, comp, culture,   │ flash      │ scores, user decides  │
 │            │ red flags, legitimacy)        │            │ Apply/Skip            │
 ├────────────┼───────────────────────────────┼────────────┼───────────────────────┤
 │ Tailoring  │ Generate tailored CV + cover  │ flash/pro  │ No (user reviews      │
 │            │ letter                        │            │ later)                │
 ├────────────┼───────────────────────────────┼────────────┼───────────────────────┤
 │ Tracking   │ Update application database   │ None       │ No                    │
 ├────────────┼───────────────────────────────┼────────────┼───────────────────────┤
 │ Prep       │ Generate interview materials  │ flash      │ No                    │
 ├────────────┼───────────────────────────────┼────────────┼───────────────────────┤
 │ Reporting  │ Format final summary          │ None       │ No                    │
 └────────────┴───────────────────────────────┴────────────┴───────────────────────┘

 Human-in-the-Loop Flow

 1. Graph runs Finding → Evaluation (produces scores)
 2. Graph pauses at interrupt point
 3. Interface reads checkpoint state, displays A-F scores
 4. User clicks Apply, Skip, or Review Later
 5. Graph resumes with user_decision set in state
 6. Conditional edge routes to Tailor (if Apply), Tracker (if Skip), or Report (if
 Review)

 5. Features: MVP vs Stretch

 MVP (Build First)

 ┌───────────────────────┬──────────┬──────────────────────────────────────────────┐
 │        Feature        │ Priority │                 Description                  │
 ├───────────────────────┼──────────┼──────────────────────────────────────────────┤
 │ A-F Evaluation        │ P0       │ Full evaluation with A-F scoring blocks      │
 │ Pipeline              │          │                                              │
 ├───────────────────────┼──────────┼──────────────────────────────────────────────┤
 │ Human-in-the-Loop     │ P0       │ Pause after evaluation for user decision     │
 ├───────────────────────┼──────────┼──────────────────────────────────────────────┤
 │ Application Tracker   │ P0       │ SQLite-backed CRUD with canonical states     │
 ├───────────────────────┼──────────┼──────────────────────────────────────────────┤
 │ Interface Evaluate    │ P0       │ Paste URL/JD, see A-F scores, make decisions │
 │ Page                  │          │                                              │
 ├───────────────────────┼──────────┼──────────────────────────────────────────────┤
 │ Interface Tracker     │ P0       │ View/filter application table                │
 │ Page                  │          │                                              │
 ├───────────────────────┼──────────┼──────────────────────────────────────────────┤
 │ Configurable          │ P0       │ YAML-defined archetypes with adjustable      │
 │ Archetypes            │          │ scoring weights                              │
 ├───────────────────────┼──────────┼──────────────────────────────────────────────┤
 │ Profile Config        │ P0       │ candidate profile, target roles,             │
 │                       │          │ compensation                                 │
 ├───────────────────────┼──────────┼──────────────────────────────────────────────┤
 │ CV Tailoring          │ P1       │ Generate tailored CV + cover letter per      │
 │                       │          │ listing                                      │
 ├───────────────────────┼──────────┼──────────────────────────────────────────────┤
 │ PDF Generation        │ P1       │ WeasyPrint HTML→PDF output                   │
 ├───────────────────────┼──────────┼──────────────────────────────────────────────┤
 │ Report Generation     │ P1       │ Markdown evaluation reports                  │
 ├───────────────────────┼──────────┼──────────────────────────────────────────────┤
 │ Settings Page         │ P1       │ Edit profile/archetypes from Interface       │
 ├───────────────────────┼──────────┼──────────────────────────────────────────────┤
 │ Dashboard Overview    │ P1       │ Pipeline stats, score distribution chart     │
 └───────────────────────┴──────────┴──────────────────────────────────────────────┘

 Stretch (Post-MVP)

 ┌──────────────────────────┬──────────────────────────────────────────────────────┐
 │         Feature          │                     Description                      │
 ├──────────────────────────┼──────────────────────────────────────────────────────┤
 │ Autonomous Scanner       │ Background discovery of new listings from boards      │
 ├──────────────────────────┼──────────────────────────────────────────────────────┤
 │ Portal Scanner           │ Automated scanning of Greenhouse/Ashby/Lever APIs    │
 ├──────────────────────────┼──────────────────────────────────────────────────────┤
 │ Batch Evaluation         │ Parallel evaluation via LangGraph Send API           │
 ├──────────────────────────┼──────────────────────────────────────────────────────┤
 │ Interview Prep           │ STAR+R story bank, QA generation, company research   │
 ├──────────────────────────┼──────────────────────────────────────────────────────┤
 │ Google ADK Wrapper       │ Natural language interface layer                     │
 ├──────────────────────────┼──────────────────────────────────────────────────────┤
 │ Writing Style            │ Learn user's writing style from samples              │
 │ Calibration              │                                                      │
 ├──────────────────────────┼──────────────────────────────────────────────────────┤
 │ Scan Scheduling          │ Cron-based recurring scans                           │
 ├──────────────────────────┼──────────────────────────────────────────────────────┤
 │ Pattern Analysis         │ Rejection pattern detection and targeting            │
 │                          │ improvements                                         │
 ├──────────────────────────┼──────────────────────────────────────────────────────┤
 │ Follow-up Cadence        │ Track follow-up timing and templates                 │
 ├──────────────────────────┼──────────────────────────────────────────────────────┤
 │ Multi-language           │ Danish mode for Danish market                        │
 ├──────────────────────────┼──────────────────────────────────────────────────────┤
 │ Tests                    │ Unit + integration test suite                        │
 └──────────────────────────┴──────────────────────────────────────────────────────┘

 6. Data Model

 SQLite Tables (agentdb/applications.db)

 listings        -- Job listings: id, title, company, url, description, source,
 location, salary_range, posted_date, archetype
 evaluations     -- A-F scores: id, listing_id, cv_match_score, north_star_score,
 comp_score, culture_score, red_flags (JSON), global_score, legitimacy
 applications    -- Tracker: id, listing_id, company, role, status, score,
 applied_date, interview_dates, notes, pdf_path, cover_letter_path
 interview_preps -- Prep materials: id, application_id, company, role, star_stories
 (JSON), qa_pairs (JSON)
 story_bank      -- Accumulated stories: id, title, situation, task, action, result,
 reflection, tags
 scan_history    -- Dedup: url, first_seen, last_seen, title, company, status, portal
 settings        -- Key-value config

 YAML Config Files

 # config/profile.yml — user identity, target roles, compensation, archetypes
 # config/archetypes.yml — archetype definitions with scoring weights

 7. Directory Structure

 recruiter-agency/
 ├── run_server.py           # Entry point: uvicorn server.main:app
 ├── requirements.txt
 ├── pyproject.toml
 ├── .env / .env.example
 ├── config/                 # User config, CV data, and secrets (gitignored)
 │   ├── profile.yml         # Candidate identity, target roles, compensation
 │   ├── archetypes.yml      # Archetype definitions with scoring weights
 │   ├── resume.md           # Base CV (markdown)
 │   ├── resumeinfo.json     # Structured resume data (used by tailoring)
 │   ├── storybank.md        # STAR stories for interview prep
 │   ├── portrait.jpg
 │   ├── cover_letters/      # Base cover letter templates
 │   └── secrets/            # Google OAuth credentials.json & token.json
 ├── utils/                  # Core project utilities
 │   ├── __init__.py
 │   └── config_loader.py    # Central YAML & CV loader used project-wide
 ├── server/                 # FastAPI backend
 │   ├── main.py             # All API routes
 │   ├── static/             # CSS, JS, assets
 │   └── templates/          # Jinja2 HTML templates
 ├── frontend/               # Next.js dashboard (primary UI)
 │   └── src/app/            # Pages: home, tracker, resume-builder, settings
 ├── graph/                  # LangGraph engine
 │   ├── state.py
 │   ├── builder.py
 │   ├── memory.py
 │   ├── runner.py
 │   └── nodes/
 │       ├── input_node.py
 │       ├── finding_node.py
 │       ├── evaluation_node.py
 │       ├── tailoring_node.py
 │       ├── tracking_node.py
 │       └── reporting_node.py
 ├── agents/                 # Agent logic (LLM prompts, scoring, scraping)
 │   ├── orchestrator.py
 │   ├── listing_finder.py
 │   ├── cv_tailor_agent.py
 │   ├── job_finder_agent.py
 │   ├── notion_tracker.py   # Legacy Notion integration
 │   └── tools.py
 ├── services/               # Shared backend services
 │   ├── llm_service.py      # LLM API calls
 │   ├── scraper_service.py  # Job board scraping
 │   ├── tracker_service.py  # SQLite CRUD
 │   └── google_docs_service.py
 ├── adk/                    # Google ADK wrapper (stretch feature — stub only)
 ├── documentation/          # PRD and design docs
 ├── agentdb/                # SQLite databases (gitignored)
 ├── output/                 # Generated outputs (gitignored)
 └── unneeded/               # Archived legacy files
 ├── adk/                    # Google ADK wrapper (stretch feature — stub only)
 ├── documentation/          # PRD and design docs
 ├── agentdb/                # SQLite databases (gitignored)
 ├── output/                 # Generated outputs (gitignored)
 │   ├── cover_letters/
 │   ├── resumes/
 │   ├── tailoring_results/
 │   ├── shortlists/
 │   └── notion/
 ├── tests/
 └── unneeded/               # Archived/legacy files (not deleted, just parked)

 8. Agent Specifications (Summary)

 ┌────────────────────┬────────────┬──────────────┬───────────────────┬────────────┐
 │       Agent        │  Node(s)   │    Input     │      Output       │   Model    │
 ├────────────────────┼────────────┼──────────────┼───────────────────┼────────────┤
 │                    │            │ Target       │                   │            │
 │ ListingFinder      │ Finding    │ roles, job   │ List[JobListing]  │ flash-lite │
 │                    │            │ boards       │                   │            │
 ├────────────────────┼────────────┼──────────────┼───────────────────┼────────────┤
 │ ListingEvaluator   │ Evaluation │ JobListing + │ Evaluation (A-F   │ flash      │
 │                    │            │  Profile     │ scores)           │            │
 ├────────────────────┼────────────┼──────────────┼───────────────────┼────────────┤
 │ ApplicationTailor  │ Tailoring  │ JobListing + │ Tailored CV +     │ flash/pro  │
 │                    │            │  CV          │ cover letter      │            │
 ├────────────────────┼────────────┼──────────────┼───────────────────┼────────────┤
 │                    │            │ Status       │                   │ None       │
 │ ApplicationTracker │ Tracking   │ changes      │ DB updates        │ (logic     │
 │                    │            │              │                   │ only)      │
 ├────────────────────┼────────────┼──────────────┼───────────────────┼────────────┤
 │ InterviewPreparer  │ Prep       │ Application  │ QA pairs, prep    │ flash      │
 │                    │            │ + story bank │ doc               │            │
 ├────────────────────┼────────────┼──────────────┼───────────────────┼────────────┤
 │ Orchestrator       │ All        │ User command │ Pipeline result   │ flash-lite │
 └────────────────────┴────────────┴──────────────┴───────────────────┴────────────┘

 9. Implementation Phases

 Phase 0: Foundation

 - Project setup (pyproject.toml, requirements.txt, .env.example)
 - SQLite schema + tracker_service.py
 - Config loader (YAML)
 - AgentState TypedDict in graph/state.py
 - Checkpointing setup in graph/memory.py

 Phase 1: Core Pipeline

 - Evaluation node (A-F scoring via LLM)
 - Tracking node (SQLite CRUD)
 - Reporting node (markdown output)
 - Graph builder with interrupt points
 - Graph runner entry point

 Phase 2: Minimum NextJS Dashboard

 - Home + Evaluate page (paste URL, score display, decision buttons)
 - Tracker page (table, filters)
 - Settings page (profile editor)
 - Engine bridge (NextJS → LangGraph)

 Phase 3: Agent Implementations

 - ListingEvaluator: archetype detection, scoring logic
 - URL Scraper: playwright-based JD extraction (enrichment)
 - ApplicationTailor: keyword extraction, CV rewriting, PDF generation

 Phase 4: Advanced Nodes

 - Tailoring node (CV + cover letter)
 - Prep node (interview materials)
 - Dashboard charts and analytics

 Phase 5: Polish + ADK

 - Dashboard page with charts
 - Google ADK wrapper
 - Error handling, edge cases
 - Documentation pass

 10. Ethical Rules

 1. Never invent experience or metrics — only reformulate existing CV content
 2. Never submit applications — the system evaluates and prepares, user decides
 3. Discourage low-fit applications — scores below 3.5/5 recommend against
 4. Data sovereignty — all data stays local in SQLite, no cloud sync
 5. Quality over quantity — 5 good applications > 50 generic ones

 11. Verification

     After each phase, verify by:
     1. Running app/Home.py and navigating each page
     2. Pasting a real job URL and completing the full evaluation flow
     3. Testing the human-in-the-loop pause by evaluating a listing and clicking
     Apply/Skip
     4. Checking the SQLite database for correct entries in all tables
     5. Generating a PDF and verifying the output

     For the final system:
     - Full pipeline: URL → Scrape → Evaluate → HITL pause → Tailor CV → Track → Report
     - Batch: multiple URLs → parallel evaluation → aggregated results
     - Tracker: view, filter, sort, update application statuses
     - Settings: change profile, add archetype, adjust weights → re-evaluate reflects
     changes