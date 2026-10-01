"""Test script to trace Phase 3: Web API & NDJSON Streaming of Multi-Agent Events:
1. Greeting streaming (/chat -> NDJSON answer)
2. Architecture & tool streaming (/chat -> status -> tool_call -> tool_result -> answer)
"""

from pathlib import Path
import sys
import os
import json

# Set root path to sand/
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# Fix UnicodeEncodeError on Windows cp1252 terminals
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import asyncio
from httpx import AsyncClient, ASGITransport

from api import app
from agent.tools import mcp_client


async def run_api_stream_test(client: AsyncClient, title: str, message: str):
    print("\n" + "=" * 65)
    print(f"API TEST CASE: {title}")
    print(f"REQUEST PAYLOAD: {{'message': {message!r}}}")
    print("=" * 65)

    events_received = []

    async with client.stream("POST", "/chat", json={"message": message}, timeout=60.0) as response:
        assert response.status_code == 200, f"Expected 200 OK, got {response.status_code}"
        assert "application/x-ndjson" in response.headers.get("content-type", "")

        print("\nStreaming response chunks:")
        async for line in response.aiter_lines():
            line = line.strip()
            if not line:
                continue

            try:
                data = json.loads(line)
                events_received.append(data)
                event_type = data.get("type")

                if event_type == "status":
                    print(f"  [STREAM STATUS]    : {data.get('content')}")
                elif event_type == "tool_call":
                    agent = data.get("agent", "unknown")
                    tool = data.get("tool", "unknown")
                    print(f"  [STREAM TOOL CALL] : Agent={agent} | Tool={tool}")
                elif event_type == "tool_result":
                    print(f"  [STREAM TOOL RESULT]: Tool finished execution")
                elif event_type == "answer":
                    preview = data.get("content", "").strip().split("\n")[0]
                    print(f"  [STREAM ANSWER]    : {preview[:100]}...")
                else:
                    print(f"  [STREAM UNKNOWN]   : {data}")

            except json.JSONDecodeError:
                print(f"  [RAW LINE - NOT JSON]: {line}")

    # Summary checks
    types = [e.get("type") for e in events_received]
    print(f"\nSummary of events captured ({len(events_received)} total): {types}")
    assert "answer" in types, "No 'answer' event received from stream!"

    # Print final answer
    final_answer = [e.get("content") for e in events_received if e.get("type") == "answer"]
    if final_answer:
        print("\n--- FINAL ANSWER DELIVERED TO CLIENT ---")
        print(final_answer[-1])
        print("----------------------------------------")

    print(f"[OK] Completed: {title}\n")


async def main():
    print("\n" + "#" * 65)
    print("### RUNNING PHASE 3 API STREAMING VERIFICATION & TRACE ###")
    print("#" * 65)

    print("\n[Init] Connecting MCP client...")
    try:
        await mcp_client.connect()
        print("[Init] MCP client connected.\n")

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Test 1: Direct greeting (Supervisor answers directly)
            await run_api_stream_test(
                client=client,
                title="1. Direct Non-tool Greeting Stream",
                message="Hi! What can the engineering multi-agent system do?",
            )

            await asyncio.sleep(2.5)

            # Test 2: Multi-agent Tool execution Stream (Supervisor -> Specialist -> Tool -> Answer)
            await run_api_stream_test(
                client=client,
                title="2. Architecture / ADR Stream with Tool Execution",
                message="What architecture decision records (ADRs) exist in this project?",
            )

    finally:
        print("\n[Teardown] Closing MCP client...")
        await mcp_client.close()
        print("[Teardown] MCP client closed.")

    print("\n" + "=" * 65)
    print("ALL PHASE 3 API STREAMING TESTS COMPLETED SUCCESSFULLY")
    print("=" * 65 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
