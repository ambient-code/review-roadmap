import sys
import os

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from review_roadmap.github.client import GitHubClient

def verify_pr_links(owner: str, repo: str, pr_number: int):
    client = GitHubClient()
    print(f"Fetching PR {owner}/{repo}#{pr_number}...")
    
    try:
        ctx = client.get_pr_context(owner, repo, pr_number)
    except Exception as e:
        print(f"Error fetching PR: {e}")
        return

    print(f"\nTitle: {ctx.metadata.title}")
    print(f"Author: {ctx.metadata.author}")
    print(f"Head SHA: {ctx.metadata.head_commit_sha}")
    print(f"Repo URL: {ctx.metadata.repo_url}")
    print("-" * 50)
    
    print(f"Files Changed: {len(ctx.files)}\n")
    
    for f in ctx.files[:3]:  # Show first 3 files
        print(f"File: {f.path} ({f.status})")
        link = f.get_github_link(ctx.metadata.repo_url, ctx.metadata.head_commit_sha, start_line=1)
        print(f"Link to Line 1: {link}")
        print("-" * 30)

if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("Usage: python verify_links.py owner repo pr_number")
        sys.exit(1)
        
    verify_pr_links(sys.argv[1], sys.argv[2], int(sys.argv[3]))
