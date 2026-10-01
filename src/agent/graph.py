import os
from pathlib import Path
from typing import TypedDict
from dotenv import load_dotenv

from langgraph.checkpoint.memory import InMemorySaver
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, AIMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import StateGraph, START, MessagesState
from langgraph.prebuilt import ToolNode, tools_condition

# Load .env from src/ or project root
SRC_DIR = Path(__file__).resolve().parents[1]
PROJECT_DIR = SRC_DIR.parent
for env_file in [SRC_DIR / ".env", PROJECT_DIR / ".env"]:
    if env_file.exists():
        load_dotenv(env_file, override=False)

# Normalize LangSmith / LangChain tracing environment variables
if os.environ.get("LANGSMITH_TRACING", "").lower() in ("true", "1") or os.environ.get("LANGCHAIN_TRACING_V2", "").lower() in ("true", "1"):
    os.environ["LANGCHAIN_TRACING_V2"] = "true"
    os.environ["LANGSMITH_TRACING"] = "true"

if os.environ.get("LANGSMITH_API_KEY") and not os.environ.get("LANGCHAIN_API_KEY"):
    os.environ["LANGCHAIN_API_KEY"] = os.environ["LANGSMITH_API_KEY"]

if os.environ.get("LANGSMITH_PROJECT") and not os.environ.get("LANGCHAIN_PROJECT"):
    os.environ["LANGCHAIN_PROJECT"] = os.environ["LANGSMITH_PROJECT"]

from .tools import (
    search_knowledge,
    get_current_time,
    list_decisions,
    get_document,
    get_github_file,
    search_github,
    list_github_files,
    list_github_issues,
    list_github_prs,
)

tools = [
    search_knowledge,
    get_current_time,
    list_decisions,
    get_document,
    get_github_file,
    search_github,
    list_github_files,
    list_github_issues,
    list_github_prs,
]


def _get_llm_and_tools():
    api_key = (
        os.environ.get("XAI_API_KEY")
        or os.environ.get("OPENAI_API_KEY")
        or os.environ.get("OPENAI_ADMIN_KEY")
    )
    if not api_key:
        return None, None

    llm = ChatOpenAI(
        model_name="openai/gpt-oss-20b",
        api_key=api_key,
        base_url="https://api.groq.com/openai/v1",
    )
    return llm, llm.bind_tools(tools=tools)


llm, llm_with_tools = _get_llm_and_tools()


class AgentState(MessagesState):
    user_query: str
    knowledge_result: str
    github_result: str


async def agent(state: AgentState, config: RunnableConfig = None) -> dict[str, list[AIMessage]]:
    global llm, llm_with_tools
    if llm_with_tools is None:
        llm, llm_with_tools = _get_llm_and_tools()

    last_message = state["messages"][-1] if state["messages"] else None
    if (
        isinstance(last_message, ToolMessage)
        and isinstance(last_message.content, str)
        and last_message.content.startswith("search_docs failed:")
    ):
        return {
            "messages": [
                AIMessage(
                    content=(
                        "The knowledge search failed and was not retried. "
                        f"{last_message.content}"
                    )
                )
            ]
        }

    if llm_with_tools is None:
        return {
            "messages": [
                AIMessage(
                    content=(
                        "I don't have a valid LLM API key in this environment, "
                        "so I cannot query the live model."
                    )
                )
            ]
        }

    system_message = SystemMessage(
        content=(
            "You are an engineering knowledge assistant. "
            "Use the available tools whenever you need information "
            "from the engineering knowledge base. "
            "Do not invent information."
        )
    )

    try:
        response = await llm_with_tools.ainvoke(
            [system_message] + state["messages"],
            config=config,
        )

    except Exception:
        try:
            response = await llm.ainvoke(
                [system_message] + state["messages"],
                config=config,
            )

        except Exception:
            return {
                "messages": [
                    AIMessage(
                        content=(
                            "The configured model rejected the tool-calling "
                            "schema for this request."
                        )
                    )
                ]
            }

    return {"messages": [response]}


builder = StateGraph(AgentState)

builder.add_node("agent", agent)

tool_node = ToolNode(tools)


async def logged_tool_node(state, config: RunnableConfig = None):
    print("[graph] ToolNode execution started", flush=True)
    result = await tool_node.ainvoke(state, config=config)
    print("[graph] ToolNode execution returned", flush=True)
    return result


builder.add_node("tools", logged_tool_node)

builder.add_edge(START, "agent")

builder.add_conditional_edges(
    "agent",
    tools_condition,
)

builder.add_edge("tools", "agent")

checkpointer = InMemorySaver()
graph = builder.compile(checkpointer=checkpointer)
