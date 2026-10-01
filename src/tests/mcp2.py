from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import asyncio
import traceback

from agent.tools import mcp_client


async def main():
    try:
        print("1. Connecting...")
        await mcp_client.connect()

        print("2. Session:", mcp_client.session)

        print("3. Calling list_github_prs directly...")
        result = await mcp_client.list_github_prs(
            "Lomesh-AI",
            "sand"
        )

        print("4. RESULT:")
        print(result)

    except Exception as e:
        print("\n========== EXCEPTION ==========")
        print(type(e).__name__, str(e))
        traceback.print_exc()

    finally:
        print("\n5. Closing...")
        try:
            await mcp_client.close()
        except Exception as e:
            print("Close error:", type(e).__name__, str(e))


if __name__ == "__main__":
    asyncio.run(main())