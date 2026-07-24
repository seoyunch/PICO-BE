import uuid

import httpx

from app.core.config import settings

_STAGE_LABELS = {
    "market_research": "시장조사",
    "pestel": "PESTEL 분석",
    "lean_canvas": "Lean Canvas",
    "competitor_analysis": "경쟁사 비교분석",
    "market_sizing": "TAM/SAM/SOM 시장 사이징",
    "vpc_features": "VPC 및 핵심 기능 정의",
    "mvp_roadmap": "MVP 및 개발 로드맵",
}


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
        if stage == "lean_canvas":
            return await self._generate(self._lean_canvas_prompt(context))
        if stage == "competitor_analysis":
            return await self._generate(self._competitor_analysis_prompt(context))
        if stage == "market_sizing":
            return await self._generate(self._market_sizing_prompt(context))
        if stage == "vpc_features":
            return await self._generate(self._vpc_features_prompt(context))
        if stage == "mvp_roadmap":
            return await self._generate(self._mvp_roadmap_prompt(context))
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

    def _feedback_points_block(self, keywords: list[str]) -> str:
        if not keywords:
            return ""
        return f"\n\n[이전 수정 요청에서 반영할 포인트]\n{', '.join(keywords)}"

    def _lean_canvas_prompt(self, context: dict) -> str:
        idea = context.get("idea", "")
        market_research = context.get("market_research", "")
        pestel = context.get("pestel", "")
        feedback_block = self._feedback_points_block(context.get("keywords", []))
        return (
            "당신은 스타트업 비즈니스 모델을 설계하는 전략가입니다. "
            "Lean Canvas 9개 블록을 가설 형태로 작성합니다.\n\n"
            f"[아이디어]\n{idea}\n\n"
            f"[시장조사 분석]\n{market_research}\n\n"
            f"[PESTEL 분석]\n{pestel}"
            f"{feedback_block}\n\n"
            "위 분석 내용을 근거로 삼되, 이 단계부터는 검증되지 않은 가설을 세우는 "
            "단계이니 확정된 사실인 것처럼 쓰지 말고 '~일 것으로 가정한다' 식으로 "
            "가설 톤을 유지해줘. 아래 9개 블록을 한국어로 작성해줘.\n\n"
            "1. Problem\n"
            "(핵심 문제 Top 3 + 현재 사용자가 쓰는 대안)\n\n"
            "2. Customer Segments\n"
            "(Early Adopter를 구체적으로 특정)\n\n"
            "3. Unique Value Proposition\n"
            "(왜 이 서비스를 선택해야 하는지 단일 메시지로)\n\n"
            "4. Solution\n"
            "(Problem을 해결하는 핵심 기능 3개 이내)\n\n"
            "5. Channels\n"
            "(타겟 고객에게 도달할 경로)\n\n"
            "6. Revenue Streams\n"
            "(수익 모델과 단가 가설)\n\n"
            "7. Cost Structure\n"
            "(고정비/변동비/CAC/인프라 비용 가설)\n\n"
            "8. Key Metrics\n"
            "(AARRR 또는 North Star Metric 중 이 서비스에 맞는 것 선택)\n\n"
            "9. Unfair Advantage\n"
            "(경쟁자가 쉽게 모방할 수 없는 우위. 없으면 '아직 명확한 우위 없음'이라고 "
            "솔직히 밝혀줘)\n\n"
            "10. 핵심 가설 3개 및 검증 계획\n"
            "(위 9블록 중 이 사업의 성패를 가장 크게 좌우할 가설 3개를 뽑아, "
            "각각 어떻게 검증할지 - 예: 랜딩페이지 테스트, 사전예약, 인터뷰 - 함께 제시)"
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

    def _market_sizing_prompt(self, context: dict) -> str:
        idea = context.get("idea", "")
        keywords = context.get("keywords", [])
        market_research = context.get("market_research", "")
        search_results = context.get("search_results", [])
        sources_text = (
            "\n".join(
                f"- {r.get('title', '')}: {r.get('link', '')}\n  {r.get('description', '')}"
                for r in search_results
            )
            or "(검색 결과 없음)"
        )
        return (
            "당신은 시장 규모를 추정하는 애널리스트입니다. TAM/SAM/SOM을 산정합니다.\n\n"
            f"[아이디어]\n{idea}\n\n"
            f"[검색 키워드]\n{', '.join(keywords)}\n\n"
            f"[시장조사 분석 결과 (참고용 컨텍스트)]\n{market_research}\n\n"
            f"[시장 규모 관련 검색 결과]\n{sources_text}\n\n"
            "위 내용에 근거해서 아래 형식으로 한국어로 작성해줘. 정확한 통계가 없으면 "
            "지어내지 말고 어떤 가정으로 추정했는지 명시하고 '추정치'라고 밝혀줘.\n\n"
            "1. TAM (Total Addressable Market)\n"
            "(전체 잠재 시장 규모와 산출 근거: 잠재 사용자 수 × 평균 지출 등)\n\n"
            "2. SAM (Serviceable Addressable Market)\n"
            "(지역/언어/연령 등으로 좁힌 도달 가능 시장과 그 근거)\n\n"
            "3. SOM (Serviceable Obtainable Market)\n"
            "(1~3년차에 실제 점유 가능한 시장, 보통 SAM의 1~5% 수준, 근거와 함께)\n\n"
            "4. 교차 검증\n"
            "(Top-down 추정치와, 가능하면 Bottom-up 추정치(고객수 × 단가 × 이용빈도)를 "
            "비교해서 두 방식이 얼마나 일치/차이 나는지 서술)\n\n"
            "5. 참고한 출처\n"
            "- (위 검색 결과 중 실제로 참고한 것만 제목과 링크로 나열. 없으면 "
            "'참고할 만한 검색 출처 없음, 일반 상식 기반 추정'이라고 밝혀줘)"
        )

    def _vpc_features_prompt(self, context: dict) -> str:
        idea = context.get("idea", "")
        market_research = context.get("market_research", "")
        competitor_analysis = context.get("competitor_analysis", "")
        feedback_block = self._feedback_points_block(context.get("keywords", []))
        return (
            "당신은 Value Proposition Canvas(VPC)로 서비스 컨셉과 핵심 기능을 "
            "정의하는 PO입니다.\n\n"
            f"[아이디어]\n{idea}\n\n"
            f"[시장조사 분석 - 타겟 고객 니즈]\n{market_research}\n\n"
            f"[경쟁사 비교 분석 - 차별화 포인트]\n{competitor_analysis}"
            f"{feedback_block}\n\n"
            "위 내용을 근거로 아래 형식에 맞춰 한국어로 작성해줘.\n\n"
            "1. 고객 프로필\n"
            "- Customer Jobs: (고객이 해결하려는 과제)\n"
            "- Pains: (수행 중 겪는 불편·장애)\n"
            "- Gains: (원하는 결과·기대 가치)\n\n"
            "2. 가치 지도\n"
            "- Products & Services: (제공할 제품/서비스)\n"
            "- Pain Relievers: (Pain을 해소하는 방식)\n"
            "- Gain Creators: (Gain을 강화하는 방식)\n\n"
            "3. Fit 검증\n"
            "(고객 프로필과 가치 지도가 얼마나 맞아떨어지는지, 안 맞는 부분이 있다면 "
            "무엇인지 솔직히 서술)\n\n"
            "4. 핵심 기능 (5~7개)\n"
            "위 Fit을 근거로 핵심 기능을 아래 마크다운 표로 작성해줘. 난이도는 개발 "
            "구현 난이도, 중요도는 핵심 가치 기여도를 뜻하며 반드시 '상'/'중'/'하' "
            "셋 중 하나로만 표기해줘.\n\n"
            "| 기능명 | 설명 | 난이도 | 중요도 |\n"
            "|---|---|---|---|\n"
            "| ... | ... | 상/중/하 | 상/중/하 |\n\n"
            "5. Use Case (3종)\n"
            "(위 핵심 기능이 실제로 어떻게 쓰이는지 구체적 시나리오 3개, 각 2~3문장)"
        )

    def _mvp_roadmap_prompt(self, context: dict) -> str:
        idea = context.get("idea", "")
        vpc_features = context.get("vpc_features", "")
        feedback_block = self._feedback_points_block(context.get("keywords", []))
        return (
            "당신은 서비스 개발 로드맵을 수립하는 PM입니다.\n\n"
            f"[아이디어]\n{idea}\n\n"
            f"[VPC 및 핵심 기능 정의]\n{vpc_features}"
            f"{feedback_block}\n\n"
            "위에서 도출된 핵심 기능들을 근거로 아래 형식에 맞춰 한국어로 작성해줘.\n\n"
            "1. MoSCoW 분류\n"
            "(핵심 기능들을 Must have / Should have / Could have / Won't have로 "
            "분류. Won't have는 이번 범위에서 제외하는 이유도 한 줄로 명시)\n\n"
            "2. Kano 모델 매핑\n"
            "(Must have로 분류된 기능들을 Basic(당연)/Performance(성능)/"
            "Excitement(매력) 중 하나로 매핑)\n\n"
            "3. MVP 정의\n"
            "(Must have 전체 + Performance 핵심 + Excitement 1~2개로 MVP 범위 확정, "
            "이유와 함께)\n\n"
            "4. 마일스톤 & KPI\n"
            "(MVP 이후 2~3개월 단위 마일스톤 3~4개 + 출시 후 확인할 KPI 2~3개)\n\n"
            "5. Epic 예시\n"
            "(MVP 기능을 Epic 2~3개로 묶어서 나열. 각 Epic마다 대표 User Story 1개를 "
            "'As a ~, I want ~, So that ~' 형식으로, Acceptance Criteria는 "
            "'Given ~, When ~, Then ~' 형식으로 하나씩만 작성)"
        )

    async def classify_feedback_intent(self, stage: str, message: str) -> str:
        stage_label = _STAGE_LABELS.get(stage, stage)
        result = await self._generate(
            f"당신은 {stage_label} 담당 애널리스트입니다. 사용자가 분석 결과를 보고 "
            "아래와 같이 말했습니다.\n\n"
            f"[사용자 메시지]\n{message}\n\n"
            "이 메시지가 다음 중 무엇에 해당하는지 판단해줘:\n"
            "- edit: 분석 본문 내용을 실제로 바꿔달라는 요청 "
            "(예: '~~를 반영해서 수정해줘', '~~ 내용을 더 자세히 다뤄줘', '~~는 빼줘')\n"
            "- chat: 아직 본문 수정을 명시적으로 요청하지 않은 단순 질문이나 의견 요청 "
            "(예: '이 문제를 완화할 방법이 있을까?', '이게 왜 이런거야?')\n\n"
            "정확히 'edit' 또는 'chat' 중 하나만, 그 단어만 답해줘. 다른 설명은 절대 넣지 마."
        )
        first_line = result.strip().splitlines()[0].strip(" *\"'").lower() if result.strip() else ""
        return "edit" if first_line == "edit" else "chat"

    async def answer_question(self, stage: str, message: str, analysis: str) -> str:
        stage_label = _STAGE_LABELS.get(stage, stage)
        return await self._generate(
            f"당신은 {stage_label} 담당 애널리스트입니다. 아래는 방금 작성한 분석 내용입니다.\n\n"
            f"[분석 내용]\n{analysis}\n\n"
            f"[사용자 질문]\n{message}\n\n"
            "위 분석 내용을 참고해서 사용자의 질문에 대화체로 답변해줘. 분석 본문 형식"
            "(번호, 표 등)을 새로 만들지 말고, 질문에 대한 답만 자연스럽게 설명해줘."
        )

    async def interpret_feedback(self, stage: str, message: str, prior_state: dict) -> list[str]:
        stage_label = _STAGE_LABELS.get(stage, stage)
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
        self,
        market_research: str,
        pestel: str,
        lean_canvas: str,
        competitor_analysis: str,
        market_sizing: str,
        vpc_features: str,
        mvp_roadmap: str,
    ) -> str:
        return await self._generate(
            "당신은 스타트업 기획서를 작성하는 컨설턴트입니다.\n"
            "아래 7단계 분석 결과는 이미 사용자가 각각 검토·승인한 최종 내용이니, "
            "새로운 사실을 지어내지 말고 이 내용을 재구성·요약해서 하나의 기획서로 만들어줘.\n\n"
            f"[시장조사 분석]\n{market_research}\n\n"
            f"[PESTEL 분석]\n{pestel}\n\n"
            f"[Lean Canvas]\n{lean_canvas}\n\n"
            f"[경쟁사 비교 분석]\n{competitor_analysis}\n\n"
            f"[TAM/SAM/SOM 시장 사이징]\n{market_sizing}\n\n"
            f"[VPC 및 핵심 기능 정의]\n{vpc_features}\n\n"
            f"[MVP 및 개발 로드맵]\n{mvp_roadmap}\n\n"
            "아래 목차와 형식을 지켜서 한국어 마크다운으로 작성해줘. 각 섹션은 원문을 "
            "그대로 복붙하지 말고 핵심만 재구성해줘.\n\n"
            "# 1. 서비스 개요\n"
            "(분석 내용에서 유추할 수 있는 서비스 컨셉과 핵심 가치를 3~4문장으로)\n\n"
            "# 2. 시장조사 요약\n"
            "(시장조사 분석 내용을 핵심만 재구성)\n\n"
            "# 3. PESTEL 분석\n"
            "(6개 요인과 종합 시사점 위주로 요약)\n\n"
            "# 4. Lean Canvas\n"
            "(9개 블록을 표 또는 목록으로 압축 요약 + 핵심 가설 3개)\n\n"
            "# 5. 경쟁사 비교\n"
            "(경쟁 구도와 차별화 포인트 위주로 요약)\n\n"
            "# 6. 시장 규모 (TAM/SAM/SOM)\n"
            "(TAM/SAM/SOM 수치와 산출 근거를 간결하게 정리)\n\n"
            "# 7. 서비스 컨셉 및 핵심 기능\n"
            "(VPC Fit 요약 + 핵심 기능 표를 그대로 재사용해서 넣어줘. "
            "새로 기능을 지어내지 말고 원문의 표를 그대로 옮겨줘.)\n\n"
            "# 8. 개발 로드맵\n"
            "(MVP 범위, 마일스톤·KPI, Epic 예시를 요약)\n\n"
            "# 9. 종합 결론 및 제언\n"
            "(위 분석들을 종합했을 때 이 아이디어의 핵심 기회 요인과 리스크를 각각 "
            "2~3개씩, 그리고 다음 단계로 무엇을 검증/실행해야 할지 제언)"
        )


llm_client = LLMClient()
