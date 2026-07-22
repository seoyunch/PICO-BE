import uuid

import httpx

from app.core.config import settings


class LLMClient:
    def __init__(self) -> None:
        self.api_key = settings.CLOVA_API_KEY
        self.model = settings.CLOVA_MODEL
        self.base_url = settings.CLOVA_API_BASE_URL

    async def _generate(self, prompt: str) -> str:
        async with httpx.AsyncClient(base_url=self.base_url, timeout=60.0) as client:
            response = await client.post(
                f"/v3/chat-completions/{self.model}",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "X-NCP-CLOVASTUDIO-REQUEST-ID": str(uuid.uuid4()),
                    "Content-Type": "application/json",
                },
                json={
                    "messages": [{"role": "user", "content": prompt}],
                    "topP": 0.8,
                    "temperature": 0.5,
                    "maxTokens": 1024,
                },
            )
            response.raise_for_status()
            return response.json()["result"]["message"]["content"]

    async def extract_keywords(self, idea: str) -> list[str]:
        result = await self._generate(
            f"다음 아이디어의 시장조사용 검색 키워드를 뽑아줘: {idea}\n\n"
            "정확히 3~5개만, 쉼표(,)로 구분한 한 줄로만 답해줘. "
            "설명, 번호 매기기, 마크다운, 줄바꿈은 절대 넣지 마."
        )
        first_line = result.strip().splitlines()[0] if result.strip() else ""
        return [kw.strip(" *") for kw in first_line.split(",") if kw.strip(" *")]

    async def synthesize_analysis(self, stage: str, context: dict) -> str:
        if stage == "market_research":
            return await self._generate(self._market_research_prompt(context))
        # TODO: pestel/competitor_analysis도 프롬프트 템플릿으로 교체
        return await self._generate(f"[{stage}] 아래 컨텍스트를 바탕으로 분석해줘: {context}")

    def _market_research_prompt(self, context: dict) -> str:
        idea = context.get("idea", "")
        keywords = context.get("keywords", [])
        search_results = context.get("search_results", [])
        sources_text = (
            "\n".join(
                f"- {r.get('title', '')}: {r.get('link', '')}\n  {r.get('description', '')}"
                for r in search_results
            )
            or "(검색 결과 없음)"
        )
        return (
            "당신은 스타트업 아이디어의 시장조사를 담당하는 애널리스트입니다.\n"
            "PESTEL 분석과 경쟁사 비교분석은 이후 별도 단계에서 다루니, "
            "정치/경제/사회/기술/환경/법률 같은 거시환경 얘기나 "
            "특정 경쟁사 이름별 비교는 이 분석에 넣지 마세요.\n\n"
            f"[아이디어]\n{idea}\n\n"
            f"[검색 키워드]\n{', '.join(keywords)}\n\n"
            f"[검색 결과]\n{sources_text}\n\n"
            "위 검색 결과만 근거로 삼아서, 없는 내용은 지어내지 말고\n"
            "아래 형식에 맞춰 한국어로 작성해줘.\n\n"
            "1. 리서치 요약\n"
            "(2~3문장으로 핵심 발견 요약)\n\n"
            "2. 시장 규모/성장성\n"
            "(검색 결과에 근거한 시장 규모·성장 추세. 정확한 수치가 없으면 "
            "정성적 추정이라고 밝히고 서술)\n\n"
            "3. 타겟 고객 & 니즈\n"
            "(누가 쓸 서비스인지, 그들의 페인포인트/니즈가 뭔지)\n\n"
            "4. 핵심 트렌드/시그널\n"
            "- (시장 동향·화제성 관련 포인트 3~5개, 각 한 줄)\n\n"
            "5. 참고한 출처\n"
            "- (위 검색 결과 중 실제로 참고한 것만 제목과 링크로 나열)"
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
