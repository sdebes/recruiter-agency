# Recruiter Agency - Checkpointing and Persistent Memory
#
# LangGraph checkpointing stores graph execution state so we can
# pause (for human-in-the-loop), inspect, and resume the pipeline.
# Persistent memory stores learned preferences across sessions.

from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv

load_dotenv()


def get_db_path(name: str = "checkpoints.db") -> str:
    """Get the path for a database file, ensuring the directory exists."""
    base = os.getenv("CHECKPOINT_DB_PATH", "agentdb/checkpoints.db")
    db_dir = Path(base).parent
    db_dir.mkdir(parents=True, exist_ok=True)
    return str(db_dir / name)


def get_checkpointer():
    """Create a LangGraph SQLite checkpointer for graph execution state.

    Uses langgraph.checkpoint.sqlite.SqliteSaver for persistent
    checkpointing across sessions. Each run gets a thread_id.
    """
    try:
        import sqlite3
        from langgraph.checkpoint.sqlite import SqliteSaver
        db_path = get_db_path()
        conn = sqlite3.connect(db_path, check_same_thread=False)
        return SqliteSaver(conn)
    except ImportError:
        # Fallback: in-memory checkpointer for development
        from langgraph.checkpoint.memory import MemorySaver
        return MemorySaver()


def get_checkpointer_sync():
    """Synchronous checkpoint saver for the graph."""
    return get_checkpointer()


# ── Persistent Memory ────────────────────────────────────────────────────

class PersistentMemory:
    """Stores learned preferences and feedback across sessions.

    This is separate from LangGraph checkpoints (which store graph
    execution state). This stores what the system has learned about
    the user's preferences over time.
    """

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or get_db_path("memory.db")
        self._init_db()

    def _init_db(self):
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS learned_preferences (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                key TEXT UNIQUE NOT NULL,
                value TEXT NOT NULL,
                confidence REAL DEFAULT 1.0,
                source TEXT,
                created_at TEXT DEFAULT (datetime('now')),
                updated_at TEXT DEFAULT (datetime('now'))
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS feedback_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                evaluation_id TEXT,
                listing_title TEXT,
                user_action TEXT,
                user_note TEXT,
                score REAL,
                created_at TEXT DEFAULT (datetime('now'))
            )
        """)
        conn.commit()
        conn.close()

    def get_preference(self, key: str, default: Any = None) -> Any:
        conn = sqlite3.connect(self.db_path)
        row = conn.execute(
            "SELECT value FROM learned_preferences WHERE key = ?", (key,)
        ).fetchone()
        conn.close()
        if row:
            return json.loads(row[0])
        return default

    def set_preference(self, key: str, value: Any, source: str = "inferred"):
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            INSERT INTO learned_preferences (key, value, source, updated_at)
            VALUES (?, ?, ?, datetime('now'))
            ON CONFLICT(key) DO UPDATE SET
                value = excluded.value,
                source = excluded.source,
                updated_at = datetime('now'),
                confidence = MIN(confidence + 0.1, 1.0)
        """, (key, json.dumps(value), source))
        conn.commit()
        conn.close()

    def log_feedback(
        self,
        evaluation_id: str,
        user_action: str,
        listing_title: Optional[str] = None,
        user_note: Optional[str] = None,
        score: Optional[float] = None,
    ):
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            INSERT INTO feedback_log (evaluation_id, listing_title, user_action, user_note, score)
            VALUES (?, ?, ?, ?, ?)
        """, (evaluation_id, listing_title, user_action, user_note, score))
        conn.commit()
        conn.close()

    def get_all_preferences(self) -> Dict[str, Any]:
        conn = sqlite3.connect(self.db_path)
        rows = conn.execute(
            "SELECT key, value, confidence, source FROM learned_preferences"
        ).fetchall()
        conn.close()
        return {
            row[0]: {"value": json.loads(row[1]), "confidence": row[2], "source": row[3]}
            for row in rows
        }

    def get_feedback_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        conn = sqlite3.connect(self.db_path)
        rows = conn.execute(
            "SELECT * FROM feedback_log ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        conn.close()
        return [
            {
                "id": r[0],
                "evaluation_id": r[1],
                "listing_title": r[2],
                "user_action": r[3],
                "user_note": r[4],
                "score": r[5],
                "created_at": r[6],
            }
            for r in rows
        ]