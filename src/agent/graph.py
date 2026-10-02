import os
from pathlib import Path
from typing import Literal
from dotenv import load_dotenv
from pydantic import BaseModel, Field

from langgraph.checkpoint.memory import InMemorySaver
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, AIMessage, ToolMessage, HumanMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import StateGraph, START, END, MessagesState
from langgraph.prebuilt import ToolNode

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
    DOCS_TOOLS,
    GITHUB_TOOLS,
    GENERAL_TOOLS,
    ALL_TOOLS,
)
from .prompts import (
    SUPERVISOR_SYSTEM_PROMPT,
    DOCS_SPECIALIST_PROMPT,
    GITHUB_SPECIALIST_PROMPT,
)

# Backwards compatibility export
tools = ALL_TOOLS


def _get_base_llm():
    api_key = (
        os.environ.get("XAI_API_KEY")
        or os.environ.get("OPENAI_API_KEY")
        or os.environ.get("OPENAI_ADMIN_KEY")
    )
    if not api_key:
        return None

    return ChatOpenAI(
        model_name="openai/gpt-oss-20b",
        api_key=api_key,
        base_url="https://api.groq.com/openai/v1",
        temperature=0.0,
        max_retries=5,
    )


# --- Multi-Agent State & Router Models ---

class TeamState(MessagesState):
    next_step: str
    visited_specialists: list[str]


# Backwards compatibility alias
AgentState = TeamState


class RouterDecision(BaseModel):
    next_step: Literal["docs_specialist", "github_specialist", "FINISH"] = Field(
        description="Next agent to delegate to: 'docs_specialist', 'github_specialist', or 'FINISH'."
    )
    reasoning: str = Field(
        description="Short reason explaining the delegation choice or why we are finishing."
    )


# --- Helper Functions ---

def _get_current_turn_messages(messages: list) -> list:
    """Return only the messages belonging to the current user turn."""
    human_indices = [i for i, m in enumerate(messages) if isinstance(m, HumanMessage)]
    if not human_indices:
        return messages
    return messages[human_indices[-1]:]


# --- Nodes ---

async def supervisor_node(state: TeamState, config: RunnableConfig = None) -> dict:
    llm = _get_base_llm()
    if llm is None:
        return {
            "messages": [
                AIMessage(content="I don't have a valid LLM API key configured in this environment.")
            ],
            "next_step": "FINISH",
        }

    last_msg = state["messages"][-1] if state["messages"] else None
    is_user_turn_start = isinstance(last_msg, HumanMessage)
    visited = [] if is_user_turn_start else list(state.get("visited_specialists") or [])

    # If returning from a specialist investigation in this turn, synthesize the final response
    if visited and not is_user_turn_start:
        # If specialist already produced a complete text response without tool calls, adopt it directly
        if isinstance(last_msg, AIMessage) and last_msg.content and not getattr(last_msg, "tool_calls", None):
            return {"messages": [last_msg], "next_step": "FINISH", "visited_specialists": []}

        # Otherwise synthesize across current turn's specialist findings
        turn_messages = _get_current_turn_messages(state["messages"])
        findings = []
        user_query = ""
        for m in turn_messages:
            if isinstance(m, HumanMessage):
                user_query = m.content
            elif isinstance(m, AIMessage) and m.content and not getattr(m, "tool_calls", None):
                findings.append(m.content)
            elif isinstance(m, ToolMessage):
                findings.append(str(m.content))

        context_str = "\n\n".join(findings)
        synthesis_prompt = SystemMessage(
            content=(
                "You are the Lead Engineering Orchestrator.\n"
                "The specialist investigation for the current query is complete. Below are the findings collected:\n"
                "--------------------\n"
                f"{context_str}\n"
                "--------------------\n"
                "Synthesize the findings into a clear, professional, and well-structured engineering response. "
                "Cite all relevant documents, ADRs, or repository findings. Write in clean markdown text."
            )
        )
        response = await llm.ainvoke([synthesis_prompt, HumanMessage(content=user_query)], config=config)
        return {"messages": [response], "next_step": "FINISH", "visited_specialists": []}

    # Formulate routing decision with awareness of conversation history
    router_llm = llm.with_structured_output(RouterDecision)
    router_prompt = SystemMessage(
        content=(
            f"{SUPERVISOR_SYSTEM_PROMPT}\n\n"
            "Review the conversation history and the latest user request to make a routing decision.\n"
            "Decide whether to delegate to 'docs_specialist', 'github_specialist', or 'FINISH'.\n"
            "- If the query or follow-up is about architecture, decisions (ADRs), or docs -> 'docs_specialist'.\n"
            "- If the query or follow-up refers to code, repositories, pull requests, issues, or 'the above repo' -> 'github_specialist'.\n"
            "- If the query is a simple greeting or general question requiring no external tools -> 'FINISH'."
        )
    )

    try:
        decision = await router_llm.ainvoke(
            [router_prompt] + state["messages"],
            config=config,
        )
        next_step = decision.next_step
        print(f"[supervisor] Routing -> {next_step} (Reason: {decision.reasoning})", flush=True)
    except Exception as e:
        print(f"[supervisor] Router fallback: {e}", flush=True)
        next_step = "FINISH"

    if next_step == "FINISH":
        synthesis_prompt = SystemMessage(
            content=(
                f"{SUPERVISOR_SYSTEM_PROMPT}\n\n"
                "Provide a comprehensive, direct, and well-structured response to the user based on the conversation."
            )
        )
        response = await llm.ainvoke([synthesis_prompt] + state["messages"], config=config)
        return {"messages": [response], "next_step": "FINISH", "visited_specialists": []}

    return {"next_step": next_step, "visited_specialists": visited}


async def docs_specialist_node(state: TeamState, config: RunnableConfig = None) -> dict:
    llm = _get_base_llm()
    if llm is None:
        return {"messages": [AIMessage(content="LLM API key missing.")], "next_step": "FINISH"}

    visited = list(state.get("visited_specialists") or [])
    if "docs_specialist" not in visited:
        visited.append("docs_specialist")

    turn_messages = _get_current_turn_messages(state["messages"])
    tool_messages = [m for m in turn_messages if isinstance(m, ToolMessage)]

    # If tools have executed in this turn, synthesize the findings without further tool calls
    if tool_messages:
        user_query = ""
        retrieved_contexts = []
        for m in turn_messages:
            if isinstance(m, HumanMessage):
                user_query = m.content
            elif isinstance(m, ToolMessage):
                retrieved_contexts.append(str(m.content))

        context_str = "\n\n".join(retrieved_contexts)
        synthesis_prompt = SystemMessage(
            content=(
                "You are the Senior Architecture & Documentation Specialist.\n"
                "Below is the information retrieved from documentation tools:\n"
                "--------------------\n"
                f"{context_str}\n"
                "--------------------\n"
                "Provide a comprehensive, professional, and well-structured engineering response answering the user question based strictly on the retrieved documentation.\n"
                "Cite sources properly (e.g. [SOURCE: docs/...]). Write in clean markdown text. Do not make any tool calls."
            )
        )
        response = await llm.ainvoke([synthesis_prompt, HumanMessage(content=user_query)], config=config)
        return {
            "messages": [response],
            "visited_specialists": visited,
        }

    # Initial turn: bind tools to let specialist query documentation
    docs_llm = llm.bind_tools(DOCS_TOOLS)
    system_msg = SystemMessage(
        content=(
            f"{DOCS_SPECIALIST_PROMPT}\n\n"
            "Select the most appropriate tool to search or read documentation for the user query."
        )
    )

    response = await docs_llm.ainvoke([system_msg] + state["messages"], config=config)

    return {
        "messages": [response],
        "visited_specialists": visited,
    }


async def github_specialist_node(state: TeamState, config: RunnableConfig = None) -> dict:
    llm = _get_base_llm()
    if llm is None:
        return {"messages": [AIMessage(content="LLM API key missing.")], "next_step": "FINISH"}

    visited = list(state.get("visited_specialists") or [])
    if "github_specialist" not in visited:
        visited.append("github_specialist")

    turn_messages = _get_current_turn_messages(state["messages"])
    tool_messages = [m for m in turn_messages if isinstance(m, ToolMessage)]

    # If tool executed in this turn, synthesize response
    if tool_messages:
        user_query = ""
        retrieved_contexts = []
        for m in turn_messages:
            if isinstance(m, HumanMessage):
                user_query = m.content
            elif isinstance(m, ToolMessage):
                retrieved_contexts.append(str(m.content))

        context_str = "\n\n".join(retrieved_contexts)
        synthesis_prompt = SystemMessage(
            content=(
                "You are the Senior GitHub & Codebase Specialist.\n"
                "Below is the data retrieved from GitHub tools:\n"
                "--------------------\n"
                f"{context_str}\n"
                "--------------------\n"
                "Synthesize the findings into a clear, precise, and actionable engineering response for the user.\n"
                "If a repository or file was not found (404) or an error occurred, explain the issue clearly without retrying.\n"
                "Write in clean markdown text. Do not make any tool calls."
            )
        )
        response = await llm.ainvoke([synthesis_prompt, HumanMessage(content=user_query)], config=config)
        return {
            "messages": [response],
            "visited_specialists": visited,
        }

    # Initial turn: bind tools to query GitHub
    github_llm = llm.bind_tools(GITHUB_TOOLS)
    system_msg = SystemMessage(
        content=(
            f"{GITHUB_SPECIALIST_PROMPT}\n\n"
            "Select the most appropriate tool to inspect the repository or code for the user query.\n"
            "If the user refers to an earlier repository or context from the conversation history (e.g. 'the above repo'), resolve the repository owner and name from the prior messages."
        )
    )

    response = await github_llm.ainvoke([system_msg] + state["messages"], config=config)

    return {
        "messages": [response],
        "visited_specialists": visited,
    }


# --- Routing Conditions ---

def route_supervisor(state: TeamState) -> Literal["docs_specialist", "github_specialist", "__end__"]:
    next_step = state.get("next_step", "FINISH")
    if next_step == "docs_specialist":
        return "docs_specialist"
    elif next_step == "github_specialist":
        return "github_specialist"
    return "__end__"


def route_docs_specialist(state: TeamState) -> Literal["docs_tools", "supervisor"]:
    last_message = state["messages"][-1] if state["messages"] else None
    if last_message and hasattr(last_message, "tool_calls") and last_message.tool_calls:
        # Enforce maximum tool call limit for the current turn to prevent loops
        turn_messages = _get_current_turn_messages(state["messages"])
        tool_count = len([m for m in turn_messages if isinstance(m, ToolMessage)])
        if tool_count < 2:
            return "docs_tools"
    return "supervisor"


def route_github_specialist(state: TeamState) -> Literal["github_tools", "supervisor"]:
    last_message = state["messages"][-1] if state["messages"] else None
    if last_message and hasattr(last_message, "tool_calls") and last_message.tool_calls:
        # Enforce maximum tool call limit for the current turn to prevent loops
        turn_messages = _get_current_turn_messages(state["messages"])
        tool_count = len([m for m in turn_messages if isinstance(m, ToolMessage)])
        if tool_count < 2:
            return "github_tools"
    return "supervisor"


# --- Graph Assembly ---

builder = StateGraph(TeamState)

# Nodes
builder.add_node("supervisor", supervisor_node)
builder.add_node("docs_specialist", docs_specialist_node)
builder.add_node("docs_tools", ToolNode(DOCS_TOOLS))
builder.add_node("github_specialist", github_specialist_node)
builder.add_node("github_tools", ToolNode(GITHUB_TOOLS))

# Edges
builder.add_edge(START, "supervisor")

builder.add_conditional_edges(
    "supervisor",
    route_supervisor,
    {
        "docs_specialist": "docs_specialist",
        "github_specialist": "github_specialist",
        "__end__": END,
    },
)

builder.add_conditional_edges(
    "docs_specialist",
    route_docs_specialist,
    {
        "docs_tools": "docs_tools",
        "supervisor": "supervisor",
    },
)
builder.add_edge("docs_tools", "docs_specialist")

builder.add_conditional_edges(
    "github_specialist",
    route_github_specialist,
    {
        "github_tools": "github_tools",
        "supervisor": "supervisor",
    },
)
builder.add_edge("github_tools", "github_specialist")

checkpointer = InMemorySaver()
graph = builder.compile(checkpointer=checkpointer)
