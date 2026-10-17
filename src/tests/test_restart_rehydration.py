import urllib.request
import json
import sys

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE_URL = "http://localhost:8000"
THREAD_ID = "interview-demo-thread-1792227573"

def test_turn3():
    print(f"\n==================================================================")
    print(f">> POST-RESTART RE-CONTINUATION TEST (Thread: {THREAD_ID})")
    print(f">> Server was killed and restarted. InMemorySaver RAM is completely EMPTY.")
    print(f"==================================================================")

    url = f"{BASE_URL}/chat"
    payload = json.dumps({
        "message": "And what was my job role that I mentioned when I first introduced myself?",
        "thread_id": THREAD_ID
    }).encode("utf-8")

    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST"
    )

    answer_parts = []
    with urllib.request.urlopen(req) as resp:
        for line in resp:
            line_str = line.decode("utf-8").strip()
            if not line_str:
                continue
            try:
                event = json.loads(line_str)
                if event.get("type") == "answer":
                    answer_parts.append(event.get("content", ""))
            except Exception:
                pass

    final_answer = "\n".join(answer_parts).strip()
    print(f"\n>> AGENT RESPONSE FROM RE-HYDRATED AWS MEMORY:\n{final_answer}\n")
    assert "appsec" in final_answer.lower(), "Agent failed to remember job role from AWS RDS PostgreSQL!"
    print("[SUCCESS] The agent successfully re-hydrated the conversation directly from AWS RDS PostgreSQL after server restart!")

if __name__ == "__main__":
    test_turn3()
