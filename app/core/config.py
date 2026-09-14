"""
app/core/config.py
===================
Application configuration from environment variables (.env).

All values here are DEFAULT values at startup.
Runtime changes (without restart) are made via the developer dashboard
and saved to Redis so the Celery worker picks them up too.
"""

import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    DATABASE_URL: str = os.getenv("DATABASE_URL", "")
    SECRET_KEY:   str = os.getenv("SECRET_KEY",   "not-secret")

    # LLM_PROVIDER  : "ollama" | "openai" | "gemini" | "fireworks" | "none"
    LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "ollama")
    LLM_MODEL:    str = os.getenv("LLM_MODEL",    "llama3")
    LLM_API_KEY:  str = os.getenv("LLM_API_KEY",  "")
    LLM_BASE_URL: str = os.getenv("LLM_BASE_URL", "http://localhost:11434")

    NUM_SAMPLES:         int   = int(  os.getenv("NUM_SAMPLES",          "5"))
    TEMPERATURE_SAMPLE:  float = float(os.getenv("TEMPERATURE_SAMPLE",   "1.0"))
    EVAL_METHOD:         str   =       os.getenv("EVAL_METHOD",          "nli")
    THRESHOLD_HIGH:      float = float(os.getenv("THRESHOLD_HIGH",       "0.60"))
    THRESHOLD_MID:       float = float(os.getenv("THRESHOLD_MID",        "0.40"))

    REDIS_HOST: str = os.getenv("REDIS_HOST", "localhost")
    REDIS_PORT: int = int(os.getenv("REDIS_PORT", "6379"))

    MLFLOW_TRACKING_URI: str = os.getenv("MLFLOW_TRACKING_URI", "http://localhost:5000")
    MLFLOW_EXPERIMENT:   str = os.getenv("MLFLOW_EXPERIMENT",   "SelfCheckNLI_Evaluation")

    HF_HOME: str = os.getenv("HF_HOME", "")


settings = Settings()