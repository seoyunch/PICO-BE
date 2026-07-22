from uuid import uuid4

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from langgraph.types import Command

from app.core.sse import sse_stream
from app.graph.graph import pico_graph
from app.graph.state import new_stage_state
from app.schemas.plan import DraftUpdateRequest, PlanMessageRequest, PlanStartRequest
from app.services.draft_repository import draft_repository

router = APIRouter()


def _config(thread_id: str) -> dict:
    return {"configurable": {"thread_id": thread_id}}


@router.post("/plan/start")
async def start_plan(request: PlanStartRequest) -> StreamingResponse:
    thread_id = str(uuid4())
    initial_state = {
        "idea": request.idea,
        "market_research": new_stage_state(),
        "pestel": new_stage_state(),
        "competitor_analysis": new_stage_state(),
        "draft": "",
    }

    async def events():
        yield {"thread_id": thread_id}
        async for event in pico_graph.astream(
            initial_state, config=_config(thread_id), stream_mode="updates"
        ):
            yield event

    return StreamingResponse(sse_stream(events()), media_type="text/event-stream")


@router.post("/plan/{thread_id}/message")
async def send_message(thread_id: str, request: PlanMessageRequest) -> StreamingResponse:
    async def events():
        async for event in pico_graph.astream(
            Command(resume={"action": request.action, "message": request.message}),
            config=_config(thread_id),
            stream_mode="updates",
        ):
            yield event

    return StreamingResponse(sse_stream(events()), media_type="text/event-stream")


@router.patch("/plan/{thread_id}/draft")
async def update_draft(thread_id: str, request: DraftUpdateRequest) -> dict:
    draft_repository.save(thread_id, request.draft)
    return {"thread_id": thread_id, "draft": request.draft}


@router.get("/plan/{thread_id}/draft")
async def get_draft(thread_id: str) -> dict:
    draft = draft_repository.get(thread_id)
    if draft is None:
        raise HTTPException(status_code=404, detail="draft not found")
    return {"thread_id": thread_id, "draft": draft}
