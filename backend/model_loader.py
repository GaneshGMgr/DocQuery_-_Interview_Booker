import os
from dotenv import load_dotenv
from typing import Literal
from pydantic import BaseModel, Field
from config_loader import load_config # yaml loader
from langchain_ollama import ChatOllama

load_dotenv()

class ConfigLoader:
    def __init__(self):
        print("Loading config...")
        self.config = load_config()

    def __getitem__(self, key):
        return self.config[key]

class ModelLoader(BaseModel): # BaseModel helps with data validation, settings management, and more 
    # it can only be one of these exact strings: "groq", "openai", "ollama-deepseek", "ollama-llama3", or "ollama-mistral"
    # It acts like a validation check: if you try to create a ModelLoader instance with some other string as model_key, Pydantic will raise an error.
    model_key: Literal[
        "ollama-deepseek", 
        "ollama-llama3", 
        "ollama-mistral"
    ] = "ollama-llama3" # default is ollama-llama3

    config: ConfigLoader = Field(default_factory=ConfigLoader, exclude=True)

    class Config:
        arbitrary_types_allowed = True

    def load_llm(self):
        print("LLM loading...")
        print(f"Loading model with config key: {self.model_key}")

        # Read provider and model_name dynamically from config
        provider = self.config["llm"][self.model_key]["provider"]
        model_name = self.config["llm"][self.model_key]["model_name"]


        if provider == "ollama":
            print(f"Using Ollama model: {model_name}")
            return ChatOllama(model=model_name)

        else:
            raise ValueError(f"Unsupported provider: {provider}")