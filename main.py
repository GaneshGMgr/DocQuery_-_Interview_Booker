from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse
from pydantic import BaseModel
from langchain_core.messages import HumanMessage, SystemMessage

import redis
import json
import os
import traceback
from dotenv import load_dotenv

from backend.workflow_pipeline import GraphBuilder
from langgraph.checkpoint.redis import RedisSaver
from langgraph.store.redis import RedisStore
from fastapi.responses import StreamingResponse
import asyncio

load_dotenv()

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class QueryRequest(BaseModel):
    question: str
    thread_id: str


# Initialize Redis persistence and store
REDIS_URI = "redis://localhost:6379"
checkpointer = RedisSaver.from_conn_string(REDIS_URI)  # For chat history
file_store = RedisStore.from_conn_string(REDIS_URI)    # For file metadata
# Compile graph
builder = GraphBuilder(streaming=True)
chatbot = builder(checkpointer=checkpointer, store=file_store)

print(f"Checkpointer type: {type(checkpointer)}")
print(f"Checkpointer client: {checkpointer.client}")

@app.post("/query_stream")
async def query_chatbot_stream(query: QueryRequest):
    try:
        llm = builder.model_loader.llm # Get the LLM instance directly from the builder
        messages = [SystemMessage(content=builder.system_prompt), 
                   HumanMessage(content=query.question)]
        try:
            png_graph = chatbot.get_graph().draw_mermaid_png()
            os.makedirs("./data/media", exist_ok=True)
            with open("./data/media/my_graph.png", "wb") as f:
                f.write(png_graph)
            print(f"Graph saved as 'my_graph.png' in {os.getcwd()}")
        except Exception as e:
            print("Failed to save graph image:", e)

        # Then stream the response
        async def event_generator():
            # Stream directly from the LLM
            async for chunk in llm.astream(messages):
                if hasattr(chunk, 'content'):
                    yield f"data: {chunk.content}\n\n"
                    await asyncio.sleep(0.01)

        return StreamingResponse(event_generator(), media_type="text/event-stream")

    except Exception as e:
        traceback.print_exc()
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.get("/threads")
async def get_threads():
    threads = GraphBuilder.retrieve_all_threads(checkpointer)
    return {"threads": threads}

@app.get("/conversation/{thread_id}")
async def get_conversation(thread_id: str):
    try:
        state = chatbot.get_state(config={'configurable': {'thread_id': thread_id}})
        messages = state.values.get('messages', [])
        serialized = []
        for msg in messages:
            role = 'user' if isinstance(msg, HumanMessage) else 'assistant'
            serialized.append({'role': role, 'content': msg.content})
        return {"messages": serialized}
    except Exception as e:
        traceback.print_exc()
        return JSONResponse(status_code=500, content={"error": str(e)})


# python -m uvicorn main:app --reload