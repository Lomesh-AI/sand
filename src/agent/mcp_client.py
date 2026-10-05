from contextlib import AsyncExitStack
import os
from pathlib import Path
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


class MCPClient:

    def __init__(self):
        project_root = Path(__file__).resolve().parents[2]  # E:\agentic\sand
        server_script = project_root / "src" / "mcp_server.py"

        # Check virtualenv in E:\agentic\.venv or fallback to current sys.executable
        venv_python = project_root.parent / ".venv" / "Scripts" / "python.exe"
        python_exe = str(venv_python if venv_python.exists() else sys.executable)

        self.server_params = StdioServerParameters(
            command=python_exe,
            args=["-u", str(server_script)],
            cwd=str(project_root),
            env={**os.environ, "PYTHONUNBUFFERED": "1", "PYTHONIOENCODING": "utf-8"},
        )

        self.exit_stack = AsyncExitStack()
        self.session = None
        self.read = None
        self.write = None

    async def connect(self):
        log_file = Path(__file__).resolve().parents[2] / "server_stderr.log"
        errlog = open(log_file, "w", encoding="utf-8")
        self.exit_stack.callback(errlog.close)

        self.read, self.write = await self.exit_stack.enter_async_context(
            stdio_client(self.server_params, errlog=errlog)
        )

        self.session = await self.exit_stack.enter_async_context(
            ClientSession(self.read, self.write)
        )

        try:
            await self.session.initialize()
            print("[mcp_client] connected", flush=True)
        except Exception:
            errlog.flush()
            err_content = log_file.read_text(encoding="utf-8", errors="replace")
            print(
                f"\n[mcp_client] FAILED TO INITIALIZE SERVER!\n"
                f"--- Subprocess Command ---\n"
                f"{self.server_params.command} {' '.join(self.server_params.args)}\n"
                f"--- Subprocess Stderr ({log_file}) ---\n"
                f"{err_content}\n"
                f"-----------------------------------------\n",
                file=sys.stderr,
                flush=True,
            )
            raise

    async def search_docs(self, query: str) -> str:
        print(f"[mcp_client] search_docs entry query={query!r}", flush=True)

        result = await self.session.call_tool(
            "search_docs",
            {"query": query},
        )

        return result.content[0].text

    async def list_decisions(self) -> str:
        result = await self.session.call_tool(
            "list_decisions",
            {},
        )
        return result.content[0].text

    async def get_document(self, path: str) -> str:
        result = await self.session.call_tool(
            "get_document",
            {"path": path},
        )
        return result.content[0].text

    async def get_github_file(self, owner: str, repo: str, path: str) -> str:
        result = await self.session.call_tool(
            "get_github_file",
            {
                "owner": owner,
                "repo": repo,
                "path": path,
            },
        )
        return result.content[0].text

    async def search_github(
        self,
        owner: str,
        repo: str,
        query: str,
    ) -> str:
        result = await self.session.call_tool(
            "search_github",
            {
                "owner": owner,
                "repo": repo,
                "query": query,
            },
        )
        return result.content[0].text

    async def list_github_files(self, owner: str, repo: str, path: str = "") -> str:
        args = {"owner": owner, "repo": repo}
        if path:
            args["path"] = path
        result = await self.session.call_tool(
            "list_github_files",
            args,
        )
        return result.content[0].text

    async def list_github_issues(self, owner: str, repo: str) -> str:
        result = await self.session.call_tool(
            "list_github_issues",
            {"owner": owner, "repo": repo},
        )
        return result.content[0].text

    async def list_github_prs(self, owner: str, repo: str) -> str:
        result = await self.session.call_tool(
            "list_github_prs",
            {"owner": owner, "repo": repo},
        )
        return result.content[0].text

    async def close(self):
        await self.exit_stack.aclose()
        self.session = None
        self.read = None
        self.write = None
        print("[mcp_client] disconnected", flush=True)