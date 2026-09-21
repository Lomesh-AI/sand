import asyncio
import os

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def main():

    server_params = StdioServerParameters(
        command="python",
        args=["-m", "src.mcp_server"],
        env={"GITHUB_TOKEN": token} if (token := os.environ.get("GITHUB_TOKEN")) else {},
    )

    async with stdio_client(server_params) as (read, write):

        async with ClientSession(read, write) as session:

            # Initialize MCP connection
            await session.initialize()

            # Ask server what tools it provides
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
            result = await session.call_tool(
                "search_github",
                {"query": "authentication"},
            )

            print("\nGITHUB SEARCH:")
            print(result.content[0].text)

if __name__ == "__main__":
    asyncio.run(main())