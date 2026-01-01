"""Data models for GitHub Pull Request context.

This module defines Pydantic models that represent the structured data
fetched from GitHub's API, including PR metadata, file diffs, and comments.
"""

from typing import List, Optional
from pydantic import BaseModel, Field


class FileDiff(BaseModel):
    """Represents a single file change in a Pull Request.

    Contains the file path, change statistics, and the unified diff content.
    Provides methods to generate deep links to GitHub's web interface.

    Attributes:
        path: Relative path to the file in the repository.
        status: Change type - 'added', 'modified', 'removed', or 'renamed'.
        additions: Number of lines added.
        deletions: Number of lines deleted.
        diff_content: The unified diff patch for this file.
    """

    path: str
    status: str  # added, modified, removed, renamed
    additions: int
    deletions: int
    diff_content: str = Field(description="The actual unified diff content for this file")

    def get_github_link(
        self,
        repo_url: str,
        commit_sha: str,
        start_line: Optional[int] = None,
        end_line: Optional[int] = None,
    ) -> str:
        """Generate a deep link to the file at a specific commit (blob view).

        Args:
            repo_url: The GitHub repository URL (e.g., 'https://github.com/owner/repo').
            commit_sha: The commit SHA to link to.
            start_line: Optional starting line number for highlighting.
            end_line: Optional ending line number for range highlighting.

        Returns:
            A URL to the file on GitHub, optionally with line highlighting.
        """
        base = f"{repo_url}/blob/{commit_sha}/{self.path}"
        if start_line and end_line:
            return f"{base}#L{start_line}-L{end_line}"
        if start_line:
            return f"{base}#L{start_line}"
        return base

    def get_pr_diff_link(
        self, repo_url: str, pr_number: int, line: Optional[int] = None
    ) -> str:
        """Generate a deep link to the file in the PR diff view.

        GitHub uses a SHA256 hash of the file path as the anchor for diff views.

        Args:
            repo_url: The GitHub repository URL (e.g., 'https://github.com/owner/repo').
            pr_number: The pull request number.
            line: Optional line number to link to in the diff.

        Returns:
            A URL to the file's diff in the PR, optionally with line anchor.
        """
        import hashlib

        path_hash = hashlib.sha256(self.path.encode("utf-8")).hexdigest()
        base = f"{repo_url}/pull/{pr_number}/files#diff-{path_hash}"

        if line:
            return f"{base}R{line}"
        return base


class PRMetadata(BaseModel):
    """Core metadata about a Pull Request.

    Attributes:
        number: The PR number.
        title: The PR title.
        description: The PR body/description text.
        author: GitHub username of the PR author.
        base_branch: The branch the PR will merge into.
        head_branch: The branch containing the PR changes.
        head_commit_sha: SHA of the latest commit on the PR branch.
        repo_url: Full URL to the repository (e.g., 'https://github.com/owner/repo').
        is_draft: Whether the PR is marked as a draft.
    """

    number: int
    title: str
    description: str
    author: str
    base_branch: str
    head_branch: str
    head_commit_sha: str
    repo_url: str
    is_draft: bool


class PRComment(BaseModel):
    """A comment on a Pull Request.

    Can represent either a general conversation comment or an inline
    code review comment (when path and line are set).

    Attributes:
        id: Unique identifier for the comment.
        body: The comment text content.
        user: GitHub username of the commenter.
        path: File path for inline comments, None for general comments.
        line: Line number for inline comments, None for general comments.
        created_at: ISO 8601 timestamp of when the comment was created.
    """

    id: int
    body: str
    user: str
    path: Optional[str] = None
    line: Optional[int] = None
    created_at: str


class PRContext(BaseModel):
    """Complete context for reviewing a Pull Request.

    Aggregates all the information needed to generate a review roadmap:
    PR metadata, file changes, and existing discussion.

    Attributes:
        metadata: Core PR information (title, author, branches, etc.).
        files: List of all files changed in the PR with their diffs.
        comments: All comments on the PR (both general and inline).
    """

    metadata: PRMetadata
    files: List[FileDiff]
    comments: List[PRComment] = Field(default_factory=list)
