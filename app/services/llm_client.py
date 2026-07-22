from google import genai

from app.core.config import settings


class LLMClient:
    def __init__(self) -> None:
        self.model = settings.GEMINI_MODEL
        self._client: genai.Client | None = None

    def _get_client(self) -> genai.Client:
        if self._client is None:
            self._client = genai.Client(api_key=settings.GEMINI_API_KEY)
        return self._client

    async def _generate(self, prompt: str, *, use_search: bool = False) -> str:
        tools = [{"type": "google_search"}] if use_search else None
        interaction = await self._get_client().aio.interactions.create(
            model=self.model, input=prompt, tools=tools
        )
        return interaction.output_text or ""

    async def extract_keywords(self, idea: str) -> list[str]:
        # TODO: idea에서 검색 키워드를 추출하는 프롬프트로 교체
        result = await self._generate(f"다음 아이디어의 시장조사용 검색 키워드를 뽑아줘: {idea}")
        return [kw.strip() for kw in result.split(",") if kw.strip()]

    async def synthesize_analysis(
        self, stage: str, context: dict, *, use_search: bool = False
    ) -> str:
        # TODO: stage별(market_research/pestel/competitor_analysis) 프롬프트 템플릿으로 교체
        return await self._generate(
            f"[{stage}] 아래 컨텍스트를 바탕으로 분석해줘: {context}", use_search=use_search
        )

    async def interpret_feedback(self, stage: str, message: str, prior_state: dict) -> list[str]:
        # TODO: 사용자 피드백을 새 키워드/포커스 목록으로 변환하는 프롬프트로 교체
        result = await self._generate(
            f"[{stage}] 기존 키워드 {prior_state.get('keywords')}에 대해 "
            f"사용자가 이렇게 피드백했어: '{message}'. 새 키워드를 뽑아줘."
        )
        return [kw.strip() for kw in result.split(",") if kw.strip()]

    async def synthesize_draft(
        self, market_research: str, pestel: str, competitor_analysis: str
    ) -> str:
        # TODO: 세 분석을 취합해 최종 기획안을 만드는 프롬프트로 교체
        return await self._generate(
            "아래 세 분석을 취합해서 최종 기획안을 작성해줘.\n"
            f"[시장조사]\n{market_research}\n\n[PESTEL]\n{pestel}\n\n[경쟁사분석]\n{competitor_analysis}"
        )


llm_client = LLMClient()
