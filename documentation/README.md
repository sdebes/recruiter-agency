# 🎯 Recruiter Agency

**Multi-agent job search system** — Evaluate listings, tailor CVs, track applications, and prep for interviews. Built with LangGraph, FastAPI (run_server.py), and Google ADK.

---

## Features

| Feature | Description |
|---------|-------------|
| **A-F Evaluation** | Multi-block scoring (CV match, north star, comp, culture, red flags) with configurable archetypes and weights |
| **Human-in-the-Loop** | LangGraph interrupts pause after evaluation — you decide Apply, Skip, or Review Later |
| **Application Tracker** | SQLite-backed tracker with canonical states and inline status updates |
| **CV Tailoring** | LLM-powered CV + cover letter generation per listing |
| **Persistent Memory** | Learned preferences and feedback history across sessions |
| **Configurable Archetypes** | YAML-defined archetypes (Data Scientist, ML Engineer, AI Engineer, etc.) with adjustable scoring |
| **Streamlit Dashboard** | Evaluate, track, and configure from a single UI |

## Architecture

```
User (Streamlit Dashboard)
    │
    ▼
┌──────────────────────────────────────────┐
│  Google ADK Agent (RecruiterAgency)       │
│  ─ Natural language interface (stretch)   │
│                                          │
│  ┌────────────────────────────────────┐  │
│  │  LangGraph Engine                  │  │
│  │  ─ Stateful graph with HITL       │  │
│  │  ─ SQLite checkpointing           │  │
│  │  ─ Interrupt BEFORE user decision │  │
│  │                                    │  │
│  │  Input → Evaluate → [PAUSE] →     │  │
│  │  Routing → Track → Report → Done  │  │
│  └────────────────────────────────────┘  │
└──────────────────────────────────────────┘
```

### Pipeline Flow

```
1. INPUT      — Paste a job URL or description
2. EVALUATE   — A-F scoring via LLM (CV match, north star, comp, culture, red flags)
3. [PAUSE]    — **Human-in-the-loop:** review scores, decide Apply / Skip / Review Later
4. TRACK      — Record in local SQL-based SQLite database
5. REPORT     — Generate markdown evaluation report
```

## Quick Start

```bash
# 1. Clone and set up
git clone <your-repo-url>
cd recruiter-agency
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 2. Configure
cp .env.example .env
# Edit .env → set OPENROUTER_API_KEY=your_key_here

# 2. Start the server
python run_server.py
```

## Usage

1. **Evaluate a listing** — On the home page, paste a job URL or description, and click "Add Job Listing"
2. **Review the listing** — The listing is added to the table, and you can click it to inspect the details.
3. **Make a decision** — Here you can click the button to have AI tailor your CV and cover letter to this listing.
4. **Apply for the job** — For now, you will have to download the generated files and apply manually.
5. **Track everything** — The **Tracker** page shows all your applications with filters and inline status updates
6. **Configure** — The **Settings** page lets you update your profile and adjust archetype scoring weights

## Project Structure

```
recruiter-agency/
├── app/                    # Streamlit dashboard
│   ├── Home.py             # Entry point
│   ├── pages/              # Evaluate, Tracker, Settings
│   ├── core/engine.py      # Streamlit ↔ LangGraph bridge
│   └── components/         # Scoring display, decision buttons
├── graph/                  # LangGraph pipeline engine
│   ├── state.py            # AgentState TypedDict
│   ├── builder.py          # Graph construction + compilation
│   ├── memory.py           # SQLite checkpointing + persistent memory
│   ├── runner.py           # Pipeline entry point
│   └── nodes/              # Input, evaluation, tracking, reporting
├── agents/                 # Agent logic (stubs for extension)
├── adk/                    # Google ADK wrapper (stretch)
├── services/               # Backend services
│   ├── llm_service.py      # Gemini API calls
│   └── tracker_service.py  # SQLite CRUD
├── config/                 # YAML configuration (user layer)
│   ├── profile.yml         # Your identity, targets, compensation
│   └── archetypes.yml      # Archetype definitions + scoring weights
├── personal_documents/     # Your CV, cover letter template
├── agentdb/                # SQLite databases (gitignored)
├── reports/                # Generated markdown reports
└── output/                 # Generated PDFs
```

## Tech Stack

| Layer | Technology |
|-------|------------|
| **Agent Framework** | LangGraph (stateful graphs, HITL, checkpointing) |
| **Interface** | Google ADK (wrapping LangGraph as an agent) |
| **Backend** | FastAPI (run_server.py) |
| **LLM** | Gemini 2.0 Flash (via OpenRouter or Google SDK) |
| **Database** | SQLite (local-first, zero config) |
| **Config** | YAML (human-readable) |

## Ethical Design

- **Never invent experience** — only reformulate existing CV content
- **Never auto-submit** — the system evaluates, you decide
- **Low-score discouragement** — scores below 3.5/5 recommend against applying
- **Data sovereignty** — all data stays in local SQLite

## License

MIT
