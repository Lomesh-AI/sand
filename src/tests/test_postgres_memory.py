import asyncio
import sys
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SRC_DIR))

from dotenv import load_dotenv
load_dotenv(SRC_DIR / ".env")
load_dotenv(SRC_DIR.parent / ".env")

if sys.platform == "win32":
    import asyncio
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from agent.memory import init_postgres_tables, record_conversation_turn, list_past_conversations, get_thread_history

async def main():
    print("[1] Initializing PostgreSQL schema on AWS RDS...", flush=True)
    success = await init_postgres_tables()
    print(f" -> Schema initialization: {success}", flush=True)
    assert success, "Failed to initialize schema on AWS RDS!"

    print("\n[2] Storing sample conversation turn to AWS RDS...", flush=True)
    saved = await record_conversation_turn(
        thread_id="aws-test-thread-001",
        user_query="What are the security requirements for our production services?",
        final_answer="Production services require mTLS, OAuth2 token validation, and rate limiting per ADR-0002.",
        visited_specialists=["docs_specialist"],
        tools_called=["search_knowledge"],
        latency_seconds=2.85,
    )
    print(f" -> Saved to AWS RDS: {saved}", flush=True)
    assert saved, "Failed to record conversation turn!"

    print("\n[3] Querying past conversations from AWS RDS...", flush=True)
    past = await list_past_conversations(limit=5)
    print(f" -> Found {len(past)} recent conversation(s):", flush=True)
    for p in past:
        print(f"    - Thread: {p['thread_id']} | Query: {p['user_query']}", flush=True)

    print("\n[4] Querying full thread history for 'aws-test-thread-001'...", flush=True)
    history = await get_thread_history("aws-test-thread-001")
    print(f" -> Turns in thread: {len(history)}", flush=True)
    for turn in history:
        print(f"    - Query: {turn['user_query']}", flush=True)
        print(f"    - Answer: {turn['final_answer']}", flush=True)
        print(f"    - Tools: {turn['tools_called']} | Latency: {turn['latency_seconds']}s", flush=True)

    print("\n[SUCCESS] AWS RDS PostgreSQL Conversation Storage Verified!", flush=True)

if __name__ == "__main__":
    if sys.platform == "win32":
        import selectors
        asyncio.run(main(), loop_factory=lambda: asyncio.SelectorEventLoop(selectors.SelectSelector()))
    else:
        asyncio.run(main())

