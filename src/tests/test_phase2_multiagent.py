"""Test script to trace Phase 2 Multi-Agent Graph:
1. Direct Greeting / Non-tool query (Supervisor -> END)
2. Architecture / ADR query (Supervisor -> Docs Specialist -> Tools -> Docs -> Supervisor -> END)
3. GitHub / PR query (Supervisor -> GitHub Specialist -> Tools -> GitHub -> Supervisor -> END)
"""

from pathlib import Path
import sys
import os
import uuid

# Set root path to sand/
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# Fix UnicodeEncodeError on Windows cp1252 terminals
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import asyncio
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage

from agent.graph import graph
from agent.tools import mcp_client


async def run_traced_query(title: str, query: str):
    print("\n" + "=" * 65)
    print(f"TEST CASE: {title}")
    print(f"USER QUERY: {query!r}")
    print("=" * 65)

    thread_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}

    step_num = 1
    async for event in graph.astream(
        {"messages": [HumanMessage(content=query)]},
        config=config,
        stream_mode="updates",
    ):
        for node_name, node_output in event.items():
            print(f"\n[Step {step_num}] Node Executed: >>> {node_name} <<<")
            step_num += 1

            if "next_step" in node_output:
                print(f"  Router Next Step: {node_output.get('next_step')}")

            if "messages" in node_output and node_output["messages"]:
                last_msg = node_output["messages"][-1]
                if isinstance(last_msg, AIMessage):
                    if last_msg.tool_calls:
                        for tc in last_msg.tool_calls:
                            print(f"  Tool Call Requested: {tc['name']} with args {tc['args']}")
                    elif last_msg.content:
                        preview = last_msg.content.strip().split("\n")[0]
                        print(f"  AIMessage Content: {preview[:120]}...")
                elif isinstance(last_msg, ToolMessage):
                    preview = str(last_msg.content).strip().split("\n")[0]
                    print(f"  ToolMessage Result: {preview[:120]}...")

    # Fetch final state to print the final answer
    state = await graph.aget_state(config)
    final_messages = state.values.get("messages", [])
    if final_messages:
        final_ai = [m for m in final_messages if isinstance(m, AIMessage) and m.content and not m.tool_calls]
        if final_ai:
            print("\n--- FINAL SYNTHESIZED RESPONSE ---")
            print(final_ai[-1].content)
            print("----------------------------------")

    print(f"[OK] Completed: {title}\n")


async def main():
    print("\n" + "#" * 65)
    print("### RUNNING PHASE 2 MULTI-AGENT GRAPH VERIFICATION & TRACE ###")
    print("#" * 65)

    print("\n[Init] Connecting MCP client...")
    try:
        await mcp_client.connect()
        print("[Init] MCP client connected successfully.\n")

        # Test Case 1: Direct conversation (No tools needed)
        await run_traced_query(
            title="1. Direct Greeting / Non-tool query",
            query="Hello! What are your capabilities as the engineering supervisor?",
        )

        await asyncio.sleep(2.5)

        # Test Case 2: Documentation / Architecture Query
        await run_traced_query(
            title="2. Architecture / ADR Documentation Query",
            query="What architecture decision records (ADRs) exist in this project?",
        )

        await asyncio.sleep(2.5)

        # Test Case 3: GitHub Repository Query
        await run_traced_query(
            title="3. GitHub Repository & PR Query",
            query="List the open pull requests in repository Lomesh-AI/sand.",
        )

    finally:
        print("\n[Teardown] Closing MCP client...")
        await mcp_client.close()
        print("[Teardown] MCP client closed.")

    print("\n" + "=" * 65)
    print("ALL PHASE 2 MULTI-AGENT TESTS COMPLETED")
    print("=" * 65 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
