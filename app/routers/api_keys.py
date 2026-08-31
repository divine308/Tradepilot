from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPBearer
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import (
    generate_api_key,
    hash_api_key,
)
from app.database.database import get_db
from app.models.api_key import APIKey
from app.schemas.api_key import (
    CreateAPIKeyRequest,
    APIKeyCreatedResponse,
)

from fastapi import (
    APIRouter,
    Depends,
)

from app.core.security import get_current_user

router = APIRouter(
    prefix="/api/keys",
    tags=["API Keys"],
    dependencies=[
        Depends(get_current_user)
    ],
)

router = APIRouter(
    prefix="/api/keys",
    tags=["API Keys"],
)

bearer = HTTPBearer()


async def get_current_user_id(
    credentials=Depends(bearer),
):

    token = credentials.credentials

    try:
        payload = jwt.decode(
            token,
            settings.secret_key,
            algorithms=["HS256"],
        )

        user_id = payload.get("sub")

        if not user_id:
            raise HTTPException(
                status_code=401,
                detail="Invalid token.",
            )

        return int(user_id)

    except JWTError:

        raise HTTPException(
            status_code=401,
            detail="Invalid token.",
        )


@router.post(
    "",
    response_model=APIKeyCreatedResponse,
)
async def create_api_key(
    data: CreateAPIKeyRequest,
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):

    raw_key = generate_api_key()

    key = APIKey(
        user_id=user_id,
        name=data.name,
        key_prefix=raw_key[:16],
        key_hash=hash_api_key(raw_key),
    )

    db.add(key)

    await db.commit()

    await db.refresh(key)

    return {
        "id": key.id,
        "name": key.name,
        "prefix": key.key_prefix,
        "active": key.active,
        "created_at": key.created_at.isoformat(),
        "key": raw_key,
    }


@router.get("")
async def list_api_keys(
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):

    result = await db.execute(
        select(APIKey)
        .where(APIKey.user_id == user_id)
    )

    keys = result.scalars().all()

    return [
        {
            "id": key.id,
            "name": key.name,
            "prefix": key.key_prefix,
            "active": key.active,
            "requests_used": key.requests_used,
            "created_at": key.created_at.isoformat(),
            "last_used_at": (
                key.last_used_at.isoformat()
                if key.last_used_at
                else None
            ),
        }
        for key in keys
    ]