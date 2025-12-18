from uuid import uuid4, UUID
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from src.database.session import get_db
from src.models.user import User, APIKey
from src.api.deps import get_current_user

router = APIRouter()


@router.get("/keys")
async def list_api_keys(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all API keys for the current user."""
    stmt = select(APIKey).where(APIKey.user_id == user.id, APIKey.is_active == True)
    result = await db.execute(stmt)
    keys = result.scalars().all()
    
    return [
        {
            "id": k.id,
            "name": k.name,
            "prefix": k.prefix,
            "created_at": k.created_at,
            "last_used_at": k.last_used_at
        }
        for k in keys
    ]


@router.post("/keys")
async def create_api_key(
    name: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new API key."""
    # Generate a key (mocking a secure key generation)
    raw_key = f"sk_live_{uuid4().hex}"
    
    # Store directly (in real app, hash this!)
    # But as per deps.py logic logic we are matching against key_hash
    db_key = APIKey(
        user_id=user.id,
        name=name,
        key_hash=raw_key, # Storing raw for MVP as noted in deps.py
        prefix=raw_key[:7] + "..."
    )
    
    db.add(db_key)
    await db.commit()
    await db.refresh(db_key)
    
    return {
        "id": db_key.id,
        "name": db_key.name,
        "key": raw_key, # Show ONCE
        "created_at": db_key.created_at
    }


@router.delete("/keys/{key_id}")
async def revoke_api_key(
    key_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Revoke (delete) an API key."""
    stmt = select(APIKey).where(APIKey.id == key_id, APIKey.user_id == user.id)
    result = await db.execute(stmt)
    key = result.scalar_one_or_none()
    
    if not key:
        raise HTTPException(status_code=404, detail="Key not found")
        
    key.is_active = False # Soft delete or actually delete?
    await db.delete(key) # Hard delete for now to keep table clean? Or soft?
    # Logic: Delete or set inactive. Let's delete.
    
    await db.commit()
    return {"status": "revoked"}
