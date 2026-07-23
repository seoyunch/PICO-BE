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
        if stage == "pestel":
            return await self._generate(self._pestel_prompt(context))
        if stage == "competitor_analysis":
            return await self._generate(self._competitor_analysis_prompt(context))
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

    async def decide_pestel_search_query(self, idea: str, market_research: str) -> str | None:
        result = await self._generate(
            "당신은 PESTEL(정치/경제/사회/기술/환경/법률) 분석을 준비하는 애널리스트입니다.\n"
            f"[아이디어]\n{idea}\n\n"
            f"[이미 확보한 시장조사 내용]\n{market_research}\n\n"
            "위 내용만으로 PESTEL 6개 요인(정치/경제/사회/기술/환경/법률)을 근거 있게 "
            "채울 수 있으면 정확히 '충분함' 이라고만 답해줘.\n"
            "부족한 요인이 있으면(예: 관련 규제·정책 동향 등) 그 정보를 찾기 위한 검색창에 그대로 "
            "넣을 검색어를 딱 한 줄로만 답해줘. 설명, 번호, 따옴표, 마크다운은 절대 넣지 마."
        )
        first_line = result.strip().splitlines()[0].strip(" *\"'") if result.strip() else ""
        if not first_line or first_line == "충분함":
            return None
        return first_line

    def _pestel_prompt(self, context: dict) -> str:
        idea = context.get("idea", "")
        keywords = context.get("keywords", [])
        market_research = context.get("market_research", "")
        search_results = context.get("search_results") or []

        additional_search_block = ""
        sources_instruction = ""
        if search_results:
            sources_text = "\n".join(
                f"- {r.get('title', '')}: {r.get('link', '')}\n  {r.get('description', '')}"
                for r in search_results
            )
            additional_search_block = f"\n\n[추가 검색 결과]\n{sources_text}"
            sources_instruction = (
                "\n\n8. 참고한 출처\n"
                "- (위 추가 검색 결과 중 실제로 참고한 것만 제목과 링크로 나열. "
                "검색 결과에 없는 링크는 절대 지어내지 마)"
            )

        return (
            "당신은 스타트업 아이디어의 거시환경(PESTEL)을 분석하는 애널리스트입니다.\n"
            "시장 규모, 타겟 고객, 경쟁사 비교는 다른 단계에서 이미 다루거나 이후에 다루니 "
            "이 분석에는 넣지 마세요. 여기서는 정치/경제/사회/기술/환경/법률 요인만 다룹니다.\n\n"
            f"[아이디어]\n{idea}\n\n"
            f"[검색 키워드]\n{', '.join(keywords)}\n\n"
            f"[시장조사 분석 결과 (참고용 컨텍스트)]\n{market_research}"
            f"{additional_search_block}\n\n"
            "위 시장조사 내용" + ("과 추가 검색 결과" if search_results else "") + "과 "
            "일반 상식에 근거해서, 확실하지 않은 내용은 추정이라고 밝히고\n"
            "아래 형식에 맞춰 한국어로 작성해줘. 각 항목은 2~3문장으로 간결하게 작성해줘.\n\n"
            "1. Political (정치)\n"
            "2. Economic (경제)\n"
            "3. Social (사회)\n"
            "4. Technological (기술)\n"
            "5. Environmental (환경)\n"
            "6. Legal (법률)\n\n"
            "7. 종합 시사점\n"
            "(위 6가지 요인 중 이 아이디어에 특히 중요한 리스크·기회를 2~3개 짚어줘)"
            f"{sources_instruction}"
        )

    def _competitor_analysis_prompt(self, context: dict) -> str:
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
            "당신은 스타트업 아이디어의 경쟁사를 비교분석하는 애널리스트입니다.\n"
            "시장 규모나 PESTEL 같은 거시환경 얘기는 다른 단계에서 다루니 "
            "이 분석에는 넣지 마세요.\n\n"
            f"[아이디어]\n{idea}\n\n"
            f"[검색 키워드]\n{', '.join(keywords)}\n\n"
            f"[검색 결과]\n{sources_text}\n\n"
            "위 검색 결과만 근거로 삼아서, 없는 내용은 지어내지 말고\n"
            "실제로 존재가 확인되는 경쟁 서비스를 3~5개 골라 아래 형식에 맞춰 한국어로 작성해줘.\n"
            "검색 결과에서 경쟁 서비스를 명확히 특정할 수 없으면, 억지로 지어내지 말고 "
            "'검색 결과로는 구체적 경쟁사를 특정하기 어려움'이라고 밝혀줘.\n\n"
            "1. 경쟁 구도 요약\n"
            "(2~3문장으로 이 시장의 경쟁 구도 요약)\n\n"
            "2. 경쟁 서비스별 비교\n"
            "(각 경쟁 서비스마다 아래 항목을 채워서 나열)\n"
            "- 이름:\n"
            "  유형(직접경쟁/대체재 등):\n"
            "  가격:\n"
            "  핵심 기능:\n"
            "  강점:\n"
            "  약점:\n\n"
            "3. 차별화 포인트\n"
            "(위 경쟁사 대비 이 아이디어가 가질 수 있는 차별화 요소 2~3개)\n\n"
            "4. 참고한 출처\n"
            "- (위 검색 결과 중 실제로 참고한 것만 제목과 링크로 나열)"
        )

    async def interpret_feedback(self, stage: str, message: str, prior_state: dict) -> list[str]:
        stage_labels = {
            "market_research": "시장조사",
            "pestel": "PESTEL 분석",
            "competitor_analysis": "경쟁사 비교분석",
        }
        stage_label = stage_labels.get(stage, stage)
        prior_keywords = prior_state.get("keywords", [])

        result = await self._generate(
            f"당신은 {stage_label} 담당 애널리스트입니다. "
            "사용자가 이전 분석 결과에 대해 수정 요청을 했습니다.\n\n"
            f"[기존 검색 키워드]\n{', '.join(prior_keywords)}\n\n"
            f"[사용자 수정 요청]\n{message}\n\n"
            "이 수정 요청을 반영해서 다시 검색할 새 키워드를 뽑아줘. 기존 키워드 중 "
            "여전히 유효한 것은 유지하고, 요청 내용을 반영한 키워드를 추가/교체해줘.\n"
            "정확히 3~5개만, 쉼표(,)로 구분한 한 줄로만 답해줘. "
            "설명, 번호 매기기, 마크다운, 줄바꿈은 절대 넣지 마."
        )
        first_line = result.strip().splitlines()[0] if result.strip() else ""
        return [kw.strip(" *") for kw in first_line.split(",") if kw.strip(" *")]

    async def synthesize_draft(
        self, market_research: str, pestel: str, competitor_analysis: str
    ) -> str:
        return await self._generate(
            "당신은 스타트업 기획서를 작성하는 컨설턴트입니다.\n"
            "아래 세 단계 분석 결과를 이미 사용자가 검토·승인한 최종 내용이니, "
            "새로운 사실을 지어내지 말고 이 내용을 재구성·요약해서 하나의 기획서로 만들어줘.\n\n"
            f"[시장조사 분석]\n{market_research}\n\n"
            f"[PESTEL 분석]\n{pestel}\n\n"
            f"[경쟁사 비교 분석]\n{competitor_analysis}\n\n"
            "아래 목차와 형식을 지켜서 한국어 마크다운으로 작성해줘.\n\n"
            "# 1. 서비스 개요\n"
            "(분석 내용에서 유추할 수 있는 서비스 컨셉과 핵심 가치를 3~4문장으로)\n\n"
            "# 2. 시장조사 요약\n"
            "(시장조사 분석 내용을 핵심만 재구성. 원문을 그대로 복붙하지 말고 요약)\n\n"
            "# 3. PESTEL 분석\n"
            "(PESTEL 분석 내용을 요약. 6개 요인과 종합 시사점 위주로)\n\n"
            "# 4. 경쟁사 비교\n"
            "(경쟁사 비교 분석 내용을 요약. 경쟁 구도와 차별화 포인트 위주로)\n\n"
            "# 5. 핵심 기능\n"
            "(시장조사의 타겟 고객 니즈, 경쟁사 비교의 차별화 포인트를 근거로 "
            "이 서비스가 갖춰야 할 핵심 기능을 4~6개 도출해서 아래 마크다운 표로 작성해줘.\n"
            "난이도는 개발 구현 난이도, 중요도는 서비스 핵심 가치에 대한 기여도를 뜻하며 "
            "반드시 '상'/'중'/'하' 셋 중 하나로만 표기해줘.)\n\n"
            "| 기능명 | 설명 | 난이도 | 중요도 |\n"
            "|---|---|---|---|\n"
            "| ... | ... | 상/중/하 | 상/중/하 |\n\n"
            "# 6. 종합 결론 및 제언\n"
            "(위 세 분석을 종합했을 때 이 아이디어의 핵심 기회 요인과 리스크를 각각 2~3개씩, "
            "그리고 다음 단계로 무엇을 검증/실행해야 할지 제언)"
        )


llm_client = LLMClient()
