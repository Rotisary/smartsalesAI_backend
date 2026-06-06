from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import Business, BusinessSettings, RefreshToken
from app.schemas.auth import (
    AuthResponse, 
    LoginRequest, 
    LogoutRequest,
    LogoutResponse, 
    RefreshRequest, 
    SignupRequest, 
    TokenResponse
)
from app.schemas.business import BusinessRead
from app.schemas.settings import BusinessSettingsRead
from app.utils.auth.jwt import (
    create_access_token, 
    create_refresh_token, 
    decode_token, 
    get_business_id, 
    get_token_jti, 
    get_token_type
)
from app.utils.auth.password import hash_password, verify_password


class AuthService:
    async def signup(self, payload: SignupRequest, db: AsyncSession) -> AuthResponse:
        email = payload.business.business_email.strip().lower()
        existing = await db.execute(
            select(Business).where(Business.business_email == email)
        )
        if existing.scalar_one_or_none():
            raise ValueError("A business with this email already exists")

        business = Business(
            business_owner_name=payload.business.business_owner_name,
            business_email=email,
            password_hash=hash_password(payload.business.password),
            business_name=payload.business.business_name,
            industry_category=payload.business.industry_category,
            support_whatsapp=payload.business.support_whatsapp,
            website_url=payload.business.website_url,
            timezone=payload.business.timezone,
        )

        if payload.whatsapp_connection:
            business.whatsapp_phone_number_id = payload.whatsapp_connection.whatsapp_phone_number_id
            business.whatsapp_connected = True
            connected_at = payload.whatsapp_connection.connected_at or datetime.now(timezone.utc)
            # Ensure connected_at is timezone-aware UTC
            if connected_at.tzinfo is None:
                connected_at = connected_at.replace(tzinfo=timezone.utc)
            business.connected_at = connected_at
        else:
            business.whatsapp_connected = False
            business.connected_at = None

        db.add(business)
        await db.flush()

        settings_row = BusinessSettings(
            business_id=business.id,
            business_name=payload.settings.business_name or business.business_name,
            ai_persona_name=payload.settings.ai_persona_name or settings.DEFAULT_AI_PERSONA_NAME,
            ai_tone=payload.settings.ai_tone or "Friendly",
            knowledge_base=payload.settings.knowledge_base or "",
            auto_followup=payload.settings.auto_followup if payload.settings.auto_followup is not None else True,
            human_handoff_trigger=payload.settings.human_handoff_trigger if payload.settings.human_handoff_trigger is not None else True,
        )
        db.add(settings_row)
        await db.flush()

        token_response, _ = await self._issue_token_pair(db, business.id)
        await db.commit()
        await db.refresh(business)
        await db.refresh(settings_row)

        return AuthResponse(
            business=BusinessRead.model_validate(business),
            settings=BusinessSettingsRead.model_validate(settings_row),
            tokens=token_response,
        )

    async def login(self, payload: LoginRequest, db: AsyncSession) -> AuthResponse:
        email = payload.business_email.strip().lower()
        result = await db.execute(
            select(Business).where(Business.business_email == email)
        )
        business = result.scalar_one_or_none()
        if not business or not verify_password(payload.password, business.password_hash):
            raise ValueError("Invalid email or password")

        business.last_login_at = datetime.now(timezone.utc)
        await db.flush()

        settings_result = await db.execute(
            select(BusinessSettings).where(BusinessSettings.business_id == business.id)
        )
        settings_row = settings_result.scalar_one_or_none()
        if not settings_row:
            settings_row = BusinessSettings(
                business_id=business.id,
                business_name=business.business_name,
                ai_persona_name=settings.DEFAULT_AI_PERSONA_NAME,
                ai_tone="Friendly",
                knowledge_base="",
                auto_followup=True,
                human_handoff_trigger=True,
            )
            db.add(settings_row)
            await db.flush()

        token_response, _ = await self._issue_token_pair(db, business.id)
        await db.commit()
        await db.refresh(business)
        await db.refresh(settings_row)

        return AuthResponse(
            business=BusinessRead.model_validate(business),
            settings=BusinessSettingsRead.model_validate(settings_row),
            tokens=token_response,
        )

    async def refresh(self, payload: RefreshRequest, db: AsyncSession) -> TokenResponse:
        try:
            token_payload = decode_token(payload.refresh_token)
        except Exception as exc:
            raise ValueError("Invalid refresh token") from exc

        if get_token_type(token_payload) != "refresh":
            raise ValueError("Invalid refresh token")

        jti = get_token_jti(token_payload)
        business_id = get_business_id(token_payload)

        business = await db.get(Business, business_id)
        if not business or not business.is_active:
            raise ValueError("Business account is inactive or missing")

        result = await db.execute(select(RefreshToken).where(RefreshToken.jti == jti))
        refresh_row = result.scalar_one_or_none()
        if not refresh_row:
            raise ValueError("Refresh token not found")

        now = datetime.now(timezone.utc)
        if refresh_row.revoked_at is not None:
            raise ValueError("Refresh token has been revoked")
        if refresh_row.expires_at <= now:
            raise ValueError("Refresh token has expired")

        refresh_row.revoked_at = now

        token_response, new_refresh_jti = await self._issue_token_pair(db, business_id)
        refresh_row.replaced_by_jti = new_refresh_jti
        await db.commit()
        return token_response

    async def logout(self, payload: LogoutRequest, db: AsyncSession) -> LogoutResponse:
        try:
            token_payload = decode_token(payload.refresh_token)
        except Exception as exc:
            raise ValueError("Invalid refresh token") from exc

        if get_token_type(token_payload) != "refresh":
            raise ValueError("Invalid refresh token")

        jti = get_token_jti(token_payload)
        result = await db.execute(select(RefreshToken).where(RefreshToken.jti == jti))
        refresh_row = result.scalar_one_or_none()
        
        if not refresh_row:
            return LogoutResponse(
                status="success",
                revoked_at=None,
                message="Token not found; already logged out"
            )

        if refresh_row.revoked_at is not None:
            return LogoutResponse(
                status="already_revoked",
                revoked_at=refresh_row.revoked_at,
                message=f"Token was previously revoked on {refresh_row.revoked_at.isoformat()}"
            )

        revoked_now = datetime.now(timezone.utc)
        refresh_row.revoked_at = revoked_now
        await db.commit()
        
        return LogoutResponse(
            status="success",
            revoked_at=revoked_now,
            message="Token revoked successfully"
        )

    async def _issue_token_pair(self, db: AsyncSession, business_id) -> tuple[TokenResponse, str]:
        access_token, _, access_expires_in = create_access_token(business_id=str(business_id))
        refresh_token, refresh_jti, refresh_expires_in = create_refresh_token(business_id=str(business_id))

        expires_at = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
        db.add(
            RefreshToken(
                jti=refresh_jti,
                business_id=business_id,
                expires_at=expires_at,
            )
        )

        token_response = TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
            access_token_expires_in=access_expires_in,
            refresh_token_expires_in=refresh_expires_in,
        )
        return token_response, refresh_jti