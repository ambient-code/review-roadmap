# Phase 3 Design: LangGraph Logic & Tools

## Core Philosophy
The agent acts as a **Guide**, not a Reviewer. It aggregates context to tell the human *where to look* and *in what order*, rather than telling them *what is wrong*.

## Data Sources
The agent will have access to the following data, injected into the context window or accessible via tools:
1.  **PR Metadata**: Title, Description, Author, Branch names.
2.  **File Manifest**: List of all changed files + stats (additions/deletions).
3.  **File Diffs**: The unified diffs (patches) for the changed files.
    *   *Constraint*: Large diffs may be truncated.
4.  **Review Comments**: Existing comments on the PR/Issue to avoid redundant "discoveries" and understand ongoing discussions.
5.  **File Content**: The *full* content of specific files (retrieved on-demand via tool).

## Agent Tools
We will provide the model with a **read-only** toolset to fetch more context if the diff is insufficient.

### `read_file_content(path: str, start_line: int, end_line: int)`
- **Purpose**: Allows the agent to see the code *surrounding* a change to understand the broader impact.
- **Implementation**: Fetches the blob from GitHub using the `head_sha`.
- **Usage**: The agent might decide "I see a change in `auth.py`, I need to read the class definition to understand the inheritance."

## LangGraph Workflow
The "State" object will pass through these nodes:

### 1. `Node: Structure Analysis`
- **Input**: List of changed files, PR Title/Desc.
- **Goal**: Group files into logical clusters (e.g., "API Layer", "Database Schema", "Frontend").
- **Output**: A structured `Topology` object (JSON) inside the state.

### 2. `Node: Context Expansion` (Iterative / Optional)
- **Input**: The `Topology` + High-risk diffs + **Existing Comments**.
- **Action**: The model *decides* if it needs more info.
- **Tool Call**: `read_file_content` for critical files where the diff is ambiguous.
- **Loop**: Can loop 1-2 times to gather context.

### 3. `Node: Roadmap Generation`
- **Input**: Full Context + Topology + Extra Fetched Content + Comments.
- **Goal**: Write the final Markdown.
- **Behavior**:
    1.  **Summary**: One paragraph explaining the "Big Picture".
    2.  **Walkthrough**: Ordered list of files to review.
    3.  **Key Checkpoints**: Specific line numbers to check (using the generated deep links).
    4.  **Discussion Highlights**: Mention active discussions or resolved threads from the comments.
    5.  **Tests**: Report on what tests were added/modified.

## Prompting Strategy
- **System Prompt**: "You are a Senior Staff Engineer preparing a handover for a code review. You do not judge the code, you explain the *map* of the changes."
- **Context Management**: We must carefully manage token limits. If the PR is huge, we process files in batches or summaries.
