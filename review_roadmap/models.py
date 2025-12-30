from typing import List, Optional
from pydantic import BaseModel, Field

class FileDiff(BaseModel):
    path: str
    status: str  # added, modified, removed, renamed
    additions: int
    deletions: int
    diff_content: str = Field(description="The actual unified diff content for this file")
    
    def get_github_link(self, repo_url: str, commit_sha: str, start_line: Optional[int] = None, end_line: Optional[int] = None) -> str:
        """Generates a deep link to the file at a specific commit (BLOB view)."""
        base = f"{repo_url}/blob/{commit_sha}/{self.path}"
        if start_line and end_line:
            return f"{base}#L{start_line}-L{end_line}"
        if start_line:
            return f"{base}#L{start_line}"
        return base

    def get_pr_diff_link(self, repo_url: str, pr_number: int, line: Optional[int] = None) -> str:
        """Generates a deep link to the specific line in the PR DIFF view."""
        # GitHub uses SHA256 of the file path for the anchor
        import hashlib
        path_hash = hashlib.sha256(self.path.encode("utf-8")).hexdigest()
        
        # Base PR files link
        base = f"{repo_url}/pull/{pr_number}/files#diff-{path_hash}"
        
        if line:
            return f"{base}R{line}"
        return base

class PRMetadata(BaseModel):
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
    id: int
    body: str
    user: str
    path: Optional[str] = None
    line: Optional[int] = None
    created_at: str

class PRContext(BaseModel):
    metadata: PRMetadata
    files: List[FileDiff]
    comments: List[PRComment] = Field(default_factory=list)
