from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc

from src.database.session import get_db
from src.models.user import User
from src.models.chat import ChatSession, ChatMessage
from src.api.deps import get_current_user

router = APIRouter()


@router.get("/chats")
async def list_chats(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    limit: int = 20,
    offset: int = 0
):
    """List chat sessions."""
    stmt = select(ChatSession).where(ChatSession.user_id == user.id).order_by(desc(ChatSession.updated_at)).limit(limit).offset(offset)
    result = await db.execute(stmt)
    sessions = result.scalars().all()
    return sessions


@router.get("/chats/{session_id}")
async def get_chat_history(
    session_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get messages for a specific chat session."""
    stmt = select(ChatSession).where(ChatSession.id == session_id, ChatSession.user_id == user.id)
    result = await db.execute(stmt)
    session = result.scalar_one_or_none()
    
    if not session:
        raise HTTPException(status_code=404, detail="Chat session not found")
        
    # Messages are loaded via relationship automatically if eager, or we query them
    # Because we didn't set lazy='joined' explicitly, let's query messages manually just to be safe and ordered
    stmt_msgs = select(ChatMessage).where(ChatMessage.session_id == session_id).order_by(ChatMessage.created_at)
    res_msgs = await db.execute(stmt_msgs)
    messages = res_msgs.scalars().all()
    
    return {
        "session": session,
        "messages": messages
    }


@router.post("/chats")
async def create_chat_session(
    title: Optional[str] = Body("New Chat"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new chat session."""
    session = ChatSession(user_id=user.id, title=title)
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return session
