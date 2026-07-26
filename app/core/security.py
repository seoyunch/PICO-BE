from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import bcrypt
from jose import JWTError, jwt

from app.core.config import settings


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


def _create_token(user_id: UUID, token_type: str, expires_delta: timedelta, jti: str) -> str:
    payload = {
        "sub": str(user_id),
        "type": token_type,
        "jti": jti,
        "exp": datetime.now(timezone.utc) + expires_delta,
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def create_access_token(user_id: UUID) -> str:
    return _create_token(
        user_id,
        "access",
        timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
        jti=str(uuid4()),
    )


@dataclass
class RefreshToken:
    token: str
    jti: str
    expires_in_seconds: int


def create_refresh_token(user_id: UUID) -> RefreshToken:
    jti = str(uuid4())
    expires_delta = timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    token = _create_token(user_id, "refresh", expires_delta, jti=jti)
    return RefreshToken(token=token, jti=jti, expires_in_seconds=int(expires_delta.total_seconds()))


@dataclass
class TokenPayload:
    user_id: UUID
    jti: str


def _decode_token(token: str, expected_type: str) -> TokenPayload | None:
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
    except JWTError:
        return None
    if payload.get("type") != expected_type:
        return None
    sub = payload.get("sub")
    jti = payload.get("jti")
    if sub is None or jti is None:
        return None
    return TokenPayload(user_id=UUID(sub), jti=jti)


def decode_access_token(token: str) -> UUID | None:
    payload = _decode_token(token, "access")
    return payload.user_id if payload else None


def decode_refresh_token(token: str) -> TokenPayload | None:
    return _decode_token(token, "refresh")
