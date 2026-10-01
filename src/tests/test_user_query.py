import os
import sys
import uuid
import asyncio
from pathlib import Path
from dotenv import load_dotenv

SRC_DIR = Path(__file__).resolve().parents[1]
load_dotenv(SRC_DIR / ".env")

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
from src.agent.graph import graph
from src.agent.tools import mcp_client

async def test_query():
    print("[Init] Connecting MCP client...")
    await mcp_client.connect()
    print("[Init] Connected.")

    query = "What are the security requirements and authentication mechanisms in this system?"
    thread_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}

    step = 0
    try:
        async for event in graph.astream(
            {"messages": [HumanMessage(content=query)]},
            config=config,
            stream_mode="updates",
        ):
            step += 1
            for node, output in event.items():
                print(f"\n--- [Step {step}] Node: {node} ---")
                if "messages" in output:
                    for m in output["messages"]:
                        if isinstance(m, AIMessage):
                            if m.tool_calls:
                                print(f"  Tool calls: {[tc['name'] for tc in m.tool_calls]}")
                            else:
                                print(f"  AI content: {m.content[:100]}...")
                        elif isinstance(m, ToolMessage):
                            print(f"  Tool result: {str(m.content)[:100]}...")
                if step > 15:
                    print("\n[LOOP DETECTED] Step exceeded 15! Stopping test.")
                    return
    finally:
        await mcp_client.close()

if __name__ == "__main__":
    asyncio.run(test_query())
