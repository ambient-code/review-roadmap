"""LangGraph workflow definition for the review roadmap agent.

This module constructs the directed graph that orchestrates the multi-step
analysis process for generating PR review roadmaps.
"""

from langgraph.graph import StateGraph, END
from langgraph.graph.state import CompiledStateGraph

from review_roadmap.agent.state import ReviewState
from review_roadmap.agent.nodes import analyze_structure, context_expansion, draft_roadmap


def build_graph() -> CompiledStateGraph:
    """Build and compile the LangGraph workflow for review roadmap generation.

    The workflow consists of three sequential nodes:
    1. analyze_structure: Groups changed files into logical components
    2. context_expansion: Optionally fetches additional file content for context
    3. draft_roadmap: Generates the final Markdown roadmap

    Returns:
        A compiled LangGraph that can be invoked with a ReviewState containing
        the PR context.

    Example:
        >>> graph = build_graph()
        >>> result = graph.invoke({"pr_context": pr_context})
        >>> roadmap = result["roadmap"]
    """
    workflow = StateGraph(ReviewState)

    # Add Nodes
    workflow.add_node("analyze_structure", analyze_structure)
    workflow.add_node("context_expansion", context_expansion)
    workflow.add_node("draft_roadmap", draft_roadmap)

    # Define Edges
    workflow.set_entry_point("analyze_structure")
    workflow.add_edge("analyze_structure", "context_expansion")
    workflow.add_edge("context_expansion", "draft_roadmap")
    workflow.add_edge("draft_roadmap", END)

    return workflow.compile()
