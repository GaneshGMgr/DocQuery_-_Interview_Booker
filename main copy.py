from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
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

class QueryRequest(BaseModel):
    question: str
    thread_id: str

class ThreadRequest(BaseModel):
    thread_id: str
    title: Optional[str] = None

# Initialize Redis
REDIS_URI = "redis://localhost:6379"

with RedisSaver.from_conn_string(REDIS_URI) as checkpointer:
    checkpointer.setup()
    
    with RedisStore.from_conn_string(REDIS_URI) as store:
        store.setup()
        
        # Compile graph
        builder = GraphBuilder(streaming=True)
        chatbot = builder(checkpointer=checkpointer, store=store)

# Initializes a new chat thread with a fresh state and default system message
@app.post("/init_thread")
async def init_thread(request: ThreadRequest):
    try:
        # Initialize thread with system message
        initial_state = {
            "messages": [SystemMessage(content=builder.system_prompt)],
            "metadata": {
                "created_at": datetime.now().timestamp(),
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

# Add these new endpoints
@app.get("/threads/{thread_id}/full")
async def get_full_conversation(thread_id: str):
    """Get complete conversation history for a thread"""
    try:
        state = chatbot.get_state(config={'configurable': {'thread_id': thread_id}})
        messages = [
            {
                "role": "user" if isinstance(msg, HumanMessage) else "assistant",
                "content": msg.content,
                "timestamp": getattr(msg, "timestamp", None)
            }
            for msg in state.values.get("messages", [])
            if not isinstance(msg, SystemMessage)
        ]
        return {"messages": messages}
    except Exception as e:
        raise HTTPException(status_code=404, detail="Thread not found")

@app.post("/threads/{thread_id}/clear")
async def clear_conversation(thread_id: str):
    """Reset a conversation thread"""
    try:
        initial_state = {
            "messages": [SystemMessage(content=builder.system_prompt)],
            "metadata": {
                "created_at": datetime.now().timestamp(),
                "title": "New Chat",
                "updated_at": datetime.now().timestamp()
            }
        }
        chatbot.update_state(
            config={'configurable': {'thread_id': thread_id}},
            values=initial_state
        )
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
# Enhanced query endpoint
@app.post("/query_stream")
async def query_chatbot_stream(query: QueryRequest):
    try:
        state = chatbot.get_state(config={'configurable': {'thread_id': query.thread_id}})
        messages = state.values.get('messages', [])
        
        # Store user message with timestamp
        user_message = HumanMessage(
            content=query.question,
            timestamp=datetime.now().timestamp()
        )
        
        # Generate response
        async def event_generator():
            full_response = ""
            async for chunk in builder.model_loader.llm.astream(
                [SystemMessage(content=builder.system_prompt)] +
                [msg for msg in messages if not isinstance(msg, SystemMessage)] +
                [user_message]
            ):
                if hasattr(chunk, 'content'):
                    content = chunk.content
                    full_response += content
                    yield f"data: {content}\n\n"
                    await asyncio.sleep(0.01)
            
            if full_response:
                # Store assistant response with timestamp
                assistant_message = AIMessage(
                    content=full_response,
                    timestamp=datetime.now().timestamp()
                )
                
                # Update thread title if first interaction
                metadata = state.values.get('metadata', {})
                if len(messages) <= 1:  # Only system message exists
                    metadata['title'] = query.question[:30] + ("..." if len(query.question) > 30 else "")
                
                chatbot.update_state(
                    config={'configurable': {'thread_id': query.thread_id}},
                    values={
                        'messages': messages + [user_message, assistant_message],
                        'metadata': metadata
                    }
                )

        return StreamingResponse(event_generator(), media_type="text/event-stream")
    
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


# Fetches a list of all chat threads stored in the Redis
@app.get("/threads")
async def get_threads():
    try:
        r = redis.Redis.from_url(REDIS_URI)
        unique_threads = []
        
        # Get all thread IDs from checkpoint_latest keys
        seen_threads = set()
        for latest_key in r.scan_iter("checkpoint_latest:*"):
            thread_id = latest_key.decode().split(':')[1]
            seen_threads.add(thread_id)
            
            # Get the full conversation
            state = chatbot.get_state(config={'configurable': {'thread_id': thread_id}})
            messages = state.values.get('messages', [])
            
            # Extract human messages for preview
            chat_preview = [
                msg.content for msg in messages 
                if isinstance(msg, HumanMessage)
            ][-3:]  # Last 3 human messages
            
            unique_threads.append({
                'id': thread_id,
                'title': state.values.get('metadata', {}).get('title', "New Chat"),
                'timestamp': state.values.get('metadata', {}).get('created_at', datetime.now().timestamp()),
                'preview_messages': chat_preview,
                'message_count': len(messages)
            })

        return {
            "threads": sorted(
                unique_threads, 
                key=lambda x: x['timestamp'], 
                reverse=True
            )
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    

# Updates the title of a specific chat thread
@app.put("/thread_title")
async def update_thread_title(request: ThreadRequest):
    try:
        state = chatbot.get_state(config={'configurable': {'thread_id': request.thread_id}})
        metadata = state.values.get('metadata', {})
        metadata.update({
        'title': request.title or metadata.get('title', f"Chat"),
        'updated_at': datetime.now().timestamp()
    })
        
        chatbot.update_state(
            config={'configurable': {'thread_id': request.thread_id}},
            values={'metadata': metadata}
        )
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Fetches the full message history for a given thread ID.
@app.get("/conversation/{thread_id}")
async def get_conversation(thread_id: str):
    try:
        state = chatbot.get_state(config={'configurable': {'thread_id': thread_id}})
        messages = state.values.get('messages', [])
        print(f"Retrieved {len(messages)} messages for thread {thread_id}")
        
        serialized = []
        for msg in messages:
            if isinstance(msg, SystemMessage):
                continue
                
            role = 'user' if isinstance(msg, HumanMessage) else 'assistant'
            serialized.append({
                'role': role,
                'content': msg.content,
                'timestamp': getattr(msg, 'timestamp', None)
            })
            
        return {"messages": serialized}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# python -m uvicorn main:app --reload
# docker run --name redis-server -d -p 6379:6379 redis
# docker ps
## check if data is still there or not in redis
# docker exec -it redis-server redis-cli
# keys *