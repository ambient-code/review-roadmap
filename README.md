# Review Roadmap

A CLI tool that uses LLMs (Claude) to generate a structured, human-friendly roadmap for reviewing GitHub Pull Requests. It acts as a guide, helping you understand the architecture and review order of a complex PR before you dive into the diffs.

## Features

- **Topology Analysis**: Groups changed files into logical components (e.g., API, DB, Frontend).
- **Deep Linking**: Generates links to specific lines of code in the PR.
- **Review Guidance**: Suggests a logical order for reviewing files.
- **Self-Reflection**: Reviews its own output before presenting, catching issues and improving quality.
- **Integration**: Fetches PR metadata, diffs, and existing comments from GitHub.

## Installation

1. **Clone the repository**:

```bash
git clone https://github.com/ambient-code/review-roadmap.git
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
| `GITHUB_TOKEN` | GitHub personal access token for API access ([see below](#github-token-setup)) |
| `ANTHROPIC_API_KEY` | Anthropic API key (required if provider is `anthropic`) |
| `OPENAI_API_KEY` | OpenAI API key (required if provider is `openai`) |
| `GOOGLE_API_KEY` | Google API key (required if provider is `google`) |
| `REVIEW_ROADMAP_LLM_PROVIDER` | LLM provider: `anthropic`, `anthropic-vertex`, `openai`, or `google` |
| `REVIEW_ROADMAP_MODEL_NAME` | Model name (e.g., `claude-opus-4-5`, `gpt-4o`) |
| `REVIEW_ROADMAP_LOG_LEVEL` | Logging level: `DEBUG`, `INFO`, `WARNING`, `ERROR` |
| `ANTHROPIC_VERTEX_PROJECT_ID` | GCP project ID (required if provider is `anthropic-vertex`) |
| `ANTHROPIC_VERTEX_REGION` | GCP region (optional, defaults to `us-east5`) |
| `GOOGLE_APPLICATION_CREDENTIALS` | Path to GCP credentials JSON (optional, defaults to `~/.config/gcloud/application_default_credentials.json`) |

> **Note**: The `.env` file values are overridden by any matching environment variables in your shell.  If you do not want to have a .env file, you can just skip these steps and set these variables in your environment instead.

### GitHub Token Setup

A GitHub personal access token (PAT) is required to fetch PR data. The type of token and permissions needed depend on your use case:

#### Read-Only Access (default)

For generating roadmaps without posting comments, a token with **read access to repositories** is sufficient.

#### Write Access (for `--post` flag)

To post roadmaps as PR comments using the `--post` flag, your token needs **write access**. The specific requirements differ by token type:

| Token Type | Required Permissions |
|------------|---------------------|
| **Fine-grained PAT** | Repository access → Pull requests: **Read and write** |
| **Classic PAT** | `repo` scope (full repo access) or `public_repo` (public repos only) |

#### Creating a Fine-Grained Personal Access Token (Recommended)

Fine-grained tokens are more secure because they limit access to specific repositories.

1. Go to [GitHub Settings → Developer settings → Personal access tokens → Fine-grained tokens](https://github.com/settings/tokens?type=beta)
2. Click **"Generate new token"**
3. Configure the token:
   - **Token name**: e.g., `review-roadmap`
   - **Expiration**: Choose an appropriate duration
   - **Repository access**: Select "Only select repositories" and choose the repos you want to analyze
   - **Permissions**:
     - **Pull requests**: Read-only (for basic usage) or Read and write (for `--post`)
     - **Contents**: Read-only (required to fetch file contents for context expansion)
4. Click **"Generate token"** and copy the token value

#### Creating a Classic Personal Access Token

Classic tokens are simpler but grant broader access.

1. Go to [GitHub Settings → Developer settings → Personal access tokens → Tokens (classic)](https://github.com/settings/tokens)
2. Click **"Generate new token"** → **"Generate new token (classic)"**
3. Configure the token:
   - **Note**: e.g., `review-roadmap`
   - **Expiration**: Choose an appropriate duration
   - **Scopes**:
     - `repo` — Full access (works for both public and private repos)
     - Or `public_repo` — Only for public repositories
4. Click **"Generate token"** and copy the token value

#### Important: Token Scopes vs. User Permissions

Even if you have collaborator access to a repository, your token must also have the correct **OAuth scopes** to perform write operations. A common mistake is using a token with read-only scopes while expecting write access to work based on your user permissions. The tool checks both your repository permissions and your token's scopes before attempting to post comments.

## Usage

Run the tool using the CLI:

```bash
review_roadmap {PR link in the form owner/repo/pr_number or just a URL to the PR}
```

> **Note:** After installation with `pip install .`, the `review_roadmap` command is available in your PATH. You can also run it as `python -m review_roadmap` if preferred.

**Options:**

| Option | Description |
|--------|-------------|
| `--output`, `-o` | Save the roadmap to a file instead of printing to stdout |
| `--post`, `-p` | Post the roadmap as a comment directly on the PR |
| `--no-reflection` | Skip the self-reflection step for faster results |

You can use both `-o` and `-p` together—the roadmap will be generated once and saved to both the file and the PR comment.

> **Note:** The `--post` flag requires a token with write access. See [GitHub Token Setup](#github-token-setup) for details.

### Examples

Generate a roadmap for `llamastack/llama-stack` PR 3674 and save it to `roadmap.md`:

```bash
review_roadmap https://github.com/llamastack/llama-stack/pull/3674 -o roadmap.md
```

Post the roadmap directly as a comment on the PR:

```bash
review_roadmap https://github.com/llamastack/llama-stack/pull/3674 --post
```

Generate and both save to file and post to PR:

```bash
review_roadmap https://github.com/llamastack/llama-stack/pull/3674 -o roadmap.md -p
```

Generate quickly without self-reflection (faster but may have lower quality):

```bash
review_roadmap https://github.com/llamastack/llama-stack/pull/3674 --no-reflection
```

## Development

```bash
# Install in development mode
pip install -e .

# Run tests
pytest

# Run tests with verbose output
pytest -v
```

## Architecture

The tool uses **LangGraph** to orchestrate the workflow:

1. **Analyze Structure**: LLM analyzes file paths to understand component groups.
2. **Context Expansion**: Fetches additional file content if diffs are ambiguous.
3. **Draft Roadmap**: Synthesizes metadata, diffs, and comments into a coherent guide.
4. **Self-Reflection**: Reviews the generated roadmap for completeness and accuracy, retrying if needed.

The self-reflection step implements the [self-review pattern](https://github.com/jeremyeder/reference/blob/main/docs/patterns/self-review-reflection.md), where the agent evaluates its own output before presenting it to users. This catches issues like missing files, generic advice, or unclear reasoning—improving quality without manual review.
