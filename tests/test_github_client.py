import pytest
import respx
from httpx import Response
from review_roadmap.github.client import GitHubClient
from review_roadmap.config import settings
from review_roadmap.models import WriteAccessStatus

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
def test_check_write_access_fine_grained_pat_with_push():
    """Fine-grained PAT with push permission returns UNCERTAIN status.
    
    We can't verify fine-grained PAT access because GitHub returns user permissions,
    not token-specific permissions for each repository.
    """
    owner = "owner"
    repo = "repo"
    url = f"https://api.github.com/repos/{owner}/{repo}"
    
    # Fine-grained PATs don't return X-OAuth-Scopes header
    respx.get(url).mock(return_value=Response(200, json={
        "id": 12345,
        "name": repo,
        "private": False,
        "permissions": {
            "admin": False,
            "push": True,
            "pull": True
        }
    }))
    
    client = GitHubClient(token="fake-token")
    result = client.check_write_access(owner, repo)
    
    assert result.status == WriteAccessStatus.UNCERTAIN
    assert result.is_fine_grained_pat is True
    assert "Fine-grained PAT" in result.message


@respx.mock
def test_check_write_access_fine_grained_pat_with_admin():
    """Fine-grained PAT with admin permission returns UNCERTAIN status."""
    owner = "owner"
    repo = "repo"
    url = f"https://api.github.com/repos/{owner}/{repo}"
    
    respx.get(url).mock(return_value=Response(200, json={
        "id": 12345,
        "name": repo,
        "private": False,
        "permissions": {
            "admin": True,
            "push": False,
            "pull": True
        }
    }))
    
    client = GitHubClient(token="fake-token")
    result = client.check_write_access(owner, repo)
    
    assert result.status == WriteAccessStatus.UNCERTAIN
    assert result.is_fine_grained_pat is True


@respx.mock
def test_check_write_access_fine_grained_pat_no_permission():
    """Fine-grained PAT without push/admin returns DENIED status."""
    owner = "owner"
    repo = "repo"
    url = f"https://api.github.com/repos/{owner}/{repo}"
    
    respx.get(url).mock(return_value=Response(200, json={
        "id": 12345,
        "name": repo,
        "private": False,
        "permissions": {
            "admin": False,
            "push": False,
            "pull": True
        }
    }))
    
    client = GitHubClient(token="fake-token")
    result = client.check_write_access(owner, repo)
    
    assert result.status == WriteAccessStatus.DENIED
    assert "does not have write access" in result.message


@respx.mock
def test_check_write_access_no_permissions_field():
    """Missing permissions field returns DENIED status."""
    owner = "owner"
    repo = "repo"
    url = f"https://api.github.com/repos/{owner}/{repo}"
    
    # Public repos without authentication may not have permissions field
    respx.get(url).mock(return_value=Response(200, json={
        "id": 12345,
        "name": repo
    }))
    
    client = GitHubClient(token="fake-token")
    result = client.check_write_access(owner, repo)
    
    assert result.status == WriteAccessStatus.DENIED


@respx.mock
def test_check_write_access_classic_pat_with_repo_scope():
    """Classic PAT with 'repo' scope returns GRANTED status."""
    owner = "owner"
    repo = "repo"
    url = f"https://api.github.com/repos/{owner}/{repo}"
    
    # Classic PATs include X-OAuth-Scopes header
    respx.get(url).mock(return_value=Response(
        200,
        json={
            "id": 12345,
            "name": repo,
            "private": False,
            "permissions": {"admin": False, "push": True, "pull": True}
        },
        headers={"X-OAuth-Scopes": "repo, read:user"}
    ))
    
    client = GitHubClient(token="fake-token")
    result = client.check_write_access(owner, repo)
    
    assert result.status == WriteAccessStatus.GRANTED
    assert result.is_fine_grained_pat is False


@respx.mock
def test_check_write_access_classic_pat_with_public_repo_scope():
    """Classic PAT with 'public_repo' scope on public repo returns GRANTED."""
    owner = "owner"
    repo = "repo"
    url = f"https://api.github.com/repos/{owner}/{repo}"
    
    respx.get(url).mock(return_value=Response(
        200,
        json={
            "id": 12345,
            "name": repo,
            "private": False,
            "permissions": {"admin": False, "push": True, "pull": True}
        },
        headers={"X-OAuth-Scopes": "public_repo, read:user"}
    ))
    
    client = GitHubClient(token="fake-token")
    result = client.check_write_access(owner, repo)
    
    assert result.status == WriteAccessStatus.GRANTED


@respx.mock
def test_check_write_access_classic_pat_without_write_scope():
    """Classic PAT without write scope returns DENIED, even with push permission.
    
    This is the key bug fix: the user may have push permission on the repo,
    but the token lacks the OAuth scope to actually write.
    """
    owner = "owner"
    repo = "repo"
    url = f"https://api.github.com/repos/{owner}/{repo}"
    
    respx.get(url).mock(return_value=Response(
        200,
        json={
            "id": 12345,
            "name": repo,
            "private": False,
            "permissions": {"admin": False, "push": True, "pull": True}  # User has push access
        },
        headers={"X-OAuth-Scopes": "read:user, read:org"}  # But token lacks write scope
    ))
    
    client = GitHubClient(token="fake-token")
    result = client.check_write_access(owner, repo)
    
    assert result.status == WriteAccessStatus.DENIED
    assert "lacks required scope" in result.message


@respx.mock
def test_check_write_access_classic_pat_private_repo_needs_repo_scope():
    """Private repo with only 'public_repo' scope returns DENIED."""
    owner = "owner"
    repo = "repo"
    url = f"https://api.github.com/repos/{owner}/{repo}"
    
    respx.get(url).mock(return_value=Response(
        200,
        json={
            "id": 12345,
            "name": repo,
            "private": True,  # Private repo
            "permissions": {"admin": False, "push": True, "pull": True}
        },
        headers={"X-OAuth-Scopes": "public_repo, read:user"}  # Only has public_repo scope
    ))
    
    client = GitHubClient(token="fake-token")
    result = client.check_write_access(owner, repo)
    
    assert result.status == WriteAccessStatus.DENIED


@respx.mock
def test_check_write_access_classic_pat_private_repo_with_repo_scope():
    """Private repo with 'repo' scope returns GRANTED."""
    owner = "owner"
    repo = "repo"
    url = f"https://api.github.com/repos/{owner}/{repo}"
    
    respx.get(url).mock(return_value=Response(
        200,
        json={
            "id": 12345,
            "name": repo,
            "private": True,
            "permissions": {"admin": False, "push": True, "pull": True}
        },
        headers={"X-OAuth-Scopes": "repo, read:user"}
    ))
    
    client = GitHubClient(token="fake-token")
    result = client.check_write_access(owner, repo)
    
    assert result.status == WriteAccessStatus.GRANTED


@respx.mock
def test_check_write_access_classic_pat_empty_scopes():
    """Classic PAT with empty scopes returns DENIED."""
    owner = "owner"
    repo = "repo"
    url = f"https://api.github.com/repos/{owner}/{repo}"
    
    respx.get(url).mock(return_value=Response(
        200,
        json={
            "id": 12345,
            "name": repo,
            "private": False,
            "permissions": {"admin": True, "push": True, "pull": True}
        },
        headers={"X-OAuth-Scopes": ""}  # Empty scopes
    ))
    
    client = GitHubClient(token="fake-token")
    result = client.check_write_access(owner, repo)
    
    assert result.status == WriteAccessStatus.DENIED


@respx.mock
def test_check_write_access_fine_grained_pat_live_test_success():
    """Fine-grained PAT with successful live write test returns GRANTED."""
    owner = "owner"
    repo = "repo"
    pr_number = 42
    
    # Mock repo endpoint (no X-OAuth-Scopes = fine-grained PAT)
    respx.get(f"https://api.github.com/repos/{owner}/{repo}").mock(
        return_value=Response(200, json={
            "id": 12345,
            "name": repo,
            "private": False,
            "permissions": {"admin": False, "push": True, "pull": True}
        })
    )
    
    # Mock successful reaction creation
    respx.post(f"https://api.github.com/repos/{owner}/{repo}/issues/{pr_number}/reactions").mock(
        return_value=Response(201, json={"id": 99999, "content": "eyes"})
    )
    
    # Mock reaction deletion
    respx.delete(f"https://api.github.com/repos/{owner}/{repo}/issues/{pr_number}/reactions/99999").mock(
        return_value=Response(204)
    )
    
    client = GitHubClient(token="fake-token")
    result = client.check_write_access(owner, repo, pr_number)
    
    assert result.status == WriteAccessStatus.GRANTED
    assert result.is_fine_grained_pat is True
    assert "verified via live test" in result.message


@respx.mock
def test_check_write_access_fine_grained_pat_live_test_denied():
    """Fine-grained PAT with failed live write test returns DENIED."""
    owner = "owner"
    repo = "repo"
    pr_number = 42
    
    # Mock repo endpoint (no X-OAuth-Scopes = fine-grained PAT)
    respx.get(f"https://api.github.com/repos/{owner}/{repo}").mock(
        return_value=Response(200, json={
            "id": 12345,
            "name": repo,
            "private": False,
            "permissions": {"admin": False, "push": True, "pull": True}
        })
    )
    
    # Mock 403 on reaction creation (token not configured for this repo)
    respx.post(f"https://api.github.com/repos/{owner}/{repo}/issues/{pr_number}/reactions").mock(
        return_value=Response(403, json={"message": "Resource not accessible by integration"})
    )
    
    client = GitHubClient(token="fake-token")
    result = client.check_write_access(owner, repo, pr_number)
    
    assert result.status == WriteAccessStatus.DENIED
    assert result.is_fine_grained_pat is True
    assert "write test failed" in result.message


@respx.mock
def test_check_write_access_fine_grained_pat_no_pr_number():
    """Fine-grained PAT without pr_number returns UNCERTAIN (can't do live test)."""
    owner = "owner"
    repo = "repo"
    
    # Mock repo endpoint (no X-OAuth-Scopes = fine-grained PAT)
    respx.get(f"https://api.github.com/repos/{owner}/{repo}").mock(
        return_value=Response(200, json={
            "id": 12345,
            "name": repo,
            "private": False,
            "permissions": {"admin": False, "push": True, "pull": True}
        })
    )
    
    client = GitHubClient(token="fake-token")
    # Don't pass pr_number - should return UNCERTAIN
    result = client.check_write_access(owner, repo)
    
    assert result.status == WriteAccessStatus.UNCERTAIN
    assert result.is_fine_grained_pat is True


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


# --- Tests for minimize_old_roadmap_comments ---

ROADMAP_PREFIX = "🗺️ **Auto-Generated Review Roadmap**"


@respx.mock
def test_minimize_old_roadmap_comments_no_comments():
    """Returns (0, 0) when there are no comments on the PR."""
    owner = "owner"
    repo = "repo"
    pr_number = 42
    
    url = f"https://api.github.com/repos/{owner}/{repo}/issues/{pr_number}/comments"
    respx.get(url).mock(return_value=Response(200, json=[]))
    
    client = GitHubClient(token="fake-token")
    minimized, errors = client.minimize_old_roadmap_comments(owner, repo, pr_number, ROADMAP_PREFIX)
    
    assert minimized == 0
    assert errors == 0


@respx.mock
def test_minimize_old_roadmap_comments_no_matching_comments():
    """Returns (0, 0) when no comments match the roadmap prefix."""
    owner = "owner"
    repo = "repo"
    pr_number = 42
    
    url = f"https://api.github.com/repos/{owner}/{repo}/issues/{pr_number}/comments"
    respx.get(url).mock(return_value=Response(200, json=[
        {
            "id": 1,
            "node_id": "IC_node1",
            "body": "This is a regular comment",
            "user": {"login": "user1"},
            "created_at": "2024-01-01T00:00:00Z"
        },
        {
            "id": 2,
            "node_id": "IC_node2",
            "body": "Another comment mentioning roadmap but not starting with prefix",
            "user": {"login": "user2"},
            "created_at": "2024-01-02T00:00:00Z"
        }
    ]))
    
    client = GitHubClient(token="fake-token")
    minimized, errors = client.minimize_old_roadmap_comments(owner, repo, pr_number, ROADMAP_PREFIX)
    
    assert minimized == 0
    assert errors == 0


@respx.mock
def test_minimize_old_roadmap_comments_success():
    """Successfully minimizes roadmap comments and ignores non-roadmap comments."""
    owner = "owner"
    repo = "repo"
    pr_number = 42
    
    comments_url = f"https://api.github.com/repos/{owner}/{repo}/issues/{pr_number}/comments"
    graphql_url = "https://api.github.com/graphql"
    
    # Mix of roadmap and non-roadmap comments
    respx.get(comments_url).mock(return_value=Response(200, json=[
        {
            "id": 1,
            "node_id": "IC_roadmap1",
            "body": f"{ROADMAP_PREFIX}\n\nOld roadmap content here",
            "user": {"login": "github-actions[bot]"},
            "created_at": "2024-01-01T00:00:00Z"
        },
        {
            "id": 2,
            "node_id": "IC_regular",
            "body": "Regular comment - should not be minimized",
            "user": {"login": "reviewer"},
            "created_at": "2024-01-02T00:00:00Z"
        },
        {
            "id": 3,
            "node_id": "IC_roadmap2",
            "body": f"{ROADMAP_PREFIX}\n\nAnother old roadmap",
            "user": {"login": "user1"},
            "created_at": "2024-01-03T00:00:00Z"
        }
    ]))
    
    # Mock GraphQL responses for both roadmap comments
    respx.post(graphql_url).mock(return_value=Response(200, json={
        "data": {
            "minimizeComment": {
                "minimizedComment": {"isMinimized": True}
            }
        }
    }))
    
    client = GitHubClient(token="fake-token")
    minimized, errors = client.minimize_old_roadmap_comments(owner, repo, pr_number, ROADMAP_PREFIX)
    
    # Should minimize 2 roadmap comments, not the regular one
    assert minimized == 2
    assert errors == 0


@respx.mock
def test_minimize_old_roadmap_comments_graphql_error():
    """Handles GraphQL errors gracefully and counts them."""
    owner = "owner"
    repo = "repo"
    pr_number = 42
    
    comments_url = f"https://api.github.com/repos/{owner}/{repo}/issues/{pr_number}/comments"
    graphql_url = "https://api.github.com/graphql"
    
    respx.get(comments_url).mock(return_value=Response(200, json=[
        {
            "id": 1,
            "node_id": "IC_roadmap1",
            "body": f"{ROADMAP_PREFIX}\n\nOld roadmap",
            "user": {"login": "user1"},
            "created_at": "2024-01-01T00:00:00Z"
        }
    ]))
    
    # Mock GraphQL error response
    respx.post(graphql_url).mock(return_value=Response(200, json={
        "errors": [{"message": "Could not resolve to a node with the global id"}]
    }))
    
    client = GitHubClient(token="fake-token")
    minimized, errors = client.minimize_old_roadmap_comments(owner, repo, pr_number, ROADMAP_PREFIX)
    
    assert minimized == 0
    assert errors == 1


@respx.mock
def test_minimize_old_roadmap_comments_http_error():
    """Handles HTTP errors on GraphQL endpoint gracefully."""
    owner = "owner"
    repo = "repo"
    pr_number = 42
    
    comments_url = f"https://api.github.com/repos/{owner}/{repo}/issues/{pr_number}/comments"
    graphql_url = "https://api.github.com/graphql"
    
    respx.get(comments_url).mock(return_value=Response(200, json=[
        {
            "id": 1,
            "node_id": "IC_roadmap1",
            "body": f"{ROADMAP_PREFIX}\n\nOld roadmap",
            "user": {"login": "user1"},
            "created_at": "2024-01-01T00:00:00Z"
        }
    ]))
    
    # Mock HTTP 403 error on GraphQL
    respx.post(graphql_url).mock(return_value=Response(403, json={
        "message": "Forbidden"
    }))
    
    client = GitHubClient(token="fake-token")
    minimized, errors = client.minimize_old_roadmap_comments(owner, repo, pr_number, ROADMAP_PREFIX)
    
    assert minimized == 0
    assert errors == 1


@respx.mock
def test_minimize_old_roadmap_comments_fetch_error():
    """Returns (0, 0) when fetching comments fails."""
    owner = "owner"
    repo = "repo"
    pr_number = 42
    
    comments_url = f"https://api.github.com/repos/{owner}/{repo}/issues/{pr_number}/comments"
    respx.get(comments_url).mock(return_value=Response(404, json={"message": "Not Found"}))
    
    client = GitHubClient(token="fake-token")
    minimized, errors = client.minimize_old_roadmap_comments(owner, repo, pr_number, ROADMAP_PREFIX)
    
    assert minimized == 0
    assert errors == 0


# --- Tests for find_working_token ---

from unittest.mock import patch
from review_roadmap.github.client import find_working_token, TokenSearchResult
from review_roadmap.models import WriteAccessResult


@respx.mock
def test_find_working_token_first_token_works():
    """find_working_token returns first token when it has write access."""
    owner = "owner"
    repo = "repo"
    pr_number = 42
    
    # Mock repo endpoint with push permission
    respx.get(f"https://api.github.com/repos/{owner}/{repo}").mock(
        return_value=Response(200, json={
            "id": 12345,
            "name": repo,
            "private": False,
            "permissions": {"admin": False, "push": True, "pull": True}
        }, headers={"X-OAuth-Scopes": "repo"})
    )
    
    with patch("review_roadmap.github.client.settings") as mock_settings:
        mock_settings.get_github_tokens.return_value = ["token1", "token2"]
        
        result = find_working_token(owner, repo, pr_number)
        
        assert result.token == "token1"
        assert result.access_result.status == WriteAccessStatus.GRANTED
        assert result.tokens_tried == 1


@respx.mock
def test_find_working_token_second_token_works():
    """find_working_token tries second token when first fails."""
    owner = "owner"
    repo = "repo"
    pr_number = 42
    
    # Track which token is being used via call count
    call_count = [0]
    
    def repo_response(request):
        call_count[0] += 1
        if call_count[0] == 1:
            # First token: no push permission
            return Response(200, json={
                "id": 12345,
                "name": repo,
                "private": False,
                "permissions": {"admin": False, "push": False, "pull": True}
            })
        else:
            # Second token: has push permission
            return Response(200, json={
                "id": 12345,
                "name": repo,
                "private": False,
                "permissions": {"admin": False, "push": True, "pull": True}
            }, headers={"X-OAuth-Scopes": "repo"})
    
    respx.get(f"https://api.github.com/repos/{owner}/{repo}").mock(side_effect=repo_response)
    
    with patch("review_roadmap.github.client.settings") as mock_settings:
        mock_settings.get_github_tokens.return_value = ["token1", "token2"]
        
        result = find_working_token(owner, repo, pr_number)
        
        assert result.token == "token2"
        assert result.access_result.status == WriteAccessStatus.GRANTED
        assert result.tokens_tried == 2


@respx.mock
def test_find_working_token_no_tokens_configured():
    """find_working_token returns None when no tokens configured."""
    owner = "owner"
    repo = "repo"
    pr_number = 42
    
    with patch("review_roadmap.github.client.settings") as mock_settings:
        mock_settings.get_github_tokens.return_value = []
        
        result = find_working_token(owner, repo, pr_number)
        
        assert result.token is None
        assert result.access_result.status == WriteAccessStatus.DENIED
        assert result.tokens_tried == 0
        assert "No GitHub tokens configured" in result.access_result.message


@respx.mock
def test_find_working_token_all_tokens_fail():
    """find_working_token returns None when all tokens fail."""
    owner = "owner"
    repo = "repo"
    pr_number = 42
    
    # All tokens have no push permission
    respx.get(f"https://api.github.com/repos/{owner}/{repo}").mock(
        return_value=Response(200, json={
            "id": 12345,
            "name": repo,
            "private": False,
            "permissions": {"admin": False, "push": False, "pull": True}
        })
    )
    
    with patch("review_roadmap.github.client.settings") as mock_settings:
        mock_settings.get_github_tokens.return_value = ["token1", "token2", "token3"]
        
        result = find_working_token(owner, repo, pr_number)
        
        assert result.token is None
        assert result.access_result.status == WriteAccessStatus.DENIED
        assert result.tokens_tried == 3


@respx.mock
def test_find_working_token_handles_invalid_token():
    """find_working_token handles invalid/revoked tokens gracefully."""
    owner = "owner"
    repo = "repo"
    pr_number = 42
    
    call_count = [0]
    
    def repo_response(request):
        call_count[0] += 1
        if call_count[0] == 1:
            # First token is invalid
            return Response(401, json={"message": "Bad credentials"})
        else:
            # Second token works
            return Response(200, json={
                "id": 12345,
                "name": repo,
                "private": False,
                "permissions": {"admin": False, "push": True, "pull": True}
            }, headers={"X-OAuth-Scopes": "repo"})
    
    respx.get(f"https://api.github.com/repos/{owner}/{repo}").mock(side_effect=repo_response)
    
    with patch("review_roadmap.github.client.settings") as mock_settings:
        mock_settings.get_github_tokens.return_value = ["bad-token", "good-token"]
        
        result = find_working_token(owner, repo, pr_number)
        
        assert result.token == "good-token"
        assert result.access_result.status == WriteAccessStatus.GRANTED
        assert result.tokens_tried == 2
