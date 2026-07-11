from pydantic import BaseModel, Field


class PlanRequest(BaseModel):
    idea: str = Field(..., min_length=1, description="한 줄 서비스 아이디어")


class PlanResponse(BaseModel):
    idea: str
    market_research: str
    pestel: str
    competitor_analysis: str
    draft: str
