"""GitHub API client for fetching Pull Request data.

This module provides a synchronous HTTP client for interacting with
GitHub's REST API, specifically for fetching PR context needed to
generate review roadmaps.
"""

from typing import Any, Dict, List, Optional

import httpx

from review_roadmap.config import settings
from review_roadmap.models import (
    PRContext, PRMetadata, FileDiff, PRComment,
    WriteAccessResult, WriteAccessStatus,
)


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

    def _test_write_with_reaction(self, owner: str, repo: str, pr_number: int) -> bool:
        """Test write access by creating and immediately deleting a reaction.

        This is a non-destructive way to verify the token can write to the PR.
        Uses the 'eyes' emoji (👀) as it's unobtrusive if cleanup fails.

        Args:
            owner: Repository owner.
            repo: Repository name.
            pr_number: PR number to test against.

        Returns:
            True if write access is confirmed, False otherwise.
        """
        try:
            # Create a reaction on the PR (PRs are issues in GitHub's API)
            create_resp = self.client.post(
                f"/repos/{owner}/{repo}/issues/{pr_number}/reactions",
                json={"content": "eyes"}
            )
            
            if create_resp.status_code in (200, 201):
                # Successfully created - now clean it up
                reaction_id = create_resp.json().get("id")
                if reaction_id:
                    self.client.delete(
                        f"/repos/{owner}/{repo}/issues/{pr_number}/reactions/{reaction_id}"
                    )
                return True
            elif create_resp.status_code == 403:
                return False
            else:
                # Unexpected status - treat as uncertain
                return False
        except Exception:
            return False

    def check_write_access(
        self, owner: str, repo: str, pr_number: Optional[int] = None
    ) -> WriteAccessResult:
        """Check if the authenticated token can write to the repository.

        Validates:
        1. The user has push/admin permissions on the repository
        2. The token has the required OAuth scopes (for classic PATs/OAuth tokens)
        3. For fine-grained PATs: performs a live test using reactions if pr_number provided

        Args:
            owner: Repository owner.
            repo: Repository name.
            pr_number: Optional PR number for live write test (used for fine-grained PATs).

        Returns:
            WriteAccessResult with status, confidence level, and explanation.

        Raises:
            httpx.HTTPStatusError: If the repository request fails.
        """
        resp = self.client.get(f"/repos/{owner}/{repo}")
        resp.raise_for_status()
        repo_data = resp.json()
        
        # Check user's role-based permissions
        permissions = repo_data.get("permissions", {})
        has_role_access = permissions.get("push", False) or permissions.get("admin", False)
        
        if not has_role_access:
            return WriteAccessResult(
                status=WriteAccessStatus.DENIED,
                is_fine_grained_pat=False,
                message="Your user account does not have write access to this repository."
            )
        
        # Check token's OAuth scopes (only present for classic PATs and OAuth tokens)
        oauth_scopes_header = resp.headers.get("X-OAuth-Scopes")
        
        if oauth_scopes_header is not None:
            # Classic PAT or OAuth token - can verify scopes definitively
            scopes = [s.strip() for s in oauth_scopes_header.split(",") if s.strip()]
            is_private = repo_data.get("private", False)
            
            if is_private:
                has_token_scope = "repo" in scopes
                required_scope = "repo"
            else:
                has_token_scope = "repo" in scopes or "public_repo" in scopes
                required_scope = "repo or public_repo"
            
            if has_token_scope:
                return WriteAccessResult(
                    status=WriteAccessStatus.GRANTED,
                    is_fine_grained_pat=False,
                    message="Classic token with correct scopes verified."
                )
            else:
                return WriteAccessResult(
                    status=WriteAccessStatus.DENIED,
                    is_fine_grained_pat=False,
                    message=f"Token lacks required scope ({required_scope}). Current scopes: {', '.join(scopes) or 'none'}"
                )
        
        # No X-OAuth-Scopes header = fine-grained PAT
        # Try a live write test if we have a PR number
        if pr_number is not None:
            if self._test_write_with_reaction(owner, repo, pr_number):
                return WriteAccessResult(
                    status=WriteAccessStatus.GRANTED,
                    is_fine_grained_pat=True,
                    message="Fine-grained PAT write access verified via live test."
                )
            else:
                return WriteAccessResult(
                    status=WriteAccessStatus.DENIED,
                    is_fine_grained_pat=True,
                    message=(
                        "Fine-grained PAT detected but write test failed. "
                        f"Ensure your token has 'Pull requests: Read and write' permission "
                        f"for {owner}/{repo}."
                    )
                )
        
        # No PR number provided - can't do live test
        return WriteAccessResult(
            status=WriteAccessStatus.UNCERTAIN,
            is_fine_grained_pat=True,
            message=(
                "Fine-grained PAT detected. Cannot verify if this token is configured "
                f"for {owner}/{repo}. If posting fails, ensure your token has "
                "'Pull requests: Read and write' permission for this specific repository."
            )
        )

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
