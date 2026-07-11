from fastapi import APIRouter

from app.graph.graph import pico_graph
from app.schemas.plan import PlanRequest, PlanResponse

router = APIRouter()


@router.post("/plan", response_model=PlanResponse)
async def create_plan(request: PlanRequest):
    result = await pico_graph.ainvoke({"idea": request.idea})
    return PlanResponse(**result)
