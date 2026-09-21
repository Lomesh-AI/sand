import os

from langgraph.checkpoint.memory import InMemorySaver
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, AIMessage
from langgraph.graph import StateGraph, START, MessagesState
from langgraph.prebuilt import ToolNode, tools_condition

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

api_key = (
    os.environ.get("XAI_API_KEY")
    or os.environ.get("OPENAI_API_KEY")
    or os.environ.get("OPENAI_ADMIN_KEY")
)

llm = None

if api_key:
    llm = ChatOpenAI(
        model_name="openai/gpt-oss-20b",
        api_key=api_key,
        base_url="https://api.groq.com/openai/v1",
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

llm_with_tools = (
    llm.bind_tools(tools=tools)
    if llm is not None
    else None
)


async def agent(state: MessagesState):

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
            [system_message] + state["messages"]
        )

    except Exception:
        try:
            response = await llm.ainvoke(
                [system_message] + state["messages"]
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


builder = StateGraph(MessagesState)

builder.add_node("agent", agent)
builder.add_node("tools", ToolNode(tools))

builder.add_edge(START, "agent")

builder.add_conditional_edges(
    "agent",
    tools_condition,
)

builder.add_edge("tools", "agent")

checkpointer = InMemorySaver()
graph = builder.compile(checkpointer=checkpointer)
