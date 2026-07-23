from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.api import api_router
from app.core.config import settings

tags_metadata = [
    {"name": "health", "description": "서버 상태 확인용 헬스체크"},
    {
        "name": "plan",
        "description": "LangGraph 기반 기획서 생성 파이프라인 — "
        "시작/재개(승인·수정·질문)/초안 조회·수정",
    },
]

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="PICO — LangGraph 멀티에이전트 기반 스타트업 기획서 자동 생성 서비스",
    version="0.1.0",
    openapi_tags=tags_metadata,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix=settings.API_STR)
