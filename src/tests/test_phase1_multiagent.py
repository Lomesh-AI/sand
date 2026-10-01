"""Test script to trace Phase 1 Multi-Agent setup:
1. Tool partitioning and domain isolation (Docs vs GitHub vs General).
2. Persona and system prompt validation.
3. Specialist LLM tool-binding simulation & trace.
"""

from pathlib import Path
import sys
import os

# Set root path to sand/
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# Fix UnicodeEncodeError on Windows cp1252 terminals
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import asyncio
from dotenv import load_dotenv

# Load .env
for env_path in [Path(".env"), Path("src/.env"), Path(__file__).resolve().parents[2] / ".env"]:
    if env_path.exists():
        load_dotenv(env_path, override=False)

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

from agent.tools import DOCS_TOOLS, GITHUB_TOOLS, GENERAL_TOOLS, ALL_TOOLS
from agent.prompts import (
    SUPERVISOR_SYSTEM_PROMPT,
    DOCS_SPECIALIST_PROMPT,
    GITHUB_SPECIALIST_PROMPT,
)


def get_llm():
    api_key = (
        os.environ.get("XAI_API_KEY")
        or os.environ.get("OPENAI_API_KEY")
        or os.environ.get("OPENAI_ADMIN_KEY")
    )
    if not api_key:
        print("[WARN] No LLM API key found. LLM tool-calling trace will be skipped.")
        return None

    return ChatOpenAI(
        model_name="openai/gpt-oss-20b",
        api_key=api_key,
        base_url="https://api.groq.com/openai/v1",
        temperature=0.0,
    )


def test_tool_partitioning():
    print("\n" + "=" * 60)
    print("STEP 1: TRACING TOOL PARTITIONING & DOMAIN ISOLATION")
    print("=" * 60)

    docs_names = [t.name for t in DOCS_TOOLS]
    github_names = [t.name for t in GITHUB_TOOLS]
    general_names = [t.name for t in GENERAL_TOOLS]
    all_names = [t.name for t in ALL_TOOLS]

    print(f"\n[Docs Specialist Tools] ({len(docs_names)}):")
    for name in docs_names:
        print(f"  - {name}")

    print(f"\n[GitHub Specialist Tools] ({len(github_names)}):")
    for name in github_names:
        print(f"  - {name}")

    print(f"\n[General / Utility Tools] ({len(general_names)}):")
    for name in general_names:
        print(f"  - {name}")

    # Assertions for domain isolation
    assert set(docs_names).isdisjoint(set(github_names)), "Overlap found between Docs and GitHub tools!"
    assert len(all_names) == len(docs_names) + len(github_names) + len(general_names), "Tool count mismatch!"
    print("\n[OK] Strict domain separation confirmed: zero tool overlap between specialists.")


def test_prompts():
    print("\n" + "=" * 60)
    print("STEP 2: TRACING SPECIALIST PERSONAS & PROMPTS")
    print("=" * 60)

    prompts = {
        "Supervisor Prompt": SUPERVISOR_SYSTEM_PROMPT,
        "Docs Specialist Prompt": DOCS_SPECIALIST_PROMPT,
        "GitHub Specialist Prompt": GITHUB_SPECIALIST_PROMPT,
    }

    for title, prompt in prompts.items():
        print(f"\n--- {title} ---")
        lines = prompt.strip().split("\n")
        # Print first 4 lines as preview
        preview = "\n".join(lines[:4])
        print(preview)
        print(f"  ... ({len(lines)} lines total, length: {len(prompt)} chars)")
        assert len(prompt) > 100, f"{title} prompt is unexpectedly short!"

    print("\n[OK] All specialist prompts defined and validated.")


async def test_specialist_llm_bindings(llm):
    print("\n" + "=" * 60)
    print("STEP 3: TRACING SPECIALIST LLM TOOL SELECTION")
    print("=" * 60)

    if llm is None:
        print("[SKIP] Skipping LLM execution due to missing API key.")
        return

    # 1. Test Docs Specialist
    print("\n[Test 3A] Docs Specialist Tool Selection:")
    docs_llm = llm.bind_tools(DOCS_TOOLS)
    user_query_docs = "What are the security requirements and architecture decisions for our system?"
    print(f"User Query : {user_query_docs}")

    docs_response = await docs_llm.ainvoke([
        SystemMessage(content=DOCS_SPECIALIST_PROMPT),
        HumanMessage(content=user_query_docs),
    ])

    if docs_response.tool_calls:
        for tc in docs_response.tool_calls:
            print(f"  -> Generated Tool Call : {tc['name']} with args {tc['args']}")
            assert tc['name'] in [t.name for t in DOCS_TOOLS], f"Docs agent called non-docs tool {tc['name']}!"
        print("  [OK] Docs Specialist accurately picked a docs tool.")
    else:
        print(f"  -> Direct Response: {docs_response.content[:150]}...")

    # 2. Test GitHub Specialist
    print("\n[Test 3B] GitHub Specialist Tool Selection:")
    github_llm = llm.bind_tools(GITHUB_TOOLS)
    user_query_github = "Show me the open pull requests in Lomesh-AI/sand."
    print(f"User Query : {user_query_github}")

    github_response = await github_llm.ainvoke([
        SystemMessage(content=GITHUB_SPECIALIST_PROMPT),
        HumanMessage(content=user_query_github),
    ])

    if github_response.tool_calls:
        for tc in github_response.tool_calls:
            print(f"  -> Generated Tool Call : {tc['name']} with args {tc['args']}")
            assert tc['name'] in [t.name for t in GITHUB_TOOLS], f"GitHub agent called non-github tool {tc['name']}!"
        print("  [OK] GitHub Specialist accurately picked a GitHub tool.")
    else:
        print(f"  -> Direct Response: {github_response.content[:150]}...")


async def main():
    print("\n" + "#" * 60)
    print("### RUNNING PHASE 1 MULTI-AGENT VERIFICATION & TRACE ###")
    print("#" * 60)

    test_tool_partitioning()
    test_prompts()

    llm = get_llm()
    await test_specialist_llm_bindings(llm)

    print("\n" + "=" * 60)
    print("ALL PHASE 1 TRACE CHECKS COMPLETED SUCCESSFULLY")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
