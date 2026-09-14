import redis
from typing import List
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.config          import settings
from app.core.database        import get_db, SessionLocal
from app.core.logging_config  import get_logger
from app.core.security import (
    verify_password,
    hash_password,
    create_access_token,
    decode_access_token,
)
from app.core.llm_manager  import llm_manager
from app.models            import domain_models
from app.schemas           import api_schemas, auth_schemas
from app.services.detection_task import run_hallucination_check

logger = get_logger(__name__)

# Imported from main so all endpoints share a single limiter instance
from slowapi import Limiter
from slowapi.util import get_remote_address
_limiter = Limiter(key_func=get_remote_address)

# ---------------------------------------------------------------------------
# INITIALIZATION
# ---------------------------------------------------------------------------

router = APIRouter()

# The main LLM is NOT created here — it's created lazily by llm_manager
# when the first chat request comes in.
# This allows FastAPI to continue starting up even if Ollama isn't running yet.

# Schema for extracting Bearer Token from Authorization Header
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

# Redis connection — for GPU coordination flags between chat and Celery
redis_client = redis.Redis(
    host=settings.REDIS_HOST,
    port=settings.REDIS_PORT,
    db=0,
)


# ---------------------------------------------------------------------------
# HELPER: ROOM OWNERSHIP VALIDATION
# ---------------------------------------------------------------------------

def _get_room_or_404(room_id: int, user_id: int, db: Session) -> domain_models.ChatRoom:
    """Check whether the room belongs to the user or not."""
    room = db.query(domain_models.ChatRoom).filter(
        domain_models.ChatRoom.id      == room_id,
        domain_models.ChatRoom.user_id == user_id,
    ).first()
    if not room:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Room not found, or does not belong to you",
        )
    return room


# ---------------------------------------------------------------------------
# DEPENDENCIES (ROUTE GUARDS / PROTECTION)
# ---------------------------------------------------------------------------

def get_current_user(
    token: str           = Depends(oauth2_scheme),
    db:    Session       = Depends(get_db),
) -> domain_models.User:
    """
    FastAPI dependency to protect endpoints.
    Decodes JWT, validates 'sub' claim, retrieves user data from DB.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired token",
        headers={"WWW-Authenticate": "Bearer"},
    )

    payload = decode_access_token(token)
    if payload is None:
        raise credentials_exception

    username: str = payload.get("sub")
    if username is None:
        raise credentials_exception

    user = db.query(domain_models.User).filter(
        domain_models.User.username == username
    ).first()
    if user is None:
        raise credentials_exception

    return user


def get_current_developer(
    current_user: domain_models.User = Depends(get_current_user),
) -> domain_models.User:
    """Ensures the logged-in user has the developer role."""
    if current_user.role != "developer":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. This feature is for developers only",
        )
    return current_user


# ---------------------------------------------------------------------------
# LLM DIAGNOSTIC ENDPOINT
# ---------------------------------------------------------------------------

@router.get("/llm/status", tags=["diagnostics"])
def get_llm_status(
    _: domain_models.User = Depends(get_current_developer),
):
    """
    Returns the status of the currently active LLM.
    Useful for verification after a developer changes config in the dashboard.

    Accessible only by developers.
    The API key is NOT returned for security reasons — only a present/not present flag.
    """
    return llm_manager.get_status()


# ---------------------------------------------------------------------------
# AUTHENTICATION ENDPOINTS
# ---------------------------------------------------------------------------

@router.post("/auth/login", response_model=auth_schemas.Token)
@_limiter.limit("10/minute")  # Max 10 logins per minute per IP (anti-brute-force)
def login(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db:        Session                   = Depends(get_db),
):
    """Endpoint to log in and get a JWT token."""
    user = db.query(domain_models.User).filter(
        domain_models.User.username == form_data.username
    ).first()

    if not user or not verify_password(form_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
        )

    access_token = create_access_token(
        data={"sub": user.username, "role": user.role}
    )
    return {"access_token": access_token, "token_type": "bearer"}


@router.post(
    "/developer/create-user",
    response_model=auth_schemas.UserResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_user_by_developer(
    payload:            auth_schemas.UserCreateByDev,
    db:                 Session              = Depends(get_db),
    current_developer:  domain_models.User   = Depends(get_current_developer),
):
    """Creates a new user. Only accounts with the 'developer' role can call this."""
    existing_user = db.query(domain_models.User).filter(
        domain_models.User.username == payload.username
    ).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already registered",
        )

    hashed = hash_password(payload.password)
    new_user = domain_models.User(
        username      = payload.username,
        password_hash = hashed,
        role          = payload.role,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user


# ---------------------------------------------------------------------------
# USER ENDPOINTS
# ---------------------------------------------------------------------------

@router.get("/users", response_model=List[api_schemas.UserResponse])
def get_all_users(
    db: Session            = Depends(get_db),
    _:  domain_models.User = Depends(get_current_developer),
):
    """Retrieves all user data."""
    return db.query(domain_models.User).all()


@router.get("/me", response_model=api_schemas.UserResponse)
def get_logged_in_user(
    current_user: domain_models.User = Depends(get_current_user),
):
    return current_user


# ---------------------------------------------------------------------------
# CHAT ROOM ENDPOINTS
# ---------------------------------------------------------------------------

@router.get("/rooms", response_model=List[api_schemas.RoomResponse])
def get_user_rooms(
    db:           Session            = Depends(get_db),
    current_user: domain_models.User = Depends(get_current_user),
):
    """Retrieves the list of rooms belonging to the currently logged-in user."""
    return db.query(domain_models.ChatRoom).filter(
        domain_models.ChatRoom.user_id == current_user.id
    ).all()


@router.post("/rooms", response_model=api_schemas.RoomResponse)
def create_room(
    room_in:      api_schemas.RoomCreate,
    db:           Session              = Depends(get_db),
    current_user: domain_models.User   = Depends(get_current_user),
):
    """Creates a new chat room."""
    new_room = domain_models.ChatRoom(
        user_id   = current_user.id,
        room_name = room_in.room_name,
    )
    db.add(new_room)
    db.commit()
    db.refresh(new_room)
    return new_room


@router.get("/rooms/{room_id}/chats", response_model=List[api_schemas.ChatLogResponse])
def get_room_chats(
    room_id:      int,
    db:           Session            = Depends(get_db),
    current_user: domain_models.User = Depends(get_current_user),
):
    """Retrieves the chat history within a single room."""
    _get_room_or_404(room_id, current_user.id, db)

    return (
        db.query(domain_models.ChatLog)
        .filter(domain_models.ChatLog.room_id == room_id)
        .order_by(domain_models.ChatLog.id.asc())
        .all()
    )


@router.patch("/rooms/{room_id}", response_model=api_schemas.RoomResponse)
def rename_room(
    room_id:      int,
    payload:      api_schemas.RoomUpdate,
    db:           Session            = Depends(get_db),
    current_user: domain_models.User = Depends(get_current_user),
):
    """Renames a room."""
    room = _get_room_or_404(room_id, current_user.id, db)
    room.room_name = payload.room_name
    db.commit()
    db.refresh(room)
    return room


@router.delete("/rooms/{room_id}")
def delete_room(
    room_id:      int,
    db:           Session            = Depends(get_db),
    current_user: domain_models.User = Depends(get_current_user),
):
    """Performs a soft-delete on a room."""
    room = _get_room_or_404(room_id, current_user.id, db)
    
    # Change db.delete(room) to flag update
    room.is_deleted = True
    room.deleted_at = datetime.now(timezone.utc)
    
    db.commit()
    return {"message": "Room successfully deleted"}


# ---------------------------------------------------------------------------
# CHAT & DETECTION ENDPOINTS
# ---------------------------------------------------------------------------

@router.post("/chat/stream")
@_limiter.limit("20/minute")  # Max 20 chats per minute per IP
def create_chat_stream(
    request: Request,
    chat_in:      api_schemas.ChatLogCreate,
    db:           Session            = Depends(get_db),
    current_user: domain_models.User = Depends(get_current_user),
):
    """
    Receives a prompt, returns an LLM stream, and triggers Celery.
    FastAPI streams the response directly to the user; Celery runs
    hallucination detection in the background.

    'none' mode (no model):
      - Sends a placeholder message to the user.
      - Chat is saved to DB with is_evaluating=False.
      - Celery is NOT triggered because there is no response to evaluate.
    """
    # Validate room ownership
    room = _get_room_or_404(chat_in.room_id, current_user.id, db)

    # Update room name with the first prompt if it's still default
    if room.room_name == "New Conversation":
        suffix    = "..." if len(chat_in.prompt_text) > 30 else ""
        room.room_name = chat_in.prompt_text[:30] + suffix

    # Save initial record to DB.
    # is_evaluating=True means Celery hasn't finished.
    # If no-model, it will be updated to False inside the generator.
    # Save the current model and provider so they can be filtered in the dashboard
    _cfg = llm_manager.get_config()
    new_chat = domain_models.ChatLog(
        room_id       = chat_in.room_id,
        prompt_text   = chat_in.prompt_text,
        llm_response  = "",
        is_evaluating = True,
        llm_model     = _cfg.model    if _cfg.provider != "none" else None,
        llm_provider  = _cfg.provider if _cfg.provider != "none" else None,
    )
    db.add(new_chat)
    db.commit()
    db.refresh(new_chat)

    chat_id = new_chat.id

    # ── Streaming generator ──────────────────────────────────────────────────
    def event_generator():
        # Turn on the red light: GPU cannot be used by Celery yet
        redis_client.set("gpu_busy_for_user", "1")
        logger.info("Chat %d: started streaming...", chat_id)

        try:
            # ── MODE WITHOUT MODEL ─────────────────────────────────────────────
            if not llm_manager.is_available():
                placeholder = (
                    "[No active LLM model at the moment. "
                    "Contact a developer to activate a model.]"
                )
                yield placeholder
                logger.info("Chat %d: provider='none', sending placeholder.", chat_id)

                # Save placeholder and mark as finished (without evaluation)
                db_bg = SessionLocal()
                try:
                    record = db_bg.query(domain_models.ChatLog).filter(
                        domain_models.ChatLog.id == chat_id
                    ).first()
                    if record:
                        record.llm_response  = placeholder
                        record.is_evaluating = False  # Nothing to evaluate
                        db_bg.commit()
                except Exception as db_err:
                    logger.error("Chat %d: failed to save placeholder: %s", chat_id, db_err, exc_info=True)
                finally:
                    db_bg.close()
                return  # Finished, no need to trigger Celery

            # ── NORMAL MODE: streaming with LLM ───────────────────────────
            full_answer = ""
            for chunk in llm_manager.stream_text_main(chat_in.prompt_text):
                full_answer += chunk
                yield chunk

            logger.info("Chat %d: streaming finished, saving to DB...", chat_id)

            # Save full answer and trigger Celery using a separate
            # session because the session from the FastAPI request is no longer active
            # inside the generator.
            db_bg = SessionLocal()
            try:
                record = db_bg.query(domain_models.ChatLog).filter(
                    domain_models.ChatLog.id == chat_id
                ).first()
                if record:
                    record.llm_response = full_answer
                    db_bg.commit()

                # Trigger Celery with a 5-second countdown — allowing time
                # for streaming to completely finish before the GPU is used by the background task
                run_hallucination_check.apply_async(
                    args=[chat_id, chat_in.prompt_text, full_answer],
                    countdown=5,
                )
                logger.info("Chat %d: Celery task successfully triggered.", chat_id)

            except Exception as db_err:
                logger.error("Chat %d: failed to save final answer: %s", chat_id, db_err, exc_info=True)
            finally:
                db_bg.close()

        except Exception as stream_err:
            # Send error message to browser so UI doesn't freeze
            logger.error("Chat %d: error during streaming: %s", chat_id, stream_err, exc_info=True)
            yield f"\n[Error: Failed to generate answer — {stream_err}]"

        finally:
            # Turn off the red light: GPU is free to be used by Celery task
            redis_client.set("gpu_busy_for_user", "0")

    # Return StreamingResponse with custom headers so Vue.js knows its Chat ID
    return StreamingResponse(
        event_generator(),
        media_type="text/plain",
        headers={
            "X-Chat-ID":                    str(chat_id),
            "Access-Control-Expose-Headers": "X-Chat-ID",
        },
    )


# ---------------------------------------------------------------------------
# FEEDBACK ENDPOINT
# ---------------------------------------------------------------------------

@router.patch("/chat/{chat_id}/feedback", response_model=api_schemas.ChatLogResponse)
def submit_feedback(
    chat_id:      int,
    feedback:     api_schemas.ChatFeedbackUpdate,
    db:           Session            = Depends(get_db),
    current_user: domain_models.User = Depends(get_current_user),
):
    """Receives thumbs input (1 or -1) from the user."""
    chat = db.query(domain_models.ChatLog).filter(
        domain_models.ChatLog.id == chat_id
    ).first()
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")

    # Ensure this chat belongs to the logged-in user
    _get_room_or_404(chat.room_id, current_user.id, db)

    chat.user_feedback = feedback.user_feedback
    db.commit()
    db.refresh(chat)
    return chat