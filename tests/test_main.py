"""Tests for the main CLI module."""

import pytest
from unittest.mock import patch, MagicMock
from typer.testing import CliRunner


# Create a CLI runner for testing
runner = CliRunner()


class TestFormatPrComment:
    """Tests for the format_pr_comment function."""

    def test_format_pr_comment_structure(self):
        """Test the structure of format_pr_comment output."""
        with patch("review_roadmap.main.settings") as mock_settings:
            mock_settings.REVIEW_ROADMAP_LLM_PROVIDER = "anthropic"
            mock_settings.REVIEW_ROADMAP_MODEL_NAME = "claude-sonnet-4-20250514"

            from review_roadmap.main import format_pr_comment

            roadmap_content = "## Review Roadmap\n\nThis is the roadmap content."
            result = format_pr_comment(roadmap_content)

            # Check header
            assert "🗺️ **Auto-Generated Review Roadmap**" in result

            # Check attribution link
            assert "https://github.com/jwm4/review-roadmap" in result

            # Check model info format (provider/model)
            assert "anthropic/claude-sonnet-4-20250514" in result

            # Check roadmap content is included at the end
            assert roadmap_content in result
            assert result.endswith(roadmap_content)

            # Check separator is present
            assert "---" in result

    def test_format_pr_comment_preserves_special_characters(self):
        """Test that special characters in roadmap content are preserved."""
        with patch("review_roadmap.main.settings") as mock_settings:
            mock_settings.REVIEW_ROADMAP_LLM_PROVIDER = "openai"
            mock_settings.REVIEW_ROADMAP_MODEL_NAME = "gpt-4o"

            from review_roadmap.main import format_pr_comment

            roadmap_content = "Code: <>&\"' and **markdown**"
            result = format_pr_comment(roadmap_content)

            assert "<>&\"'" in result
            assert "**markdown**" in result


class TestPrUrlParsing:
    """Tests for PR URL parsing logic in the generate command."""

    def test_parse_full_github_url(self):
        """Test parsing a full GitHub PR URL."""
        # This tests the parsing logic inline since the generate function
        # does the parsing internally

        pr_url = "https://github.com/owner/repo/pull/123"
        parts = pr_url.rstrip("/").split("/")
        pr_number = int(parts[-1])
        repo = parts[-3]
        owner = parts[-4]

        assert owner == "owner"
        assert repo == "repo"
        assert pr_number == 123

    def test_parse_short_format(self):
        """Test parsing short format owner/repo/number."""
        pr_url = "owner/repo/456"
        owner, repo, pr_number = pr_url.split("/")
        pr_number = int(pr_number)

        assert owner == "owner"
        assert repo == "repo"
        assert pr_number == 456


class TestGenerateCommand:
    """Tests for the generate CLI command."""

    def test_generate_invalid_pr_format(self):
        """Test that invalid PR format shows error."""
        with patch("review_roadmap.main.configure_logging"):
            from review_roadmap.main import app

            result = runner.invoke(app, ["invalid-format"])

            assert result.exit_code == 1
            assert "Invalid PR format" in result.output

    def test_generate_parses_full_url(self):
        """Test that full GitHub URL is parsed correctly."""
        mock_context = MagicMock()
        mock_context.metadata.title = "Test PR"
        mock_context.files = []

        mock_graph_result = {"roadmap": "# Test Roadmap"}

        with patch("review_roadmap.main.configure_logging"):
            with patch("review_roadmap.main.GitHubClient") as mock_gh:
                mock_client = MagicMock()
                mock_client.get_pr_context.return_value = mock_context
                mock_gh.return_value = mock_client

                with patch("review_roadmap.main.build_graph") as mock_build:
                    mock_graph = MagicMock()
                    mock_graph.invoke.return_value = mock_graph_result
                    mock_build.return_value = mock_graph

                    from review_roadmap.main import app

                    result = runner.invoke(
                        app, ["https://github.com/owner/repo/pull/123"]
                    )

                    # Should have called get_pr_context with parsed values
                    mock_client.get_pr_context.assert_called_once_with(
                        "owner", "repo", 123
                    )

    def test_generate_parses_short_format(self):
        """Test that short format owner/repo/number is parsed correctly."""
        mock_context = MagicMock()
        mock_context.metadata.title = "Test PR"
        mock_context.files = []

        mock_graph_result = {"roadmap": "# Test Roadmap"}

        with patch("review_roadmap.main.configure_logging"):
            with patch("review_roadmap.main.GitHubClient") as mock_gh:
                mock_client = MagicMock()
                mock_client.get_pr_context.return_value = mock_context
                mock_gh.return_value = mock_client

                with patch("review_roadmap.main.build_graph") as mock_build:
                    mock_graph = MagicMock()
                    mock_graph.invoke.return_value = mock_graph_result
                    mock_build.return_value = mock_graph

                    from review_roadmap.main import app

                    result = runner.invoke(app, ["myorg/myrepo/456"])

                    mock_client.get_pr_context.assert_called_once_with(
                        "myorg", "myrepo", 456
                    )

    def test_generate_outputs_to_file(self, tmp_path):
        """Test that --output flag writes roadmap to file."""
        mock_context = MagicMock()
        mock_context.metadata.title = "Test PR"
        mock_context.files = []

        roadmap_content = "# Test Roadmap\n\nThis is a test."
        mock_graph_result = {"roadmap": roadmap_content}

        output_file = tmp_path / "roadmap.md"

        with patch("review_roadmap.main.configure_logging"):
            with patch("review_roadmap.main.GitHubClient") as mock_gh:
                mock_client = MagicMock()
                mock_client.get_pr_context.return_value = mock_context
                mock_gh.return_value = mock_client

                with patch("review_roadmap.main.build_graph") as mock_build:
                    mock_graph = MagicMock()
                    mock_graph.invoke.return_value = mock_graph_result
                    mock_build.return_value = mock_graph

                    from review_roadmap.main import app

                    result = runner.invoke(
                        app, ["owner/repo/1", "--output", str(output_file)]
                    )

                    assert result.exit_code == 0
                    assert output_file.exists()
                    assert output_file.read_text() == roadmap_content

    def test_generate_posts_to_pr(self):
        """Test that --post flag posts roadmap as PR comment."""
        mock_context = MagicMock()
        mock_context.metadata.title = "Test PR"
        mock_context.files = []

        roadmap_content = "# Test Roadmap"
        mock_graph_result = {"roadmap": roadmap_content}

        with patch("review_roadmap.main.configure_logging"):
            with patch("review_roadmap.main.GitHubClient") as mock_gh:
                mock_client = MagicMock()
                mock_client.get_pr_context.return_value = mock_context
                mock_client.check_write_access.return_value = True
                mock_gh.return_value = mock_client

                with patch("review_roadmap.main.build_graph") as mock_build:
                    mock_graph = MagicMock()
                    mock_graph.invoke.return_value = mock_graph_result
                    mock_build.return_value = mock_graph

                    with patch("review_roadmap.main.settings") as mock_settings:
                        mock_settings.REVIEW_ROADMAP_LLM_PROVIDER = "anthropic"
                        mock_settings.REVIEW_ROADMAP_MODEL_NAME = "claude"

                        from review_roadmap.main import app

                        result = runner.invoke(app, ["owner/repo/1", "--post"])

                        assert result.exit_code == 0
                        mock_client.check_write_access.assert_called_once()
                        mock_client.post_pr_comment.assert_called_once()

    def test_generate_post_fails_without_write_access(self):
        """Test that --post fails early if no write access."""
        with patch("review_roadmap.main.configure_logging"):
            with patch("review_roadmap.main.GitHubClient") as mock_gh:
                mock_client = MagicMock()
                mock_client.check_write_access.return_value = False
                mock_gh.return_value = mock_client

                from review_roadmap.main import app

                result = runner.invoke(app, ["owner/repo/1", "--post"])

                assert result.exit_code == 1
                assert "write access" in result.output.lower()
                # Should not have tried to fetch PR context
                mock_client.get_pr_context.assert_not_called()

    def test_generate_handles_pr_fetch_error(self):
        """Test that PR fetch errors are handled gracefully."""
        with patch("review_roadmap.main.configure_logging"):
            with patch("review_roadmap.main.GitHubClient") as mock_gh:
                mock_client = MagicMock()
                mock_client.get_pr_context.side_effect = Exception("Network error")
                mock_gh.return_value = mock_client

                from review_roadmap.main import app

                result = runner.invoke(app, ["owner/repo/1"])

                assert result.exit_code == 1
                assert "Error fetching PR data" in result.output

    def test_generate_handles_post_error(self):
        """Test that posting errors are handled gracefully."""
        mock_context = MagicMock()
        mock_context.metadata.title = "Test PR"
        mock_context.files = []

        mock_graph_result = {"roadmap": "# Roadmap"}

        with patch("review_roadmap.main.configure_logging"):
            with patch("review_roadmap.main.GitHubClient") as mock_gh:
                mock_client = MagicMock()
                mock_client.get_pr_context.return_value = mock_context
                mock_client.check_write_access.return_value = True
                mock_client.post_pr_comment.side_effect = Exception("Post failed")
                mock_gh.return_value = mock_client

                with patch("review_roadmap.main.build_graph") as mock_build:
                    mock_graph = MagicMock()
                    mock_graph.invoke.return_value = mock_graph_result
                    mock_build.return_value = mock_graph

                    with patch("review_roadmap.main.settings") as mock_settings:
                        mock_settings.REVIEW_ROADMAP_LLM_PROVIDER = "anthropic"
                        mock_settings.REVIEW_ROADMAP_MODEL_NAME = "claude"

                        from review_roadmap.main import app

                        result = runner.invoke(app, ["owner/repo/1", "--post"])

                        assert result.exit_code == 1
                        assert "Error posting comment" in result.output

    def test_generate_prints_to_console_by_default(self):
        """Test that roadmap is printed to console when no output/post flags."""
        mock_context = MagicMock()
        mock_context.metadata.title = "Test PR"
        mock_context.files = []

        roadmap_content = "# Test Roadmap Content"
        mock_graph_result = {"roadmap": roadmap_content}

        with patch("review_roadmap.main.configure_logging"):
            with patch("review_roadmap.main.GitHubClient") as mock_gh:
                mock_client = MagicMock()
                mock_client.get_pr_context.return_value = mock_context
                mock_gh.return_value = mock_client

                with patch("review_roadmap.main.build_graph") as mock_build:
                    mock_graph = MagicMock()
                    mock_graph.invoke.return_value = mock_graph_result
                    mock_build.return_value = mock_graph

                    from review_roadmap.main import app

                    result = runner.invoke(app, ["owner/repo/1"])

                    assert result.exit_code == 0
                    # The roadmap should appear in output
                    assert "Generated Roadmap" in result.output
