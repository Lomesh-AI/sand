import os
import asyncio
from dotenv import load_dotenv
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[1]
load_dotenv(SRC_DIR / ".env")

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage, ToolMessage
from src.agent.tools import DOCS_TOOLS
from src.agent.prompts import DOCS_SPECIALIST_PROMPT

async def main():
    llm = ChatOpenAI(
        model_name="openai/gpt-oss-20b",
        api_key=os.environ.get("XAI_API_KEY") or os.environ.get("OPENAI_API_KEY"),
        base_url="https://api.groq.com/openai/v1",
        temperature=0.0,
    )

    docs_llm = llm.bind_tools(DOCS_TOOLS)

    # Round 1: User asks
    user_msg = HumanMessage(content="What are the security requirements and authentication mechanisms in this system?")
    system_msg = SystemMessage(
        content=(
            f"{DOCS_SPECIALIST_PROMPT}\n\n"
            "Perform your tool queries efficiently. Once you have gathered the required information, "
            "provide a complete, final summary of your findings without further tool calls."
        )
    )

    res1 = await docs_llm.ainvoke([system_msg, user_msg])
    print("RES 1:")
    print("tool_calls:", getattr(res1, "tool_calls", None))
    print("content:", res1.content)

    if not res1.tool_calls:
        return

    # Simulate tool response (first tool was search_knowledge)
    tc = res1.tool_calls[0]
    tool_msg = ToolMessage(
        content=(
            "[SOURCE: docs/security.md]\n"
            "# AppSec Incident Lab - Security Hardening Guide\n"
            "Authentication: JWT HS256 with golang-jwt/jwt/v5. Short-lived tokens (1h default).\n"
            "Security Requirements: RBAC enforced at API gateway, mTLS for internal services, HTTPS only."
        ),
        tool_call_id=tc["id"]
    )

    messages = [user_msg, res1, tool_msg]

    # Round 2: docs_specialist receives tool result
    res2 = await docs_llm.ainvoke([system_msg] + messages)
    print("\nRES 2:")
    print("tool_calls:", getattr(res2, "tool_calls", None))
    print("content:", res2.content)

    if res2.tool_calls:
        tc2 = res2.tool_calls[0]
        tool_msg2 = ToolMessage(
            content="ADR-001: JWT Auth accepted.\nADR-002: mTLS accepted.",
            tool_call_id=tc2["id"]
        )
        messages.extend([res2, tool_msg2])
        res3 = await docs_llm.ainvoke([system_msg] + messages)
        print("\nRES 3:")
        print("tool_calls:", getattr(res3, "tool_calls", None))
        print("content:", res3.content)

if __name__ == "__main__":
    asyncio.run(main())
