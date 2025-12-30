import typer
from rich.console import Console
from rich.markdown import Markdown
from review_roadmap.github.client import GitHubClient
from review_roadmap.agent.graph import build_graph

app = typer.Typer()
console = Console()

@app.command()
def generate(
    pr_url: str = typer.Argument(..., help="GitHub PR URL (e.g., owner/repo/123) or 'owner/repo/123' string"),
    output: str = typer.Option(None, "--output", "-o", help="Output file for the roadmap")
):
    """Generates a review roadmap for a given Pull Request."""
    
    # Parse PR identifier
    try:
        if "github.com" in pr_url:
            parts = pr_url.rstrip("/").split("/")
            pr_number = int(parts[-1])
            repo = parts[-3]
            owner = parts[-4]
        else:
            owner, repo, pr_number = pr_url.split("/")
            pr_number = int(pr_number)
    except Exception:
        console.print("[red]Invalid PR format. Use 'owner/repo/number' or a full URL.[/red]")
        raise typer.Exit(code=1)

    console.print(f"[bold blue]Fetching PR {owner}/{repo}#{pr_number}...[/bold blue]")
    
    # 1. Fetch Context
    gh_client = GitHubClient()
    try:
        pr_context = gh_client.get_pr_context(owner, repo, pr_number)
    except Exception as e:
        console.print(f"[red]Error fetching PR data: {e}[/red]")
        raise typer.Exit(code=1)

    console.print(f"[green]Found PR: {pr_context.metadata.title} (Changed files: {len(pr_context.files)})[/green]")

    # 2. Run LangGraph
    console.print("[bold purple]Generating Roadmap (this may take a minute)...[/bold purple]")
    graph = build_graph()
    initial_state = {"pr_context": pr_context}
    
    result = graph.invoke(initial_state)
    roadmap_content = result.get("roadmap", "")

    # 3. Output
    if output:
        with open(output, "w", encoding="utf-8") as f:
            f.write(roadmap_content)
        console.print(f"[bold green]Roadmap saved to {output}[/bold green]")
    else:
        console.print("\n[bold]--- Generated Roadmap ---[/bold]\n")
        console.print(Markdown(roadmap_content))

if __name__ == "__main__":
    app()
