from langchain_core.tools import tool
from .mcp_client import MCPClient
import datetime
import asyncio

mcp_client = MCPClient()


@tool
async def search_knowledge(query: str) -> str:
    """
    Search the engineering knowledge base for relevant documentation.

    Use this tool when the user asks about system architecture,
    engineering decisions, runbooks, security, infrastructure,
    or other information contained in the documentation.
    """
    # rag = RAGPipeline("docs")
    # results = rag.search(query, k=5)

    # if not results:
    #     return "No relevant information found in the knowledge base."

    # context = []

    # for score, idx in results:
    #     chunk = rag.chunks[idx]
    #     context.append(
    #         f"[SOURCE: {chunk['source']}]\n"
    #         f"[RELEVANCE: {score:.3f}]\n"
    #         f"{chunk['text']}"
    #     )

    # return "\n\n".join(context)
    print(f"[tool] search_knowledge entry query={query!r}", flush=True)
    print(
        f"[tool] MCP session connected={mcp_client.session is not None}",
        flush=True,
    )
    result = await mcp_client.search_docs(query)
    print("[tool] search_knowledge return", flush=True)
    return result

@tool
async def get_current_time() -> str:
    """
    Get the current date and time.
    Use this when the user asks what time or date it is.
    """

    return datetime.datetime.now().astimezone().isoformat()

# @tool
# def search_github(query: str) -> str:
#     """
#     Search GitHub repositories, issues, pull requests, and source code.
#     """

#     return f"GitHub search requested for: {query}"

@tool
async def list_decisions() -> str:
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
    return await mcp_client.list_decisions()

@tool
async def get_document(path: str) -> str:
    """
    Read the complete contents of a specific engineering document.
    """
    return await mcp_client.get_document(path)

@tool
async def get_github_file(owner: str, repo: str, path: str) -> str:
    """
    Read a specific file from a GitHub repository.
    """
    return await mcp_client.get_github_file(owner, repo, path)

@tool
async def search_github(
        owner: str,
        repo: str,
        query: str,
    ) -> str:
    """
    Search for code/files inside a specific GitHub repository.
    """
    return await mcp_client.search_github(owner, repo, query)

@tool
async def list_github_files(owner: str, repo: str) -> str:
    """
    List all files in a specific GitHub repository.
    """
    return await mcp_client.list_github_files(owner, repo)

@tool
async def list_github_issues(owner: str, repo: str) -> str:
    """
    List open issues in a specific GitHub repository.
    """
    return await mcp_client.list_github_issues(owner, repo)

@tool
async def list_github_prs(owner: str, repo: str) -> str:
    """
    List open pull requests in a specific GitHub repository."""
    return await mcp_client.list_github_prs(owner, repo)