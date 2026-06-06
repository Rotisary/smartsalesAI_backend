from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.business import Business
from app.utils.auth.jwt import decode_token, get_business_id, get_token_type

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


async def get_current_business(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> Business:
    try:
        payload = decode_token(token)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired access token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if get_token_type(payload) != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type",
            headers={"WWW-Authenticate": "Bearer"},
        )

    business_id = get_business_id(payload)
    business = await db.get(Business, business_id)
    if not business or not business.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Business account is inactive or missing",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return business