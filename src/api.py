from pathlib import Path
import sys
import os
import json
import uuid
from contextlib import asynccontextmanager

SRC_DIR = Path(__file__).resolve().parent
PROJECT_DIR = SRC_DIR.parent
WORKSPACE_DIR = PROJECT_DIR.parent
sys.path.insert(0, str(SRC_DIR))

# Fix Windows console UnicodeEncodeError (cp1252) when printing events
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
if sys.stderr and hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Load .env file before initializing agent/langchain
from dotenv import load_dotenv

for env_file in [SRC_DIR / ".env", PROJECT_DIR / ".env", WORKSPACE_DIR / ".env"]:
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

from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from langchain_core.tracers.langchain import LangChainTracer

from agent.tools import mcp_client
from agent.graph import graph


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("MCP client connecting...")
    await mcp_client.connect()
    print("MCP session after startup:", mcp_client.session)
    yield
    print("MCP client closing...")
    await mcp_client.close()
    print("MCP session after shutdown:", mcp_client.session)


app = FastAPI(title="Engineering Knowledge Agent", lifespan=lifespan)

static_dir = Path(__file__).resolve().parent / "static"

app.mount(
    "/static",
    StaticFiles(directory=str(static_dir), html=True),
    name="static"
)


class ChatRequest(BaseModel):
    message: str


@app.post("/chat")
async def chat(request: ChatRequest):

    thread_id = str(uuid.uuid4())
    print("Chat request received:", request.message)
    print("Chat thread_id:", thread_id)
    print("MCP session before request:", mcp_client.session)

    project_name = (
        os.environ.get("LANGSMITH_PROJECT")
        or os.environ.get("LANGCHAIN_PROJECT")
        or "engineering-knowledge-agent"
    )
    tracer = LangChainTracer(project_name=project_name)

    config = {
        "configurable": {
            "thread_id": thread_id
        },
        "callbacks": [tracer],
        "run_name": "Engineering Knowledge Agent Chat",
        "metadata": {
            "thread_id": thread_id,
            "user_query": request.message,
            "session_id": thread_id,
        },
        "tags": ["ui-query", "web-chat"],
    }

    async def event_generator():
        print("Event generator started:", thread_id)
        try:
            async for event in graph.astream(
                {
                    "messages": [
                        {
                            "role": "user",
                            "content": request.message
                        }
                    ]
                },
                config=config,
                stream_mode="updates",
            ):
                # Safe debug print for Windows consoles
                try:
                    print("LangGraph event:", thread_id, event)
                except Exception:
                    pass

                # Multi-Agent Event Streaming
                if "supervisor" in event:
                    sup_data = event["supervisor"]
                    next_step = sup_data.get("next_step")
                    if next_step and next_step != "FINISH":
                        agent_labels = {
                            "docs_specialist": "Documentation & Architecture Specialist",
                            "github_specialist": "GitHub & Codebase Specialist",
                        }
                        label = agent_labels.get(next_step, next_step)
                        yield json.dumps({
                            "type": "status",
                            "content": f"📋 Supervisor routing to {label}..."
                        }) + "\n"

                    if "messages" in sup_data and sup_data["messages"]:
                        message = sup_data["messages"][-1]
                        if message.content and not getattr(message, "tool_calls", None):
                            yield json.dumps({
                                "type": "answer",
                                "content": message.content
                            }) + "\n"

                elif "docs_specialist" in event:
                    spec_data = event["docs_specialist"]
                    if "messages" in spec_data and spec_data["messages"]:
                        message = spec_data["messages"][-1]
                        if getattr(message, "tool_calls", None):
                            yield json.dumps({
                                "type": "tool_call",
                                "agent": "docs_specialist",
                                "tool": message.tool_calls[0]["name"]
                            }) + "\n"

                elif "github_specialist" in event:
                    spec_data = event["github_specialist"]
                    if "messages" in spec_data and spec_data["messages"]:
                        message = spec_data["messages"][-1]
                        if getattr(message, "tool_calls", None):
                            yield json.dumps({
                                "type": "tool_call",
                                "agent": "github_specialist",
                                "tool": message.tool_calls[0]["name"]
                            }) + "\n"

                elif "docs_tools" in event or "github_tools" in event or "tools" in event:
                    yield json.dumps({
                        "type": "tool_result"
                    }) + "\n"

                # Backwards-compatibility for single-agent nodes
                elif "agent" in event:
                    message = event["agent"]["messages"][0]
                    if getattr(message, "tool_calls", None):
                        yield json.dumps({
                            "type": "tool_call",
                            "tool": message.tool_calls[0]["name"]
                        }) + "\n"
                    elif message.content:
                        yield json.dumps({
                            "type": "answer",
                            "content": message.content
                        }) + "\n"
        except Exception as exc:
            print("Event generator exception:", thread_id, repr(exc))
            raise
        finally:
            print("Event generator ended:", thread_id)
            print("MCP session after request:", mcp_client.session)
            try:
                tracer.wait_for_futures()
            except Exception:
                pass

    return StreamingResponse(
        event_generator(),
        media_type="application/x-ndjson",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)