import json
import logging
import re
import uuid

import httpx
from langfuse import observe

from app.core.config import settings
from app.core.langfuse_client import langfuse_client
from app.utils.perf import timed

_json_logger = logging.getLogger("pico.llm_json")
if not _json_logger.handlers:
    _handler = logging.StreamHandler()
    _handler.setFormatter(logging.Formatter("%(asctime)s %(name)s %(message)s"))
    _json_logger.addHandler(_handler)
_json_logger.setLevel(logging.INFO)

_JSON_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)

_JSON_ONLY_INSTRUCTION = (
    "\n\n[출력 형식 - 반드시 지켜줘]\n"
    "다른 설명이나 마크다운 코드블록(```) 없이, 순수한 JSON 객체 하나만 출력해줘. "
    "위에서 요구한 키를 전부 포함하고, 값은 전부 문자열이나 배열이어야 해(중첩 객체는 "
    "명시된 곳에서만). JSON 앞뒤에 다른 텍스트를 절대 붙이지 마."
)


def _parse_json_response(raw: str, *, stage: str) -> dict:
    """CLOVA가 JSON으로 답하기로 한 단계의 응답을 파싱한다.

    지시를 어기고 ```json 코드펜스로 감싸는 경우가 흔해서 먼저 벗겨내고,
    그래도 파싱이 깨지면(따옴표 누락 등) 빈 dict를 반환해서 렌더러가 각 필드의
    fallback 문구로 채우게 한다 - 한 단계 전체가 예외로 죽는 것보다 낫다.
    """
    stripped = _JSON_FENCE_RE.sub("", raw.strip()).strip()
    try:
        data = json.loads(stripped)
        _json_logger.info("json_parse stage=%s ok=true", stage)
        return data if isinstance(data, dict) else {}
    except json.JSONDecodeError:
        _json_logger.info("json_parse stage=%s ok=false", stage)
        return {}


def _pick(data: dict, key: str, fallback: str = "정보 없음") -> str:
    value = data.get(key)
    return str(value).strip() if value else fallback


_VALID_LEVELS = {"상", "중", "하"}


def _clamp_level(value) -> str:
    text = str(value).strip() if value else ""
    return text if text in _VALID_LEVELS else "중"


_SECTION_FORMAT_RULE = (
    "[형식 규칙 - 반드시 지켜줘]\n"
    "- 각 섹션 제목은 그 줄에 번호와 제목만 쓰고, 같은 줄에 본문을 이어 쓰지 마.\n"
    "- 제목 줄 바로 다음 줄부터 본문을 시작해줘(제목과 본문 사이에 다른 문장 없이 줄바꿈만).\n"
    "- 제목에 '**' 같은 마크다운 강조 기호를 붙이지 마.\n"
    "- 섹션 본문 안에서는 번호 목록(1. 2. 3. ...)을 절대 쓰지 말고, 항목을 나열할 때는 "
    "대시(-) 목록만 사용해줘. 번호는 섹션 제목에서만 쓰는 거야.\n\n"
)

_CITATION_INSTRUCTION = (
    "출처를 표시할 때는 절대 URL이나 링크 텍스트를 직접 쓰지 말고, 위 검색 결과 번호만 "
    "대괄호로 표시해(예: [1], [3]). 실제 링크는 시스템이 번호에 맞춰 자동으로 채워 넣으니 "
    "번호 외에 다른 텍스트는 쓰지 마. <a href=...> 같은 HTML 태그나 마크다운 링크 문법도 "
    "절대 쓰지 마 — 순수 텍스트로 번호만 적어."
)


def _numbered_sources(search_results: list[dict]) -> str:
    if not search_results:
        return "(검색 결과 없음)"
    return "\n".join(
        f"[{i}] {r.get('title', '')}\n    {r.get('description', '')}"
        for i, r in enumerate(search_results, start=1)
    )


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

    @timed("clova_generate")
    @observe(as_type="generation", name="clova_generate")
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
            body = response.json()
            content = body["result"]["message"]["content"]
            usage = body.get("result", {}).get("usage") or {}
            usage_details = {
                "input": usage.get("promptTokens"),
                "output": usage.get("completionTokens"),
                "total": usage.get("totalTokens"),
            }
            langfuse_client.update_current_generation(
                model=self.model,
                usage_details={k: v for k, v in usage_details.items() if v is not None},
            )
            return content

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
            raw = await self._generate(self._pestel_prompt(context))
            data = _parse_json_response(raw, stage=stage)
            return self._render_pestel(data, context.get("search_results") or [])
        if stage == "lean_canvas":
            raw = await self._generate(self._lean_canvas_prompt(context))
            data = _parse_json_response(raw, stage=stage)
            return self._render_lean_canvas(data)
        if stage == "competitor_analysis":
            return await self._generate(self._competitor_analysis_prompt(context))
        if stage == "market_sizing":
            return await self._generate(self._market_sizing_prompt(context))
        if stage == "vpc_features":
            raw = await self._generate(self._vpc_features_prompt(context))
            data = _parse_json_response(raw, stage=stage)
            return self._render_vpc_features(data)
        if stage == "mvp_roadmap":
            raw = await self._generate(self._mvp_roadmap_prompt(context))
            data = _parse_json_response(raw, stage=stage)
            return self._render_mvp_roadmap(data)
        return await self._generate(f"[{stage}] 아래 컨텍스트를 바탕으로 분석해줘: {context}")

    def _market_research_prompt(self, context: dict) -> str:
        idea = context.get("idea", "")
        keywords = context.get("keywords", [])
        search_results = context.get("search_results", [])
        sources_text = _numbered_sources(search_results)
        feedback_block = self._revision_context_block(
            context.get("previous_analysis", ""), context.get("feedback_message", "")
        )
        return (
            "당신은 스타트업 아이디어의 시장조사를 담당하는 애널리스트입니다.\n"
            "PESTEL 분석과 경쟁사 비교분석은 이후 별도 단계에서 다루니, "
            "정치/경제/사회/기술/환경/법률 같은 거시환경 얘기나 "
            "특정 경쟁사 이름별 비교는 이 분석에 넣지 마세요.\n\n"
            f"[아이디어]\n{idea}\n\n"
            f"[검색 키워드]\n{', '.join(keywords)}\n\n"
            f"[검색 결과]\n{sources_text}"
            f"{feedback_block}\n\n"
            "위 검색 결과만 근거로 삼아서, 없는 내용은 지어내지 말고\n"
            "아래 형식에 맞춰 한국어로 작성해줘.\n\n"
            f"{_SECTION_FORMAT_RULE}"
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
            "- (위 검색 결과 중 실제로 참고한 것만 번호로 나열)\n"
            f"{_CITATION_INSTRUCTION}"
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
        if search_results:
            additional_search_block = f"\n\n[추가 검색 결과]\n{_numbered_sources(search_results)}"
        feedback_block = self._revision_context_block(
            context.get("previous_analysis", ""), context.get("feedback_message", "")
        )

        citations_key_line = (
            '"citations": [실제로 참고한 검색 결과 번호만 정수로, 예: 1, 3],\n'
            if search_results
            else ""
        )

        return (
            "당신은 스타트업 아이디어의 거시환경(PESTEL)을 분석하는 애널리스트입니다.\n"
            "시장 규모, 타겟 고객, 경쟁사 비교는 다른 단계에서 이미 다루거나 이후에 다루니 "
            "이 분석에는 넣지 마세요. 여기서는 정치/경제/사회/기술/환경/법률 요인만 다룹니다.\n\n"
            f"[아이디어]\n{idea}\n\n"
            f"[검색 키워드]\n{', '.join(keywords)}\n\n"
            f"[시장조사 분석 결과 (참고용 컨텍스트)]\n{market_research}"
            f"{additional_search_block}"
            f"{feedback_block}\n\n"
            "위 시장조사 내용" + ("과 추가 검색 결과" if search_results else "") + "과 "
            "일반 상식에 근거해서, 확실하지 않은 내용은 추정이라고 밝히고 아래 키를 가진 "
            "JSON 객체로 답해줘. 각 값은 2~3문장으로 간결하게 작성해줘.\n\n"
            "{\n"
            '  "political": "정책·규제 동향 2~3문장",\n'
            '  "economic": "경제 상황·소비 여력 2~3문장",\n'
            '  "social": "사회적 인식·라이프스타일 변화 2~3문장",\n'
            '  "technological": "활용 가능한 기술 트렌드 2~3문장",\n'
            '  "environmental": "환경적 요인·지속가능성 이슈 2~3문장",\n'
            '  "legal": "법률·인증·컴플라이언스 이슈 2~3문장",\n'
            '  "synthesis": "위 6가지 요인 중 이 아이디어에 특히 중요한 리스크·기회 2~3개",\n'
            f"{citations_key_line}"
            "}"
            f"{_JSON_ONLY_INSTRUCTION}"
        )

    def _render_pestel(self, data: dict, search_results: list[dict]) -> str:
        parts = [
            "1. Political (정치)",
            _pick(data, "political"),
            "",
            "2. Economic (경제)",
            _pick(data, "economic"),
            "",
            "3. Social (사회)",
            _pick(data, "social"),
            "",
            "4. Technological (기술)",
            _pick(data, "technological"),
            "",
            "5. Environmental (환경)",
            _pick(data, "environmental"),
            "",
            "6. Legal (법률)",
            _pick(data, "legal"),
            "",
            "7. 종합 시사점",
            _pick(data, "synthesis"),
        ]
        if search_results:
            citations = data.get("citations") or []
            lines = [f"- [{i}]" for i in citations if isinstance(i, int)]
            parts += ["", "8. 참고한 출처", *(lines or ["- (참고한 출처 없음)"])]
        return "\n".join(parts)

    def _revision_context_block(self, previous_analysis: str, feedback_message: str) -> str:
        if not feedback_message:
            return ""
        previous_block = f"\n\n[기존 분석 결과]\n{previous_analysis}" if previous_analysis else ""
        return (
            f"{previous_block}\n\n"
            f"[사용자 수정 요청 원문]\n{feedback_message}\n\n"
            "위 수정 요청을 반영해줘. [기존 분석 결과]가 있다면 그걸 베이스로 삼아서, "
            "요청과 관련 없는 내용은 최대한 그대로 유지하고 요청과 관련된 부분만 고치거나 "
            "덧붙여줘. 다만 사용자가 '처음부터 다시', '전체를 다시 조사/작성해줘'처럼 "
            "전면 재작성을 명확히 요청한 경우에는 기존 내용에 얽매이지 말고 완전히 새로 "
            "작성해도 돼."
        )

    def _lean_canvas_prompt(self, context: dict) -> str:
        idea = context.get("idea", "")
        market_research = context.get("market_research", "")
        pestel = context.get("pestel", "")
        feedback_block = self._revision_context_block(
            context.get("previous_analysis", ""), context.get("feedback_message", "")
        )
        return (
            "당신은 스타트업 비즈니스 모델을 설계하는 전략가입니다. "
            "Lean Canvas 9개 블록을 가설 형태로 작성합니다.\n\n"
            f"[아이디어]\n{idea}\n\n"
            f"[시장조사 분석]\n{market_research}\n\n"
            f"[PESTEL 분석]\n{pestel}"
            f"{feedback_block}\n\n"
            "위 분석 내용을 근거로 삼되, 이 단계부터는 검증되지 않은 가설을 세우는 "
            "단계이니 확정된 사실인 것처럼 쓰지 말고 '~일 것으로 가정한다' 식으로 "
            "가설 톤을 유지해줘. 아래 키를 가진 JSON 객체로 답해줘.\n\n"
            "{\n"
            '  "problem": "핵심 문제 Top 3 + 현재 사용자가 쓰는 대안",\n'
            '  "customer_segments": "Early Adopter를 구체적으로 특정",\n'
            '  "unique_value_proposition": "왜 이 서비스를 선택해야 하는지 단일 메시지",\n'
            '  "solution": "Problem을 해결하는 핵심 기능 3개 이내",\n'
            '  "channels": "타겟 고객에게 도달할 경로",\n'
            '  "revenue_streams": "수익 모델과 단가 가설",\n'
            '  "cost_structure": "고정비/변동비/CAC/인프라 비용 가설",\n'
            '  "key_metrics": "AARRR 또는 North Star Metric 중 이 서비스에 맞는 것",\n'
            '  "unfair_advantage": "경쟁자가 쉽게 모방 못하는 우위. 없으면 '
            "'아직 명확한 우위 없음'이라고 솔직히\",\n"
            '  "hypotheses": [\n'
            '    {"hypothesis": "가설 1 내용", "validation_plan": "검증 계획 - 예: '
            '랜딩페이지 테스트, 사전예약, 인터뷰"},\n'
            '    {"hypothesis": "가설 2 내용", "validation_plan": "검증 계획"},\n'
            '    {"hypothesis": "가설 3 내용", "validation_plan": "검증 계획"}\n'
            "  ]\n"
            "}\n"
            "hypotheses는 위 9블록 중 이 사업의 성패를 가장 크게 좌우할 가설 3개를 뽑은 "
            "것이어야 해. 정확히 3개."
            f"{_JSON_ONLY_INSTRUCTION}"
        )

    def _render_lean_canvas(self, data: dict) -> str:
        parts = [
            "1. Problem",
            _pick(data, "problem"),
            "",
            "2. Customer Segments",
            _pick(data, "customer_segments"),
            "",
            "3. Unique Value Proposition",
            _pick(data, "unique_value_proposition"),
            "",
            "4. Solution",
            _pick(data, "solution"),
            "",
            "5. Channels",
            _pick(data, "channels"),
            "",
            "6. Revenue Streams",
            _pick(data, "revenue_streams"),
            "",
            "7. Cost Structure",
            _pick(data, "cost_structure"),
            "",
            "8. Key Metrics",
            _pick(data, "key_metrics"),
            "",
            "9. Unfair Advantage",
            _pick(data, "unfair_advantage"),
            "",
            "10. 핵심 가설 3개 및 검증 계획",
        ]
        hypotheses = data.get("hypotheses") or []
        if not hypotheses:
            parts.append("- (가설 정보 없음)")
        for i, h in enumerate(hypotheses, start=1):
            hypothesis = _pick(h, "hypothesis", "가설 정보 없음") if isinstance(h, dict) else str(h)
            plan = _pick(h, "validation_plan", "검증 계획 없음") if isinstance(h, dict) else ""
            parts.append(f"- 가설 {i}: {hypothesis} / 검증 계획: {plan}")
        return "\n".join(parts)

    def _competitor_analysis_prompt(self, context: dict) -> str:
        idea = context.get("idea", "")
        keywords = context.get("keywords", [])
        search_results = context.get("search_results", [])
        sources_text = _numbered_sources(search_results)
        feedback_block = self._revision_context_block(
            context.get("previous_analysis", ""), context.get("feedback_message", "")
        )
        return (
            "당신은 스타트업 아이디어의 경쟁사를 비교분석하는 애널리스트입니다.\n"
            "시장 규모나 PESTEL 같은 거시환경 얘기는 다른 단계에서 다루니 "
            "이 분석에는 넣지 마세요.\n\n"
            f"[아이디어]\n{idea}\n\n"
            f"[검색 키워드]\n{', '.join(keywords)}\n\n"
            f"[검색 결과]\n{sources_text}"
            f"{feedback_block}\n\n"
            "위 검색 결과만 근거로 삼아서, 없는 내용은 지어내지 말고\n"
            "실제로 존재가 확인되는 경쟁 서비스를 3~5개 골라 아래 형식에 맞춰 한국어로 작성해줘.\n"
            "검색 결과 중에는 '~앱 추천 TOP 11', '~가이드', '~하는 방법' 같은 블로그/리스티클 "
            "글도 섞여 있을 수 있어. 그런 글의 제목을 그대로 경쟁 서비스 이름으로 쓰지 마 — "
            "'이름'에는 그 글이 소개하는 실제 제품/서비스/회사명만 적고, 그 글 안에서 구체적인 "
            "제품명을 특정할 수 없으면 그 글은 근거로 쓰지 마.\n"
            "검색 결과에서 경쟁 서비스를 명확히 특정할 수 없으면, 억지로 지어내지 말고 "
            "'검색 결과로는 구체적 경쟁사를 특정하기 어려움'이라고 밝혀줘.\n\n"
            f"{_SECTION_FORMAT_RULE}"
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
            "- (위 검색 결과 중 실제로 참고한 것만 번호로 나열)\n"
            f"{_CITATION_INSTRUCTION}"
        )

    def _market_sizing_prompt(self, context: dict) -> str:
        idea = context.get("idea", "")
        keywords = context.get("keywords", [])
        market_research = context.get("market_research", "")
        search_results = context.get("search_results", [])
        sources_text = _numbered_sources(search_results)
        feedback_block = self._revision_context_block(
            context.get("previous_analysis", ""), context.get("feedback_message", "")
        )
        return (
            "당신은 시장 규모를 추정하는 애널리스트입니다. TAM/SAM/SOM을 산정합니다.\n\n"
            f"[아이디어]\n{idea}\n\n"
            f"[검색 키워드]\n{', '.join(keywords)}\n\n"
            f"[시장조사 분석 결과 (참고용 컨텍스트)]\n{market_research}\n\n"
            f"[시장 규모 관련 검색 결과]\n{sources_text}"
            f"{feedback_block}\n\n"
            "위 내용에 근거해서 아래 형식으로 한국어로 작성해줘. 정확한 통계가 없으면 "
            "지어내지 말고 어떤 가정으로 추정했는지 명시하고 '추정치'라고 밝혀줘.\n\n"
            f"{_SECTION_FORMAT_RULE}"
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
            "- (위 검색 결과 중 실제로 참고한 것만 번호로 나열. 없으면 "
            "'참고할 만한 검색 출처 없음, 일반 상식 기반 추정'이라고 밝혀줘)\n"
            f"{_CITATION_INSTRUCTION}"
        )

    def _vpc_features_prompt(self, context: dict) -> str:
        idea = context.get("idea", "")
        market_research = context.get("market_research", "")
        competitor_analysis = context.get("competitor_analysis", "")
        feedback_block = self._revision_context_block(
            context.get("previous_analysis", ""), context.get("feedback_message", "")
        )
        return (
            "당신은 Value Proposition Canvas(VPC)로 서비스 컨셉과 핵심 기능을 "
            "정의하는 PO입니다.\n\n"
            f"[아이디어]\n{idea}\n\n"
            f"[시장조사 분석 - 타겟 고객 니즈]\n{market_research}\n\n"
            f"[경쟁사 비교 분석 - 차별화 포인트]\n{competitor_analysis}"
            f"{feedback_block}\n\n"
            "위 내용을 근거로 아래 키를 가진 JSON 객체로 답해줘.\n\n"
            "{\n"
            '  "customer_jobs": "고객이 해결하려는 과제",\n'
            '  "pains": "수행 중 겪는 불편·장애",\n'
            '  "gains": "원하는 결과·기대 가치",\n'
            '  "products_services": "제공할 제품/서비스",\n'
            '  "pain_relievers": "Pain을 해소하는 방식",\n'
            '  "gain_creators": "Gain을 강화하는 방식",\n'
            '  "fit_verification": "고객 프로필과 가치 지도가 얼마나 맞아떨어지는지, '
            "안 맞는 부분이 있다면 무엇인지 솔직히 서술 - 반드시 채워야 함, 절대 "
            '빈 값으로 두지 마",\n'
            '  "features": [\n'
            '    {"name": "기능명", "description": "설명", "difficulty": "상/중/하", '
            '"importance": "상/중/하"}\n'
            "  ],\n"
            '  "use_cases": [\n'
            '    "위 핵심 기능이 실제로 어떻게 쓰이는지 구체적 시나리오 1 (2~3문장)",\n'
            '    "시나리오 2 (2~3문장)",\n'
            '    "시나리오 3 (2~3문장)"\n'
            "  ]\n"
            "}\n"
            "features는 5~7개, difficulty/importance는 개발 구현 난이도/핵심 가치 기여도를 "
            "뜻하며 반드시 '상'/'중'/'하' 중 하나로만. use_cases는 정확히 3개."
            f"{_JSON_ONLY_INSTRUCTION}"
        )

    def _render_vpc_features(self, data: dict) -> str:
        parts = [
            "1. 고객 프로필",
            f"- Customer Jobs: {_pick(data, 'customer_jobs')}",
            f"- Pains: {_pick(data, 'pains')}",
            f"- Gains: {_pick(data, 'gains')}",
            "",
            "2. 가치 지도",
            f"- Products & Services: {_pick(data, 'products_services')}",
            f"- Pain Relievers: {_pick(data, 'pain_relievers')}",
            f"- Gain Creators: {_pick(data, 'gain_creators')}",
            "",
            "3. Fit 검증",
            _pick(data, "fit_verification"),
            "",
            "4. 핵심 기능 (5~7개)",
            "| 기능명 | 설명 | 난이도 | 중요도 |",
            "|---|---|---|---|",
        ]
        features = data.get("features") or []
        if not features:
            parts.append("| (기능 정보 없음) | - | 중 | 중 |")
        for f in features:
            if not isinstance(f, dict):
                continue
            name = _pick(f, "name", "이름 없음")
            description = _pick(f, "description", "-")
            difficulty = _clamp_level(f.get("difficulty"))
            importance = _clamp_level(f.get("importance"))
            parts.append(f"| {name} | {description} | {difficulty} | {importance} |")
        parts += ["", "5. Use Case (3종)"]
        use_cases = [str(u).strip() for u in (data.get("use_cases") or []) if str(u).strip()]
        if not use_cases:
            use_cases = ["시나리오 정보 없음"]
        for i, case in enumerate(use_cases, start=1):
            parts.append(f"- Case {i}: {case}")
        return "\n".join(parts)

    def _mvp_roadmap_prompt(self, context: dict) -> str:
        idea = context.get("idea", "")
        vpc_features = context.get("vpc_features", "")
        feedback_block = self._revision_context_block(
            context.get("previous_analysis", ""), context.get("feedback_message", "")
        )
        return (
            "당신은 서비스 개발 로드맵을 수립하는 PM입니다.\n\n"
            f"[아이디어]\n{idea}\n\n"
            f"[VPC 및 핵심 기능 정의]\n{vpc_features}"
            f"{feedback_block}\n\n"
            "위에서 도출된 핵심 기능들을 근거로 아래 키를 가진 JSON 객체로 답해줘. "
            "모든 텍스트는 한국어 문장으로만 작성해줘 - User Story나 Given/When/Then "
            "같은 영어 용어 자체를 절대 쓰지 마.\n\n"
            "{\n"
            '  "moscow": {\n'
            '    "must_have": "Must have 기능들",\n'
            '    "should_have": "Should have 기능들",\n'
            '    "could_have": "Could have 기능들",\n'
            '    "wont_have": "Won\'t have 기능들",\n'
            '    "wont_have_reason": "이번 범위에서 제외하는 이유"\n'
            "  },\n"
            '  "kano": [\n'
            '    {"feature": "기능명", "category": "Basic 또는 Performance 또는 '
            'Excitement", "reason": "이유"}\n'
            "  ],\n"
            '  "mvp_definition": {\n'
            '    "must_have_all": "Must have 전체",\n'
            '    "performance_core": "Performance 핵심",\n'
            '    "excitement_1_2": "Excitement 1~2개",\n'
            '    "rationale": "왜 이 범위로 MVP를 확정했는지 한 문단 설명"\n'
            "  },\n"
            '  "milestones": [\n'
            '    {"timeframe": "몇 개월 내", "description": "마일스톤 내용"}\n'
            "  ],\n"
            '  "kpis": ["출시 후 확인할 KPI"],\n'
            '  "epics": [\n'
            '    {"title": "Epic 제목", "user_story": "(역할)로서 나는 (하고 싶은 것)을 '
            '원한다, 왜냐하면 (그 이유) 때문이다", "acceptance_criteria": "(조건)일 때 '
            '(행동)하면 (결과)가 되어야 한다"}\n'
            "  ]\n"
            "}\n"
            "kano는 moscow의 must_have로 분류된 기능마다 하나씩. milestones는 "
            "MVP 이후 2~3개월 단위로 3~4개. kpis는 2~3개. epics는 MVP 기능을 묶은 "
            "2~3개."
            f"{_JSON_ONLY_INSTRUCTION}"
        )

    def _render_mvp_roadmap(self, data: dict) -> str:
        moscow = data.get("moscow") or {}
        parts = [
            "1. MoSCoW 분류",
            f"- Must have: {_pick(moscow, 'must_have')}",
            f"- Should have: {_pick(moscow, 'should_have')}",
            f"- Could have: {_pick(moscow, 'could_have')}",
            f"- Won't have: {_pick(moscow, 'wont_have')} / "
            f"제외 이유: {_pick(moscow, 'wont_have_reason')}",
            "",
            "2. Kano 모델 매핑",
        ]
        kano = [k for k in (data.get("kano") or []) if isinstance(k, dict)]
        if not kano:
            parts.append("- (Kano 매핑 정보 없음)")
        for k in kano:
            feature = _pick(k, "feature", "기능명 없음")
            category = _pick(k, "category", "Basic")
            reason = _pick(k, "reason", "이유 없음")
            parts.append(f"- {feature} ({category}): {reason}")

        mvp_def = data.get("mvp_definition") or {}
        parts += [
            "",
            "3. MVP 정의",
            f"- Must have 전체: {_pick(mvp_def, 'must_have_all')}",
            f"- Performance 핵심: {_pick(mvp_def, 'performance_core')}",
            f"- Excitement 1~2개: {_pick(mvp_def, 'excitement_1_2')}",
            "",
            _pick(mvp_def, "rationale", "MVP 범위 확정 근거 정보 없음"),
            "",
            "4. 마일스톤 & KPI",
        ]
        milestones = [m for m in (data.get("milestones") or []) if isinstance(m, dict)]
        if not milestones:
            parts.append("- (마일스톤 정보 없음)")
        for m in milestones:
            timeframe = _pick(m, "timeframe", "시기 미정")
            description = _pick(m, "description", "내용 없음")
            parts.append(f"- 마일스톤 ({timeframe} 내): {description}")
        kpis = [str(k).strip() for k in (data.get("kpis") or []) if str(k).strip()]
        if not kpis:
            kpis = ["KPI 정보 없음"]
        for kpi in kpis:
            parts.append(f"- KPI: {kpi}")

        parts += ["", "5. Epic 예시"]
        epics = [e for e in (data.get("epics") or []) if isinstance(e, dict)]
        if not epics:
            parts.append("- Epic 1: (Epic 정보 없음)")
        for i, e in enumerate(epics, start=1):
            title = _pick(e, "title", "제목 없음")
            user_story = _pick(e, "user_story", "사용자 스토리 정보 없음")
            acceptance = _pick(e, "acceptance_criteria", "인수 조건 정보 없음")
            parts.append(f"- Epic {i}: {title}")
            parts.append(f"  사용자 스토리: {user_story}")
            parts.append(f"  인수 조건: {acceptance}")
        return "\n".join(parts)

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

    async def answer_question(
        self, stage: str, message: str, analysis: str, search_results: list[dict]
    ) -> str:
        stage_label = _STAGE_LABELS.get(stage, stage)
        sources_text = _numbered_sources(search_results)
        return await self._generate(
            f"당신은 {stage_label} 담당 애널리스트입니다. 아래는 방금 작성한 분석 내용입니다.\n\n"
            f"[분석 내용]\n{analysis}\n\n"
            f"[질문 관련 검색 결과]\n{sources_text}\n\n"
            f"[사용자 질문]\n{message}\n\n"
            "위 분석 내용과 검색 결과를 근거로 사용자의 질문에 대화체로 답변해줘. 분석 본문 "
            "형식(번호, 표 등)을 새로 만들지 말고, 질문에 대한 답만 자연스럽게 설명해줘. "
            "분석 내용과 검색 결과 둘 다에 없는 내용은 절대 지어내지 말고, 확실하지 않으면 "
            "'확실하지 않지만' 같은 표현으로 솔직히 밝혀줘. 답변 끝에 실제로 참고한 검색 "
            "결과가 있으면 번호로만 표시해줘(예: [1], [2]).\n"
            f"{_CITATION_INSTRUCTION}"
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
            f"{_SECTION_FORMAT_RULE}"
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
