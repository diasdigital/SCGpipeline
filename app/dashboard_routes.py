"""
app/dashboard_routes.py
=======================
Dedicated REST endpoints for the developer (researcher) dashboard.

All endpoints here are protected by the get_current_developer guard —
only accounts with the 'developer' role can access them.

Available endpoints:
  GET /dashboard/stats          — overall summary statistics
  GET /dashboard/chats          — history of all chats with optional filters
  GET /dashboard/chats/{id}     — details of a single chat + per-sentence scores from MLflow
  GET /dashboard/users          — list of users + summary statistics per user
  GET /dashboard/users/{id}     — details of a single user + complete chat history
  GET /dashboard/config         — retrieve current threshold + LLM configuration
  PUT /dashboard/config         — save new threshold + LLM configuration
                                  (takes effect immediately without server restart)
"""

from datetime import datetime
from typing   import List, Optional

from fastapi          import APIRouter, Depends, HTTPException, Query, status
from pydantic         import BaseModel, Field
from sqlalchemy       import func, case
from sqlalchemy.orm   import Session

from app.core.config          import settings
from app.core.database        import get_db
from app.core.llm_manager     import llm_manager
from app.core.logging_config  import get_logger

logger = get_logger(__name__)
from app.core.security    import decode_access_token
from app.models           import domain_models
from app.api_routes       import get_current_developer


router = APIRouter(prefix="/dashboard", tags=["dashboard"])


# ---------------------------------------------------------------------------
# RESPONSE SCHEMAS — dashboard specific
# ---------------------------------------------------------------------------

class DashboardStats(BaseModel):
    """Overall summary statistics for the number cards at the top of the dashboard."""
    total_chats:           int
    evaluated_chats:       int    # Chats that already have a hallucination_score
    above_threshold:       int    # Chats with score >= threshold
    avg_score:             float
    score_distribution:    dict   # score buckets: {0.0-0.2: N, 0.2-0.4: N, ...}


class ChatSummary(BaseModel):
    """A single row in the dashboard chat history table."""
    id:                  int
    username:            str
    room_name:           str
    prompt_text:         str
    hallucination_score: Optional[float]
    user_feedback:       Optional[int]
    is_evaluating:       bool
    created_at:          datetime
    llm_model:           Optional[str]   = None
    llm_provider:        Optional[str]   = None

    class Config:
        from_attributes = True


class ChatDetail(ChatSummary):
    """Complete details of a single chat — displayed when a table row is expanded."""
    llm_response:        str
    evaluation_method:   str
    temperature_sample:  Optional[float] = None
    num_samples:         Optional[int]   = None


class UserSummary(BaseModel):
    """A single row in the participant progress table."""
    id:              int
    username:        str
    total_chats:     int
    evaluated_chats: int
    avg_score:       Optional[float]
    tasks_done:      int


class DashboardConfig(BaseModel):
    """
    Complete configuration for the developer dashboard.

    Divided into two parts:
      A. Evaluation Parameters  — threshold, num_samples, temperature, method
      B. LLM Configuration      — provider, model, api_key, base_url

    All changes via PUT /dashboard/config take effect immediately without
    a server restart. The config is also saved to Redis so the Celery worker follows it.

    Security note: api_key is sent during PUT (for update), but during
    GET it is returned as an empty string so it doesn't leak to the browser.
    """

    # ── A. Evaluation Parameters ─────────────────────────────────────────────
    threshold_high: float = Field(
        0.60, ge=0.0, le=1.0,
        description="Lower bound for hallucination category (red)",
    )
    threshold_mid: float = Field(
        0.40, ge=0.0, le=1.0,
        description="Lower bound for borderline category (yellow)",
    )
    num_samples: int = Field(
        5, ge=1, le=20,
        description="Number of stochastic samples per evaluation",
    )
    temperature: float = Field(
        1.0, ge=0.0, le=2.0,
        description="LLM temperature for stochastic sampling",
    )
    method: str = Field(
        "nli",
        description="Evaluation method: 'nli' or 'bertscore'",
    )

    # ── B. LLM Configuration ────────────────────────────────────────────────
    llm_provider: str = Field(
        "ollama",
        description=(
            "Active LLM provider. "
            "Options: 'ollama' | 'openai' | 'gemini' | 'fireworks' | 'none'. "
            "'none' = FastAPI keeps running without a model."
        ),
    )
    llm_model: str = Field(
        "llama3",
        description=(
            "Model name according to provider. "
            "Ollama examples: 'llama3', 'mistral', 'phi3'. "
            "OpenAI examples: 'gpt-4o', 'gpt-3.5-turbo'. "
            "Fireworks examples: 'accounts/fireworks/models/llama-v3-70b-instruct'. "
            "Gemini examples: 'gemini-2.0-flash', 'gemini-1.5-flash-lite'."
        ),
    )
    llm_api_key: str = Field(
        "",
        description=(
            "API key for OpenAI, Fireworks, or Gemini providers. "
            "Leave empty for Ollama. "
            "On GET, it is always returned empty for security."
        ),
    )
    llm_base_url: str = Field(
        "http://localhost:11434",
        description="Ollama server Base URL (only relevant for 'ollama' provider).",
    )


def _make_default_config() -> DashboardConfig:
    """Create the initial DashboardConfig from environment variables."""
    return DashboardConfig(
        threshold_high=settings.THRESHOLD_HIGH,
        threshold_mid=settings.THRESHOLD_MID,
        num_samples=settings.NUM_SAMPLES,
        temperature=settings.TEMPERATURE_SAMPLE,
        method=settings.EVAL_METHOD,
        llm_provider=settings.LLM_PROVIDER,
        llm_model=settings.LLM_MODEL,
        llm_api_key="",        # Not exposed in response; only used during update
        llm_base_url=settings.LLM_BASE_URL,
    )


# In-memory config — initialized from .env when the module is loaded.
# Updated by PUT /dashboard/config.
_current_config = _make_default_config()

# Sync initial config to Redis so the Celery worker also has the default values
# (especially important when the worker starts before the dashboard).
llm_manager.push_config_to_redis(extra={
    "num_samples": _current_config.num_samples,
    "temperature": _current_config.temperature,
    "method":      _current_config.method,
})


# ---------------------------------------------------------------------------
# INTERNAL HELPERS
# ---------------------------------------------------------------------------

def _score_to_label(score: Optional[float], config: DashboardConfig) -> str:
    """Convert numeric score to category label based on threshold."""
    if score is None:
        return "pending"
    if score >= config.threshold_high:
        return "halusinasi"
    if score >= config.threshold_mid:
        return "borderline"
    return "faktual"


def _get_all_evaluated_chats(db: Session):
    """
    JOIN query to fetch all chats along with username and room_name.
    Shared by multiple endpoints.
    """
    return (
        db.query(
            domain_models.ChatLog,
            domain_models.User.username,
            domain_models.ChatRoom.room_name,
        )
        .join(domain_models.ChatRoom, domain_models.ChatLog.room_id == domain_models.ChatRoom.id)
        .join(domain_models.User,     domain_models.ChatRoom.user_id == domain_models.User.id)
        .filter(domain_models.User.role == "user")  # Only participant chats, not developers
    )


# ---------------------------------------------------------------------------
# ENDPOINT: SUMMARY STATISTICS
# ---------------------------------------------------------------------------

@router.get("/stats", response_model=DashboardStats)
def get_dashboard_stats(
    user_id: Optional[int] = Query(None),
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
    llm_model: Optional[str] = Query(
        None,
        description="Filter by LLM model",
    ),
    llm_provider: Optional[str] = Query(
        None,
        description="Filter by LLM provider",
    ),
    db: Session = Depends(get_db),
    _: domain_models.User = Depends(get_current_developer),
):
    """
    Returns summary statistics for the number cards on the dashboard.
    Supports optional filters by user and date range.
    """
    query = _get_all_evaluated_chats(db)

    if user_id:
        query = query.filter(domain_models.User.id == user_id)

    if date_from:
        query = query.filter(
            domain_models.ChatLog.created_at >= date_from
        )

    if date_to:
        query = query.filter(
            domain_models.ChatLog.created_at <= date_to
        )

    if llm_model:
        query = query.filter(
            domain_models.ChatLog.llm_model == llm_model
        )

    if llm_provider:
        query = query.filter(
            domain_models.ChatLog.llm_provider == llm_provider
        )

    rows = query.all()
    chats = [row[0] for row in rows]

    if not chats:
        return DashboardStats(
            total_chats=0, evaluated_chats=0, above_threshold=0,
            avg_score=0.0, score_distribution={}
        )

    # Chats that have been evaluated (not pending)
    evaluated = [c for c in chats if c.hallucination_score is not None]
    scores    = [c.hallucination_score for c in evaluated]

    avg_score = sum(scores) / len(scores) if scores else 0.0
    above_threshold = sum(1 for s in scores if s >= _current_config.threshold_high)

    buckets = {"0.0-0.2": 0, "0.2-0.4": 0, "0.4-0.6": 0, "0.6-0.8": 0, "0.8-1.0": 0}
    for s in scores:
        if   s < 0.2: buckets["0.0-0.2"] += 1
        elif s < 0.4: buckets["0.2-0.4"] += 1
        elif s < 0.6: buckets["0.4-0.6"] += 1
        elif s < 0.8: buckets["0.6-0.8"] += 1
        else:         buckets["0.8-1.0"] += 1

    return DashboardStats(
        total_chats       = len(chats),
        evaluated_chats   = len(evaluated),
        above_threshold   = above_threshold,
        avg_score         = round(avg_score, 4),
        score_distribution= buckets,
    )


# ---------------------------------------------------------------------------
# ENDPOINT: CHAT HISTORY (TABLE)
# ---------------------------------------------------------------------------

@router.get("/chats", response_model=List[ChatSummary])
def get_all_chats(
    user_id:    Optional[int]      = Query(None),
    date_from:  Optional[datetime] = Query(None),
    date_to:    Optional[datetime] = Query(None),
    llm_model:  Optional[str]      = Query(None, description="Filter by LLM model name"),
    llm_provider: Optional[str]    = Query(None, description="Filter by LLM provider"),
    limit:      int                = Query(100, ge=1, le=500),
    offset:     int                = Query(0,   ge=0),
    db:         Session            = Depends(get_db),
    _:          domain_models.User = Depends(get_current_developer),
):
    """
    Fetches the history of all chats with optional filters.
    Ordered from newest (created_at DESC).
    Supports pagination via limit + offset.
    New filters: llm_model and llm_provider.
    """
    query = _get_all_evaluated_chats(db).order_by(
        domain_models.ChatLog.created_at.desc()
    )

    if user_id:
        query = query.filter(domain_models.User.id == user_id)
    if date_from:
        query = query.filter(domain_models.ChatLog.created_at >= date_from)
    if date_to:
        query = query.filter(domain_models.ChatLog.created_at <= date_to)
    if llm_model:
        query = query.filter(domain_models.ChatLog.llm_model == llm_model)
    if llm_provider:
        query = query.filter(domain_models.ChatLog.llm_provider == llm_provider)

    rows = query.offset(offset).limit(limit).all()

    return [
        ChatSummary(
            id                  = chat.id,
            username            = username,
            room_name           = room_name,
            prompt_text         = chat.prompt_text,
            hallucination_score = chat.hallucination_score,
            user_feedback       = chat.user_feedback,
            is_evaluating       = chat.is_evaluating,
            created_at          = chat.created_at,
            llm_model           = chat.llm_model,
            llm_provider        = chat.llm_provider,
        )
        for chat, username, room_name in rows
    ]


@router.get("/chats/{chat_id}", response_model=ChatDetail)
def get_chat_detail(
    chat_id: int,
    db:      Session            = Depends(get_db),
    _:       domain_models.User = Depends(get_current_developer),
):
    """
    Fetches complete details of a single chat including llm_response.
    Used when a researcher expands a row in the dashboard table.
    """
    row = (
        _get_all_evaluated_chats(db)
        .filter(domain_models.ChatLog.id == chat_id)
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Chat tidak ditemukan")

    chat, username, room_name = row
    return ChatDetail(
        id                  = chat.id,
        username            = username,
        room_name           = room_name,
        prompt_text         = chat.prompt_text,
        llm_response        = chat.llm_response,
        hallucination_score = chat.hallucination_score,
        user_feedback       = chat.user_feedback,
        is_evaluating       = chat.is_evaluating,
        evaluation_method   = chat.evaluation_method,
        created_at          = chat.created_at,
        llm_model           = chat.llm_model,
        llm_provider        = chat.llm_provider,
        temperature_sample  = chat.temperature_sample,
        num_samples         = chat.num_samples,
    )


# ---------------------------------------------------------------------------
# ENDPOINT: PREVIOUSLY USED MODELS LIST
# ---------------------------------------------------------------------------

@router.get("/models", response_model=List[str])
def get_used_models(
    db: Session            = Depends(get_db),
    _:  domain_models.User = Depends(get_current_developer),
):
    """
    Returns a list of distinct llm_models that have been used,
    ordered alphabetically. Used by the model filter dropdown in the dashboard.
    NULL values (old chats before migration) are automatically excluded.
    """
    rows = (
        db.query(domain_models.ChatLog.llm_model)
        .filter(domain_models.ChatLog.llm_model.isnot(None))
        .distinct()
        .order_by(domain_models.ChatLog.llm_model)
        .all()
    )
    return [row[0] for row in rows]


@router.get("/providers", response_model=List[str])
def get_used_providers(
    db: Session            = Depends(get_db),
    _:  domain_models.User = Depends(get_current_developer),
):
    """
    Returns a list of distinct llm_providers that have been used.
    Used by the provider filter dropdown in the dashboard.
    """
    rows = (
        db.query(domain_models.ChatLog.llm_provider)
        .filter(domain_models.ChatLog.llm_provider.isnot(None))
        .distinct()
        .order_by(domain_models.ChatLog.llm_provider)
        .all()
    )
    return [row[0] for row in rows]


# ---------------------------------------------------------------------------
# ENDPOINT: PER-USER DATA
# ---------------------------------------------------------------------------

@router.get("/users", response_model=List[UserSummary])
def get_users_summary(
    db: Session            = Depends(get_db),
    _:  domain_models.User = Depends(get_current_developer),
):
    """
    Fetches a list of all participants along with their chat statistics.
    Used on the Participant Progress page.
    """
    users = db.query(domain_models.User).filter(
        domain_models.User.role == "user"
    ).all()

    result = []
    for user in users:
        # Collect all chats from all rooms belonging to this user
        all_chats = []
        for room in user.rooms:
            all_chats.extend(room.chats)

        evaluated = [c for c in all_chats if c.hallucination_score is not None]
        avg_score = (
            round(sum(c.hallucination_score for c in evaluated) / len(evaluated), 4)
            if evaluated else None
        )

        result.append(UserSummary(
            id              = user.id,
            username        = user.username,
            total_chats     = len(all_chats),
            evaluated_chats = len(evaluated),
            avg_score       = avg_score,
            tasks_done      = 0,
        ))

    return result


@router.get("/users/{user_id}/chats", response_model=List[ChatSummary])
def get_user_chats(
    user_id: int,
    db:      Session            = Depends(get_db),
    _:       domain_models.User = Depends(get_current_developer),
):
    """
    Fetches all chats from a specific user.
    Used for the detail panel on the Participant Progress page.
    """
    user = db.query(domain_models.User).filter(
        domain_models.User.id   == user_id,
        domain_models.User.role == "user",
    ).first()
    if not user:
        raise HTTPException(status_code=404, detail="User tidak ditemukan")

    rows = (
        _get_all_evaluated_chats(db)
        .filter(domain_models.User.id == user_id)
        .order_by(domain_models.ChatLog.created_at.asc())
        .all()
    )

    return [
        ChatSummary(
            id                  = chat.id,
            username            = username,
            room_name           = room_name,
            prompt_text         = chat.prompt_text,
            hallucination_score = chat.hallucination_score,
            user_feedback       = chat.user_feedback,
            is_evaluating       = chat.is_evaluating,
            created_at          = chat.created_at,
        )
        for chat, username, room_name in rows
    ]


# ---------------------------------------------------------------------------
# ENDPOINT: THRESHOLD CONFIGURATION
# ---------------------------------------------------------------------------

@router.get("/config", response_model=DashboardConfig)
def get_config(
    _: domain_models.User = Depends(get_current_developer),
):
    """
    Fetches the current threshold configuration, sampling parameters, and LLM.

    Note: llm_api_key is always returned empty for security.
    To change the api_key, send the new value via PUT /dashboard/config.
    """
    # Return config without api_key
    safe = _current_config.model_copy(update={"llm_api_key": ""})
    return safe


@router.put("/config", response_model=DashboardConfig)
def update_config(
    new_config: DashboardConfig,
    _:          domain_models.User = Depends(get_current_developer),
):
    """
    Updates the threshold configuration, sampling parameters, and LLM.

    Changes take effect IMMEDIATELY without server restart:
      - The new LLM is used starting from the next chat request.
      - The Celery worker reads the new config from Redis starting from the next task.

    Notes:
      - Threshold changes only affect visual classification on the frontend.
        Scores already saved in the DB are not changed.
      - num_samples and temperature changes apply to Celery tasks
        triggered after this change — not retroactive.
      - llm_api_key can be left empty if the provider does not require it.
        If left empty when the provider is 'openai'/'fireworks'/'gemini', subsequent requests will error.
    """
    global _current_config

    # Save the api_key from the request (can contain a new value or be empty)
    incoming_api_key = new_config.llm_api_key

    # If the api_key is sent empty AND the provider has not changed,
    # retain the old api_key so it is not accidentally deleted.
    if not incoming_api_key and new_config.llm_provider == _current_config.llm_provider:
        incoming_api_key = llm_manager.get_config().api_key

    _current_config = new_config

    # Sync to llm_manager (FastAPI process) — takes effect immediately
    llm_manager.update_config(
        provider=new_config.llm_provider,
        model=new_config.llm_model,
        api_key=incoming_api_key,
        base_url=new_config.llm_base_url,
        extra={
            "num_samples": new_config.num_samples,
            "temperature": new_config.temperature,
            "method":      new_config.method,
        },
    )

    logger.info(
        "Config diperbarui: provider=%s, model=%s, num_samples=%d, method=%s",
        new_config.llm_provider, new_config.llm_model,
        new_config.num_samples, new_config.method,
    )

    # Return config without api_key
    safe = _current_config.model_copy(update={"llm_api_key": ""})
    return safe