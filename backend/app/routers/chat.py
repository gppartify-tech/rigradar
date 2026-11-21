"""The AI build assistant endpoint."""
from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import User
from app.schemas import ChatIn, ChatOut
from app.security import get_optional_user
from app.services import ratelimit
from app.services.chatbot import chat

router = APIRouter(prefix="/api/chat", tags=["assistant"])


@router.post("", response_model=ChatOut)
def ask_assistant(
    body: ChatIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_optional_user),
):
    """Send the whole conversation (the API is stateless); get the assistant's next reply.
    Logged-in users get twice the message allowance of anonymous visitors."""
    if user is not None:
        bucket, limit = f"user:{user.id}", settings.chat_rate_limit_per_10min * 2
    else:
        bucket, limit = f"ip:{request.client.host if request.client else 'unknown'}", settings.chat_rate_limit_per_10min
    ratelimit.hit(f"chat:{bucket}", limit, 600)
    return chat(db, body.messages[-20:])  # the last 20 messages are plenty of context
