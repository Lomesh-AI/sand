import asyncio
import os
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def main():

    server_params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "src.mcp_server"],
        env={"GITHUB_TOKEN": token} if (token := os.environ.get("GITHUB_TOKEN")) else {},
    )

    async with stdio_client(server_params) as (read, write):

        async with ClientSession(read, write) as session:

            # Initialize MCP connection
            print("Connecting to MCP server...", flush=True)
            await asyncio.wait_for(session.initialize(), timeout=10)

            # Ask server what tools it provides
            print("Requesting tool list...", flush=True)
            tools = await session.list_tools()

            print("\nAVAILABLE TOOLS:")
            for tool in tools.tools:
                print("-", tool.name)
                print(" ", tool.description)

            # Call our tool
            # result = await session.call_tool(
            #     "search_docs",
            #     {
            #         "query": "Why was RabbitMQ selected?"
            #     }
            # )

            # print("\nTOOL RESULT:")
            # print(result.content)

            # result = await session.call_tool(
            #     "list_decisions",
            #     {}
            # )

            # print("\nDECISIONS:")
            # print(result.content)

            # # github tool
            # result = await session.call_tool(
            #     "get_github_file",
            #     {
            #         "owner": "Lomesh-AI",
            #         "repo": "sand",
            #         "path": "README.md",
            #     },
            # )

            
            # print("\nGITHUB FILE:")
            # print(result.content[0].text)

            # search github
            print("Calling GitHub search...", flush=True)

            try:
                result = await session.call_tool(
                    "search_github",
                    {
                        "owner": "Lomesh-AI",
                        "repo": "sand",
                        "query": "authentication",
                    },
                )

                print("\nGITHUB SEARCH:")
                print(result.content[0].text)

            except Exception as e:
                print("GITHUB SEARCH ERROR:", repr(e), flush=True)

if __name__ == "__main__":
    asyncio.run(main())