import hashlib
from review_roadmap.models import FileDiff

def test_get_pr_diff_link():
    """Verifies that the PR diff link uses the correct SHA256 hash formatting."""
    repo_url = "https://github.com/owner/repo"
    pr_number = 123
    
    # Case 1: Standard file
    file_path = "src/main.py"
    diff = FileDiff(path=file_path, status="modified", additions=10, deletions=5, diff_content="...")
    
    link = diff.get_pr_diff_link(repo_url, pr_number)
    
    expected_hash = hashlib.sha256(file_path.encode("utf-8")).hexdigest()
    expected_link = f"{repo_url}/pull/{pr_number}/files#diff-{expected_hash}"
    
    assert link == expected_link
    
def test_get_pr_diff_link_unicode():
    """Verifies hashing works for unicode paths."""
    repo_url = "https://github.com/owner/repo"
    pr_number = 123
    file_path = "src/🚀.py"
    
    diff = FileDiff(path=file_path, status="modified", additions=1, deletions=1, diff_content="...")
    
    link = diff.get_pr_diff_link(repo_url, pr_number)
    
    expected_hash = hashlib.sha256(file_path.encode("utf-8")).hexdigest()
    assert link.endswith(f"#diff-{expected_hash}")
