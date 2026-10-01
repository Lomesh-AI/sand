from pathlib import Path
import sys
import os

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import asyncio, sys, os
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

SERVER = r"E:\agentic\sand\src\mcp_server.py"

async def main():
    params = StdioServerParameters(
        command=sys.executable,
        args=["-u", SERVER],  # direct path, -u = unbuffered
        env={**os.environ, "PYTHONUNBUFFERED": "1", "PYTHONIOENCODING": "utf-8"},
    )
    print("spawning server...")
    with open("server_err.log", "w", encoding="utf-8") as errlog:
        async with stdio_client(params, errlog=errlog) as (read, write):
            print("connected")
            async with ClientSession(read, write) as session:
                print("initializing...")
                result = await session.initialize()
                print("OK:", result.server_info)

asyncio.run(main())