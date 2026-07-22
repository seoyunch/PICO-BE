import httpx

from app.core.config import settings


class LLMClient:
    def __init__(self) -> None:
        self.provider = settings.LLM_PROVIDER
        self.api_key = settings.LLM_API_KEY
        self.base_url = settings.LLM_API_BASE_URL
        self.model = settings.LLM_MODEL

    async def complete(self, prompt: str) -> str:
        # TODO: provider(clova 등)별 요청 포맷에 맞춰 구현
        async with httpx.AsyncClient(base_url=self.base_url) as client:
            response = await client.post(
                "/",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={"model": self.model, "prompt": prompt},
            )
            response.raise_for_status()
            return response.text

    async def extract_keywords(self, idea: str) -> list[str]:
        # TODO: idea에서 검색 키워드를 추출하는 프롬프트로 교체
        result = await self.complete(f"다음 아이디어의 시장조사용 검색 키워드를 뽑아줘: {idea}")
        return [kw.strip() for kw in result.split(",") if kw.strip()]

    async def synthesize_analysis(self, stage: str, context: dict) -> str:
        # TODO: stage별(market_research/pestel/competitor_analysis) 프롬프트 템플릿으로 교체
        return await self.complete(f"[{stage}] 아래 컨텍스트를 바탕으로 분석해줘: {context}")

    async def interpret_feedback(self, stage: str, message: str, prior_state: dict) -> list[str]:
        # TODO: 사용자 피드백을 새 키워드/포커스 목록으로 변환하는 프롬프트로 교체
        result = await self.complete(
            f"[{stage}] 기존 키워드 {prior_state.get('keywords')}에 대해 "
            f"사용자가 이렇게 피드백했어: '{message}'. 새 키워드를 뽑아줘."
        )
        return [kw.strip() for kw in result.split(",") if kw.strip()]

    async def synthesize_draft(
        self, market_research: str, pestel: str, competitor_analysis: str
    ) -> str:
        # TODO: 세 분석을 취합해 최종 기획안을 만드는 프롬프트로 교체
        return await self.complete(
            "아래 세 분석을 취합해서 최종 기획안을 작성해줘.\n"
            f"[시장조사]\n{market_research}\n\n[PESTEL]\n{pestel}\n\n[경쟁사분석]\n{competitor_analysis}"
        )


llm_client = LLMClient()
