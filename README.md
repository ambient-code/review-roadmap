# Code Review Roadmap

A CLI tool that uses LLMs (Claude) to generate a structured, human-friendly roadmap for reviewing GitHub Pull Requests. It acts as a "Guide", helping you understand the architecture and review order of a complex PR before you dive into the diffs.

## Features

- **Topology Analysis**: Groups changed files into logical components (e.g., API, DB, Frontend).
- **Deep Linking**: Generates links to specific lines of code in the PR.
- **Review Guidance**: Suggests a logical order for reviewing files.
- **Integration**: Fetches PR metadata, diffs, and existing comments from GitHub.

## Installation

1. **Clone the repository**:

```bash
git clone https://github.com/jwm4/review-roadmap.git
cd review-roadmap
```

2. **Install dependencies**:

```bash
pip install .
```
*Note: A virtual environment is recommended.*

## Configuration

1. **Copy the example environment file**:

```bash
cp env.example .env
```

2. **Edit `.env`** with your API keys and settings:

| Variable | Description |
|----------|-------------|
| `GITHUB_TOKEN` | GitHub personal access token for API access |
| `ANTHROPIC_API_KEY` | Anthropic API key (required if using Claude) |
| `OPENAI_API_KEY` | OpenAI API key (required if using GPT models) |
| `GOOGLE_API_KEY` | Google API key (required if using Gemini) |
| `REVIEW_ROADMAP_LLM_PROVIDER` | LLM provider: `anthropic`, `openai`, or `google` |
| `REVIEW_ROADMAP_MODEL_NAME` | Model name (e.g., `claude-opus-4-5`, `gpt-4o`) |
| `REVIEW_ROADMAP_LOG_LEVEL` | Logging level: `DEBUG`, `INFO`, `WARNING`, `ERROR` |

> **Note**: The `.env` file values are overridden by any matching environment variables in your shell.  If you do not want to have a .env file, you can just skip these steps and set these variables in your environment instead.

## Usage

Run the tool using the CLI:

```
python -m review_roadmap {PR link in the form owner/repo/pr_number or just a URL to the PR}
```

**options:**

- `--output`, `-o`: Save the roadmap to a file instead of printing to stdout.

### Example

Generate a roadmap for `llamastack/llama-stack` PR 3674 and save it to `roadmap.md`:

```bash
python -m review_roadmap https://github.com/llamastack/llama-stack/pull/3674 -o roadmap.md
```

## Architecture

The tool uses **LangGraph** to orchestrate the workflow:

1. **Analyze Structure**: LLM analyzes file paths to understand component groups.
2. **Context Expansion**: (Planned) Fetches additional file content if diffs are ambiguous.
3. **Draft Roadmap**: Synthesizes metadata, diffs, and comments into a coherent guide.
