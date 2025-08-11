from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse
from pydantic import BaseModel
from langchain_core.messages import HumanMessage

import redis
import json
import os
import traceback
from dotenv import load_dotenv

from backend.workflow_pipeline import GraphBuilder

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

class RedisSaver:
    def __init__(self, redis_url="redis://localhost:6379/0"):
        self.client = redis.from_url(redis_url)

    def save_checkpoint(self, checkpoint_id, checkpoint_data):
        self.client.hset("checkpoints", checkpoint_id, json.dumps(checkpoint_data))

    def list(self, _):
        keys = self.client.hkeys("checkpoints")
        checkpoints = []
        for key in keys:
            data = self.client.hget("checkpoints", key)
            if data:
                try:
                    checkpoints.append(json.loads(data))
                except json.JSONDecodeError:
                    continue
        return checkpoints

    def get_checkpoint(self, checkpoint_id):
        data = self.client.hget("checkpoints", checkpoint_id)
        if data:
            return json.loads(data)
        return None

# Instantiate RedisSaver
checkpointer = RedisSaver(redis_url="redis://localhost:6379/0")

builder = GraphBuilder()
chatbot = builder(checkpointer=checkpointer)

@app.post("/query")
async def query_chatbot(query: QueryRequest):
    try:
        print("User query:", query.question)
        print("Thread ID:", query.thread_id)

        messages = {"messages": [HumanMessage(content=query.question)]}

        # Optional: save graph image
        try:
            png_graph = chatbot.get_graph().draw_mermaid_png()
            os.makedirs("./data/media", exist_ok=True)
            with open("./data/media/my_graph.png", "wb") as f:
                f.write(png_graph)
            print(f"Graph saved as 'my_graph.png' in {os.getcwd()}")
        except Exception as e:
            print("Failed to save graph image:", e)

        output = chatbot.invoke(messages, config={'configurable': {'thread_id': query.thread_id}})

        return {"response": output}

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
