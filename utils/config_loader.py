# Recruiter Agency — Config Loader
#
# Loads YAML configuration files (profile.yml, archetypes.yml) from config/.
# Imported project-wide by server, graph, agents, and services.

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, Optional

import yaml


def _find_project_root() -> Path:
    """Resolve project root as the parent of this utils/ directory."""
    # This file lives at <root>/utils/config_loader.py — root is two levels up.
    return Path(__file__).resolve().parent.parent


PROJECT_ROOT = _find_project_root()


def load_yaml(path: str) -> Dict[str, Any]:
    """Load a YAML file and return its contents."""
    full_path = Path(path)
    if not full_path.is_absolute():
        full_path = PROJECT_ROOT / full_path

    if not full_path.exists():
        raise FileNotFoundError(f"Config file not found: {full_path}")

    with open(full_path, "r") as f:
        return yaml.safe_load(f)


def load_profile(path: Optional[str] = None) -> Dict[str, Any]:
    """Load the candidate profile configuration."""
    return load_yaml(path or PROJECT_ROOT / "config" / "profile.yml")


def load_archetypes(path: Optional[str] = None) -> Dict[str, Any]:
    """Load the archetypes configuration."""
    return load_yaml(path or PROJECT_ROOT / "config" / "archetypes.yml")


def load_all_config() -> Dict[str, Any]:
    """Load all configuration files at once."""
    return {
        "profile": load_profile(),
        "archetypes": load_archetypes(),
    }


def get_cv_text() -> str:
    """Read the canonical CV markdown from config/."""
    profile = load_profile()
    cv_path = profile.get("cv", {}).get("source_path", "config/resume.md")
    full_path = Path(cv_path)
    if not full_path.is_absolute():
        full_path = PROJECT_ROOT / full_path
    if full_path.exists():
        return full_path.read_text()
    return ""


def get_job_boards() -> Dict[str, Any]:
    """Get enabled job boards from archetypes config."""
    config = load_archetypes()
    return config.get("job_boards", {})