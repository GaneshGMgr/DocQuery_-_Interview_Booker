from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
import redis
import json
import traceback
from datetime import datetime
from dotenv import load_dotenv
from backend.workflow_pipeline import GraphBuilder
from langgraph.checkpoint.redis import RedisSaver
from langgraph.store.redis import RedisStore
from fastapi.responses import StreamingResponse
import asyncio
import uuid

load_dotenv()

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pydantic Models
class QueryRequest(BaseModel):
    question: str
    thread_id: str

class ThreadRequest(BaseModel):
    thread_id: str
    title: Optional[str] = None

class MessageResponse(BaseModel):
    role: str
    content: str
    timestamp: Optional[float]

# Redis Setup
REDIS_URI = "redis://localhost:6379"

def setup_redis():
    with RedisSaver.from_conn_string(REDIS_URI) as checkpointer:
        checkpointer.setup()
        with RedisStore.from_conn_string(REDIS_URI) as store:
            store.setup()
            builder = GraphBuilder(streaming=True)
            compiled_graph = builder(checkpointer=checkpointer, store=store)
            return {
                    'graph': compiled_graph,
                    'builder': builder
                }

chatbot = setup_redis()

# Helper Functions
def generate_thread_title(messages: List) -> str:
    """Generate title from first user message"""
    for msg in messages:
        if isinstance(msg, HumanMessage) and msg.content.strip():
            return msg.content[:30] + ("..." if len(msg.content) > 30 else "")
    return "New Chat"

def serialize_message(msg) -> dict:
    """Convert message to API response format"""
    return {
        "role": "user" if isinstance(msg, HumanMessage) else "assistant",
        "content": msg.content,
        "timestamp": getattr(msg, "timestamp", None)
    }

# API Endpoints
@app.post("/init_thread")
async def init_thread(request: ThreadRequest):
    """Initialize a new chat thread"""
    try:
        initial_state = {
            "messages": [SystemMessage(content=chatbot.builder.system_prompt)],
            "metadata": {
                "created_at": datetime.now().timestamp(),
                "updated_at": datetime.now().timestamp(),
                "title": "New Chat"
            }
        }
        
        chatbot.update_state(
            config={'configurable': {'thread_id': request.thread_id}},
            values=initial_state
        )
        return {"status": "success", "thread_id": request.thread_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/threads")
async def get_threads():
    """List all conversation threads"""
    try:
        threads = []
        r = redis.Redis.from_url(REDIS_URI)
        
        # Get all thread IDs
        seen_threads = set()
        for key in r.scan_iter("checkpoint:*:__empty__:*"):
            thread_id = key.decode().split(':')[1]
            if thread_id in seen_threads:
                continue
            seen_threads.add(thread_id)
            
            state = chatbot['graph'].get_state(
                config={'configurable': {'thread_id': thread_id}}
            )
            
            threads.append({
                'id': str(thread_id),
                'title': str(state.values.get('metadata', {}).get('title', "New Chat")),
                'timestamp': float(state.values.get('metadata', {}).get('created_at', datetime.now().timestamp())),
                'message_count': len([m for m in state.values.get('messages', []) 
                                   if not isinstance(m, SystemMessage)])
            })
        
        return {"threads": sorted(threads, key=lambda x: x['timestamp'], reverse=True)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/threads/{thread_id}/full")
async def get_full_thread(thread_id: str):
    """Get complete conversation history"""
    try:
        state = chatbot.get_state(
            config={'configurable': {'thread_id': thread_id}}
        )
        messages = [
            serialize_message(msg) 
            for msg in state.values.get('messages', [])
            if not isinstance(msg, SystemMessage)
        ]
        return {"messages": messages}
    except Exception as e:
        raise HTTPException(status_code=404, detail="Thread not found")

# In main.py

def setup_redis():
    with RedisSaver.from_conn_string(REDIS_URI) as checkpointer:
        checkpointer.setup()
        with RedisStore.from_conn_string(REDIS_URI) as store:
            store.setup()
            builder = GraphBuilder(streaming=True)
            # Store both the builder and compiled graph
            compiled_graph = builder(checkpointer=checkpointer, store=store)
            return {
                'graph': compiled_graph,
                'builder': builder  # Keep reference to the builder
            }

# Then modify your streaming endpoint:
@app.post("/query_stream")
async def query_chatbot_stream(query: QueryRequest):
    """Handle chat message and stream response"""
    try:
        state = chatbot['graph'].get_state(
            config={'configurable': {'thread_id': query.thread_id}}
        )
        messages = state.values.get('messages', [])
        metadata = state.values.get('metadata', {})
        
        # Add user message with timestamp
        user_msg = HumanMessage(
            content=query.question,
            timestamp=datetime.now().timestamp()
        )
        
        async def event_generator():
            full_response = ""
            # Access LLM through the builder we stored
            async for chunk in chatbot['builder'].model_loader.llm.astream(
                [SystemMessage(content=chatbot['builder'].system_prompt)] +
                [msg for msg in messages if not isinstance(msg, SystemMessage)] +
                [user_msg]
            ):
                if hasattr(chunk, 'content'):
                    content = chunk.content
                    full_response += content
                    yield f"data: {content}\n\n"
                    await asyncio.sleep(0.01)
            
            if full_response:
                assistant_msg = AIMessage(
                    content=full_response,
                    timestamp=datetime.now().timestamp()
                )
                
                if len([m for m in messages if not isinstance(m, SystemMessage)]) == 0:
                    metadata['title'] = generate_thread_title([user_msg])
                
                metadata['updated_at'] = datetime.now().timestamp()
                
                chatbot['graph'].update_state(
                    config={'configurable': {'thread_id': query.thread_id}},
                    values={
                        'messages': messages + [user_msg, assistant_msg],
                        'metadata': metadata
                    }
                )
        
        return StreamingResponse(event_generator(), media_type="text/event-stream")
    
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
    

@app.put("/thread_title")
async def update_thread_title(request: ThreadRequest):
    """Update thread title"""
    try:
        state = chatbot.get_state(
            config={'configurable': {'thread_id': request.thread_id}}
        )
        metadata = state.values.get('metadata', {})
        metadata.update({
            'title': request.title or metadata.get('title', "New Chat"),
            'updated_at': datetime.now().timestamp()
        })
        
        chatbot.update_state(
            config={'configurable': {'thread_id': request.thread_id}},
            values={'metadata': metadata}
        )
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/conversation/{thread_id}")
async def get_conversation(thread_id: str):
    """Get conversation history (legacy endpoint)"""
    try:
        state = chatbot['graph'].get_state(
            config={'configurable': {'thread_id': thread_id}}
        )
        messages = [
            serialize_message(msg)
            for msg in state.values.get('messages', [])
            if not isinstance(msg, SystemMessage)
        ]
        return {"messages": messages}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))