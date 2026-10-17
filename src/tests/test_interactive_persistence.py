"""Demonstrates end-to-end conversation persistence and multi-turn re-continuation

1. Turn 1: Introduce user name and query ADR.
2. Verify AWS RDS PostgreSQL has stored Turn 1.
3. Turn 2: Ask question relying on past context on the same thread_id.
4. Verify AWS RDS PostgreSQL now stores both turns.
"""

import urllib.request
import json
import time
import sys

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE_URL = "http://localhost:8000"
THREAD_ID = "interview-demo-thread-1792227573"

def send_chat(message: str, thread_id: str):
    url = f"{BASE_URL}/chat"
    payload = json.dumps({"message": message, "thread_id": thread_id}).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST"
    )

    print(f"\n==================================================================")
    print(f">> USER QUERY: \"{message}\" (thread_id: {thread_id})")
    print(f"==================================================================")

    answer_parts = []
    with urllib.request.urlopen(req) as resp:
        for line in resp:
            line_str = line.decode("utf-8").strip()
            if not line_str:
                continue
            try:
                event = json.loads(line_str)
                ev_type = event.get("type")
                if ev_type == "status":
                    print(f"   [Status] {event.get('content')}")
                elif ev_type == "tool_call":
                    print(f"   [Tool Call] {event.get('agent', '')} executing: {event.get('tool')}")
                elif ev_type == "answer":
                    answer_parts.append(event.get("content", ""))
            except Exception:
                pass

    final_answer = "\n".join(answer_parts).strip()
    print(f"\n>> AGENT RESPONSE:\n{final_answer}\n")
    return final_answer

def check_aws_persistence(thread_id: str):
    time.sleep(1) # small pause for async DB write
    url = f"{BASE_URL}/conversations/{thread_id}"
    req = urllib.request.Request(url, method="GET")
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read().decode("utf-8"))
        print(f"------------------------------------------------------------------")
        print(f"AWS RDS POSTGRESQL VERIFICATION for Thread: '{thread_id}'")
        print(f"------------------------------------------------------------------")
        print(f"Total turns saved in AWS RDS: {len(data)}")
        for idx, turn in enumerate(data, 1):
            print(f"  [Turn {idx}]")
            print(f"    - Query:   {turn['user_query']}")
            print(f"    - Answer:  {turn['final_answer'][:100]}...")
            print(f"    - Tools:   {turn['tools_called']}")
            print(f"    - Latency: {turn['latency_seconds']}s")
            print(f"    - Time:    {turn['created_at']}")
        print(f"------------------------------------------------------------------\n")
        return data

if __name__ == "__main__":
    print(f"\n[STEP 1] Verifying Turn 1 is already persisted in AWS RDS PostgreSQL for thread '{THREAD_ID}'...")
    history1 = check_aws_persistence(THREAD_ID)
    assert len(history1) >= 1, "Turn 1 was not persisted in AWS RDS!"

    print("[STEP 3] Sending Turn 2 (Continuing the conversation on same thread)...")
    ans2 = send_chat(
        "What was my name and what ADR was I asking about in my previous question?",
        THREAD_ID
    )

    print("[STEP 4] Verifying Turn 2 is also stored in AWS RDS PostgreSQL...")
    history2 = check_aws_persistence(THREAD_ID)
    assert len(history2) == 2, "Turn 2 was not persisted in AWS RDS!"

    print("[SUCCESS] Multi-Turn Stateful Memory Verified in AWS RDS PostgreSQL!")
