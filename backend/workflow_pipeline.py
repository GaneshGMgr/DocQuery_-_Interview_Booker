from typing import TypedDict, Annotated
from langgraph.graph import StateGraph, MessagesState, START, END
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage

from model_loader import ModelLoader
from prompt import SYSTEM_PROMPT

class ChatState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]

class GraphBuilder:
    def __init__(self, model_provider: str = "ollama-llama3"):
        self.model_loader = ModelLoader(model_key=model_provider)
        self.llm = self.model_loader.load_llm()

        self.tools = []
        self.llm_with_tools = self.llm

        self.graph = None
        self.system_prompt = SYSTEM_PROMPT

    def agent_function(self, state: MessagesState):
        user_question = state["messages"]
        input_question = [self.system_prompt] + user_question
        response = self.llm.invoke(input_question)
        return {"messages": [response]}

    def build_graph(self, checkpointer=None):
        graph = StateGraph(ChatState)
        graph.add_node("chat_node", self.agent_function)
        graph.add_edge(START, "chat_node")
        graph.add_edge("chat_node", END)
        self.graph = graph.compile(checkpointer=checkpointer)
        return self.graph

    @staticmethod
    def retrieve_all_threads(checkpointer):
        all_threads = set()
        for checkpoint in checkpointer.list(None):
            try:
                thread_id = checkpoint['configurable']['thread_id']
                all_threads.add(thread_id)
            except (KeyError, AttributeError):
                continue
        return list(all_threads)

    def __call__(self, checkpointer=None):
        return self.build_graph(checkpointer=checkpointer)
