"""State definition for the LangGraph workflow.

This module defines the ReviewState model that flows through the graph,
accumulating data as each node processes it.
"""

from typing import List, Dict, Any
from pydantic import BaseModel, Field
from review_roadmap.models import PRContext


class ReviewState(BaseModel):
    """State container for the review roadmap workflow.

    This Pydantic model is passed through each node in the LangGraph workflow.
    Nodes read from and write to this state to share information.

    The workflow progresses as:
    1. Input: pr_context is provided at invocation
    2. analyze_structure: populates topology
    3. context_expansion: populates fetched_content (if needed)
    4. draft_roadmap: populates roadmap (final output)
    5. reflect_on_roadmap: self-reviews and optionally triggers retry

    Attributes:
        pr_context: Input PR data including metadata, files, and comments.
        topology: Analysis of file groupings from the structure analysis node.
        required_context: File paths identified for fetching (intermediate).
        fetched_content: Additional file contents fetched for context.
        roadmap: The final generated Markdown roadmap (output).
        reflection_feedback: Feedback from self-reflection step for improvements.
        reflection_passed: Whether the roadmap passed self-review.
        reflection_iterations: Number of reflection iterations completed.
        skip_reflection: Whether to skip the self-reflection step entirely.
    """

    # Input
    pr_context: PRContext

    # Intermediate Reasoning
    topology: Dict[str, Any] = Field(
        default_factory=dict, description="Grouped files logic"
    )
    required_context: List[str] = Field(
        default_factory=list, description="List of file paths to fetch content for"
    )
    fetched_content: Dict[str, str] = Field(
        default_factory=dict, description="Content of fetched files"
    )

    # Output
    roadmap: str = ""

    # Reflection
    reflection_feedback: str = Field(
        default="", description="Feedback from self-reflection step"
    )
    reflection_passed: bool = Field(
        default=False, description="Whether the roadmap passed self-review"
    )
    reflection_iterations: int = Field(
        default=0, description="Number of reflection iterations completed"
    )
    skip_reflection: bool = Field(
        default=False, description="Whether to skip the self-reflection step"
    )
