import httpx
from typing import Optional
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
        self.client = httpx.Client(headers=self.headers, base_url="https://api.github.com", follow_redirects=True)

    def get_pr_context(self, owner: str, repo: str, pr_number: int) -> PRContext:
        """Fetches all necessary context for a PR."""
        
        # 1. Fetch PR Metadata
        pr_resp = self.client.get(f"/repos/{owner}/{repo}/pulls/{pr_number}")
        pr_resp.raise_for_status()
        pr_data = pr_resp.json()
        
        metadata = PRMetadata(
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

        # 2. Fetch File Diffs
        files_resp = self.client.get(f"/repos/{owner}/{repo}/pulls/{pr_number}/files")
        files_resp.raise_for_status()
        files_data = files_resp.json()
        
        files = []
        for f in files_data:
            files.append(FileDiff(
                path=f["filename"],
                status=f["status"],
                additions=f["additions"],
                deletions=f["deletions"],
                diff_content=f.get("patch", "")  # Patch might be missing for binary/large files
            ))

        # 3. Fetch Comments (Issue comments + Review comments)
        comments = []
        
        # Issue comments (general conversation)
        issue_comments_resp = self.client.get(f"/repos/{owner}/{repo}/issues/{pr_number}/comments")
        if issue_comments_resp.status_code == 200:
            for c in issue_comments_resp.json():
                comments.append(PRComment(
                    id=c["id"],
                    body=c["body"],
                    user=c["user"]["login"],
                    created_at=c["created_at"]
                ))

        # Review comments (inline code comments)
        review_comments_resp = self.client.get(f"/repos/{owner}/{repo}/pulls/{pr_number}/comments")
        if review_comments_resp.status_code == 200:
            for c in review_comments_resp.json():
                comments.append(PRComment(
                    id=c["id"],
                    body=c["body"],
                    user=c["user"]["login"],
                    path=c.get("path"),
                    line=c.get("line"),
                    created_at=c["created_at"]
                ))
        
        return PRContext(metadata=metadata, files=files, comments=comments)

    def get_file_content(self, owner: str, repo: str, path: str, ref: str) -> str:
        """Fetches raw file content for a specific ref."""
        resp = self.client.get(f"/repos/{owner}/{repo}/contents/{path}", params={"ref": ref})
        resp.raise_for_status()
        
        # GitHub API returns base64 content, but also a 'download_url' or raw media type
        # Simplest is to request raw media type
        headers = self.headers.copy()
        headers["Accept"] = "application/vnd.github.v3.raw"
        raw_resp = self.client.get(f"/repos/{owner}/{repo}/contents/{path}", params={"ref": ref}, headers=headers)
        raw_resp.raise_for_status()
        return raw_resp.text

    def check_write_access(self, owner: str, repo: str) -> bool:
        """
        Check if the authenticated user has write access to the repository.
        Returns True if the user can push/write, False otherwise.
        """
        resp = self.client.get(f"/repos/{owner}/{repo}")
        resp.raise_for_status()
        repo_data = resp.json()
        
        # The 'permissions' field is only present when authenticated
        permissions = repo_data.get("permissions", {})
        return permissions.get("push", False) or permissions.get("admin", False)

    def post_pr_comment(self, owner: str, repo: str, pr_number: int, body: str) -> dict:
        """
        Post a comment on a pull request.
        Uses the issues API since PR comments are issue comments.
        Returns the created comment data.
        """
        resp = self.client.post(
            f"/repos/{owner}/{repo}/issues/{pr_number}/comments",
            json={"body": body}
        )
        resp.raise_for_status()
        return resp.json()
