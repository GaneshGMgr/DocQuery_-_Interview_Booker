from typing import TypedDict, Annotated, Optional
from langgraph.graph import StateGraph, MessagesState, START, END
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage, AIMessage

from backend.model_loader import ModelLoader
from backend.prompt import SYSTEM_PROMPT

class ChatState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]

class GraphBuilder:
    def __init__(self, model_provider: str = "ollama-llama3", streaming: bool = False):
        self.model_loader = ModelLoader(model_key=model_provider, streaming=streaming)
        self.llm = self.model_loader.load_llm()
        self.streaming = streaming

        self.tools = []
        self.llm_with_tools = self.llm

        self.graph = None
        self.system_prompt = SYSTEM_PROMPT

    def agent_function(self, state: MessagesState):
        messages = state["messages"]
        input_question = [self.system_prompt] + messages
        if self.streaming:
            response = self.llm.invoke(input_question) # For streaming, we'll handle it differently in the endpoint
            return {"messages": [response]}
        else:
            response = self.llm.invoke(input_question)
            return {"messages": [response]}

    def build_graph(self, checkpointer=None, store=None):
        graph = StateGraph(ChatState)
        graph.add_node("chat_node", self.agent_function)
        graph.add_edge(START, "chat_node")
        graph.add_edge("chat_node", END)
        self.graph = graph.compile(checkpointer=checkpointer, store=store)
        return self.graph

    # In workflow.py
    @staticmethod
    def retrieve_all_threads(checkpointer):
        all_threads = set()
        try:
            # Get the raw Redis client
            redis_client = checkpointer.client.connection
            
            # Scan for all thread keys (adjust pattern based on your actual key structure)
            for key in redis_client.scan_iter("*thread*"):
                try:
                    # Extract thread_id - this depends on your key naming scheme
                    parts = key.decode().split(':')
                    thread_id = parts[-1]  # Adjust index if needed
                    all_threads.add(thread_id)
                except Exception as e:
                    print(f"Error processing key {key}: {e}")
                    continue
                    
            return list(all_threads)
        except Exception as e:
            print(f"Error in retrieve_all_threads: {e}")
            return []

    def __call__(self, checkpointer=None, store=None):
        return self.build_graph(checkpointer=checkpointer, store=store)