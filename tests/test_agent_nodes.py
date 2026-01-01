"""Tests for the agent node functions and helpers."""

import pytest
from unittest.mock import MagicMock, patch
from review_roadmap.agent.state import ReviewState
from review_roadmap.models import PRContext


class TestHelperFunctions:
    """Tests for helper functions that don't require LLM mocking."""

    def test_parse_repo_info(self):
        """Test extracting owner and repo from GitHub URL."""
        from review_roadmap.agent.nodes import _parse_repo_info

        owner, repo = _parse_repo_info("https://github.com/owner/repo")
        assert owner == "owner"
        assert repo == "repo"

        # With trailing slash
        owner, repo = _parse_repo_info("https://github.com/my-org/my-repo/")
        assert owner == "my-org"
        assert repo == "my-repo"

    def test_build_files_context(self, sample_review_state: ReviewState):
        """Test building file context strings with PR diff links."""
        from review_roadmap.agent.nodes import _build_files_context

        result = _build_files_context(sample_review_state)

        assert len(result) == 3
        assert "src/main.py" in result[0]
        assert "modified" in result[0]
        assert "https://github.com/owner/repo/pull/42/files#diff-" in result[0]

    def test_build_comments_context(self, sample_review_state: ReviewState):
        """Test building comment context strings."""
        from review_roadmap.agent.nodes import _build_comments_context

        result = _build_comments_context(sample_review_state)

        assert len(result) == 2
        # General comment
        assert "reviewer1" in result[0]
        assert "(General)" in result[0]
        assert "Looks good to me!" in result[0]
        # Inline comment
        assert "reviewer2" in result[1]
        assert "(src/main.py:15)" in result[1]
        assert "docstring" in result[1]

    def test_build_comments_context_empty(self, sample_pr_context: PRContext):
        """Test building comment context with no comments."""
        from review_roadmap.agent.nodes import _build_comments_context

        state = ReviewState(
            pr_context=PRContext(
                metadata=sample_pr_context.metadata,
                files=sample_pr_context.files,
                comments=[],
            )
        )
        result = _build_comments_context(state)
        assert result == []

    def test_build_fetched_content_str_empty(self):
        """Test building fetched content string when empty."""
        from review_roadmap.agent.nodes import _build_fetched_content_str

        result = _build_fetched_content_str({})
        assert result == ""

    def test_build_fetched_content_str_with_content(self):
        """Test building fetched content string with files."""
        from review_roadmap.agent.nodes import _build_fetched_content_str

        content = {
            "src/main.py": "def main():\n    pass",
            "src/utils.py": "def helper():\n    return True",
        }
        result = _build_fetched_content_str(content)

        assert "fetched_content:" in result
        assert "--- File: src/main.py ---" in result
        assert "def main():" in result
        assert "--- File: src/utils.py ---" in result

    def test_build_fetched_content_str_truncation(self):
        """Test that large files are truncated."""
        from review_roadmap.agent.nodes import _build_fetched_content_str

        # Create content longer than 2000 chars
        long_content = "x" * 3000
        content = {"large_file.py": long_content}
        result = _build_fetched_content_str(content)

        assert "... (truncated)" in result
        # Should only include first 2000 chars + truncation message
        assert len(result) < 3000 + 100  # Some buffer for formatting


class TestFetchToolCallContent:
    """Tests for _fetch_tool_call_content helper."""

    def test_fetch_tool_call_content_success(self):
        """Test fetching content for read_file tool calls."""
        from review_roadmap.agent.nodes import _fetch_tool_call_content

        mock_client = MagicMock()
        mock_client.get_file_content.return_value = "file content here"

        tool_calls = [
            {"name": "read_file", "args": {"path": "src/main.py"}},
            {"name": "read_file", "args": {"path": "src/utils.py"}},
        ]

        result = _fetch_tool_call_content(
            tool_calls, mock_client, "owner", "repo", "abc123"
        )

        assert len(result) == 2
        assert result["src/main.py"] == "file content here"
        assert result["src/utils.py"] == "file content here"
        assert mock_client.get_file_content.call_count == 2

    def test_fetch_tool_call_content_ignores_non_read_file(self):
        """Test that non-read_file tool calls are ignored."""
        from review_roadmap.agent.nodes import _fetch_tool_call_content

        mock_client = MagicMock()

        tool_calls = [
            {"name": "other_tool", "args": {"path": "src/main.py"}},
            {"name": "read_file", "args": {"path": "src/utils.py"}},
        ]

        result = _fetch_tool_call_content(
            tool_calls, mock_client, "owner", "repo", "abc123"
        )

        assert len(result) == 1
        assert "src/utils.py" in result
        mock_client.get_file_content.assert_called_once()

    def test_fetch_tool_call_content_handles_errors(self):
        """Test that fetch errors are captured in the result."""
        from review_roadmap.agent.nodes import _fetch_tool_call_content

        mock_client = MagicMock()
        mock_client.get_file_content.side_effect = Exception("Network error")

        tool_calls = [{"name": "read_file", "args": {"path": "src/main.py"}}]

        result = _fetch_tool_call_content(
            tool_calls, mock_client, "owner", "repo", "abc123"
        )

        assert len(result) == 1
        assert "Error fetching content" in result["src/main.py"]
        assert "Network error" in result["src/main.py"]

    def test_fetch_tool_call_content_skips_empty_path(self):
        """Test that tool calls without path are skipped."""
        from review_roadmap.agent.nodes import _fetch_tool_call_content

        mock_client = MagicMock()

        tool_calls = [
            {"name": "read_file", "args": {}},  # No path
            {"name": "read_file", "args": {"path": ""}},  # Empty path
        ]

        result = _fetch_tool_call_content(
            tool_calls, mock_client, "owner", "repo", "abc123"
        )

        assert len(result) == 0
        mock_client.get_file_content.assert_not_called()


class TestAnalyzeStructureNode:
    """Tests for the analyze_structure node function."""

    def test_analyze_structure_returns_topology(self, sample_review_state: ReviewState):
        """Test that analyze_structure returns topology analysis."""
        # Create a mock LLM response
        mock_response = MagicMock()
        mock_response.content = '{"groups": ["Backend", "Tests"]}'

        mock_chain = MagicMock()
        mock_chain.invoke.return_value = mock_response

        with patch("review_roadmap.agent.nodes.llm") as mock_llm:
            # Make the pipe operator return our mock chain
            mock_llm.__or__ = MagicMock(return_value=mock_chain)

            # We need to patch at the point of use
            with patch("review_roadmap.agent.nodes.ChatPromptTemplate") as mock_template:
                mock_prompt = MagicMock()
                mock_prompt.__or__ = MagicMock(return_value=mock_chain)
                mock_template.from_messages.return_value = mock_prompt

                from review_roadmap.agent.nodes import analyze_structure

                result = analyze_structure(sample_review_state)

        assert "topology" in result
        assert "analysis" in result["topology"]
        assert '{"groups": ["Backend", "Tests"]}' in result["topology"]["analysis"]


class TestContextExpansionNode:
    """Tests for the context_expansion node function."""

    def test_context_expansion_no_tool_calls(self, sample_review_state: ReviewState):
        """Test context_expansion when LLM doesn't request files."""
        mock_response = MagicMock()
        mock_response.tool_calls = []  # No tool calls

        mock_chain = MagicMock()
        mock_chain.invoke.return_value = mock_response

        with patch("review_roadmap.agent.nodes.llm") as mock_llm:
            mock_llm.bind_tools.return_value = mock_llm
            mock_llm.__or__ = MagicMock(return_value=mock_chain)

            with patch("review_roadmap.agent.nodes.ChatPromptTemplate") as mock_template:
                mock_prompt = MagicMock()
                mock_prompt.__or__ = MagicMock(return_value=mock_chain)
                mock_template.from_messages.return_value = mock_prompt

                from review_roadmap.agent.nodes import context_expansion

                result = context_expansion(sample_review_state)

        assert "fetched_content" in result
        assert result["fetched_content"] == {}

    def test_context_expansion_with_tool_calls(self, sample_review_state: ReviewState):
        """Test context_expansion when LLM requests files."""
        mock_response = MagicMock()
        mock_response.tool_calls = [
            {"name": "read_file", "args": {"path": "src/base.py"}}
        ]

        mock_chain = MagicMock()
        mock_chain.invoke.return_value = mock_response

        with patch("review_roadmap.agent.nodes.llm") as mock_llm:
            mock_llm.bind_tools.return_value = mock_llm
            mock_llm.__or__ = MagicMock(return_value=mock_chain)

            with patch("review_roadmap.agent.nodes.ChatPromptTemplate") as mock_template:
                mock_prompt = MagicMock()
                mock_prompt.__or__ = MagicMock(return_value=mock_chain)
                mock_template.from_messages.return_value = mock_prompt

                with patch("review_roadmap.agent.nodes.GitHubClient") as mock_gh:
                    mock_client = MagicMock()
                    mock_client.get_file_content.return_value = "base class content"
                    mock_gh.return_value = mock_client

                    from review_roadmap.agent.nodes import context_expansion

                    result = context_expansion(sample_review_state)

        assert "fetched_content" in result
        assert "src/base.py" in result["fetched_content"]
        assert result["fetched_content"]["src/base.py"] == "base class content"


class TestDraftRoadmapNode:
    """Tests for the draft_roadmap node function."""

    def test_draft_roadmap_returns_markdown(
        self, sample_review_state_with_fetched_content: ReviewState
    ):
        """Test that draft_roadmap returns a roadmap string."""
        mock_response = MagicMock()
        mock_response.content = "# Review Roadmap\n\n## Summary\nThis PR adds..."

        mock_chain = MagicMock()
        mock_chain.invoke.return_value = mock_response

        with patch("review_roadmap.agent.nodes.llm") as mock_llm:
            mock_llm.__or__ = MagicMock(return_value=mock_chain)

            with patch("review_roadmap.agent.nodes.ChatPromptTemplate") as mock_template:
                mock_prompt = MagicMock()
                mock_prompt.__or__ = MagicMock(return_value=mock_chain)
                mock_template.from_messages.return_value = mock_prompt

                from review_roadmap.agent.nodes import draft_roadmap

                result = draft_roadmap(sample_review_state_with_fetched_content)

        assert "roadmap" in result
        assert "# Review Roadmap" in result["roadmap"]
        assert "Summary" in result["roadmap"]

    def test_draft_roadmap_uses_all_context(self, sample_review_state: ReviewState):
        """Test that draft_roadmap includes all context in the prompt."""
        captured_context = {}

        def capture_invoke(args):
            captured_context["context"] = args["context"]
            mock_response = MagicMock()
            mock_response.content = "# Roadmap"
            return mock_response

        mock_chain = MagicMock()
        mock_chain.invoke.side_effect = capture_invoke

        with patch("review_roadmap.agent.nodes.llm") as mock_llm:
            mock_llm.__or__ = MagicMock(return_value=mock_chain)

            with patch("review_roadmap.agent.nodes.ChatPromptTemplate") as mock_template:
                mock_prompt = MagicMock()
                mock_prompt.__or__ = MagicMock(return_value=mock_chain)
                mock_template.from_messages.return_value = mock_prompt

                from review_roadmap.agent.nodes import draft_roadmap

                draft_roadmap(sample_review_state)

        # Verify the context includes expected information
        ctx = captured_context["context"]
        assert "feat: add new feature" in ctx  # PR title
        assert "testuser" in ctx  # Author
        assert "src/main.py" in ctx  # Files
        assert "reviewer1" in ctx  # Comments

