from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))

from mcp.server.mcpserver import MCPServer
import os
from github import Github, GithubException

github_token = os.environ.get("GITHUB_TOKEN")
github_client = Github(github_token if github_token else None)
print(
    "MCP GITHUB_TOKEN:",
    bool(github_token),
    file=sys.stderr,
    flush=True
)
server = MCPServer("engineering-knowledge")

rag = None


def get_rag():
    global rag
    if rag is None:
        from rag.pipeline import RAGPipeline

        rag = RAGPipeline("docs")
    return rag


# @server.tool()
# def search_docs(query: str) -> str:
#     """
#     Search the engineering knowledge base for relevant documentation.

#     Use this tool when the user asks about system architecture,
#     engineering decisions, runbooks, security, infrastructure,
#     or other information contained in the documentation.
#     """

#     try:
#         pipeline = get_rag()
#         results = pipeline.search(query, k=5)

#         if not results:
#             return "No relevant information found."

#         output = []
#         for score, idx in results:
#             chunk = pipeline.chunks[int(idx)]
#             output.append(
#                 f"[SOURCE: {chunk['source']}]\n"
#                 f"[RELEVANCE: {float(score):.3f}]\n"
#                 f"{chunk['text']}"
#             )

#         return "\n\n".join(output)
#     except Exception as exc:
#         return f"search_docs failed: {type(exc).__name__}: {exc}"

@server.tool()
def search_docs(query: str) -> str:
    import traceback
    import sys

    try:
        print("[search_docs] starting RAG", file=sys.stderr, flush=True)

        pipeline = get_rag()

        print("[search_docs] RAG initialized", file=sys.stderr, flush=True)

        results = pipeline.search(query, k=5)

        print("[search_docs] search completed", file=sys.stderr, flush=True)

        if not results:
            return "No relevant information found."

        output = []

        for score, idx in results:
            chunk = pipeline.chunks[int(idx)]
            output.append(
                f"[SOURCE: {chunk['source']}]\n"
                f"[RELEVANCE: {float(score):.3f}]\n"
                f"{chunk['text']}"
            )

        return "\n\n".join(output)

    except Exception as exc:
        traceback.print_exc(file=sys.stderr)
        return f"search_docs failed: {type(exc).__name__}: {exc}"

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
    try:
        repository = github_client.get_repo(f"{owner}/{repo}")
        contents = repository.get_contents("")

        files = []
        for item in contents:
            files.append(
                f"[TYPE: {item.type}]\n"
                f"[PATH: {item.path}]\n"
                f"[URL: {item.html_url or 'N/A'}]"
            )

        if not files:
            return "No files found."

        return "\n\n".join(files)
    except GithubException as exc:
        status = getattr(exc, "status", "unknown")
        message = exc.data.get("message", str(exc)) if hasattr(exc, "data") else str(exc)
        return f"GitHub error listing files for {owner}/{repo}: {status} {message}"
    except Exception as exc:
        return f"Failed to list files for {owner}/{repo}: {type(exc).__name__}: {exc}"

@server.tool()
def list_github_issues(owner: str, repo: str) -> str:
    """
    List open issues in a GitHub repository.
    """
    try:
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
    except GithubException as exc:
        status = getattr(exc, "status", "unknown")
        message = exc.data.get("message", str(exc)) if hasattr(exc, "data") else str(exc)
        return f"GitHub error listing issues for {owner}/{repo}: {status} {message}"
    except Exception as exc:
        return f"Failed to list issues for {owner}/{repo}: {type(exc).__name__}: {exc}"

# @server.tool()
# def list_github_prs(owner: str, repo: str) -> str:
#     """
#     List open pull requests in a GitHub repository.
#     """
#     repository = github_client.get_repo(f"{owner}/{repo}")

#     prs = repository.get_pulls(state="open")

#     results = []

#     for i, pr in enumerate(prs):
#         if i >= 10:
#             break

#         results.append(
#             f"[PR #{pr.number}]\n"
#             f"[TITLE: {pr.title}]\n"
#             f"[AUTHOR: {pr.user.login}]\n"
#             f"[URL: {pr.html_url}]"
#         )

#     if not results:
#         return "No open pull requests found."

#     return "\n\n".join(results)

@server.tool()
def list_github_prs(owner: str, repo: str) -> str:
    print(
    ">>> list_github_prs ENTERED",
    owner,
    repo,
    file=sys.stderr,
    flush=True,
    )
    try:
        repository = github_client.get_repo(f"{owner}/{repo}")

        prs = repository.get_pulls(state="open")

        results = []

        for pr in prs:
            results.append(
                f"#{pr.number} {pr.title}\n"
                f"Author: {pr.user.login}\n"
                f"URL: {pr.html_url}"
            )

        if not results:
            return "No open pull requests."

        return "\n\n".join(results)

    except Exception as exc:
        import traceback
        traceback.print_exc()
        return f"ERROR: {type(exc).__name__}: {exc}"

if __name__ == "__main__":
    print("MCP SERVER STARTING", file=sys.stderr, flush=True)

    import threading

    def _warmup():
        try:
            get_rag()
            print("RAG PIPELINE READY", file=sys.stderr, flush=True)
        except Exception as exc:
            print(f"Warning: RAG warm-up failed: {exc}", file=sys.stderr, flush=True)

    threading.Thread(target=_warmup, daemon=True).start()

    try:
        server.run()
    except Exception:
        import traceback
        traceback.print_exc(file=sys.stderr)
        raise
