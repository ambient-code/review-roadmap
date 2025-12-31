import pytest
import respx
from httpx import Response
from review_roadmap.github.client import GitHubClient
from review_roadmap.config import settings

@respx.mock
def test_get_pr_context_success():
    """Verifies that get_pr_context fetches and parses all data correctly."""
    
    owner = "owner"
    repo = "repo"
    pr_number = 1
    
    # Mocks
    pr_url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}"
    files_url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}/files"
    issue_comments_url = f"https://api.github.com/repos/{owner}/{repo}/issues/{pr_number}/comments"
    review_comments_url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}/comments"
    
    respx.get(pr_url).mock(return_value=Response(200, json={
        "number": 1,
        "title": "Test PR",
        "body": "Description",
        "user": {"login": "author"},
        "base": {"ref": "main", "repo": {"html_url": "https://github.com/base/repo"}},
        "head": {"ref": "feature", "sha": "abc1234", "repo": {"html_url": "https://github.com/head/fork"}},
        "draft": False
    }))
    
    respx.get(files_url).mock(return_value=Response(200, json=[
        {"filename": "file1.py", "status": "modified", "additions": 10, "deletions": 5, "patch": "..."}
    ]))
    
    respx.get(issue_comments_url).mock(return_value=Response(200, json=[
        {"id": 1, "body": "Comment 1", "user": {"login": "user1"}, "created_at": "2023-01-01T00:00:00Z"}
    ]))
    
    respx.get(review_comments_url).mock(return_value=Response(200, json=[
        {"id": 2, "body": "Inline comment", "user": {"login": "user2"}, "path": "file1.py", "line": 10, "created_at": "2023-01-01T00:00:00Z"}
    ]))
    
    # Execute
    client = GitHubClient(token="fake-token")
    context = client.get_pr_context(owner, repo, pr_number)
    
    # Assertions
    assert context.metadata.title == "Test PR"
    assert context.metadata.author == "author"
    assert context.metadata.repo_url == "https://github.com/base/repo"
    assert len(context.files) == 1
    assert context.files[0].path == "file1.py"
    assert len(context.comments) == 2
    assert context.comments[0].body == "Comment 1"
    assert context.comments[1].path == "file1.py"

@respx.mock
def test_get_file_content_success():
    """Verifies fetching raw file content."""
    owner = "owner"
    repo = "repo"
    path = "src/main.py"
    ref = "abc1234"
    
    url = f"https://api.github.com/repos/{owner}/{repo}/contents/{path}"
    
    respx.get(url, params={"ref": ref}).mock(return_value=Response(200, text="print('hello')"))
    
    client = GitHubClient(token="fake-token")
    content = client.get_file_content(owner, repo, path, ref)
    
    assert content == "print('hello')"


@respx.mock
def test_check_write_access_with_push_permission():
    """Verifies that check_write_access returns True when user has push permission."""
    owner = "owner"
    repo = "repo"
    url = f"https://api.github.com/repos/{owner}/{repo}"
    
    respx.get(url).mock(return_value=Response(200, json={
        "id": 12345,
        "name": repo,
        "permissions": {
            "admin": False,
            "push": True,
            "pull": True
        }
    }))
    
    client = GitHubClient(token="fake-token")
    has_access = client.check_write_access(owner, repo)
    
    assert has_access is True


@respx.mock
def test_check_write_access_with_admin_permission():
    """Verifies that check_write_access returns True when user has admin permission."""
    owner = "owner"
    repo = "repo"
    url = f"https://api.github.com/repos/{owner}/{repo}"
    
    respx.get(url).mock(return_value=Response(200, json={
        "id": 12345,
        "name": repo,
        "permissions": {
            "admin": True,
            "push": False,
            "pull": True
        }
    }))
    
    client = GitHubClient(token="fake-token")
    has_access = client.check_write_access(owner, repo)
    
    assert has_access is True


@respx.mock
def test_check_write_access_no_permission():
    """Verifies that check_write_access returns False when user lacks write access."""
    owner = "owner"
    repo = "repo"
    url = f"https://api.github.com/repos/{owner}/{repo}"
    
    respx.get(url).mock(return_value=Response(200, json={
        "id": 12345,
        "name": repo,
        "permissions": {
            "admin": False,
            "push": False,
            "pull": True
        }
    }))
    
    client = GitHubClient(token="fake-token")
    has_access = client.check_write_access(owner, repo)
    
    assert has_access is False


@respx.mock
def test_check_write_access_no_permissions_field():
    """Verifies that check_write_access returns False when permissions field is missing."""
    owner = "owner"
    repo = "repo"
    url = f"https://api.github.com/repos/{owner}/{repo}"
    
    # Public repos without authentication may not have permissions field
    respx.get(url).mock(return_value=Response(200, json={
        "id": 12345,
        "name": repo
    }))
    
    client = GitHubClient(token="fake-token")
    has_access = client.check_write_access(owner, repo)
    
    assert has_access is False


@respx.mock
def test_post_pr_comment_success():
    """Verifies that post_pr_comment posts successfully and returns the response."""
    owner = "owner"
    repo = "repo"
    pr_number = 42
    comment_body = "This is a test comment"
    
    url = f"https://api.github.com/repos/{owner}/{repo}/issues/{pr_number}/comments"
    
    respx.post(url).mock(return_value=Response(201, json={
        "id": 123456,
        "body": comment_body,
        "user": {"login": "test-user"},
        "created_at": "2024-01-01T00:00:00Z",
        "html_url": f"https://github.com/{owner}/{repo}/issues/{pr_number}#issuecomment-123456"
    }))
    
    client = GitHubClient(token="fake-token")
    result = client.post_pr_comment(owner, repo, pr_number, comment_body)
    
    assert result["id"] == 123456
    assert result["body"] == comment_body
