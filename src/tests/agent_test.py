from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# Fix UnicodeEncodeError on Windows cp1252 terminals when printing MCP results
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import asyncio

from langchain_core.messages import HumanMessage, AIMessage, ToolMessage

from agent.graph import graph
from agent.tools import mcp_client


async def main():

    try:
        await mcp_client.connect()

        result = await graph.ainvoke(
            {
                "messages": [
                    HumanMessage(
                        content="List the commits in Lomesh2000/hadoop."
                    )
                ]
            },
            config={
                "configurable": {
                    "thread_id": "agent-test"
                }
            },
        )

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
        # Always runs — even if connect() or graph.ainvoke() fails —
        # so the stdio contexts are closed cleanly from this task.
        await mcp_client.close()


if __name__ == "__main__":
    asyncio.run(main())