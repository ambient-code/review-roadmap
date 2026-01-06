"""LangGraph workflow definition for the review roadmap agent.

This module constructs the directed graph that orchestrates the multi-step
analysis process for generating PR review roadmaps.
"""

from langgraph.graph import StateGraph, END
from langgraph.graph.state import CompiledStateGraph

from review_roadmap.agent.state import ReviewState
from review_roadmap.agent.nodes import (
    analyze_structure,
    context_expansion,
    draft_roadmap,
    reflect_on_roadmap,
)
from review_roadmap.agent.prompts import MAX_REFLECTION_ITERATIONS
from review_roadmap.logging import get_logger

logger = get_logger(__name__)


def _should_reflect(state: ReviewState) -> str:
    """Determine whether to run reflection or skip to end.
    
    Args:
        state: Current workflow state.
        
    Returns:
        'reflect' to run reflection, 'end' to skip.
    """
    if state.skip_reflection:
        logger.info("reflection_skipped", reason="disabled by user")
        return "end"
    return "reflect"


def _after_reflection(state: ReviewState) -> str:
    """Determine whether to retry roadmap generation or finish.
    
    Args:
        state: Current workflow state with reflection results.
        
    Returns:
        'retry' to regenerate roadmap, 'end' to finish.
    """
    if state.reflection_passed:
        return "end"
    if state.reflection_iterations >= MAX_REFLECTION_ITERATIONS:
        logger.warning("max_reflection_iterations_reached",
                      iterations=state.reflection_iterations)
        return "end"
    return "retry"


def build_graph() -> CompiledStateGraph:
    """Build and compile the LangGraph workflow for review roadmap generation.

    The workflow consists of four nodes with conditional routing:
    1. analyze_structure: Groups changed files into logical components
    2. context_expansion: Optionally fetches additional file content for context
    3. draft_roadmap: Generates the final Markdown roadmap
    4. reflect_on_roadmap: Self-reviews the roadmap and may trigger a retry

    The reflection step can be skipped by setting skip_reflection=True in the
    initial state. If reflection fails, the workflow loops back to draft_roadmap
    with feedback, up to MAX_REFLECTION_ITERATIONS times.

    Returns:
        A compiled LangGraph that can be invoked with a ReviewState containing
        the PR context.

    Example:
        >>> graph = build_graph()
        >>> result = graph.invoke({"pr_context": pr_context})
        >>> roadmap = result["roadmap"]
        
        # Skip reflection:
        >>> result = graph.invoke({"pr_context": pr_context, "skip_reflection": True})
    """
    workflow = StateGraph(ReviewState)

    # Add Nodes
    workflow.add_node("analyze_structure", analyze_structure)
    workflow.add_node("context_expansion", context_expansion)
    workflow.add_node("draft_roadmap", draft_roadmap)
    workflow.add_node("reflect_on_roadmap", reflect_on_roadmap)

    # Define Edges
    workflow.set_entry_point("analyze_structure")
    workflow.add_edge("analyze_structure", "context_expansion")
    workflow.add_edge("context_expansion", "draft_roadmap")
    
    # After draft_roadmap, decide whether to reflect or skip
    workflow.add_conditional_edges(
        "draft_roadmap",
        _should_reflect,
        {
            "reflect": "reflect_on_roadmap",
            "end": END,
        }
    )
    
    # After reflection, decide whether to retry or finish
    workflow.add_conditional_edges(
        "reflect_on_roadmap",
        _after_reflection,
        {
            "retry": "draft_roadmap",
            "end": END,
        }
    )

    return workflow.compile()
