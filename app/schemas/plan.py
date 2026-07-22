from typing import Literal

from pydantic import BaseModel, Field


class PlanStartRequest(BaseModel):
    idea: str = Field(..., min_length=1, description="한 줄 서비스 아이디어")


class PlanMessageRequest(BaseModel):
    action: Literal["approve", "revise"]
    message: str | None = None


class DraftUpdateRequest(BaseModel):
    draft: str
