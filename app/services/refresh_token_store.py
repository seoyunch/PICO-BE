from uuid import UUID

from app.db.redis import redis_client

_KEY_PREFIX = "refresh:"


def _key(jti: str) -> str:
    return f"{_KEY_PREFIX}{jti}"


async def store(jti: str, user_id: UUID, ttl_seconds: int) -> None:
    await redis_client.set(_key(jti), str(user_id), ex=ttl_seconds)


async def is_valid(jti: str, user_id: UUID) -> bool:
    stored_user_id = await redis_client.get(_key(jti))
    return stored_user_id == str(user_id)


async def revoke(jti: str) -> None:
    await redis_client.delete(_key(jti))
