# AGENTS.md — Project Guide for AI Assistants

## Project Overview

A CLI tool that uses LLMs (Claude, GPT, Gemini) to generate structured, human-friendly roadmaps for reviewing GitHub Pull Requests. It analyzes PR diffs and metadata, then synthesizes a review guide with logical file ordering and deep links.

- **Tech Stack:** Python 3.10+, LangGraph, LangChain, Pydantic, Typer, httpx
- **LLM Providers:** Anthropic (direct + Vertex AI), OpenAI, Google
- **Structure:**
  - `review_roadmap/` — Main application code
  - `review_roadmap/agent/` — LangGraph workflow (nodes, state, prompts)
  - `review_roadmap/github/` — GitHub API client
  - `tests/` — pytest test suite

## Critical Commands

> Agents should run these to verify changes.

- **Install:** `pip install .` (uses `pyproject.toml`, no requirements.txt)
- **Test:** `pytest`
- **Run:** `python -m review_roadmap <owner/repo/pr_number>`

## Coding Preferences

- **Style:** Use type hints for all function signatures and class attributes.
- **Data Models:** Use Pydantic `BaseModel` for all structured data (see `models.py`).
- **Config:** Use `pydantic-settings` for configuration (see `config.py`).
- **Testing:** Write `pytest` functions, not `unittest` classes. Use `respx` for mocking HTTP requests.
- **HTTP:** Use `httpx` for HTTP clients (sync), not `requests`.
- **CLI:** Use `typer` for command-line interfaces with `rich` for output formatting.
- **Patterns:** Keep functions focused and under ~40 lines. Prefer composition over inheritance.

## Architecture Notes

- **LangGraph Workflow:** The agent uses LangGraph to orchestrate multi-step analysis:
  1. Analyze file structure → group into logical components
  2. (Planned) Expand context by fetching additional file content
  3. Draft the final roadmap using all gathered context
- **State Management:** See `review_roadmap/agent/state.py` for the `ReviewState` model that flows through the graph.
- **Prompts:** LLM prompts are centralized in `review_roadmap/agent/prompts.py`.

## Guidelines & Rules

- **Never** delete `.env` files or `env.example`.
- **Never** hardcode API keys — all secrets go through environment variables.
- **Always** run `pytest` after modifying logic in `review_roadmap/`.
- **Always** update `env.example` when adding new environment variables.
- **Ask** before adding new heavy dependencies (especially LLM providers or frameworks).
- **Commits:** Use [Conventional Commits](https://www.conventionalcommits.org/) (e.g., `feat:`, `fix:`, `docs:`).

## Environment Variables

Required variables are documented in `env.example`. Key ones:

| Variable | Purpose |
|----------|---------|
| `GITHUB_TOKEN` | GitHub API access (read for fetching PRs, write for posting comments) |
| `REVIEW_ROADMAP_LLM_PROVIDER` | Provider selection: `anthropic`, `anthropic-vertex`, `openai`, `google` |
| `REVIEW_ROADMAP_MODEL_NAME` | Model name (e.g., `claude-opus-4-5`, `gpt-4o`) |
| `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` / `GOOGLE_API_KEY` | Provider-specific API keys |

