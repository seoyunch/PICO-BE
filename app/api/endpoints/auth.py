from uuid import UUID

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.config import settings
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_refresh_token,
    hash_password,
    verify_password,
)
from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import LoginRequest, SignupRequest, TokenResponse, UserResponse
from app.services import refresh_token_store

router = APIRouter()

REFRESH_COOKIE_NAME = "refresh_token"
REFRESH_COOKIE_PATH = f"{settings.API_STR}/auth"


async def _issue_tokens(response: Response, user_id: UUID) -> TokenResponse:
    refresh = create_refresh_token(user_id)
    await refresh_token_store.store(refresh.jti, user_id, refresh.expires_in_seconds)
    response.set_cookie(
        key=REFRESH_COOKIE_NAME,
        value=refresh.token,
        max_age=refresh.expires_in_seconds,
        path=REFRESH_COOKIE_PATH,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite="lax",
    )
    return TokenResponse(access_token=create_access_token(user_id))


@router.post("/auth/signup", summary="회원가입", response_model=TokenResponse)
async def signup(
    request: SignupRequest, response: Response, db: AsyncSession = Depends(get_db)
) -> TokenResponse:
    existing = await db.scalar(select(User).where(User.email == request.email))
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="이미 가입된 이메일입니다")

    user = User(
        email=request.email,
        password_hash=hash_password(request.password),
        name=request.name,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    return await _issue_tokens(response, user.id)


@router.post("/auth/login", summary="로그인", response_model=TokenResponse)
async def login(
    request: LoginRequest, response: Response, db: AsyncSession = Depends(get_db)
) -> TokenResponse:
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED, detail="이메일 또는 비밀번호가 올바르지 않습니다"
    )
    user = await db.scalar(select(User).where(User.email == request.email))
    if user is None or not verify_password(request.password, user.password_hash):
        raise unauthorized

    return await _issue_tokens(response, user.id)


@router.post("/auth/refresh", summary="access token 재발급", response_model=TokenResponse)
async def refresh(
    response: Response,
    refresh_token: str | None = Cookie(default=None, alias=REFRESH_COOKIE_NAME),
) -> TokenResponse:
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED, detail="refresh token이 유효하지 않습니다"
    )
    if refresh_token is None:
        raise unauthorized

    payload = decode_refresh_token(refresh_token)
    if payload is None or not await refresh_token_store.is_valid(payload.jti, payload.user_id):
        raise unauthorized

    await refresh_token_store.revoke(payload.jti)
    return await _issue_tokens(response, payload.user_id)


@router.post("/auth/logout", summary="로그아웃", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    response: Response,
    refresh_token: str | None = Cookie(default=None, alias=REFRESH_COOKIE_NAME),
) -> None:
    if refresh_token is not None:
        payload = decode_refresh_token(refresh_token)
        if payload is not None:
            await refresh_token_store.revoke(payload.jti)
    response.delete_cookie(REFRESH_COOKIE_NAME, path=REFRESH_COOKIE_PATH)


@router.get("/auth/me", summary="내 정보 조회", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)) -> UserResponse:
    return UserResponse(id=current_user.id, email=current_user.email, name=current_user.name)
