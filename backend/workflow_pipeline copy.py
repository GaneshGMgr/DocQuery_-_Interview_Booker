from typing import TypedDict, Annotated, List, Dict, Any
from langgraph.graph import StateGraph, MessagesState, START, END
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage, AIMessage, SystemMessage, HumanMessage
from backend.model_loader import ModelLoader
from backend.prompt import SYSTEM_PROMPT
from datetime import datetime
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ChatState(TypedDict):
    messages: Annotated[List[BaseMessage], add_messages]
    metadata: Dict[str, Any]

class GraphBuilder:
    def __init__(self, model_provider: str = "ollama-llama3", streaming: bool = True):
        self.model_loader = ModelLoader(model_key=model_provider, streaming=streaming)
        self.llm = self.model_loader.load_llm()
        self.streaming = streaming
        self.system_prompt = SYSTEM_PROMPT or """You are a helpful AI assistant. 
            Be concise, friendly, and maintain conversation context."""
        self.graph = None
        logger.info("GraphBuilder initialized with %s provider", model_provider)

    def _add_message_metadata(self, message: BaseMessage) -> BaseMessage:
        """Ensure all messages have proper metadata"""
        if not hasattr(message, 'timestamp'):
            message.timestamp = datetime.now().timestamp()
        return message

    def agent_function(self, state: ChatState) -> Dict[str, List[BaseMessage]]:
        """Process messages and generate response"""
        try:
            messages = state["messages"]
            
            # Filter and prepare messages
            input_messages = [
                self._add_message_metadata(msg) 
                for msg in messages 
                if not isinstance(msg, SystemMessage)
            ]
            
            # Prepare full context
            full_context = [SystemMessage(content=self.system_prompt)] + input_messages
            
            if self.streaming:
                logger.debug("Returning streaming placeholder")
                return {"messages": [AIMessage(content="", timestamp=datetime.now().timestamp())]}
            
            # Generate response
            response = self.llm.invoke(full_context)
            response = self._add_message_metadata(response)
            
            logger.info("Generated response for %d message conversation", len(input_messages))
            return {"messages": [response]}
            
        except Exception as e:
            logger.error("Error in agent_function: %s", str(e))
            raise

    def build_graph(self, checkpointer=None, store=None):
        """Build and compile the state graph"""
        try:
            workflow = StateGraph(ChatState)
            
            # Define nodes
            workflow.add_node("chat_node", self.agent_function)
            
            # Define edges
            workflow.add_edge(START, "chat_node")
            workflow.add_edge("chat_node", END)
            
            # Compile graph
            compilation_params = {}
            if checkpointer:
                compilation_params["checkpointer"] = checkpointer
                logger.debug("Building graph with checkpointer")
            
            self.graph = workflow.compile(**compilation_params)
            logger.info("Successfully compiled workflow graph")
            return self.graph
            
        except Exception as e:
            logger.error("Error building graph: %s", str(e))
            raise

    @staticmethod
    def retrieve_all_threads(checkpointer) -> List[Dict[str, str]]:
        """Get all conversation threads from Redis"""
        threads = []
        try:
            if not checkpointer or not hasattr(checkpointer, 'client'):
                logger.warning("No valid checkpointer provided")
                return threads
                
            redis_client = checkpointer.client.client.connection
            
            # Scan for all thread keys
            for key in redis_client.scan_iter("checkpoint:*:__empty__:*"):
                try:
                    parts = key.decode().split(':')
                    if len(parts) >= 4:  # checkpoint:{thread_id}:__empty__:{version}
                        thread_id = parts[1]
                        threads.append({
                            'id': thread_id,
                            'key': key.decode()
                        })
                except Exception as e:
                    logger.error("Error processing key %s: %s", key, str(e))
        
            logger.info("Retrieved %d threads from Redis", len(threads))
            return threads
            
        except Exception as e:
            logger.error("Error retrieving threads: %s", str(e))
            return []

    def __call__(self, checkpointer=None, store=None):
        """Callable interface for graph building"""
        return self.build_graph(checkpointer=checkpointer, store=store)