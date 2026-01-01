"""GitHub API client for fetching Pull Request data.

This module provides a synchronous HTTP client for interacting with
GitHub's REST API, specifically for fetching PR context needed to
generate review roadmaps.
"""

from typing import Any, Dict, List, Optional

import httpx

from review_roadmap.config import settings
from review_roadmap.models import PRContext, PRMetadata, FileDiff, PRComment


class GitHubClient:
    """Synchronous GitHub API client for PR data retrieval.

    Uses httpx for HTTP requests with automatic authentication via
    the configured GitHub token. All methods use GitHub's REST API v3.

    Attributes:
        token: GitHub API token for authentication.
        headers: Default HTTP headers including auth and API version.
        client: httpx.Client instance for making requests.

    Example:
        >>> client = GitHubClient()
        >>> context = client.get_pr_context("owner", "repo", 123)
        >>> print(context.metadata.title)
    """

    def __init__(self, token: Optional[str] = None):
        """Initialize the GitHub client.

        Args:
            token: GitHub API token. If not provided, uses GITHUB_TOKEN from settings.
        """
        self.token = token or settings.GITHUB_TOKEN
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/vnd.github.v3+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        self.client = httpx.Client(
            headers=self.headers,
            base_url="https://api.github.com",
            follow_redirects=True,
        )

    def _fetch_pr_metadata(self, owner: str, repo: str, pr_number: int) -> PRMetadata:
        """Fetch and parse PR metadata from the pulls endpoint.

        Args:
            owner: Repository owner (user or organization).
            repo: Repository name.
            pr_number: Pull request number.

        Returns:
            PRMetadata with title, author, branches, etc.

        Raises:
            httpx.HTTPStatusError: If the API request fails.
        """
        pr_resp = self.client.get(f"/repos/{owner}/{repo}/pulls/{pr_number}")
        pr_resp.raise_for_status()
        pr_data = pr_resp.json()
        
        return PRMetadata(
            number=pr_data["number"],
            title=pr_data["title"],
            description=pr_data["body"] or "",
            author=pr_data["user"]["login"],
            base_branch=pr_data["base"]["ref"],
            head_branch=pr_data["head"]["ref"],
            head_commit_sha=pr_data["head"]["sha"],
            repo_url=pr_data["base"]["repo"]["html_url"],
            is_draft=pr_data["draft"]
        )

    def _fetch_file_diffs(self, owner: str, repo: str, pr_number: int) -> List[FileDiff]:
        """Fetch the list of changed files with their diffs.

        Args:
            owner: Repository owner.
            repo: Repository name.
            pr_number: Pull request number.

        Returns:
            List of FileDiff objects with paths, stats, and patch content.

        Raises:
            httpx.HTTPStatusError: If the API request fails.
        """
        files_resp = self.client.get(f"/repos/{owner}/{repo}/pulls/{pr_number}/files")
        files_resp.raise_for_status()
        
        return [
            FileDiff(
                path=f["filename"],
                status=f["status"],
                additions=f["additions"],
                deletions=f["deletions"],
                diff_content=f.get("patch", "")  # Patch might be missing for binary/large files
            )
            for f in files_resp.json()
        ]

    def _fetch_issue_comments(self, owner: str, repo: str, pr_number: int) -> List[PRComment]:
        """Fetch general conversation comments from the issues endpoint.

        These are top-level comments on the PR, not inline code comments.

        Args:
            owner: Repository owner.
            repo: Repository name.
            pr_number: Pull request number.

        Returns:
            List of PRComment objects (with path=None for general comments).
        """
        resp = self.client.get(f"/repos/{owner}/{repo}/issues/{pr_number}/comments")
        if resp.status_code != 200:
            return []
        
        return [
            PRComment(
                id=c["id"],
                body=c["body"],
                user=c["user"]["login"],
                created_at=c["created_at"]
            )
            for c in resp.json()
        ]

    def _fetch_review_comments(self, owner: str, repo: str, pr_number: int) -> List[PRComment]:
        """Fetch inline code review comments from the pulls endpoint.

        These are comments attached to specific lines in the diff.

        Args:
            owner: Repository owner.
            repo: Repository name.
            pr_number: Pull request number.

        Returns:
            List of PRComment objects with path and line set for inline comments.
        """
        resp = self.client.get(f"/repos/{owner}/{repo}/pulls/{pr_number}/comments")
        if resp.status_code != 200:
            return []
        
        return [
            PRComment(
                id=c["id"],
                body=c["body"],
                user=c["user"]["login"],
                path=c.get("path"),
                line=c.get("line"),
                created_at=c["created_at"]
            )
            for c in resp.json()
        ]

    def get_pr_context(self, owner: str, repo: str, pr_number: int) -> PRContext:
        """Fetch complete PR context including metadata, files, and comments.

        This is the main entry point for gathering all information needed
        to generate a review roadmap.

        Args:
            owner: Repository owner (user or organization).
            repo: Repository name.
            pr_number: Pull request number.

        Returns:
            PRContext with metadata, file diffs, and all comments.

        Raises:
            httpx.HTTPStatusError: If fetching metadata or files fails.
        """
        metadata = self._fetch_pr_metadata(owner, repo, pr_number)
        files = self._fetch_file_diffs(owner, repo, pr_number)
        
        comments = self._fetch_issue_comments(owner, repo, pr_number)
        comments.extend(self._fetch_review_comments(owner, repo, pr_number))
        
        return PRContext(metadata=metadata, files=files, comments=comments)

    def get_file_content(self, owner: str, repo: str, path: str, ref: str) -> str:
        """Fetch raw file content at a specific Git ref.

        Used by the context expansion node to fetch additional files
        that help understand the PR changes.

        Args:
            owner: Repository owner.
            repo: Repository name.
            path: Path to the file in the repository.
            ref: Git ref (branch, tag, or commit SHA).

        Returns:
            The raw text content of the file.

        Raises:
            httpx.HTTPStatusError: If the file doesn't exist or request fails.
        """
        # First request to validate the file exists
        resp = self.client.get(f"/repos/{owner}/{repo}/contents/{path}", params={"ref": ref})
        resp.raise_for_status()
        
        # Request with raw media type to get actual content
        headers = self.headers.copy()
        headers["Accept"] = "application/vnd.github.v3.raw"
        raw_resp = self.client.get(
            f"/repos/{owner}/{repo}/contents/{path}",
            params={"ref": ref},
            headers=headers
        )
        raw_resp.raise_for_status()
        return raw_resp.text

    def check_write_access(self, owner: str, repo: str) -> bool:
        """Check if the authenticated user has write access to the repository.

        Used to validate permissions before attempting to post a PR comment.

        Args:
            owner: Repository owner.
            repo: Repository name.

        Returns:
            True if the user has push or admin access, False otherwise.

        Raises:
            httpx.HTTPStatusError: If the repository request fails.
        """
        resp = self.client.get(f"/repos/{owner}/{repo}")
        resp.raise_for_status()
        repo_data = resp.json()
        
        permissions = repo_data.get("permissions", {})
        return permissions.get("push", False) or permissions.get("admin", False)

    def post_pr_comment(self, owner: str, repo: str, pr_number: int, body: str) -> Dict[str, Any]:
        """Post a comment on a pull request.

        Args:
            owner: Repository owner.
            repo: Repository name.
            pr_number: Pull request number.
            body: Comment body text (Markdown supported).

        Returns:
            The created comment data from GitHub's API.

        Raises:
            httpx.HTTPStatusError: If posting fails (e.g., no write access).
        """
        resp = self.client.post(
            f"/repos/{owner}/{repo}/issues/{pr_number}/comments",
            json={"body": body}
        )
        resp.raise_for_status()
        return resp.json()
