from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from langgraph.types import Command
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.sse import sse_stream
from app.db.session import get_db
from app.graph.graph import pico_graph
from app.graph.state import new_pico_state
from app.models.user import User
from app.schemas.plan import DraftSummary, DraftUpdateRequest, PlanMessageRequest, PlanStartRequest
from app.services import draft_repository

router = APIRouter()


def _config(thread_id: str) -> dict:
    return {"configurable": {"thread_id": thread_id}}


@router.post(
    "/plan/start",
    summary="기획서 생성 시작",
    description="아이디어를 받아 새 스레드를 만들고 시장조사 단계부터 그래프를 실행한다. "
    "SSE로 스트리밍되며, 리뷰 단계에서 interrupt로 멈춘다.",
)
async def start_plan(request: PlanStartRequest) -> StreamingResponse:
    thread_id = str(uuid4())
    initial_state = new_pico_state(request.idea)

    async def events():
        yield {"thread_id": thread_id}
        async for event in pico_graph.astream(
            initial_state, config=_config(thread_id), stream_mode="updates"
        ):
            yield event

    return StreamingResponse(sse_stream(events()), media_type="text/event-stream")


@router.post(
    "/plan/{thread_id}/message",
    summary="리뷰 단계 재개 (승인/수정/질문)",
    description="interrupt로 멈춘 스레드를 재개한다. action이 approve면 다음 단계로, "
    "revise면 메시지 의도(edit/chat)를 판단해 본문을 재생성하거나 질문에 답한다.",
)
async def send_message(thread_id: str, request: PlanMessageRequest) -> StreamingResponse:
    async def events():
        async for event in pico_graph.astream(
            Command(resume={"action": request.action, "message": request.message}),
            config=_config(thread_id),
            stream_mode="updates",
        ):
            yield event

    return StreamingResponse(sse_stream(events()), media_type="text/event-stream")


@router.get(
    "/plan/drafts", summary="최근 생성한 기획서 초안 목록", response_model=list[DraftSummary]
)
async def list_drafts(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[DraftSummary]:
    drafts = await draft_repository.list_recent(db, current_user.id)
    return [
        DraftSummary(thread_id=d.thread_id, idea=d.idea, created_at=d.created_at) for d in drafts
    ]


@router.patch("/plan/{thread_id}/draft", summary="기획서 초안 수정")
async def update_draft(
    thread_id: str,
    request: DraftUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    draft = await draft_repository.save_draft(
        db, current_user.id, thread_id, request.idea, request.draft
    )
    return {"thread_id": thread_id, "idea": draft.idea, "draft": draft.content}


@router.get("/plan/{thread_id}/draft", summary="기획서 초안 조회")
async def get_draft(
    thread_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    draft = await draft_repository.get_draft(db, current_user.id, thread_id)
    if draft is None:
        raise HTTPException(status_code=404, detail="draft not found")
    return {"thread_id": thread_id, "idea": draft.idea, "draft": draft.content}
