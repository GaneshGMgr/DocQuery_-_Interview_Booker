from langgraph.graph import StateGraph, START, END
from typing import TypedDict, Annotated
from langchain_core.messages import BaseMessage
# from langchain_openai import ChatOpenAI
from langchain_ollama import ChatOllama
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph.message import add_messages
from dotenv import load_dotenv
import sqlite3

GRAPH_IMAGE_PATH = "chatbot_architecture.png"

load_dotenv()

# llm = ChatOpenAI()
llm = ChatOllama(model="llama3.2")

class ChatState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]

def chat_node(state: ChatState):
    messages = state['messages']
    response = llm.invoke(messages)
    return {"messages": [response]}

conn = sqlite3.connect(database='chatbot_database.db', check_same_thread=False)
# Checkpointer
checkpointer = SqliteSaver(conn=conn)

graph = StateGraph(ChatState)
graph.add_node("chat_node", chat_node)
graph.add_edge(START, "chat_node")
graph.add_edge("chat_node", END)


chatbot = graph.compile(checkpointer=checkpointer)


# Collects all unique thread_id values from the checkpointer’s
def retrieve_all_threads():
    # set to store unique thread IDs (sets automatically avoid duplicates)
    all_threads = set()

    # Loop through all checkpoints stored in the checkpointer
    # Passing None means "list all checkpoints without filtering"
    for checkpoint in checkpointer.list(None):
        
        # Access the configuration data for this checkpoint
        # 'configurable' is a dictionary holding metadata like 'thread_id'
        thread_id = checkpoint.config['configurable']['thread_id']
        all_threads.add(thread_id) # Add this thread ID to the set

    return list(all_threads)