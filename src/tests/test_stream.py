from pathlib import Path
import sys
import os
import asyncio

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# Fix UnicodeEncodeError on Windows cp1252 terminals when printing MCP results
if sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

LOG = Path(__file__).resolve().parents[2] / "server_stderr.log"


async def main():

    project_root = Path(__file__).resolve().parents[2]  # e:\agentic\sand

    server_params = StdioServerParameters(
        command=sys.executable,                                   # identical to test_minimal
        args=["-u", str(project_root / "src" / "mcp_server.py")], # direct path, unbuffered
        cwd=str(project_root),                                    # ← the one remaining difference
        env={**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUNBUFFERED": "1"},
    )

    print("1. Starting MCP...")

    try:
        with open(LOG, "w", encoding="utf-8") as errlog:
            async with stdio_client(server_params, errlog=errlog) as (read, write):

                print("2. stdio connected")

                async with ClientSession(read, write) as session:

                    print("3. session created")

                    await session.initialize()
                    print("4. MCP initialized")

                    result = await session.call_tool(
                        "search_docs",
                        {"query": "What are the security requirements?"},
                    )

                    print("5. RESULT:")
                    output = str(result)
                    print(output.encode("utf-8", errors="replace").decode("utf-8"))

    finally:
        # Guaranteed capture: the file is closed before this prints,
        # so even a crash-fast server's last words are included.
        print(f"\n--- server stderr ({LOG}) ---")
        try:
            print(LOG.read_text(encoding="utf-8", errors="replace"))
        except FileNotFoundError:
            print("(log file was not written)")


if __name__ == "__main__":
    asyncio.run(main())