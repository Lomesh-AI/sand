import asyncio
import os

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


class MCPClient:

    def __init__(self):
        self.server_params = StdioServerParameters(
            command="python",
            args=["-m", "src.mcp_server"],
            env={"GITHUB_TOKEN": token} if (token := os.environ.get("GITHUB_TOKEN")) else {},
        )

        self.read = None
        self.write = None
        self.session = None

    async def connect(self):
        self.stdio = stdio_client(self.server_params)

        self.read, self.write = await self.stdio.__aenter__()

        self.session = ClientSession(
            self.read,
            self.write,
        )

        await self.session.__aenter__()
        await self.session.initialize()

    async def search_docs(self, query: str) -> str:
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

    async def close(self):
        if self.session:
            await self.session.__aexit__(None, None, None)

        if self.stdio:
            await self.stdio.__aexit__(None, None, None)
    
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
    
    async def list_github_files(self, owner: str, repo: str) -> str:
        result = await self.session.call_tool(
            "list_github_files",
            {"owner": owner, "repo": repo},
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