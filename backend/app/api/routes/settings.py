from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import current_user
from app.core.security import decrypt_secret, encrypt_secret, mask_secret
from app.db.session import get_db
from app.models.entities import User, UserSettings
from app.schemas.dto import SettingsIn, SettingsOut

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("", response_model=SettingsOut)
async def get_user_settings(user: User = Depends(current_user), db: AsyncSession = Depends(get_db)) -> SettingsOut:
    settings = await _settings_for(user, db)
    return _serialize(settings)


@router.put("", response_model=SettingsOut)
async def update_user_settings(payload: SettingsIn, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)) -> SettingsOut:
    settings = await _settings_for(user, db)
    settings.exchange = payload.exchange
    settings.risk_percent = payload.risk_percent
    settings.daily_risk_percent = payload.daily_risk_percent
    settings.max_positions = payload.max_positions
    settings.min_rating = payload.min_rating
    settings.scan_interval = payload.scan_interval
    settings.stop_loss_percent = payload.stop_loss_percent
    settings.take_profit_percent = payload.take_profit_percent
    if payload.api_key:
        settings.api_key_encrypted = encrypt_secret(payload.api_key)
    if payload.secret_key:
        settings.secret_key_encrypted = encrypt_secret(payload.secret_key)
    if payload.passphrase:
        settings.passphrase_encrypted = encrypt_secret(payload.passphrase)
    await db.commit()
    await db.refresh(settings)
    return _serialize(settings)


async def _settings_for(user: User, db: AsyncSession) -> UserSettings:
    settings = (await db.execute(select(UserSettings).where(UserSettings.user_id == user.id))).scalar_one_or_none()
    if settings:
        return settings
    settings = UserSettings(user_id=user.id)
    db.add(settings)
    await db.commit()
    await db.refresh(settings)
    return settings


def _serialize(settings: UserSettings) -> SettingsOut:
    return SettingsOut(
        exchange=settings.exchange,
        api_key_masked=mask_secret(decrypt_secret(settings.api_key_encrypted)),
        secret_key_masked=mask_secret(decrypt_secret(settings.secret_key_encrypted)),
        passphrase_masked=mask_secret(decrypt_secret(settings.passphrase_encrypted)),
        risk_percent=settings.risk_percent,
        daily_risk_percent=settings.daily_risk_percent,
        max_positions=settings.max_positions,
        min_rating=settings.min_rating,
        scan_interval=settings.scan_interval,
        stop_loss_percent=settings.stop_loss_percent,
        take_profit_percent=settings.take_profit_percent,
    )
