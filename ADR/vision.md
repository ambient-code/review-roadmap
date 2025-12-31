# Code Review Roadmap Vision

I am trying to build a system that can provide a roadmap for a person to follow to review a pull request in GitHub. It should not try to do its own review -- I already have plenty of tools for automated reviews. What I want is something that will guide a human through the review process in a way that is efficient and effective.

## Core Features

- **Input**: A user can point the tool at a pull request in GitHub (e.g., via URL or `owner/repo/pr` format).
- **Analysis**: The tool will analyze the PR context (diffs, commit messages, file dependencies, and test results).
- **Output**: A **Markdown Roadmap** that guides the reviewer.
    - **Logical Flow**: The summary should be presented in an order that follows the code's execution flow or logical architecture, rather than alphabetical order.
    - **Deep Links**: The roadmap should contain links to specific lines of code in the PR.
    - **Reviewer Hints**: Comments about specific concerns (e.g., "Check this regex for ReDoS", "Verify this DB migration rollback").
    - **Test Context**: If tests are present, summarize their coverage and results. Prioritize showing tests if they explain the functionality well.
- **Non-Invasive**: The tool must **not** post to GitHub automatically or approve/reject PRs. It produces a guide for the human.

## Technical Architecture

- **Framework**: **LangGraph**
    - **Reasoning**: We need a structured, deterministic workflow (`Fetch -> Analyze -> Plan -> Write`), not an open-ended agent. LangGraph provides the state machine control required.
- **Model Layer**:
    - **Default**: Claude 4.5/3.5 Sonnet (optimized for coding tasks).
    - **Configurable**: User must be able to switch models and provide credentials (e.g., via `.env` or config file).
- **Interface**:
    - **Initial**: Command Line Interface (CLI).
    - **Future**: GitHub Action (out of scope for v1).

## Workflow Steps (Conceptual)

1.  **Ingest**: Fetch PR metadata, diffs, and check statuses from GitHub API.
2.  **Structural Analysis**: Identify key entry points and modified components.
3.  **Risk Assessment**: Scan for critical changes (auth, database, external APIs).
4.  **Roadmap Generation**: detailed Markdown report generation using the LLM.

## Constraints & Considerations

- **Security**: Code will be sent to the configured LLM provider. Users must provide their own API keys.
- **Context Window**: Large PRs may require chunking or map-reduce strategies (to be handled by the logic).