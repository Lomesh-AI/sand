from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))

from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import json
import uuid

from src.agent.tools import mcp_client
from src.agent.graph import graph


app = FastAPI(title="Engineering Knowledge Agent")

app.mount(
    "/static",
    StaticFiles(directory="src/static", html=True),
    name="static"
)


class ChatRequest(BaseModel):
    message: str


@app.on_event("startup")
async def startup():
    await mcp_client.connect()
    print("MCP session after startup:", mcp_client.session)


@app.on_event("shutdown")
async def shutdown():
    print("MCP session before shutdown:", mcp_client.session)
    await mcp_client.close()
    print("MCP session after shutdown:", mcp_client.session)


@app.post("/chat")
async def chat(request: ChatRequest):

    thread_id = str(uuid.uuid4())
    print("Chat request received:", request.message)
    print("Chat thread_id:", thread_id)
    print("MCP session before request:", mcp_client.session)

    config = {
        "configurable": {
            "thread_id": thread_id
        }
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
                print("LangGraph event:", thread_id, event)

                if "agent" in event:

                    message = event["agent"]["messages"][0]

                    if message.tool_calls:
                        yield json.dumps({
                            "type": "tool_call",
                            "tool": message.tool_calls[0]["name"]
                        }) + "\n"

                    elif message.content:
                        yield json.dumps({
                            "type": "answer",
                            "content": message.content
                        }) + "\n"

                elif "tools" in event:

                    yield json.dumps({
                        "type": "tool_result"
                    }) + "\n"
        except Exception as exc:
            print("Event generator exception:", thread_id, repr(exc))
            raise
        finally:
            print("Event generator ended:", thread_id)
            print("MCP session after request:", mcp_client.session)

    return StreamingResponse(
        event_generator(),
        media_type="application/x-ndjson",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )