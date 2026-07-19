import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token, hash_password, verify_password
from app.core.config import get_settings
from app.db.session import get_db
from app.models.entities import User, UserSettings
from app.schemas.dto import LoginRequest, RegisterRequest, TokenResponse

router = APIRouter(prefix="/auth", tags=["auth"])
logger = logging.getLogger(__name__)


@router.post("/register", response_model=TokenResponse)
async def register(payload: RegisterRequest, db: AsyncSession = Depends(get_db)) -> TokenResponse:
    try:
        user_count = int((await db.execute(select(func.count()).select_from(User))).scalar_one())
        if not _registration_allowed(user_count, get_settings().registration_enabled):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Registration is disabled")
        existing = await db.execute(select(User).where(User.email == payload.email))
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")
        user = User(email=payload.email, hashed_password=hash_password(payload.password))
        db.add(user)
        await db.flush()
        db.add(UserSettings(user_id=user.id))
        await db.commit()
        return TokenResponse(access_token=create_access_token(user.email))
    except HTTPException:
        raise
    except Exception:
        await db.rollback()
        logger.exception("Failed to register user %s", payload.email)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Registration failed",
        )


def _registration_allowed(user_count: int, registration_enabled: bool) -> bool:
    return user_count == 0 or registration_enabled


@router.post("/login", response_model=TokenResponse)
async def login(payload: LoginRequest, db: AsyncSession = Depends(get_db)) -> TokenResponse:
    result = await db.execute(select(User).where(User.email == payload.email))
    user = result.scalar_one_or_none()
    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect email or password")
    return TokenResponse(access_token=create_access_token(user.email))
