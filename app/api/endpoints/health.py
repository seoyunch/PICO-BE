from fastapi import APIRouter

router = APIRouter()


@router.get("/health", summary="헬스체크")
async def health_check():
    return {"status": "ok"}
