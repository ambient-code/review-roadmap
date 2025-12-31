from typing import Any, Dict, List, Optional

import httpx

from review_roadmap.config import settings
from review_roadmap.models import PRContext, PRMetadata, FileDiff, PRComment


class GitHubClient:
    def __init__(self, token: Optional[str] = None):
        self.token = token or settings.GITHUB_TOKEN
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/vnd.github.v3+json",
            "X-GitHub-Api-Version": "2022-11-28"
        }
        self.client = httpx.Client(
            headers=self.headers,
            base_url="https://api.github.com",
            follow_redirects=True
        )

    def _fetch_pr_metadata(self, owner: str, repo: str, pr_number: int) -> PRMetadata:
        """Fetch and parse PR metadata."""
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
        """Fetch and parse file diffs for a PR."""
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
        """Fetch general conversation comments on the PR."""
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
        """Fetch inline code review comments on the PR."""
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
        """Fetches all necessary context for a PR."""
        metadata = self._fetch_pr_metadata(owner, repo, pr_number)
        files = self._fetch_file_diffs(owner, repo, pr_number)
        
        comments = self._fetch_issue_comments(owner, repo, pr_number)
        comments.extend(self._fetch_review_comments(owner, repo, pr_number))
        
        return PRContext(metadata=metadata, files=files, comments=comments)

    def get_file_content(self, owner: str, repo: str, path: str, ref: str) -> str:
        """Fetches raw file content for a specific ref."""
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
        """Check if the authenticated user has write access to the repository."""
        resp = self.client.get(f"/repos/{owner}/{repo}")
        resp.raise_for_status()
        repo_data = resp.json()
        
        permissions = repo_data.get("permissions", {})
        return permissions.get("push", False) or permissions.get("admin", False)

    def post_pr_comment(self, owner: str, repo: str, pr_number: int, body: str) -> Dict[str, Any]:
        """Post a comment on a pull request."""
        resp = self.client.post(
            f"/repos/{owner}/{repo}/issues/{pr_number}/comments",
            json={"body": body}
        )
        resp.raise_for_status()
        return resp.json()
