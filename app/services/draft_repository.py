import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.draft import Draft


async def save_draft(db: AsyncSession, user_id: uuid.UUID, thread_id: str, content: str) -> Draft:
    draft = await db.scalar(
        select(Draft).where(Draft.user_id == user_id, Draft.thread_id == thread_id)
    )
    if draft is None:
        draft = Draft(user_id=user_id, thread_id=thread_id, content=content)
        db.add(draft)
    else:
        draft.content = content
    await db.commit()
    await db.refresh(draft)
    return draft


async def get_draft(db: AsyncSession, user_id: uuid.UUID, thread_id: str) -> Draft | None:
    return await db.scalar(
        select(Draft).where(Draft.user_id == user_id, Draft.thread_id == thread_id)
    )
