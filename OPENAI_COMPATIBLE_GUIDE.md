# OpenAI-Compatible LLM Provider Guide

This application now supports **any OpenAI-compatible API provider** for question generation. You can use cloud providers, local models, or self-hosted solutions.

## Quick Setup

### 1. Install Dependencies

```bash
pip install openai
```

### 2. Configure Environment Variables

Set these in your `.env` file:

```bash
# Required: Choose your provider
LLM_PROVIDER=openai

# Required: Your API key (or "not-needed" for local models)
LLM_API_KEY=your-api-key

# Optional: Custom base URL for self-hosted or alternative providers
LLM_BASE_URL=https://api.example.com/v1

# Optional: Model name
LLM_MODEL=gpt-4o-mini
```

## Supported Providers

### Cloud Providers

#### OpenAI
```bash
LLM_PROVIDER=openai
LLM_API_KEY=sk-...
LLM_MODEL=gpt-4o-mini
# No need to set LLM_BASE_URL - uses default
```

#### Google Gemini (via OpenAI-compatible endpoint)
```bash
LLM_PROVIDER=gemini
LLM_API_KEY=your-gemini-api-key
LLM_MODEL=gemini-2.0-flash-exp
# Uses Google's OpenAI-compatible endpoint automatically
```

#### Anthropic Claude (via proxy like LiteLLM)
```bash
LLM_PROVIDER=anthropic
LLM_API_KEY=your-anthropic-key
LLM_BASE_URL=http://localhost:4000  # Your proxy URL
LLM_MODEL=claude-3-5-sonnet-20241022
```

#### OpenRouter (Multiple models)
```bash
LLM_PROVIDER=openrouter
LLM_API_KEY=your-openrouter-key
LLM_BASE_URL=https://openrouter.ai/api/v1
LLM_MODEL=anthropic/claude-3-5-sonnet
```

#### Together AI
```bash
LLM_PROVIDER=together
LLM_API_KEY=your-together-key
LLM_BASE_URL=https://api.together.xyz/v1
LLM_MODEL=meta-llama/Llama-3-70b-chat-hf
```

#### Groq
```bash
LLM_PROVIDER=groq
LLM_API_KEY=your-groq-key
LLM_BASE_URL=https://api.groq.com/openai/v1
LLM_MODEL=llama-3.1-70b-versatile
```

### Local Models

#### Ollama
1. Install Ollama: https://ollama.ai
2. Pull a model: `ollama pull llama2`
3. Configure:
```bash
LLM_PROVIDER=ollama
LLM_API_KEY=not-needed
LLM_BASE_URL=http://localhost:11434/v1
LLM_MODEL=llama2
```

#### LM Studio
1. Install LM Studio: https://lmstudio.ai
2. Load a model and start server
3. Configure:
```bash
LLM_PROVIDER=lmstudio
LLM_API_KEY=not-needed
LLM_BASE_URL=http://localhost:1234/v1
LLM_MODEL=local-model
```

#### vLLM
1. Install and run vLLM with your model
2. Configure:
```bash
LLM_PROVIDER=vllm
LLM_API_KEY=not-needed
LLM_BASE_URL=http://localhost:8000/v1
LLM_MODEL=your-model-name
```

#### LocalAI
```bash
LLM_PROVIDER=localai
LLM_API_KEY=not-needed
LLM_BASE_URL=http://localhost:8080/v1
LLM_MODEL=your-model
```

## Configuration Priority

The system checks for API keys in this order:
1. `LLM_API_KEY` (recommended)
2. `OPENAI_API_KEY` (backward compatibility)
3. `GEMINI_API_KEY` (backward compatibility)

## Features

### JSON Schema Support
The implementation uses OpenAI's structured outputs (JSON Schema mode) when available, ensuring reliable JSON responses for question generation.

### Streaming Support
Both streaming and non-streaming responses are supported for real-time feedback.

### Web Search
Web search is supported for providers that offer it:
- OpenAI: `web_search_preview` tool
- Gemini: `googleSearch` tool

## Troubleshooting

### "openai package not installed"
```bash
pip install openai
```

### "LLM_API_KEY environment variable not set"
Set your API key in the `.env` file or as an environment variable.

### Connection errors with local providers
- Ensure the local server is running
- Check the `LLM_BASE_URL` is correct
- Verify firewall settings allow connections

### JSON parsing errors
Some models may not fully support JSON schema mode. Try:
- Using a more capable model
- Setting `LLM_BASE_URL` to a provider with better JSON support
- Checking model documentation for structured output support

## Example .env Files

### Using OpenAI
```bash
LLM_PROVIDER=openai
LLM_API_KEY=sk-proj-xxxxx
LLM_MODEL=gpt-4o-mini
```

### Using Ollama (Local)
```bash
LLM_PROVIDER=ollama
LLM_API_KEY=not-needed
LLM_BASE_URL=http://localhost:11434/v1
LLM_MODEL=llama3.1
```

### Using OpenRouter
```bash
LLM_PROVIDER=openrouter
LLM_API_KEY=sk-or-xxxxx
LLM_BASE_URL=https://openrouter.ai/api/v1
LLM_MODEL=google/gemma-2-9b-it:free
```

### Using Gemini via OpenAI-compatible API
```bash
LLM_PROVIDER=gemini
LLM_API_KEY=your-gemini-key
LLM_MODEL=gemini-2.0-flash-exp
```

## Migration from Google GenAI SDK

If you were using the native Google GenAI SDK, the new implementation maintains backward compatibility:

1. Old `GEMINI_API_KEY` still works
2. The interface remains the same (`model.generate_content()`)
3. All existing code continues to work without changes

Simply update your `.env` file to use the new variables if you want to switch providers.
