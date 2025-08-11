from typing import TypedDict, Annotated, List, Dict, Any
from langgraph.graph import StateGraph, MessagesState, START, END
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage, AIMessage, SystemMessage, HumanMessage
from backend.model_loader import ModelLoader
from backend.prompt import SYSTEM_PROMPT
import uuid
from datetime import datetime

class ChatState(TypedDict):
    messages: Annotated[List[BaseMessage], add_messages]
    metadata: Dict[str, Any]

class GraphBuilder:
    def __init__(self, model_provider: str = "ollama-llama3", streaming: bool = False):
        self.model_loader = ModelLoader(model_key=model_provider, streaming=streaming)
        self.llm = self.model_loader.load_llm()
        self.streaming = streaming
        self.system_prompt = SYSTEM_PROMPT
        self.graph = None

    def agent_function(self, state: MessagesState):
        messages = state["messages"]
        # Filter out system messages for the actual question
        input_messages = [msg for msg in messages if not isinstance(msg, SystemMessage)]
        
        if self.streaming:
            return {"messages": [AIMessage(content="")]}  # Placeholder for streaming
        else:
            response = self.llm.invoke([SystemMessage(content=self.system_prompt)] + input_messages)
            return {"messages": [response]}

    def build_graph(self, checkpointer=None, store=None):
        workflow = StateGraph(ChatState)
        workflow.add_node("chat_node", self.agent_function)
        workflow.add_edge(START, "chat_node")
        workflow.add_edge("chat_node", END)
        
        # Corrected compilation without config parameter
        if checkpointer:
            self.graph = workflow.compile(
                checkpointer=checkpointer
            )
        else:
            self.graph = workflow.compile()
            
        return self.graph

    @staticmethod
    def retrieve_all_threads(checkpointer):
        try:
            if not checkpointer or not hasattr(checkpointer, 'client'):
                return []
                
            redis_client = checkpointer.client.client.connection
            all_threads = []
            
            # Scan for all thread states
            for key in redis_client.scan_iter("langgraph:checkpoint:*:thread:*"):
                print(f"Found Redis key: {key}")
                try:
                    parts = key.decode().split(':')
                    if len(parts) >= 5:  # langgraph:checkpoint:{hash}:thread:{id}
                        thread_id = parts[-1]
                        all_threads.append({
                            'id': thread_id,
                            'key': key.decode()
                        })
                except Exception as e:
                    print(f"Error processing key {key}: {e}")
                    continue
            
            print(f"Total threads found: {len(all_threads)}")
            return all_threads
        except Exception as e:
            print(f"Error in retrieve_all_threads: {e}")
            return []

    def _get_conversation_preview(self, messages: List[BaseMessage]) -> str:
        """Generate a preview snippet from conversation messages"""
        for msg in reversed(messages):
            if isinstance(msg, HumanMessage):
                return msg.content[:50] + "..." if len(msg.content) > 50 else msg.content
        return "New Chat"

    def __call__(self, checkpointer=None, store=None):
        return self.build_graph(checkpointer=checkpointer, store=store)