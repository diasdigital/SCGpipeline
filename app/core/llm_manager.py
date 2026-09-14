"""
app/core/llm_manager.py
=======================
Factory and manager for all LLM providers.

Supported providers:
  "ollama"   -- Local LLM via Ollama (default, no API key required)
  "openai"   -- OpenAI GPT series (requires LLM_API_KEY)
  "fireworks" -- Fireworks AI (requires API_KEY)
  "gemini"   -- Google Gemini (requires LLM_API_KEY, free tier available)
  "none"     -- No active model; FastAPI keeps running, response is a placeholder

How it works:
  1. On startup, configuration is read from .env via settings.
  2. Developers can change the config via PUT /api/dashboard/config -- without restarting.
  3. Changes apply immediately in FastAPI AND are saved to Redis
     so the Celery worker (separate process) can also read them.

Usage in api_routes.py:
  from app.core.llm_manager import llm_manager

  # Streaming to user
  for chunk in llm_manager.stream_text_main(prompt):
      yield chunk

  # Check if model is available
  if not llm_manager.is_available():
      ...

  # Status for diagnostic endpoint
  status = llm_manager.get_status()
"""

import json
from dataclasses import dataclass, asdict
from typing import Any, Generator, Optional

import redis as redis_lib

from app.core.config         import settings
from app.core.logging_config  import get_logger

_logger = get_logger(__name__)

REDIS_APP_CONFIG_KEY = "app:config"

@dataclass
class LLMConfig:
    """Configuration for a single LLM instance."""
    provider: str = "ollama"                   
    model:    str = "llama3"
    api_key:  str = ""
    base_url: str = "http://localhost:11434"    


# ── Helper: normalize LLM vs ChatModel output ─────────────────────────────
#
# IMPORTANT NOTE -- Difference in Gemini 2.x vs 3.x formats:
#
#   Gemini 2.5 and earlier:
#     AIMessage.content  → "J'adore la programmation."  (plain string)
#
#   Gemini 3.x (including gemini-3.1-flash-lite):
#     AIMessage.content  → [{'type': 'text', 'text': "J'adore...", 'extras': {...}}]
#     AIMessage.text     → "J'adore la programmation."  (normalized by LangChain)
#
#   Reference: https://docs.langchain.com/oss/python/integrations/chat/google_generative_ai
#   "Gemini 3 series models return a list of content blocks to capture thought
#    signatures. Use .text to get string content."
#
# Strategy: check .text first (LangChain already normalizes this for all
# Gemini versions), then fallback to .content (for Ollama / other providers).

def _to_text(result: Any) -> str:
    """
    Convert invoke() output to a string.
    Compatible with: OllamaLLM (str), ChatModel Gemini 2.x (AIMessage.content=str),
    and Gemini 3.x (AIMessage.content=list, AIMessage.text=str).
    """
    if isinstance(result, str):
        return result

    if hasattr(result, 'text') and isinstance(result.text, str):
        return result.text

    if hasattr(result, 'content'):
        content = result.content
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            return ''.join(
                part.get('text', '') if isinstance(part, dict) else str(part)
                for part in content
            )

    return str(result)


def _chunk_to_text(chunk: Any) -> str:
    """
    Convert a single stream chunk to a string.
    Compatible with: OllamaLLM (str), AIMessageChunk Gemini 2.x (content=str),
    and AIMessageChunk Gemini 3.x (content=list, .text=str).
    """
    if isinstance(chunk, str):
        return chunk

    if hasattr(chunk, 'text') and isinstance(chunk.text, str):
        return chunk.text

    if hasattr(chunk, 'content'):
        content = chunk.content
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            return ''.join(
                part.get('text', '') if isinstance(part, dict) else str(part)
                for part in content
            )

    return str(chunk)


def build_llm(config: LLMConfig, temperature: float) -> Optional[Any]:
    """
    Create an LLM instance based on the configuration.

    Supported providers:
      - "ollama"    : Local LLM
      - "openai"    : OpenAI GPT series
      - "fireworks"  : Fireworks API
      - "gemini"    : Google Gemini (free tier available)
      - "none"      : No model mode (development)

    Return:
        LLM Instance (OllamaLLM / ChatOpenAI / ChatFireworks / ChatGoogleGenerativeAI),
        or None if provider = 'none'.

    Raise:
        ImportError  -- provider library is not installed.
        ValueError   -- provider is unrecognized or config is incomplete.
    """
    provider = config.provider.strip().lower()

    if provider == "none":
        _logger.info("[LLMManager] Provider='none' -- no model mode active.")
        return None

    if provider == "ollama":
        try:
            from langchain_ollama import OllamaLLM
        except ImportError:
            raise ImportError(
                "langchain-ollama library is not installed. "
                "Run: pip install langchain-ollama"
            )
        return OllamaLLM(
            model=config.model,
            base_url=config.base_url,
            temperature=temperature,
        )

    if provider == "openai":
        try:
            from langchain_openai import ChatOpenAI
        except ImportError:
            raise ImportError(
                "langchain-openai library is not installed. "
                "Run: pip install langchain-openai"
            )
        if not config.api_key:
            raise ValueError(
                "Provider 'openai' requires LLM_API_KEY. "
                "Fill it in .env or update via dashboard."
            )
        return ChatOpenAI(
            model=config.model,
            openai_api_key=config.api_key,
            temperature=temperature,
        )

    if provider == "gemini":
        try:
            from langchain_google_genai import ChatGoogleGenerativeAI
        except ImportError:
            raise ImportError(
                "langchain-google-genai library is not installed. "
                "Run: pip install langchain-google-genai"
            )
        if not config.api_key:
            raise ValueError(
                "Provider 'gemini' requires LLM_API_KEY. "
                "Get it from https://aistudio.google.com/app/apikey"
            )

        # Detect if the model is Gemini 3.0+ based on the model name.
        # LangChain docs: "Using 0.7 with Gemini 3.0+ can cause infinite loops
        # and degraded reasoning. Temperature defaults to 1.0 for Gemini 3.0+."
        # Reference: https://docs.langchain.com/oss/python/integrations/chat/google_generative_ai
        model_name = config.model.lower()
        is_gemini_3_plus = any(
            model_name.startswith(prefix)
            for prefix in ("gemini-3",)
        )

        # If temperature is 0.0 on Gemini 3.0+, leave it as is --
        # the user intentionally requested deterministic. But if using the default 0.7,
        # increase it to 1.0 according to Google's recommendation for Gemini 3.0+.
        effective_temperature = temperature
        if is_gemini_3_plus and abs(temperature - 0.7) < 1e-9:
            effective_temperature = 1.0
            _logger.info(
                f"[LLMManager] Gemini 3.x detected ({config.model}): "
                "temperature increased from 0.7 → 1.0 according to Google's recommendation."
            )

        try:
            return ChatGoogleGenerativeAI(
                model=config.model,
                api_key=config.api_key,
                temperature=effective_temperature,
            )
        except TypeError:
            return ChatGoogleGenerativeAI(
                model=config.model,
                google_api_key=config.api_key,
                temperature=effective_temperature,
            )
    
    if provider == "fireworks":
        try:
            from langchain_fireworks import ChatFireworks
        except ImportError:
            raise ImportError(
                "langchain-fireworks library is not installed. "
                "Run: pip install langchain-fireworks"
            )
        if not config.api_key:
            raise ValueError(
                "Provider 'fireworks' requires LLM_API_KEY. "
                "Fill it in .env or update via dashboard."
            )
        try:
            return ChatFireworks(
                model=config.model,
                api_key=config.api_key,
                temperature=temperature,
            )
        except TypeError:
            return ChatFireworks(
                model=config.model,
                fireworks_api_key=config.api_key,
                temperature=temperature,
            )


    raise ValueError(
        f"Provider '{config.provider}' is unrecognized. "
        "Valid options: 'ollama', 'openai', 'fireworks', 'gemini', 'none'."
    )


def invoke_llm(llm: Any, prompt: str) -> str:
    """Invoke LLM and always return a string (normalize ChatModel output)."""
    return _to_text(llm.invoke(prompt))


def stream_llm(llm: Any, prompt: str) -> Generator[str, None, None]:
    """Stream LLM and yield strings per chunk (normalize ChatModel output)."""
    for chunk in llm.stream(prompt):
        yield _chunk_to_text(chunk)

class LLMManager:
    """
    Singleton to manage configuration and main LLM instances.

    - Lazy init: LLM is not created on import, only when first used.
    - Runtime update: update_config() takes effect immediately without server restart.
    - Redis sync: Runtime config is saved to Redis so Celery workers follow it.
    """

    def __init__(self):
        self._config = LLMConfig(
            provider=settings.LLM_PROVIDER,
            model=settings.LLM_MODEL,
            api_key=settings.LLM_API_KEY,
            base_url=settings.LLM_BASE_URL,
        )
        self._main_llm   = None   
        self._redis: Optional[redis_lib.Redis] = None

    def _get_redis(self) -> Optional[redis_lib.Redis]:
        """Lazy-init Redis client. Returns None if Redis is unavailable."""
        if self._redis is None:
            try:
                r = redis_lib.Redis(
                    host=settings.REDIS_HOST,
                    port=settings.REDIS_PORT,
                    db=0,
                    socket_connect_timeout=2,
                )
                r.ping()
                self._redis = r
            except Exception as e:
                _logger.warning(f"[LLMManager] Redis is unavailable ({e}). "
                      "Config will not be synced to the Celery worker.")
        return self._redis

    def push_config_to_redis(self, extra: Optional[dict] = None):
        """
        Save the current LLM config to Redis.
        The 'extra' field (num_samples, temperature, method, etc.) is also saved
        so the Celery worker can read the latest evaluation config.

        Called automatically by update_config().
        """
        r = self._get_redis()
        if not r:
            return
        payload = asdict(self._config)
        if extra:
            payload.update(extra)
        try:
            r.set(REDIS_APP_CONFIG_KEY, json.dumps(payload))
            _logger.info(f"[LLMManager] Config successfully saved to Redis: "
                  f"provider={self._config.provider}, model={self._config.model}")
        except Exception as e:
            _logger.warning(f"[LLMManager] Failed to save config to Redis: {e}")

    def get_main_llm(self) -> Optional[Any]:
        """
        Get the main LLM instance (temperature=0.0).
        Created lazily when first called.
        Returns None if provider='none'.
        """
        if self._main_llm is None:
            _logger.info(f"[LLMManager] Loading main LLM: "
                  f"provider={self._config.provider}, model={self._config.model}")
            self._main_llm = build_llm(self._config, temperature=0.0)
        return self._main_llm

    def stream_text_main(self, prompt: str) -> Generator[str, None, None]:
        """
        Stream the main LLM response as string chunks.
        If provider='none', yield a placeholder message and finish.
        """
        llm = self.get_main_llm()
        if llm is None:
            yield ("[No active LLM model currently. "
                   "Contact the developer to activate a model.]")
            return
        yield from stream_llm(llm, prompt)

    def get_config(self) -> LLMConfig:
        return self._config

    def update_config(
        self,
        provider: Optional[str] = None,
        model:    Optional[str] = None,
        api_key:  Optional[str] = None,
        base_url: Optional[str] = None,
        extra:    Optional[dict] = None,
    ):
        """
        Update the LLM configuration at runtime (without server restart).

        - The old LLM instance is discarded; a new instance is created when first used again.
        - The config is immediately saved to Redis so Celery workers can read it.

        Args:
            provider : New provider ('ollama'|'openai'|'fireworks'|'none').
            model    : New model name.
            api_key  : New API key.
            base_url : New Base URL (Ollama).
            extra    : Additional fields for Redis -- e.g., num_samples,
                       temperature, method from DashboardConfig.
        """
        if provider is not None: self._config.provider = provider
        if model    is not None: self._config.model    = model
        if api_key  is not None: self._config.api_key  = api_key
        if base_url is not None: self._config.base_url = base_url

        self._main_llm = None

        self.push_config_to_redis(extra=extra)

        _logger.info(
            f"[LLMManager] Config updated -- "
            f"provider={self._config.provider}, "
            f"model={self._config.model}, "
            f"api_key={'✓ present' if self._config.api_key else '✗ empty'}"
        )

    def is_available(self) -> bool:
        """True if there is an active model (provider != 'none')."""
        return self._config.provider.strip().lower() != "none"

    def get_status(self) -> dict:
        """
        LLM status summary for the GET /api/llm/status diagnostic endpoint.
        The API key is NOT returned for security reasons -- only a presence flag.
        """
        return {
            "provider":    self._config.provider,
            "model":       self._config.model,
            "base_url":    (self._config.base_url
                            if self._config.provider == "ollama" else None),
            "has_api_key": bool(self._config.api_key),
            "available":   self.is_available(),
        }


llm_manager = LLMManager()