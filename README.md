# Code Review Roadmap

A CLI tool that uses LLMs (Claude) to generate a structured, human-friendly roadmap for reviewing GitHub Pull Requests. It acts as a "Guide", helping you understand the architecture and review order of a complex PR before you dive into the diffs.

## Features

-   **Topology Analysis**: Groups changed files into logical components (e.g., API, DB, Frontend).
-   **Deep Linking**: Generates links to specific lines of code in the PR.
-   **Review Guidance**: Suggests a logical order for reviewing files.
-   **Integration**: Fetches PR metadata, diffs, and existing comments from GitHub.

## Installation

1.  **Clone the repository**:
    ```bash
    git clone https://github.com/jwm4/review-roadmap.git
    cd review-roadmap
    ```

2.  **Install dependencies**:
    ```bash
    pip install .
    ```
    *Note: A virtual environment is recommended.*

## Configuration

1.  **Copy the example environment file**:
    ```bash
    cp env.example .env
    ```

2.  **Edit `.env`** with your API keys and Model Selection:

    ```properties
    # GitHub Token
    GITHUB_TOKEN=ghp_...

    # LLM Settings
    LLM_PROVIDER=anthropic  # Options: anthropic, openai, google
    MODEL_NAME=claude-3-5-sonnet-20240620  # Or any other model ID

    # API Keys (Set the one relevant to your provider)
    ANTHROPIC_API_KEY=sk-ant-...
    OPENAI_API_KEY=sk-...
    ```

## Usage

Run the tool using the CLI:

```bash
python -m src.main owner/repo/pr_number
```

**options:**
-   `--output`, `-o`: Save the roadmap to a file instead of printing to stdout.

### Example

Generate a roadmap for `llamastack/llama-stack` PR 3674 and save it to `roadmap.md`:

```bash
python -m src.main https://github.com/llamastack/llama-stack/pull/3674 -o roadmap.md
```

## Architecture

The tool uses **LangGraph** to orchestrate the workflow:
1.  **Analyze Structure**: LLM analyzes file paths to understand component groups.
2.  **Context Expansion**: (Planned) Fetches additional file content if diffs are ambiguous.
3.  **Draft Roadmap**: Synthesizes metadata, diffs, and comments into a coherent guide.
