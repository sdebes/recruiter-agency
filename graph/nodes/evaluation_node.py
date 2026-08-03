# Recruiter Agency - Evaluation Node
#
# Performs A-F scoring for a job listing using the LLM service.
# This is the most important node — it determines whether a listing
# is worth pursuing.

from __future__ import annotations

import os
import re
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv

# Ensure .env is loaded
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), ".env"))
load_dotenv() # Fallback

from graph.state import AgentState, Evaluation
from services.llm_service import LLMService

load_dotenv()


def _get_archetype_weights(
    archetype_name: str, archetypes_config: Dict[str, Any]
) -> Dict[str, float]:
    """Get scoring weights for a detected archetype, or defaults."""
    defaults = {"cv_match": 0.25, "north_star": 0.20, "compensation": 0.20, "culture": 0.20, "red_flags": 0.15}
    for a in archetypes_config.get("archetypes", []):
        if a["name"].lower() == archetype_name.lower():
            return a.get("scoring_weights", defaults)
    return defaults


def _parse_evaluation_result(text: str) -> Evaluation:
    """Parse LLM output into a structured Evaluation dict.

    Extracts scores from the markdown-formatted evaluation output.
    Falls back to defaults if parsing fails.
    """
    result: Evaluation = {
        "listing_id": "",
        "cv_match_score": 0.0,
        "north_star_score": 0.0,
        "comp_score": 0.0,
        "culture_score": 0.0,
        "red_flags": [],
        "global_score": 0.0,
        "legitimacy": "Proceed with Caution",
        "detailed_notes": text,
    }

    def extract_score(pattern: str, text: str) -> Optional[float]:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            try:
                return float(m.group(1))
            except ValueError:
                pass
        return None

    # Extract scores — the LLM may use "Block B — CV Match Score: [X.X/5]" or
    # "Block C — North Star Alignment: [X.X/5]" (with or without "Score:" in
    # the block name, with or without brackets around the value).
    def block_score(block: str, text: str) -> Optional[float]:
        return extract_score(
            rf"Block {block}.*?\[?\s*(\d+\.?\d*)\s*\]?\s*/5",
            text,
        )

    scores = {
        "cv_match_score": block_score("B", text),
        "north_star_score": block_score("C", text),
        "comp_score": block_score("D", text),
        "culture_score": block_score("E", text),
        "global_score": extract_score(r"Global Score.*?\[?\s*(\d+\.?\d*)\s*\]?\s*/5", text),
    }

    for key, val in scores.items():
        if val is not None and 0.0 <= val <= 5.0:
            result[key] = val  # type: ignore

    # Extract legitimacy
    leg_m = re.search(r"Legitimacy:\s*(High Confidence|Proceed with Caution|Suspicious)", text)
    if leg_m:
        result["legitimacy"] = leg_m.group(1)

    # Extract red flags
    flag_section = re.search(r"Block F.*?Red Flags:(.*?)(?:\*\*Global|\Z)", text, re.DOTALL)
    if flag_section:
        flags = []
        for line in flag_section.group(1).strip().split("\n"):
            line = line.strip().strip("- ").strip()
            if line and len(line) > 5:
                flags.append(line)
        result["red_flags"] = flags

    return result


def evaluate_listing_node(state: AgentState) -> dict:
    """Evaluate the current listing using A-F scoring.

    This node runs the LLM evaluation, sets user_approval_required=True
    to trigger the human-in-the-loop interrupt.
    """
    listings = state.get("listings", [])
    idx = state.get("current_listing_index", 0)

    if not listings or idx >= len(listings):
        return {
            "errors": ["No listing found at index " + str(idx)],
            "pipeline_phase": "done",
        }

    listing = listings[idx]
    profile = state.get("profile", {})
    archetypes_config = state.get("archetypes_config", {})

    # Step 1: Detect archetype
    cv_text = profile.get("_cv_text", "")
    jd_text = listing.get("description", listing.get("raw_text", ""))

    try:
        llm = LLMService()
    except ValueError as e:
        return {
            "errors": [str(e)],
            "pipeline_phase": "done",
        }

    try:
        archetype_result = llm.detect_archetype(jd_text, archetypes_config)
    except Exception as e:
        return {
            "errors": [f"Archetype detection failed: {e}"],
            "pipeline_phase": "evaluating",
        }

    # Parse archetype from result
    arch_match = re.search(r"ARCHETYPE:\s*(.+)", archetype_result)
    archetype_name = arch_match.group(1).strip() if arch_match else "Data Scientist"

    # Step 2: Get scoring weights
    weights = _get_archetype_weights(archetype_name, archetypes_config)

    # Step 3: Run full evaluation
    try:
        eval_text = llm.evaluate_listing(
            jd_text=jd_text,
            cv_text=cv_text,
            profile=profile,
            archetype=archetype_name,
            archetype_weights=weights,
        )
    except Exception as e:
        return {
            "errors": [f"Evaluation failed: {e}"],
            "pipeline_phase": "evaluating",
        }

    # Step 4: Parse results into structured Evaluation
    evaluation = _parse_evaluation_result(eval_text)
    evaluation["listing_id"] = listing.get("id", "")
    evaluation["archetype_detected"] = archetype_name

    # Step 5: Calculate global score if not in LLM output
    if evaluation["global_score"] == 0.0:
        weighted = (
            weights.get("cv_match", 0.25) * evaluation["cv_match_score"]
            + weights.get("north_star", 0.20) * evaluation["north_star_score"]
            + weights.get("compensation", 0.20) * evaluation["comp_score"]
            + weights.get("culture", 0.20) * evaluation["culture_score"]
        )
        # Penalize for red flags (up to -1.0)
        flag_penalty = min(len(evaluation.get("red_flags", [])) * 0.2, 1.0)
        evaluation["global_score"] = round(max(weighted - flag_penalty, 1.0), 1)

    message = (
        f"Evaluated **{listing.get('title', 'Unknown')}** at **{listing.get('company', 'Unknown')}** "
        f"— Score: {evaluation['global_score']}/5"
    )

    return {
        "current_evaluation": evaluation,
        "evaluations": state.get("evaluations", []) + [evaluation],
        "user_approval_required": True,
        "interrupt_reason": "evaluation_complete",
        "pipeline_phase": "evaluating",
        "messages": state.get("messages", []) + [message],
    }