"""Shared test fixtures for the review-roadmap test suite."""

import pytest
from review_roadmap.models import PRContext, PRMetadata, FileDiff, PRComment
from review_roadmap.agent.state import ReviewState


@pytest.fixture
def sample_pr_metadata() -> PRMetadata:
    """Create a sample PRMetadata for testing."""
    return PRMetadata(
        number=42,
        title="feat: add new feature",
        description="This PR adds a new feature to the codebase.",
        author="testuser",
        base_branch="main",
        head_branch="feature/new-feature",
        head_commit_sha="abc123def456",
        repo_url="https://github.com/owner/repo",
        is_draft=False,
    )


@pytest.fixture
def sample_file_diffs() -> list[FileDiff]:
    """Create sample FileDiffs for testing."""
    return [
        FileDiff(
            path="src/main.py",
            status="modified",
            additions=10,
            deletions=5,
            diff_content="@@ -1,5 +1,10 @@\n+new line",
        ),
        FileDiff(
            path="src/utils.py",
            status="added",
            additions=50,
            deletions=0,
            diff_content="@@ -0,0 +1,50 @@\n+new file content",
        ),
        FileDiff(
            path="tests/test_main.py",
            status="modified",
            additions=20,
            deletions=2,
            diff_content="@@ -1,2 +1,20 @@\n+new tests",
        ),
    ]


@pytest.fixture
def sample_pr_comments() -> list[PRComment]:
    """Create sample PRComments for testing."""
    return [
        PRComment(
            id=1,
            body="Looks good to me!",
            user="reviewer1",
            path=None,
            line=None,
            created_at="2024-01-01T10:00:00Z",
        ),
        PRComment(
            id=2,
            body="Can you add a docstring here?",
            user="reviewer2",
            path="src/main.py",
            line=15,
            created_at="2024-01-01T11:00:00Z",
        ),
    ]


@pytest.fixture
def sample_pr_context(
    sample_pr_metadata: PRMetadata,
    sample_file_diffs: list[FileDiff],
    sample_pr_comments: list[PRComment],
) -> PRContext:
    """Create a sample PRContext for testing."""
    return PRContext(
        metadata=sample_pr_metadata,
        files=sample_file_diffs,
        comments=sample_pr_comments,
    )


@pytest.fixture
def sample_review_state(sample_pr_context: PRContext) -> ReviewState:
    """Create a sample ReviewState for testing."""
    return ReviewState(
        pr_context=sample_pr_context,
        topology={"analysis": "Backend: src/main.py, src/utils.py\nTests: tests/test_main.py"},
        fetched_content={},
    )


@pytest.fixture
def sample_review_state_with_fetched_content(sample_pr_context: PRContext) -> ReviewState:
    """Create a sample ReviewState with fetched content for testing."""
    return ReviewState(
        pr_context=sample_pr_context,
        topology={"analysis": "Backend module with tests"},
        fetched_content={
            "src/base.py": "class BaseClass:\n    pass",
            "src/config.py": "DEBUG = True\nAPI_KEY = 'xxx'",
        },
    )


@pytest.fixture
def sample_review_state_with_roadmap(sample_pr_context: PRContext) -> ReviewState:
    """Create a sample ReviewState with a generated roadmap for reflection testing."""
    return ReviewState(
        pr_context=sample_pr_context,
        topology={"analysis": "Backend: src/main.py, src/utils.py\nTests: tests/test_main.py"},
        fetched_content={},
        roadmap="""# Review Roadmap

## Summary
This PR adds a new feature to the codebase.

## Review Order
1. Start with `src/main.py` - the main changes
2. Review `src/utils.py` - new utility file
3. Check `tests/test_main.py` - test coverage

## Watch Outs
- Check error handling in main.py
- Verify utils.py follows project conventions
""",
    )

