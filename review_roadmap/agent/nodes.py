"""LangGraph node functions for the review roadmap agent.

This module contains the node functions that make up the LangGraph workflow,
along with helper functions for LLM initialization and context building.
"""

import os
from typing import Any, Dict, List, Tuple, Union

from langchain_anthropic import ChatAnthropic
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from langchain_google_genai import ChatGoogleGenerativeAI

from review_roadmap.agent.state import ReviewState
from review_roadmap.config import settings
from review_roadmap.github.client import GitHubClient
from review_roadmap.logging import get_logger

logger = get_logger(__name__)


# Default max tokens for LLM responses (roadmaps can be lengthy)
MAX_TOKENS = 4096


def _get_anthropic_vertex_llm() -> BaseChatModel:
    """Create an Anthropic model via Google Vertex AI.

    Configures authentication using either explicit credentials path or
    default gcloud application credentials.

    Returns:
        A ChatAnthropicVertex instance configured for the project.

    Raises:
        ValueError: If ANTHROPIC_VERTEX_PROJECT_ID is not set.
    """
    from langchain_google_vertexai.model_garden import ChatAnthropicVertex
    
    credentials_path = settings.get_google_credentials_path()
    if credentials_path:
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = credentials_path
    
    if not settings.ANTHROPIC_VERTEX_PROJECT_ID:
        raise ValueError("ANTHROPIC_VERTEX_PROJECT_ID must be set when using anthropic-vertex provider")
    
    return ChatAnthropicVertex(
        model_name=settings.REVIEW_ROADMAP_MODEL_NAME,
        project=settings.ANTHROPIC_VERTEX_PROJECT_ID,
        location=settings.ANTHROPIC_VERTEX_REGION,
        max_tokens=MAX_TOKENS
    )


def get_llm() -> BaseChatModel:
    """Create and return the configured LLM instance.

    Reads the provider from REVIEW_ROADMAP_LLM_PROVIDER setting and
    initializes the appropriate LangChain chat model.

    Returns:
        A LangChain chat model instance for the configured provider.

    Raises:
        ValueError: If the provider is not supported.
    """
    provider = settings.REVIEW_ROADMAP_LLM_PROVIDER.lower()
    
    if provider == "anthropic":
        return ChatAnthropic(
            model_name=settings.REVIEW_ROADMAP_MODEL_NAME,
            api_key=settings.ANTHROPIC_API_KEY,
            max_tokens=MAX_TOKENS
        )
    elif provider == "anthropic-vertex":
        return _get_anthropic_vertex_llm()
    elif provider == "openai":
        return ChatOpenAI(
            model_name=settings.REVIEW_ROADMAP_MODEL_NAME,
            api_key=settings.OPENAI_API_KEY,
            max_tokens=MAX_TOKENS
        )
    elif provider == "google":
        return ChatGoogleGenerativeAI(
            model=settings.REVIEW_ROADMAP_MODEL_NAME,
            google_api_key=settings.GOOGLE_API_KEY,
            max_output_tokens=MAX_TOKENS
        )
    else:
        raise ValueError(f"Unsupported LLM provider: {provider}")


# Lazy LLM initialization - only created when first accessed
_llm_instance: BaseChatModel | None = None


def _get_llm_instance() -> BaseChatModel:
    """Get or create the LLM instance (lazy initialization).

    This avoids creating the LLM at module import time, which allows
    tests to mock the LLM before it's instantiated.
    """
    global _llm_instance
    if _llm_instance is None:
        _llm_instance = get_llm()
    return _llm_instance


from review_roadmap.agent.prompts import (
    ANALYZE_STRUCTURE_SYSTEM_PROMPT,
    CONTEXT_EXPANSION_SYSTEM_PROMPT,
    DRAFT_ROADMAP_SYSTEM_PROMPT,
    REFLECT_ON_ROADMAP_SYSTEM_PROMPT,
)
from review_roadmap.agent.tools import read_file


def analyze_structure(state: ReviewState) -> Dict[str, Any]:
    """Analyze PR file structure and group into logical components.

    First node in the workflow. Uses an LLM to analyze the changed files
    and identify logical groupings (e.g., 'Backend API', 'Frontend', 'Config').

    Args:
        state: Current workflow state containing PR context.

    Returns:
        Dict with 'topology' key containing the structural analysis.
    """
    logger.info("node_started", node="analyze_structure")
    
    files_list = "\n".join([
        f"- {f.path} ({f.status}, +{f.additions}/-{f.deletions})"
        for f in state.pr_context.files
    ])
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", ANALYZE_STRUCTURE_SYSTEM_PROMPT),
        ("human", "PR Title: {title}\n\nFiles:\n{files}")
    ])
    
    chain = prompt | _get_llm_instance()
    response = chain.invoke({
        "title": state.pr_context.metadata.title,
        "files": files_list
    })
    
    return {"topology": {"analysis": response.content}}


def _parse_repo_info(repo_url: str) -> Tuple[str, str]:
    """Extract owner and repo name from a GitHub repository URL.

    Args:
        repo_url: Full GitHub URL (e.g., 'https://github.com/owner/repo').

    Returns:
        Tuple of (owner, repo_name).
    """
    parts = repo_url.rstrip("/").split("/")
    return parts[-2], parts[-1]  # owner, repo


def _fetch_tool_call_content(
    tool_calls: List[Dict[str, Any]],
    client: GitHubClient,
    owner: str,
    repo: str,
    sha: str,
) -> Dict[str, str]:
    """Fetch file content from GitHub for each read_file tool call.

    Processes tool calls from the LLM and fetches the requested file
    contents from GitHub. Errors are captured in the result rather than raised.

    Args:
        tool_calls: List of tool call dicts from LLM response.
        client: GitHub API client instance.
        owner: Repository owner.
        repo: Repository name.
        sha: Commit SHA to fetch files from.

    Returns:
        Dict mapping file paths to their content (or error messages).
    """
    fetched_content: Dict[str, str] = {}
    
    for tool_call in tool_calls:
        if tool_call["name"] != "read_file":
            continue
        path = tool_call["args"].get("path")
        if not path:
            continue
            
        logger.debug("fetching_file", path=path)
        try:
            content = client.get_file_content(owner, repo, path, sha)
            fetched_content[path] = content
        except Exception as e:
            logger.warning("fetch_file_error", path=path, error=str(e))
            fetched_content[path] = f"Error fetching content: {str(e)}"
    
    return fetched_content


def context_expansion(state: ReviewState) -> Dict[str, Any]:
    """Optionally fetch additional file content for better context.

    Second node in the workflow. Uses an LLM with tool-calling to decide
    if any additional files should be fetched to understand the PR better.
    For example, fetching a parent class when reviewing inheritance changes.

    Args:
        state: Current workflow state with PR context and topology analysis.

    Returns:
        Dict with 'fetched_content' key mapping paths to file contents.
    """
    logger.info("node_started", node="context_expansion")
    
    model_with_tools = _get_llm_instance().bind_tools([read_file])
    
    files_list = "\n".join([f"- {f.path} ({f.status})" for f in state.pr_context.files])
    topology = state.topology.get('analysis', 'No analysis')
    
    context_str = f"""
    PR Title: {state.pr_context.metadata.title}
    
    Files:
    {files_list}
    
    Topology Analysis:
    {topology}
    
    Comments:
    {len(state.pr_context.comments)} existing comments.
    """
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", CONTEXT_EXPANSION_SYSTEM_PROMPT),
        ("human", "{context}")
    ])
    
    chain = prompt | model_with_tools
    response = chain.invoke({"context": context_str})
    
    fetched_content: Dict[str, str] = {}
    if hasattr(response, "tool_calls") and response.tool_calls:
        logger.info("fetching_files", count=len(response.tool_calls))
        owner, repo = _parse_repo_info(state.pr_context.metadata.repo_url)
        sha = state.pr_context.metadata.head_commit_sha
        fetched_content = _fetch_tool_call_content(
            response.tool_calls, GitHubClient(), owner, repo, sha
        )

    return {"fetched_content": fetched_content}


def _build_files_context(state: ReviewState) -> List[str]:
    """Build formatted file list with PR diff deep links.

    Args:
        state: Current workflow state containing PR context.

    Returns:
        List of formatted strings like '- path/file.py (modified): <url>'.
    """
    repo_url = state.pr_context.metadata.repo_url
    pr_number = state.pr_context.metadata.number
    return [
        f"- {f.path} ({f.status}): {f.get_pr_diff_link(repo_url, pr_number)}"
        for f in state.pr_context.files
    ]


def _build_comments_context(state: ReviewState) -> List[str]:
    """Build formatted list of existing PR comments.

    Args:
        state: Current workflow state containing PR context.

    Returns:
        List of formatted strings like '- username (file:line): comment body'.
    """
    comments_context = []
    for c in state.pr_context.comments:
        location = f"({c.path}:{c.line})" if c.path else "(General)"
        comments_context.append(f"- {c.user} {location}: {c.body}")
    return comments_context


def _build_fetched_content_str(fetched_content: Dict[str, str]) -> str:
    """Format fetched file contents for inclusion in the LLM prompt.

    Truncates large files to 2000 characters to avoid token limits.

    Args:
        fetched_content: Dict mapping file paths to their content.

    Returns:
        Formatted string with file contents, or empty string if none.
    """
    if not fetched_content:
        return ""
    
    parts = ["\n\nfetched_content:\n"]
    for path, content in fetched_content.items():
        preview = content[:2000] + ("\n... (truncated)" if len(content) > 2000 else "")
        parts.append(f"\n--- File: {path} ---\n{preview}\n")
    return "".join(parts)


# Maximum characters per diff before truncation
MAX_DIFF_CHARS = 1500
# Maximum total characters for all diffs combined
MAX_TOTAL_DIFF_CHARS = 80000


def _build_diffs_context(state: ReviewState) -> str:
    """Build formatted diff content for all changed files.

    Includes the actual unified diff for each file so the LLM can see
    the code changes, not just file names. Large diffs are truncated
    to manage token limits.

    Args:
        state: Current workflow state containing PR context.

    Returns:
        Formatted string with all diffs, suitable for LLM prompt.
    """
    if not state.pr_context.files:
        return "No files changed."

    parts = []
    total_chars = 0

    for f in state.pr_context.files:
        if not f.diff_content:
            # Binary files or very large files may not have diff content
            file_section = f"### {f.path} ({f.status}, +{f.additions}/-{f.deletions})\n[No diff available - binary or large file]\n"
        else:
            diff = f.diff_content
            if len(diff) > MAX_DIFF_CHARS:
                diff = diff[:MAX_DIFF_CHARS] + f"\n... (truncated, {len(f.diff_content)} chars total)"
            file_section = f"### {f.path} ({f.status}, +{f.additions}/-{f.deletions})\n```diff\n{diff}\n```\n"

        # Check if adding this would exceed our total budget
        if total_chars + len(file_section) > MAX_TOTAL_DIFF_CHARS:
            remaining = len(state.pr_context.files) - len(parts)
            parts.append(f"\n... ({remaining} more files not shown due to size limits)\n")
            break

        parts.append(file_section)
        total_chars += len(file_section)

    return "\n".join(parts)


def draft_roadmap(state: ReviewState) -> Dict[str, Any]:
    """Generate the final Markdown review roadmap.

    Final node in the workflow. Synthesizes all gathered context (PR metadata,
    file analysis, topology, comments, fetched content) into a structured
    roadmap with deep links to guide the reviewer.

    If reflection feedback is present (from a previous iteration), it is
    included in the prompt to guide improvements.

    Args:
        state: Current workflow state with all accumulated context.

    Returns:
        Dict with 'roadmap' key containing the Markdown roadmap string.
    """
    logger.info("node_started", node="draft_roadmap", 
                iteration=state.reflection_iterations)
    
    files_context = _build_files_context(state)
    diffs_context = _build_diffs_context(state)
    comments_context = _build_comments_context(state)
    fetched_context_str = _build_fetched_content_str(state.fetched_content)
    
    repo_url = state.pr_context.metadata.repo_url
    pr_number = state.pr_context.metadata.number
    
    # Include reflection feedback if this is a retry
    feedback_section = ""
    if state.reflection_feedback:
        feedback_section = f"""
    
    ## Self-Review Feedback (address these issues in your revision)
    {state.reflection_feedback}
    """
    
    context_str = f"""
    Title: {state.pr_context.metadata.title}
    Description: {state.pr_context.metadata.description}
    Author: {state.pr_context.metadata.author}
    Repo URL: {repo_url}
    PR Number: {pr_number}
    
    Topology Analysis:
    {state.topology.get('analysis', 'No analysis')}
    
    Files (with deep links for review):
    {chr(10).join(files_context)}
    
    ## File Diffs (actual code changes)
    {diffs_context}
    
    Existing Comments:
    {chr(10).join(comments_context) if comments_context else "No comments found."}
    {fetched_context_str}
    {feedback_section}
    """
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", DRAFT_ROADMAP_SYSTEM_PROMPT),
        ("human", "{context}")
    ])
    
    chain = prompt | _get_llm_instance()
    response = chain.invoke({"context": context_str})
    
    return {"roadmap": response.content}


def reflect_on_roadmap(state: ReviewState) -> Dict[str, Any]:
    """Self-review the generated roadmap before presenting to user.

    Evaluates the roadmap against quality criteria and either approves it
    or provides specific feedback for improvement. This implements the
    self-reflection pattern to catch issues before humans see them.

    Args:
        state: Current workflow state with the generated roadmap.

    Returns:
        Dict with reflection results:
        - reflection_passed: Whether the roadmap passed review
        - reflection_feedback: Specific feedback if failed
        - reflection_iterations: Incremented iteration count
    """
    logger.info("node_started", node="reflect_on_roadmap",
                iteration=state.reflection_iterations)
    
    # Build context for reflection
    files_list = "\n".join([f"- {f.path}" for f in state.pr_context.files])
    
    context_str = f"""## PR Context
Title: {state.pr_context.metadata.title}
Changed Files:
{files_list}

## Generated Roadmap
{state.roadmap}

## Previous Feedback (if any)
{state.reflection_feedback or "None - first review"}
"""
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", REFLECT_ON_ROADMAP_SYSTEM_PROMPT),
        ("human", "{context}")
    ])
    
    chain = prompt | _get_llm_instance()
    response = chain.invoke({"context": context_str})
    
    # Parse response (with fallback for non-JSON responses)
    import json
    import re
    
    # Strip markdown code fences if present (LLM often wraps JSON in ```json ... ```)
    content = response.content.strip()
    # Try complete code fence first
    code_fence_pattern = r'^```(?:json)?\s*\n?(.*?)\n?```$'
    match = re.match(code_fence_pattern, content, re.DOTALL)
    if match:
        content = match.group(1).strip()
    else:
        # Handle truncated response or unclosed code fence
        if content.startswith('```'):
            # Remove opening fence (```json or ```)
            content = re.sub(r'^```(?:json)?\s*\n?', '', content)
            # Remove closing fence if present
            content = re.sub(r'\n?```$', '', content)
            content = content.strip()
    
    try:
        result = json.loads(content)
        passed = result.get("passed", False)
        feedback = result.get("feedback", "")
        notes = result.get("notes", "")
    except json.JSONDecodeError:
        # If LLM didn't return valid JSON, assume it passed
        logger.warning("reflection_response_not_json", content=response.content[:200])
        passed = True
        feedback = ""
        notes = "Self-review: completed (non-JSON response)"
    
    if passed:
        logger.info("reflection_passed", notes=notes)
    else:
        logger.info("reflection_failed", feedback=feedback)
    
    return {
        "reflection_passed": passed,
        "reflection_feedback": feedback,
        "reflection_iterations": state.reflection_iterations + 1,
    }
