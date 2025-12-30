from langchain_anthropic import ChatAnthropic
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.prompts import ChatPromptTemplate
from review_roadmap.agent.state import ReviewState
from review_roadmap.config import settings
from review_roadmap.github.client import GitHubClient

from langchain_openai import ChatOpenAI
from langchain_google_genai import ChatGoogleGenerativeAI

def get_llm():
    provider = settings.REVIEW_ROADMAP_LLM_PROVIDER.lower()
    
    if provider == "anthropic":
        return ChatAnthropic(
            model_name=settings.REVIEW_ROADMAP_MODEL_NAME,
            api_key=settings.ANTHROPIC_API_KEY
        )
    elif provider == "openai":
        return ChatOpenAI(
            model_name=settings.REVIEW_ROADMAP_MODEL_NAME,
            api_key=settings.OPENAI_API_KEY
        )
    elif provider == "google":
        return ChatGoogleGenerativeAI(
            model=settings.REVIEW_ROADMAP_MODEL_NAME,
            google_api_key=settings.GOOGLE_API_KEY
        )
    else:
        raise ValueError(f"Unsupported LLM provider: {provider}")

llm = get_llm()

from review_roadmap.agent.prompts import ANALYZE_STRUCTURE_SYSTEM_PROMPT, DRAFT_ROADMAP_SYSTEM_PROMPT, CONTEXT_EXPANSION_SYSTEM_PROMPT
from review_roadmap.agent.tools import read_file

def analyze_structure(state: ReviewState) -> dict:
    """Groups files into logical components."""
    print("--- Node: Analyze Structure ---")
    
    files_list = "\n".join([f"- {f.path} ({f.status}, +{f.additions}/-{f.deletions})" for f in state.pr_context.files])
    
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

def context_expansion(state: ReviewState) -> dict:
    """Decides if we need to fetch more content."""
    print("--- Node: Context Expansion ---")
    
    # 1. Bind Tools
    tools = [read_file]
    model_with_tools = llm.bind_tools(tools)
    
    # 2. Build Context
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
    
    # 3. Handle Tool Calls
    fetched_content = {}
    
    if hasattr(response, "tool_calls") and response.tool_calls:
        print(f"--- Fetching {len(response.tool_calls)} files ---")
        client = GitHubClient()
        owner = state.pr_context.metadata.repo_url.split("/")[-4] # https://github.com/owner/repo
        repo = state.pr_context.metadata.repo_url.split("/")[-3] # Or parse properly
        # Better: parse from repo_url properly or pass in state.
        # Quick parse for now, robust enough for standard URLs
        
        # Actually, GitHubClient.get_pr_context doesn't return owner/repo explicitly in metadata,
        # but we can derive it or assume it's the same as the PR URL.
        # Let's parse carefully.
        # repo_url example: https://github.com/jwm4/platform
        parts = state.pr_context.metadata.repo_url.rstrip("/").split("/")
        repo = parts[-1]
        owner = parts[-2]
        sha = state.pr_context.metadata.head_commit_sha
        
        for tool_call in response.tool_calls:
            if tool_call["name"] == "read_file":
                path = tool_call["args"].get("path")
                if path:
                    print(f"Fetching: {path}")
                    try:
                        content = client.get_file_content(owner, repo, path, sha)
                        fetched_content[path] = content
                    except Exception as e:
                        print(f"Error fetching {path}: {e}")
                        fetched_content[path] = f"Error fetching content: {str(e)}"

    return {"fetched_content": fetched_content}

def draft_roadmap(state: ReviewState) -> dict:
    """Generates the final Markdown roadmap."""
    print("--- Node: Draft Roadmap ---")
    
    # Prepare File Context with Base Links
    files_context = []
    repo_url = state.pr_context.metadata.repo_url
    pr_number = state.pr_context.metadata.number
    
    for f in state.pr_context.files:
        file_link = f.get_pr_diff_link(repo_url, pr_number)
        files_context.append(f"- {f.path} ({f.status}): {file_link}")

    # Prepare Comments Context
    comments_context = []
    for c in state.pr_context.comments:
        location = f"({c.path}:{c.line})" if c.path else "(General)"
        comments_context.append(f"- {c.user} {location}: {c.body}")
        
    # Prepare Fetched Content Context
    fetched_context_str = ""
    if state.fetched_content:
        fetched_context_str = "\n\nfetched_content:\n"
        for path, content in state.fetched_content.items():
            # Truncate if too long? 
            # For now, simplistic truncation to 2000 chars to avoid blowing context
            preview = content[:2000] + ("\n... (truncated)" if len(content) > 2000 else "")
            fetched_context_str += f"\n--- File: {path} ---\n{preview}\n"
    
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
