from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import asyncio

from langchain_core.messages import HumanMessage, AIMessage, ToolMessage

from agent.graph import graph
from agent.tools import mcp_client


async def main():

    await mcp_client.connect()

    try:
        result = await graph.ainvoke({
            "messages": [
                HumanMessage(
                    content="List the open pull requests in Lomesh-AI/sand."
                )
            ]
        })

        print("\n========== TRACE ==========\n")

        for message in result["messages"]:

            if isinstance(message, HumanMessage):
                print("USER:")
                print(message.content)

            elif isinstance(message, AIMessage):

                if message.tool_calls:
                    print("\nLLM → TOOL CALL")

                    for call in message.tool_calls:
                        print(f"Tool : {call['name']}")
                        print(f"Args : {call['args']}")

                elif message.content:
                    print("\nLLM → FINAL ANSWER")
                    print(message.content)

            elif isinstance(message, ToolMessage):
                print("\nTOOL → LLM")
                print(f"Tool : {message.name}")
                print("Result:")
                print(message.content)

        print("\n========== END TRACE ==========\n")

    finally:
        await mcp_client.close()


if __name__ == "__main__":
    asyncio.run(main())