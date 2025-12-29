# Framework Analysis for Code Review Roadmap

## Core Requirements (from vision.md)
- **Goal**: Generate a markdown roadmap for a PR review.
- **Nature of Task**: Structured workflow (Analyze -> Summarize -> Link -> Report).
- **Interface**: CLI initially, potentially GitHub Action later.
- **Model**: Large Language Model (e.g., Claude 3.5/4.5 Sonnet).
- **Key Constraint**: Maximum control over the reasoning steps; avoid "black box" agent autonomy that tries to "solve" the PR.

## Framework Options

### 1. LangGraph (Recommended)
**Verdict**: **Best Fit**

*   **Why**: LangGraph specializes in defining explicit **state machines** and **workflows**.
*   **Fit for Roadmap**: Generating a roadmap is a sequential or DAG (Directed Acyclic Graph) process:
    1.  `FetchContext` (PR diff, files, tests)
    2.  `AnalyzeSafety` (Security scan)
    3.  `AnalyzeLogic` (Code flow)
    4.  `SynthesizeReport` (Markdown generation)
*   **Pros**:
    *   **Control**: You define exactly what data is passed between steps. You can force "Human-in-the-loop" states easily if needed.
    *   **Observability**: Steps are clearly separated, making debugging the "reasoning" easier than a single prompt.
    *   **Flexibility**: Can easily evolve from a linear chain to a cyclic agent (e.g., "This file reference is unclear, go read that file") only if/when you want to.
*   **Cons**: slightly more boilerplate than a simple script.

### 2. DeepAgents (LangChain AI)
**Verdict**: **Likely Overkill / Too Opinionated**

*   **What**: A "Batteries Included" agent runtime with built-in efficient file systems, planning steps, and "sub-agent" delegation.
*   **Fit for Roadmap**: DeepAgents is designed for **autonomous problem solving** (e.g., "Build this feature", "Fix this bug").
*   **Pros**: very powerful for coding tasks where the agent needs to explore the file system extensively.
*   **Cons**:
    *   **Too much autonomy**: You explicitly stated you *don't* want it to make automated decisions or approval. DeepAgents defaults to a "Goal -> Plan -> Execute" loop which might be hard to constrain to just "Observation".
    *   **Complexity**: Adds significant weight (virtual file systems, etc.) that might not be needed for a read-only review roadmap.

### 3. PydanticAI / Agno (formerly Phidata)
**Verdict**: **Strong Alternative for Simplicity**

*   **What**: Lightweight frameworks focused on **Type-Safe** tool usage and structured responses.
*   **Fit for Roadmap**: If the logic is mostly "Call LLM with tools -> get structured JSON roadmap -> render Markdown", this is superior to LangChain in developer experience (DX).
*   **Pros**:
    *   **Simplicity**: Pure Python, very little "framework magic".
    *   **Validation**: Guarantees the output structure (e.g., list of file links, summary text) validates against a schema before generating the implementation.
*   **Cons**: Less built-in support for complex "Graph" logic if the workflow gets complicated later (though you can just write Python functions).

## Recommendation

**Stick with LangGraph.**

The "Code Review Roadmap" is a classic **workflow** problem. You want to enforce a specific "Chain of Thought" structure:
1.  Read PR.
2.  Think about high-level flow.
3.  Think about security.
4.  Write output.

LangGraph allows you to hard-code this skeleton while letting the LLM fill in the content. "Agentic" frameworks (DeepAgents, etc.) introduce loops and planners that are often non-deterministic and hard to debug for a deterministic output product like a Roadmap.
