import os
import logging
from typing import Optional, Dict, Any, Generator, Union
from dotenv import load_dotenv

# Configure logging
logger = logging.getLogger(__name__)

# --- Configuration ---
# Explicitly load .env file from backend directory
current_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.dirname(current_dir)
env_path = os.path.join(backend_dir, ".env")
load_dotenv(env_path)

# Provider configuration
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "openai").lower()  # openai, gemini, anthropic, ollama, lmstudio, etc.
LLM_API_KEY = os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY") or os.getenv("GEMINI_API_KEY")
LLM_BASE_URL = os.getenv("LLM_BASE_URL")  # Optional: custom endpoint for OpenAI-compatible APIs
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o-mini")  # Default model name

if not LLM_API_KEY:
    logger.warning("LLM_API_KEY environment variable not set. LLM features may fail.")

# --- Schemas ---
# Schema for a single question (OpenAI compatible format)
question_schema = {
    "type": "object",
    "properties": {
        "description": {"type": "string"},
        "options": {
            "type": "array",
            "items": {"type": "string"}
        },
        "answer": {"type": "string"},
        "explanation": {"type": "string"}
    },
    "required": ["description", "options", "answer"]
}

# Schema for the list of questions (Top level response)
questions_schema = {
    "type": "array",
    "items": question_schema
}


class LLMClient:
    """
    Unified LLM client that supports multiple providers via OpenAI-compatible API.
    Supports: OpenAI, Gemini, Anthropic (via proxy), Ollama, LM Studio, vLLM, etc.
    """
    
    def __init__(self, provider: str = "openai", api_key: Optional[str] = None, 
                 base_url: Optional[str] = None, model: Optional[str] = None):
        self.provider = provider
        self.api_key = api_key
        self.base_url = base_url
        self.model = model or "gpt-4o-mini"
        self._client = None
        self._init_client()
    
    def _init_client(self):
        """Initialize the appropriate client based on provider."""
        try:
            from openai import OpenAI
            
            # Configure base URL based on provider
            if self.base_url:
                # Custom endpoint provided
                base_url = self.base_url
            elif self.provider == "openai":
                base_url = "https://api.openai.com/v1"
            elif self.provider == "gemini":
                # Google AI Studio OpenAI-compatible endpoint
                base_url = "https://generativelanguage.googleapis.com/v1beta/openai"
            elif self.provider == "ollama":
                base_url = "http://localhost:11434/v1"
            elif self.provider == "lmstudio":
                base_url = "http://localhost:1234/v1"
            elif self.provider == "anthropic":
                # Anthropic doesn't have native OpenAI compat, but can use proxies
                logger.warning("Anthropic requires an OpenAI-compatible proxy. Set LLM_BASE_URL.")
                base_url = None
            else:
                # Assume it's a custom OpenAI-compatible endpoint
                base_url = None
            
            # Initialize OpenAI client
            kwargs = {"api_key": self.api_key or "not-needed"}
            if base_url:
                kwargs["base_url"] = base_url
            
            self._client = OpenAI(**kwargs)
            logger.info(f"Initialized LLM client for provider: {self.provider}, model: {self.model}")
            
        except ImportError:
            logger.error("openai package not installed. Run: pip install openai")
            raise
    
    def generate_content(self, prompt: str, generation_config: Optional[Dict] = None, 
                        stream: bool = False, use_web_search: bool = False) -> Union[Any, Generator]:
        """
        Generate content using the configured LLM provider.
        
        Args:
            prompt: The input prompt/text
            generation_config: Configuration including response_schema, temperature, etc.
            stream: Whether to stream the response
            use_web_search: Whether to enable web search (provider-dependent)
        
        Returns:
            Response object or generator depending on stream parameter
        """
        if not self._client:
            raise RuntimeError("LLM client not initialized")
        
        # Build request parameters
        messages = [{"role": "user", "content": prompt}]
        
        config = {}
        if generation_config:
            # Map generation_config to OpenAI parameters
            if hasattr(generation_config, 'temperature'):
                config['temperature'] = generation_config.temperature
            elif isinstance(generation_config, dict) and 'temperature' in generation_config:
                config['temperature'] = generation_config['temperature']
            else:
                config['temperature'] = 0.7
            
            # Handle response schema for JSON mode
            if hasattr(generation_config, 'response_schema'):
                config['response_format'] = {
                    "type": "json_schema",
                    "json_schema": {
                        "name": "questions_response",
                        "schema": generation_config.response_schema,
                        "strict": True
                    }
                }
            elif isinstance(generation_config, dict) and 'response_schema' in generation_config:
                config['response_format'] = {
                    "type": "json_schema",
                    "json_schema": {
                        "name": "questions_response",
                        "schema": generation_config['response_schema'],
                        "strict": True
                    }
                }
            elif hasattr(generation_config, 'response_mime_type'):
                if generation_config.response_mime_type == "application/json":
                    config['response_format'] = {"type": "json_object"}
        
        # Web search tools (provider-dependent)
        tools = None
        if use_web_search:
            if self.provider == "openai":
                tools = [{"type": "web_search_preview"}]
            elif self.provider == "gemini":
                # Gemini web search via tools
                tools = [{"googleSearch": {}}]
            # Other providers may not support web search
        
        if tools:
            config['tools'] = tools
        
        try:
            if stream:
                # Streaming response
                response = self._client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    stream=True,
                    **config
                )
                return response
            else:
                # Non-streaming response
                response = self._client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    **config
                )
                return response
        except Exception as e:
            logger.error(f"Error in generate_content: {e}")
            raise e


class ModelWrapper:
    """
    Wrapper to maintain backward compatibility with existing code.
    Adapts the new LLMClient to the old interface.
    """
    def __init__(self, client: LLMClient, model_name: str):
        self.client = client
        self.model_name = model_name

    def generate_content(self, prompt: str, generation_config: Optional[Dict] = None, 
                        stream: bool = False, use_web_search: bool = False):
        """
        Wraps LLMClient.generate_content to maintain old interface.
        Supports both streaming and non-streaming responses.
        Supports grounding with Google Search when use_web_search=True.
        """
        return self.client.generate_content(
            prompt=prompt,
            generation_config=generation_config,
            stream=stream,
            use_web_search=use_web_search
        )


# Create the global model instance
llm_client = LLMClient(
    provider=LLM_PROVIDER,
    api_key=LLM_API_KEY,
    base_url=LLM_BASE_URL,
    model=LLM_MODEL
)

model = ModelWrapper(llm_client, LLM_MODEL)


# --- Utilities ---

class GenerationConfig:
    """Configuration class for backward compatibility."""
    def __init__(self, response_mime_type: Optional[str] = None, 
                 response_schema: Optional[Dict] = None, 
                 temperature: float = 0.7):
        self.response_mime_type = response_mime_type
        self.response_schema = response_schema
        self.temperature = temperature


def get_generation_config_json(schema: Dict) -> GenerationConfig:
    """
    Returns a config object for JSON response generation.
    """
    return GenerationConfig(
        response_mime_type="application/json",
        response_schema=schema,
        temperature=0.7
    )
