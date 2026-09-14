"""
app/services/detection_task.py
================================
Celery task to detect hallucination in a single LLM response.

Changes from the previous version:
  - LLM for sampling is NO longer created at the module level.
    It is now created lazily inside the task, based on the config read
    from Redis. This allows the Celery worker to start up even if Ollama
    is not yet running.

  - Config (provider, model, api_key, base_url, num_samples, temperature,
    method) is read from the Redis key 'app:config' written by FastAPI
    every time the developer changes settings in the dashboard.
    Falls back to environment variables if Redis is unavailable.

  - 'none' mode (no model): the task immediately marks is_evaluating=False
    and returns without performing sampling or evaluation.
"""

import json
import os
import sys
import time

# os.environ["HF_HUB_OFFLINE"] = "1"
# os.environ["TRANSFORMERS_OFFLINE"] = "1"

import mlflow
import redis
from celery import Celery

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from app.core.database          import SessionLocal
from app.core.logging_config    import get_logger
from app.models                 import domain_models
from app.evaluator              import HallucinationEvaluator

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# CONNECTION CONFIGURATION
# ---------------------------------------------------------------------------

_REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
_REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))

redis_client = redis.Redis(host=_REDIS_HOST, port=_REDIS_PORT, db=0)

mlflow.set_tracking_uri(os.getenv("MLFLOW_TRACKING_URI", "http://localhost:5000"))
mlflow.set_experiment(os.getenv("MLFLOW_EXPERIMENT", "SelfCheckNLI_Evaluation"))

celery_app = Celery(
    "hallucination_tasks",
    broker  = f"redis://{_REDIS_HOST}:{_REDIS_PORT}/0",
    backend = f"redis://{_REDIS_HOST}:{_REDIS_PORT}/0",
)

_REDIS_APP_CONFIG_KEY = "app:config"

# ---------------------------------------------------------------------------
# SINGLETON EVALUATOR
# ---------------------------------------------------------------------------

_evaluator: HallucinationEvaluator | None = None


def _get_evaluator(method: str = "nli") -> HallucinationEvaluator:
    """
    Returns a HallucinationEvaluator instance.
    Created once and then cached (singleton).
    If the method differs from the cached one, the evaluator is reloaded.
    """
    global _evaluator
    if _evaluator is None or _evaluator.method != method:
        logger.info(f"[DetectionTask] Loading evaluator -- method={method}...")
        _evaluator = HallucinationEvaluator(method=method)
    return _evaluator


# ---------------------------------------------------------------------------
# HELPER: READ CONFIG FROM REDIS
# ---------------------------------------------------------------------------

def _read_task_config() -> dict:
    """
    Read runtime config from Redis.
    If Redis is unavailable or the key does not exist, use env vars as fallback.

    Returns a dict with keys:
      provider, model, api_key, base_url,
      num_samples, temperature, method
    """
    fallback = {
        "provider":    os.getenv("LLM_PROVIDER", "ollama"),
        "model":       os.getenv("LLM_MODEL", "llama3"),
        "api_key":     os.getenv("LLM_API_KEY", ""),
        "base_url":    os.getenv("LLM_BASE_URL", "http://localhost:11434"),
        "num_samples": int(os.getenv("NUM_SAMPLES", "5")),
        "temperature": float(os.getenv("TEMPERATURE_SAMPLE", "1.0")),
        "method":      os.getenv("EVAL_METHOD", "nli"),
    }

    try:
        data = redis_client.get(_REDIS_APP_CONFIG_KEY)
        if data:
            redis_config = json.loads(data)
            merged = {**fallback, **redis_config}
            return merged
    except Exception as e:
        logger.error(f"[DetectionTask] Cannot read config from Redis: {e}. "
              "Using env vars.")

    return fallback


# ---------------------------------------------------------------------------
# HELPER: BUILD LLM FOR SAMPLING
# ---------------------------------------------------------------------------

def _build_sample_llm(config: dict, temperature: float):
    """
    Create an LLM instance for sampling based on the config dict.
    Returns None if provider = 'none'.
    Uses the build_llm function from llm_manager for consistent logic.
    """
    from app.core.llm_manager import build_llm, LLMConfig

    llm_cfg = LLMConfig(
        provider=config["provider"],
        model=config["model"],
        api_key=config.get("api_key", ""),
        base_url=config.get("base_url", "http://localhost:11434"),
    )
    return build_llm(llm_cfg, temperature=temperature)


# ---------------------------------------------------------------------------
# HELPER: GENERATE ONE SAMPLE
# ---------------------------------------------------------------------------

def _generate_one_sample(llm, prompt: str) -> str:
    """Generate one stochastic sample from the LLM."""
    from app.core.llm_manager import invoke_llm
    return invoke_llm(llm, prompt)


# ---------------------------------------------------------------------------
# MAIN CELERY TASK
# ---------------------------------------------------------------------------

@celery_app.task(bind=True)
def run_hallucination_check(self, chat_id: int, prompt_text: str, main_answer: str):
    """
    Celery task to detect hallucination in a single LLM response.

    Flow:
      1. Read runtime config from Redis (provider, model, num_samples, method, etc.)
      2. If provider='none' → mark is_evaluating=False, return.
      3. Generate num_samples stochastic samples (while respecting the GPU flag).
      4. Evaluate consistency with SelfCheckGPT.
      5. Save score to DB and log to MLflow.
    """
    config      = _read_task_config()
    provider    = config["provider"]
    num_samples = config["num_samples"]
    temperature = config["temperature"]
    method      = config["method"]

    logger.info(f"[DetectionTask] Chat {chat_id} -- config: "
        f"provider={provider}, model={config['model']}, "
        f"num_samples={num_samples}, temperature={temperature}, method={method}")

    db = SessionLocal()
    try:
        chat = db.query(domain_models.ChatLog).filter(
            domain_models.ChatLog.id == chat_id
        ).first()
        if not chat:
            logger.error(f"[DetectionTask] Error: ChatLog ID {chat_id} not found in DB.")
            return {"error": f"ChatLog ID {chat_id} not found"}

        # ── NO MODEL MODE ──────────────────────────────────────────────────
        if provider.strip().lower() == "none":
            logger.info(f"[DetectionTask] Chat {chat_id} -- provider='none', "
                "evaluation skipped.")
            chat.is_evaluating      = False
            chat.hallucination_score = None
            db.commit()
            return {"chat_id": chat_id, "skipped": True, "reason": "no_model"}

        # ── BUILD LLM FOR SAMPLING ─────────────────────────────────────────
        sample_llm = _build_sample_llm(config, temperature=temperature)
        if sample_llm is None:
            chat.is_evaluating = False
            db.commit()
            return {"chat_id": chat_id, "skipped": True, "reason": "llm_none"}

        # ── MLFLOW TRACKING ───────────────────────────────────────────────────
        with mlflow.start_run(run_name=f"Chat_ID_{chat_id}") as run:

            mlflow.log_param("chat_id",           chat_id)
            mlflow.log_param("num_samples",        num_samples)
            mlflow.log_param("model",              config["model"])
            mlflow.log_param("provider",           provider)
            mlflow.log_param("temperature_sample", temperature)
            mlflow.log_param("method",             method)

            # ── SAMPLING ─────────────────────────────────────────────────────
            logger.info(f"[DetectionTask] Chat {chat_id} -- "
                f"generating {num_samples} variation samples...")
            samples = []
            start_sampling = time.time()

            for i in range(num_samples):
                while redis_client.get("gpu_busy_for_user") == b"1":
                    logger.info(f"[DetectionTask] Chat {chat_id} -- GPU used by user, "
                        f"sample {i+1} delayed by 10 seconds...")
                    time.sleep(10)

                logger.info(f"[DetectionTask] Chat {chat_id} -- "
                    f"taking sample {i+1}/{num_samples}...")
                sample = _generate_one_sample(sample_llm, prompt_text)
                samples.append(sample)

            sampling_duration = time.time() - start_sampling
            logger.info(f"[DetectionTask] Chat {chat_id} -- "
                f"sampling completed in {sampling_duration:.1f} seconds.")

            # ── EVALUATION ──────────────────────────────────────────────────────
            logger.info(f"[DetectionTask] Chat {chat_id} -- starting evaluation ({method})...")
            evaluator = _get_evaluator(method=method)

            start_eval = time.time()
            report     = evaluator.evaluate(main_answer, samples)
            eval_duration = time.time() - start_eval

            hallucination_score = float(report["avg_score"])
            logger.info(f"[DetectionTask] Chat {chat_id} -- score: {hallucination_score:.4f} "
                f"(evaluation: {eval_duration:.1f} seconds)"
            )

            # ── LOG METRICS ────────────────────────────────────────────────────
            mlflow.log_metric("hallucination_score",  hallucination_score)
            mlflow.log_metric("time_sampling_sec",    sampling_duration)
            mlflow.log_metric("time_evaluation_sec",  eval_duration)
            mlflow.log_metric("total_process_sec",    sampling_duration + eval_duration)

            mlflow.log_dict(
                {
                    "prompt":              prompt_text,
                    "main_answer":         main_answer,
                    "stochastic_samples":  samples,
                    "nli_raw_report":      report,
                },
                f"evaluation_details_chat_id_{chat_id}.json",
            )

            # ── SAVE RESULTS ──────────────────────────────────────────────────
            chat.hallucination_score = hallucination_score
            chat.is_evaluating       = False
            chat.temperature_sample  = temperature
            chat.num_samples         = num_samples
            chat.time_sampling_sec   = sampling_duration
            chat.time_evaluation_sec = eval_duration
            chat.total_process_sec   = sampling_duration + eval_duration
            db.commit()

            logger.info(f"[DetectionTask] Chat {chat_id} finished. "
                f"Score {hallucination_score:.4f} saved to DB.")
            return {"chat_id": chat_id, "score": hallucination_score}

    except Exception as exc:
        db.rollback()
        logger.error(f"[DetectionTask] Error processing Chat {chat_id}: {exc}")
        raise exc

    finally:
        db.close()