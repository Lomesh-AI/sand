from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import asyncio
from agent.tools import mcp_client
from agent.graph import graph


async def main():
    await mcp_client.connect()
    config = {
        "configurable": {
            "thread_id": "stream-test"
        }
    }

    async for event in graph.astream(
        {
            "messages": [
                {
                    "role": "user",
                    "content": "What is the transactional outbox pattern?"
                }
            ]
        },
        config=config,
        stream_mode="updates",
    ):
        print(event)
    await mcp_client.close()


asyncio.run(main())