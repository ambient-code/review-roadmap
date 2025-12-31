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
    """Create Anthropic model via Google Vertex AI."""
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
    """Create and return the configured LLM instance."""
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


llm = get_llm()

from review_roadmap.agent.prompts import (
    ANALYZE_STRUCTURE_SYSTEM_PROMPT,
    CONTEXT_EXPANSION_SYSTEM_PROMPT,
    DRAFT_ROADMAP_SYSTEM_PROMPT,
)
from review_roadmap.agent.tools import read_file


def analyze_structure(state: ReviewState) -> Dict[str, Any]:
    """Groups files into logical components."""
    logger.info("node_started", node="analyze_structure")
    
    files_list = "\n".join([
        f"- {f.path} ({f.status}, +{f.additions}/-{f.deletions})"
        for f in state.pr_context.files
    ])
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", ANALYZE_STRUCTURE_SYSTEM_PROMPT),
        ("human", "PR Title: {title}\n\nFiles:\n{files}")
    ])
    
    chain = prompt | llm
    response = chain.invoke({
        "title": state.pr_context.metadata.title,
        "files": files_list
    })
    
    return {"topology": {"analysis": response.content}}


def _parse_repo_info(repo_url: str) -> Tuple[str, str]:
    """Extract owner and repo name from a GitHub repo URL."""
    parts = repo_url.rstrip("/").split("/")
    return parts[-2], parts[-1]  # owner, repo


def _fetch_tool_call_content(
    tool_calls: List[Dict[str, Any]],
    client: GitHubClient,
    owner: str,
    repo: str,
    sha: str
) -> Dict[str, str]:
    """Fetch file content for each read_file tool call."""
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
    """Decides if we need to fetch more content."""
    logger.info("node_started", node="context_expansion")
    
    model_with_tools = llm.bind_tools([read_file])
    
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
    """Build file context strings with PR diff links."""
    repo_url = state.pr_context.metadata.repo_url
    pr_number = state.pr_context.metadata.number
    return [
        f"- {f.path} ({f.status}): {f.get_pr_diff_link(repo_url, pr_number)}"
        for f in state.pr_context.files
    ]


def _build_comments_context(state: ReviewState) -> List[str]:
    """Build comment context strings."""
    comments_context = []
    for c in state.pr_context.comments:
        location = f"({c.path}:{c.line})" if c.path else "(General)"
        comments_context.append(f"- {c.user} {location}: {c.body}")
    return comments_context


def _build_fetched_content_str(fetched_content: Dict[str, str]) -> str:
    """Build fetched content string with truncation."""
    if not fetched_content:
        return ""
    
    parts = ["\n\nfetched_content:\n"]
    for path, content in fetched_content.items():
        preview = content[:2000] + ("\n... (truncated)" if len(content) > 2000 else "")
        parts.append(f"\n--- File: {path} ---\n{preview}\n")
    return "".join(parts)


def draft_roadmap(state: ReviewState) -> Dict[str, Any]:
    """Generates the final Markdown roadmap."""
    logger.info("node_started", node="draft_roadmap")
    
    files_context = _build_files_context(state)
    comments_context = _build_comments_context(state)
    fetched_context_str = _build_fetched_content_str(state.fetched_content)
    
    repo_url = state.pr_context.metadata.repo_url
    pr_number = state.pr_context.metadata.number
    
    context_str = f"""
    Title: {state.pr_context.metadata.title}
    Description: {state.pr_context.metadata.description}
    Author: {state.pr_context.metadata.author}
    Repo URL: {repo_url}
    PR Number: {pr_number}
    
    Topology Analysis:
    {state.topology.get('analysis', 'No analysis')}
    
    Files (with base links):
    {chr(10).join(files_context)}
    
    Existing Comments:
    {chr(10).join(comments_context) if comments_context else "No comments found."}
    {fetched_context_str}
    """
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", DRAFT_ROADMAP_SYSTEM_PROMPT),
        ("human", "{context}")
    ])
    
    chain = prompt | llm
    response = chain.invoke({"context": context_str})
    
    return {"roadmap": response.content}
