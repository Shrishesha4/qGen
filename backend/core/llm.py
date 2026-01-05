import os
import logging
from google import genai
from google.genai import types
from dotenv import load_dotenv

# Configure logging
logger = logging.getLogger(__name__)

# --- Configuration ---
# Explicitly load .env file from backend directory
current_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.dirname(current_dir)
env_path = os.path.join(backend_dir, ".env")
load_dotenv(env_path)

API_KEY = os.getenv("GEMINI_API_KEY")

if not API_KEY:
    logger.warning("GEMINI_API_KEY environment variable not set. LLM features may fail.")

# Initialize the client
client = genai.Client(api_key=API_KEY)

# --- Model Configuration ---
MODEL_NAME = "gemini-flash-latest"

# --- Schemas ---
# The new SDK allows defining schemas using dictionaries, similar to the old one,
# but passing them is slightly different in the config.

# Schema for a single question
question_schema = {
    "type": "OBJECT",
    "properties": {
        "description": {"type": "STRING"},
        "options": {
            "type": "ARRAY",
            "items": {"type": "STRING"}
        },
        "answer": {"type": "STRING"},
        "explanation": {"type": "STRING"}
    },
    "required": ["description", "options", "answer"]
}

# Schema for the list of questions (Top level response)
questions_schema = {
    "type": "ARRAY",
    "items": question_schema
}

# --- Wrapper Class for Compatibility ---
# The rest of the app expects a 'model' object with a 'generate_content' method.
# We'll create a wrapper to adapt the new 'client' to the old interface the app uses.

class ModelWrapper:
    def __init__(self, client, model_name):
        self.client = client
        self.model_name = model_name

    def generate_content(self, prompt, generation_config=None, stream=False, use_web_search=False):
        """
        Wraps the new client.models.generate_content to look like the old model.generate_content
        Supports both streaming and non-streaming responses.
        Supports grounding with Google Search when use_web_search=True.
        Note: Web search grounding may not work with streaming in current API version.
        """
        config = {}
        
        # Adapt the old 'generation_config' object (which was likely a GenerationConfig object)
        # to the new SDK's 'config' dictionary or types.GenerateContentConfig.
        if generation_config:
            # Check if it has a response_schema
            if hasattr(generation_config, 'response_schema'):
                config['response_schema'] = generation_config.response_schema
            if hasattr(generation_config, 'response_mime_type'):
                config['response_mime_type'] = generation_config.response_mime_type
            if hasattr(generation_config, 'temperature'):
                config['temperature'] = generation_config.temperature
        
        # Add grounding with Google Search if requested
        # Note: Some API versions may not support tools with streaming
        tools = None
        if use_web_search and not stream:
            # Only use tools with non-streaming for compatibility
            tools = [types.Tool(google_search=types.GoogleSearch())]

        try:
            if stream:
                # Use generate_content_stream for streaming responses
                # Don't pass tools to streaming - not supported in current API
                response = self.client.models.generate_content_stream(
                    model=self.model_name,
                    contents=prompt,
                    config=config
                )
            else:
                # Use regular generate_content for non-streaming
                response = self.client.models.generate_content(
                    model=self.model_name,
                    contents=prompt,
                    config=config,
                    tools=tools
                )
            return response
        except Exception as e:
            logger.error(f"Error in generate_content: {e}")
            raise e

# Create the global model instance
model = ModelWrapper(client, MODEL_NAME)


# --- Utilities ---

def get_generation_config_json(schema):
    """
    Returns a config object compatible with the new SDK.
    The new SDK expects a 'types.GenerateContentConfig' or just a dict in the 'config' arg.
    """
    return types.GenerateContentConfig(
        response_mime_type="application/json",
        response_schema=schema,
        temperature=0.7
    )
