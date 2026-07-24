from langgraph.types import interrupt

from app.graph.state import DRAFT_STAGE, STAGE_ORDER, PicoState
from app.services.llm_client import llm_client
from app.services.search_client import search_client
from app.utils.citations import verify_citations


async def _run_analysis(
    state: PicoState, stage_key: str, *, use_search: bool, search_query_suffix: str | None = None
) -> dict:
    stage = state[stage_key]
    keywords = stage["keywords"] or await llm_client.extract_keywords(state["idea"])

    context = {"idea": state["idea"], "keywords": keywords}
    if use_search:
        query = " ".join(keywords)
        if search_query_suffix:
            query = f"{query} {search_query_suffix}"
        context["search_results"] = await search_client.search(query)
    if stage_key == "market_sizing":
        context["market_research"] = state["market_research"]["analysis"]

    analysis = await llm_client.synthesize_analysis(stage_key, context)
    if use_search:
        analysis = verify_citations(analysis, context["search_results"])
    return {stage_key: {**stage, "keywords": keywords, "analysis": analysis}}


async def _analyze_pestel(state: PicoState) -> dict:
    stage = state["pestel"]
    keywords = stage["keywords"] or await llm_client.extract_keywords(state["idea"])
    market_research = state["market_research"]["analysis"]

    context = {"idea": state["idea"], "keywords": keywords, "market_research": market_research}
    query = await llm_client.decide_pestel_search_query(state["idea"], market_research)
    if query:
        context["search_results"] = await search_client.search(query)

    analysis = await llm_client.synthesize_analysis("pestel", context)
    if query:
        analysis = verify_citations(analysis, context["search_results"])
    return {"pestel": {**stage, "keywords": keywords, "analysis": analysis}}


async def _analyze_lean_canvas(state: PicoState) -> dict:
    stage = state["lean_canvas"]
    context = {
        "idea": state["idea"],
        "keywords": stage["keywords"],
        "market_research": state["market_research"]["analysis"],
        "pestel": state["pestel"]["analysis"],
    }
    analysis = await llm_client.synthesize_analysis("lean_canvas", context)
    return {"lean_canvas": {**stage, "analysis": analysis}}


async def _analyze_vpc_features(state: PicoState) -> dict:
    stage = state["vpc_features"]
    context = {
        "idea": state["idea"],
        "keywords": stage["keywords"],
        "market_research": state["market_research"]["analysis"],
        "competitor_analysis": state["competitor_analysis"]["analysis"],
    }
    analysis = await llm_client.synthesize_analysis("vpc_features", context)
    return {"vpc_features": {**stage, "analysis": analysis}}


async def _analyze_mvp_roadmap(state: PicoState) -> dict:
    stage = state["mvp_roadmap"]
    context = {
        "idea": state["idea"],
        "keywords": stage["keywords"],
        "vpc_features": state["vpc_features"]["analysis"],
    }
    analysis = await llm_client.synthesize_analysis("mvp_roadmap", context)
    return {"mvp_roadmap": {**stage, "analysis": analysis}}


_STAGE_ANALYZERS = {
    "market_research": lambda state: _run_analysis(state, "market_research", use_search=True),
    "pestel": _analyze_pestel,
    "lean_canvas": _analyze_lean_canvas,
    "competitor_analysis": lambda state: _run_analysis(
        state,
        "competitor_analysis",
        use_search=True,
        search_query_suffix="경쟁 서비스 비교 가격 기능",
    ),
    "market_sizing": lambda state: _run_analysis(
        state, "market_sizing", use_search=True, search_query_suffix="시장 규모 통계"
    ),
    "vpc_features": _analyze_vpc_features,
    "mvp_roadmap": _analyze_mvp_roadmap,
}


async def analyze_node(state: PicoState) -> dict:
    return await _STAGE_ANALYZERS[state["current_stage"]](state)


async def review_node(state: PicoState) -> dict:
    stage_key = state["current_stage"]
    stage = state[stage_key]

    decision = interrupt(
        {"stage": stage_key, "keywords": stage["keywords"], "analysis": stage["analysis"]}
    )
    message = decision.get("message", "")
    chat_history = stage["chat_history"] + [{"role": "user", "content": message}]

    if decision.get("action") == "approve":
        idx = STAGE_ORDER.index(stage_key)
        next_stage = STAGE_ORDER[idx + 1] if idx + 1 < len(STAGE_ORDER) else DRAFT_STAGE
        return {
            stage_key: {**stage, "chat_history": chat_history, "approved": True},
            "current_stage": next_stage,
            "next_route": "draft" if next_stage == DRAFT_STAGE else "analyze",
        }

    intent = await llm_client.classify_feedback_intent(stage_key, message)
    if intent == "chat":
        answer = await llm_client.answer_question(stage_key, message, stage["analysis"])
        chat_history = chat_history + [{"role": "assistant", "content": answer}]
        return {
            stage_key: {**stage, "chat_history": chat_history, "approved": False},
            "next_route": "review",
        }

    new_keywords = await llm_client.interpret_feedback(stage_key, message, stage)
    return {
        stage_key: {
            **stage,
            "chat_history": chat_history,
            "keywords": new_keywords,
            "approved": False,
        },
        "next_route": "analyze",
    }


def route_after_review(state: PicoState) -> str:
    return state["next_route"]


async def draft_node(state: PicoState) -> dict:
    draft = await llm_client.synthesize_draft(
        state["market_research"]["analysis"],
        state["pestel"]["analysis"],
        state["lean_canvas"]["analysis"],
        state["competitor_analysis"]["analysis"],
        state["market_sizing"]["analysis"],
        state["vpc_features"]["analysis"],
        state["mvp_roadmap"]["analysis"],
    )
    return {"draft": draft}
