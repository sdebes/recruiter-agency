# Recruiter Agency - LangGraph Pipeline Builder
#
# Constructs the job search pipeline as a LangGraph StateGraph.
# Key design:
#   - Interrupt points for human-in-the-loop decisions
#   - Conditional routing based on user decisions
#   - SQLite checkpointing for persistent state

from __future__ import annotations

from typing import Any, Dict, Literal

from langgraph.graph import END, StateGraph

from graph.state import AgentState, create_initial_state
from graph.memory import get_checkpointer
from graph.nodes.input_node import input_node
from graph.nodes.finding_node import enrich_url_node
from graph.nodes.evaluation_node import evaluate_listing_node
from graph.nodes.tracking_node import track_listing_node, routing_node
from graph.nodes.reporting_node import generate_report


def _route_after_input(
    state: AgentState,
) -> Literal["evaluate_listing", "enrich_url"]:
    """Route to evaluation directly (manual JD) or enrichment (URL needs scraping)."""
    phase = state.get("pipeline_phase", "")
    if phase == "finding":
        return "enrich_url"
    return "evaluate_listing"


def _route_after_evaluation(
    state: AgentState,
) -> Literal["track_listing", "report"]:
    """After evaluation, always route to tracking (record the result).

    The human-in-the-loop interrupt happens BEFORE this node runs,
    so by the time we're here, the user has already decided.
    """
    return "track_listing"


def _route_after_tracking(
    state: AgentState,
) -> Literal["generate_report", END]:
    """Route to reporting or done based on user decision."""
    phase = state.get("pipeline_phase", "")
    if phase == "tailoring":
        return "generate_report"  # Report regardless after tailoring
    return "generate_report"


def build_graph() -> StateGraph:
    """Build the recruiter agency pipeline graph.

    Returns a compiled graph ready for execution.
    The graph pauses at key points for human-in-the-loop decisions.
    """
    # ── Build Graph ──────────────────────────────────────────────────
    builder = StateGraph(AgentState)

    # Add nodes
    builder.add_node("input", input_node)
    builder.add_node("enrich_url", enrich_url_node)
    builder.add_node("evaluate_listing", evaluate_listing_node)
    builder.add_node("track_listing", track_listing_node)
    builder.add_node("routing", routing_node)
    builder.add_node("generate_report", generate_report)

    # ── Edges ────────────────────────────────────────────────────────

    # Entry point → input processing
    builder.set_entry_point("input")

    # Input → enrichment or evaluation
    builder.add_conditional_edges(
        "input",
        _route_after_input,
        {
            "evaluate_listing": "evaluate_listing",
            "enrich_url": "enrich_url",
        },
    )

    # Enrichment → evaluation
    builder.add_edge("enrich_url", "evaluate_listing")

    # Evaluation → routing (HITL interrupt happens between these)
    builder.add_edge("evaluate_listing", "routing")

    # Routing → tracking (with user decision in state)
    builder.add_edge("routing", "track_listing")

    # Tracking → report → done
    builder.add_conditional_edges(
        "track_listing",
        _route_after_tracking,
        {
            "generate_report": "generate_report",
            END: END,
        },
    )

    builder.add_edge("generate_report", END)

    # ── Compile ──────────────────────────────────────────────────────
    # Interrupt BEFORE routing to let user decide (human-in-the-loop)
    checkpointer = get_checkpointer()
    graph = builder.compile(
        interrupt_before=["routing"],  # Pause BEFORE routing to ask user
        checkpointer=checkpointer,
    )

    return graph


def get_graph() -> StateGraph:
    """Get the compiled graph (cached)."""
    return build_graph()