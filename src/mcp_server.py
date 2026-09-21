from mcp.server.mcpserver import MCPServer
import os
from github import Github, GithubException

from src.rag.pipeline import RAGPipeline
from pathlib import Path

github_client = Github(os.environ.get("GITHUB_TOKEN"))
server = MCPServer("engineering-knowledge")

rag = None


def get_rag():
    global rag
    if rag is None:
        rag = RAGPipeline("docs")
    return rag


@server.tool()
def search_docs(query: str) -> str:
    """
    Search the engineering knowledge base for relevant documentation.

    Use this tool when the user asks about system architecture,
    engineering decisions, runbooks, security, infrastructure,
    or other information contained in the documentation.
    """

    results = get_rag().search(query, k=5)

    if not results:
        return "No relevant information found."

    output = []

    for score, idx in results:
        chunk = rag.chunks[idx]
        output.append(
            f"[SOURCE: {chunk['source']}]\n"
            f"[RELEVANCE: {score:.3f}]\n"
            f"{chunk['text']}"
        )

    return "\n\n".join(output)

@server.tool()
def list_decisions() -> str:
    """
    List the architecture decision record (ADR) files available
    in the engineering knowledge base.

    ALWAYS use this tool when the user asks:
    - What architecture decisions are available?
    - What ADRs exist?
    - List the architecture decisions.
    - List the ADRs.
    - Show all architecture decisions.
    - Which engineering decisions have been documented?
    """

    decisions_dir = Path("docs/decisions")

    if not decisions_dir.exists():
        return "No architecture decisions found."

    decisions = sorted(decisions_dir.glob("*.md"))

    if not decisions:
        return "No architecture decisions found."

    return "\n".join(f"- {path}" for path in decisions)

@server.tool()
def get_document(path: str) -> str:
    """
    Read a specific engineering documentation file.

    Use this when you need the complete contents of a known
    document or architecture decision record.
    """
    file_path = Path(path)

    if not file_path.exists():
        return f"Document not found: {path}"

    if not file_path.is_file():
        return f"Not a file: {path}"

    return file_path.read_text(encoding="utf-8")

@server.tool()
def get_github_file(owner: str, repo: str, path: str) -> str:
    """
    Read a file from a GitHub repository.

    Use this when the user asks about the contents of a specific
    file in a GitHub repository.
    """
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        return "GitHub access is unavailable because GITHUB_TOKEN is not configured."

    try:
        repository = github_client.get_repo(f"{owner}/{repo}")
        file = repository.get_contents(path)

        if isinstance(file, list):
            return f"{path} is a directory, not a file."

        content = file.decoded_content.decode("utf-8")

        return (
            f"[REPOSITORY: {owner}/{repo}]\n"
            f"[PATH: {path}]\n\n"
            f"{content}"
        )
    except GithubException as exc:
        status = getattr(exc, "status", "unknown")
        message = exc.data.get("message", str(exc)) if hasattr(exc, "data") else str(exc)
        return f"GitHub access error for {owner}/{repo} at {path}: {status} {message}"
    except Exception as exc:
        return f"GitHub lookup failed for {owner}/{repo} at {path}: {exc}"

@server.tool()
async def search_github(owner: str, repo: str, query: str) -> str:
    """
    Search for code/files inside a specific GitHub repository.
    """
    search_query = f"{query} repo:{owner}/{repo}"

    results = github_client.search_code(search_query)

    matches = []

    for i, item in enumerate(results):
        if i >= 10:
            break
        matches.append(
            f"[REPOSITORY: {item.repository.full_name}]\n"
            f"[PATH: {item.path}]\n"
            f"[URL: {item.html_url}]"
        )

    if not matches:
        return "No matching files found."

    return "\n\n".join(matches)

@server.tool()
def list_github_files(owner: str, repo: str) -> str:
    """
    List files in the root of a GitHub repository.
    """
    repository = github_client.get_repo(f"{owner}/{repo}")

    contents = repository.get_contents("")

    files = []

    for item in contents:
        files.append(
            f"[TYPE: {item.type}]\n"
            f"[PATH: {item.path}]\n"
            f"[URL: {item.html_url}]"
        )

    if not files:
        return "No files found."

    return "\n\n".join(files)

@server.tool()
def list_github_issues(owner: str, repo: str) -> str:
    """
    List open issues in a GitHub repository.
    """
    repository = github_client.get_repo(f"{owner}/{repo}")

    issues = repository.get_issues(state="open")

    results = []

    for i, issue in enumerate(issues):
        if i >= 10:
            break

        results.append(
            f"[ISSUE #{issue.number}]\n"
            f"[TITLE: {issue.title}]\n"
            f"[URL: {issue.html_url}]"
        )

    if not results:
        return "No open issues found."

    return "\n\n".join(results)

@server.tool()
def list_github_prs(owner: str, repo: str) -> str:
    """
    List open pull requests in a GitHub repository.
    """
    repository = github_client.get_repo(f"{owner}/{repo}")

    prs = repository.get_pulls(state="open")

    results = []

    for i, pr in enumerate(prs):
        if i >= 10:
            break

        results.append(
            f"[PR #{pr.number}]\n"
            f"[TITLE: {pr.title}]\n"
            f"[AUTHOR: {pr.user.login}]\n"
            f"[URL: {pr.html_url}]"
        )

    if not results:
        return "No open pull requests found."

    return "\n\n".join(results)

if __name__ == "__main__":
    server.run()
