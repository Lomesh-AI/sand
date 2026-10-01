from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import asyncio

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def main():
    server_params = StdioServerParameters(
        command="python",
        args=["-m", "src.mcp_server"],
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:

            await session.initialize()

            print("TOOLS:")
            tools = await session.list_tools()

            for tool in tools.tools:
                print("-", tool.name)

            print("\nCALLING:")
            result = await session.call_tool(
                "get_github_file",
                {
                    "owner": "Lomesh-AI",
                    "repo": "sand",
                    "path": "README.md",
                },
            )

            print("\nRESULT:")
            print(result)


if __name__ == "__main__":
    asyncio.run(main())