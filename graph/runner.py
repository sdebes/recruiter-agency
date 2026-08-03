# Recruiter Agency - Graph Runner
#
# Entry point for executing the LangGraph pipeline.
# Provides both synchronous and streaming interfaces.

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv

# Ensure .env is loaded
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"))
load_dotenv() # Fallback

from graph.builder import get_graph
from graph.state import AgentState, create_initial_state
from utils.config_loader import load_all_config, get_cv_text
from services.tracker_service import init_db

load_dotenv()

# Thread ID for checkpointing — persists state across sessions
DEFAULT_THREAD_ID = "recruiter-agency-main"


def initialize_session():
    """Initialize databases and load config. Call once at startup."""
    init_db()


def get_config(thread_id: str = DEFAULT_THREAD_ID) -> dict:
    """Get the LangGraph config with thread ID for checkpointing."""
    return {"configurable": {"thread_id": thread_id}}


def _load_profile_with_cv() -> dict:
    """Load profile from config and attach CV text."""
    config = load_all_config()
    profile = config.get("profile", {})
    cv_text = get_cv_text()
    profile["_cv_text"] = cv_text
    return profile


def run_pipeline(
    input_type: str,
    input_data: str,
    thread_id: str = DEFAULT_THREAD_ID,
) -> Dict[str, Any]:
    """Run the full pipeline synchronously.

    Args:
        input_type: One of "url", "jd_text", "scan", "batch"
        input_data: URL, JD text, or command
        thread_id: Thread ID for checkpoint persistence

    Returns:
        Final state after graph execution, or paused state
        showing human-in-the-loop interruption.
    """
    initialize_session()
    profile = _load_profile_with_cv()
    config = load_all_config()
    graph = get_graph()
    run_config = get_config(thread_id)

    initial_state = create_initial_state(
        input_type=input_type,
        input_data=input_data,
        profile=profile,
        archetypes_config=config.get("archetypes", {}),
    )

    # Stream events until completion or interrupt
    result_state = None
    for event in graph.stream(initial_state, run_config):
        result_state = event
        # Check if we hit an interrupt
        if isinstance(event, dict) and "__interrupt__" in event:
            break

    return _extract_result(graph, run_config, result_state)


def continue_pipeline(
    user_decision: str,
    thread_id: str = DEFAULT_THREAD_ID,
) -> Dict[str, Any]:
    """Continue a paused pipeline with a user decision.

    Args:
        user_decision: "apply", "skip", or "review_later"
        thread_id: Thread ID matching the paused pipeline

    Returns:
        Final state after the pipeline completes.
    """
    graph = get_graph()
    run_config = get_config(thread_id)

    # Update state with user decision
    graph.update_state(run_config, {"user_decision": user_decision})

    # Continue execution
    result_state = None
    for event in graph.stream(None, run_config):
        result_state = event
        if isinstance(event, dict) and "__interrupt__" in event:
            break

    return _extract_result(graph, run_config, result_state)


def get_current_state(thread_id: str = DEFAULT_THREAD_ID) -> Dict[str, Any]:
    """Get the current (possibly paused) state of a pipeline run."""
    graph = get_graph()
    run_config = get_config(thread_id)
    return graph.get_state(run_config)


def get_pipeline_summary(thread_id: str = DEFAULT_THREAD_ID) -> Dict[str, Any]:
    """Get a human-readable summary of the current pipeline state."""
    state = get_current_state(thread_id)
    values = state.values if hasattr(state, "values") else state

    messages = values.get("messages", [])
    errors = values.get("errors", [])
    phase = values.get("pipeline_phase", "unknown")
    evaluation = values.get("current_evaluation")

    return {
        "phase": phase,
        "messages": messages,
        "errors": errors,
        "paused": is_paused(thread_id),
        "has_evaluation": evaluation is not None,
        "score": evaluation.get("global_score") if evaluation else None,
    }


def is_paused(thread_id: str = DEFAULT_THREAD_ID) -> bool:
    """Check if the pipeline is paused waiting for user input."""
    state = get_current_state(thread_id)
    if hasattr(state, "tasks") and state.tasks:
        return any(t.interrupts for t in state.tasks)
    return False


def _extract_result(graph, config, last_event):
    """Extract the final or paused state from graph execution."""
    state = graph.get_state(config)
    values = state.values if hasattr(state, "values") else state
    paused = is_paused(config["configurable"]["thread_id"])

    return {
        "paused": paused,
        "interrupts": _get_interrupt_info(state) if paused else [],
        "final": values,
    }


def _get_interrupt_info(state):
    """Extract interrupt information from the state."""
    if hasattr(state, "tasks"):
        interrupts = []
        for task in state.tasks:
            for interrupt in task.interrupts:
                interrupts.append({
                    "node": interrupt.node,
                    "value": interrupt.value,
                })
        return interrupts
    return []