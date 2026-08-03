# 🎯 Recruiter Agency

**A multi-agent job search system** that discovers job listings, evaluates them against your profile, tailors CVs and cover letters, and tracks your applications — all with human-in-the-loop control and local-first data storage.

Built with **FastAPI**, **LangGraph**, and a **Next.js** dashboard. Powered by Gemini/OpenRouter LLMs.

---

## Features

| Feature | Description |
|---------|-------------|
| **A-F Evaluation** | Multi-dimension scoring (CV match, north star, compensation, culture, red flags) with configurable archetypes and weights |
| **Human-in-the-Loop** | The pipeline pauses after evaluation — you decide Apply, Skip, or Review Later |
| **CV Tailoring** | LLM-powered CV + cover letter generation per listing |
| **Application Tracker** | SQLite-backed tracker with filters and inline status updates |
| **Listing Discovery** | Scrape job boards (jobs.ch, Jobindex.dk) via httpx/Playwright or Apify |
| **Resume Builder** | Structured resume editor feeding the tailoring agents |
| **Configurable Archetypes** | YAML-defined archetypes (Data Scientist, ML Engineer, AI Engineer, …) with adjustable scoring weights |
| **Data Sovereignty** | Everything lives in local SQLite — no cloud sync |

## Architecture

```
User (Next.js Dashboard :3000)
    │
    ▼
┌──────────────────────────────────────────┐
│  FastAPI Backend (:8000)                 │
│  ─ REST API (listings, evaluation,       │
│    tailoring, tracker, config)           │
│                                          │
│  ┌────────────────────────────────────┐  │
│  │  LangGraph Engine                  │  │
│  │  ─ Stateful pipeline               │  │
│  │  ─ Interrupt BEFORE user decision  │  │
│  │  ─ SQLite checkpointing            │  │
│  │                                    │  │
│  │  Input → Find → Evaluate → [PAUSE] │  │
│  │  → Tailor → Track → Report         │  │
│  └────────────────────────────────────┘  │
└──────────────────────────────────────────┘
```

### Pipeline Flow

```
1. INPUT      — Paste a job URL or description
2. FIND       — Scrape & enrich the listing (architype detection)
3. EVALUATE   — A–F scoring via LLM (CV match, north star, comp, culture, red flags)
4. [PAUSE]    — Human-in-the-loop: review scores, decide Apply / Skip / Review Later
5. TAILOR     — Generate a tailored CV + cover letter (if Apply)
6. TRACK      — Record in local SQLite database
7. REPORT     — Summarize results
```

## Quick Start

### Prerequisites

- Python **3.14+** ([uv](https://docs.astral.sh/uv/) recommended)
- Node.js **18+**
- An LLM API key: [OpenRouter](https://openrouter.ai/keys) or [Google Gemini](https://aistudio.google.com/apikey)

### 1. Backend

```bash
# Install Python dependencies (uv or pip)
uv sync
# or: pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Set OPENROUTER_API_KEY=<your-key> and/or GEMINI_API_KEY=<your-key>

# Start the FastAPI server on http://localhost:8000
python run_server.py
```

### 2. Frontend

```bash
cd frontend
npm install
npm run dev   # serves http://localhost:3000
```

> 💡 On macOS you can skip both steps with `./run_recruiter_server.command`, which installs dependencies and launches both servers.

## Usage

1. **Discover** — On the home page, paste a job URL or description and click **Find / Evaluate**. The system scrapes and enriches the listing.
2. **Review** — A–F scores are displayed per dimension (CV match, north star, comp, culture, red flags) with a global score and recommendation.
3. **Decide** — Choose **Apply**, **Skip**, or **Review Later**. Applying triggers CV + cover letter tailoring.
4. **Tailor** — Download the generated CV/cover letter and apply manually — the system never auto-submits.
5. **Track** — The **Tracker** page lists all applications with filters and inline status updates.
6. **Configure** — The **Settings** page edits your profile and archetype scoring weights; changes apply to future evaluations.

## Configuration

| File | Purpose |
|------|---------|
| `.env` | API keys (OpenRouter, Gemini, Apify) and DB/log settings — **never commit** |
| `config/archetypes.yml` | Archetype definitions, keywords, scoring weights, job boards |
| `config/profile.yml` | Candidate identity, target roles, compensation |
| `config/resume.md` / `config/resumeinfo.json` | Base CV (markdown + structured JSON used by tailoring) |
| `config/storybank.md` | STAR stories for interview prep |

## Project Structure

```
recruiter-agency/
├── run_server.py            # Backend entry point (uvicorn server.main:app)
├── pyproject.toml / requirements.txt / uv.lock
├── config/                  # User config, CV data (personal files gitignored)
├── server/                  # FastAPI backend
│   ├── main.py              # All API routes
│   ├── static/              # CSS, JS, assets
│   └── templates/           # Jinja2 HTML templates
├── frontend/                # Next.js dashboard (primary UI)
│   └── src/app/             # Pages: home, tracker, resume-builder, settings
├── graph/                   # LangGraph engine
│   ├── state.py             # AgentState TypedDict
│   ├── builder.py           # Graph construction
│   ├── memory.py            # SQLite checkpointing + persistent memory
│   ├── runner.py            # Pipeline entry point
│   └── nodes/               # Input, finding, evaluation, tailoring, tracking, reporting
├── agents/                  # Agent logic (scoring, scraping, tailoring)
├── services/                # Shared backend services (LLM, scraper, tracker, docs)
├── utils/                   # Core utilities (config loader)
├── adk/                     # Google ADK wrapper (stretch — stub)
├── documentation/           # PRD and design docs
├── agentdb/                 # SQLite databases (gitignored)
├── output/                  # Generated CVs, cover letters, reports (gitignored)
└── tests/
```

## Tech Stack

| Layer | Technology |
|-------|------------|
| **Backend** | FastAPI + Uvicorn |
| **Frontend** | Next.js 14, React 18, Tailwind CSS |
| **Agent Framework** | LangGraph (stateful graphs, HITL, checkpointing) |
| **LLM** | Gemini / OpenRouter (flash-lite for finding, flash for evaluation) |
| **Scraping** | httpx + BeautifulSoup, Playwright, Apify |
| **Database** | SQLite (local-first, zero config) |
| **Config** | YAML (human-readable) |

## Ethical Design

1. **Never invent experience** — only reformulate existing CV content
2. **Never auto-submit** — the system evaluates and prepares, you decide and apply
3. **Low-score discouragement** — scores below 3.5/5 recommend against applying
4. **Data sovereignty** — all data stays in local SQLite, no cloud sync
5. **Quality over quantity** — a few good applications beat many generic ones

## License

MIT
