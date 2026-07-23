from langgraph.types import interrupt

from app.graph.state import PicoState
from app.services.llm_client import llm_client
from app.services.search_client import search_client
from app.utils.citations import verify_citations


async def _run_analysis(state: PicoState, stage_key: str, *, use_search: bool) -> dict:
    stage = state[stage_key]
    keywords = stage["keywords"] or await llm_client.extract_keywords(state["idea"])

    context = {"idea": state["idea"], "keywords": keywords}
    if use_search:
        context["search_results"] = await search_client.search(" ".join(keywords))
    if stage_key == "pestel":
        context["market_research"] = state["market_research"]["analysis"]

    analysis = await llm_client.synthesize_analysis(stage_key, context)
    if use_search:
        analysis = verify_citations(analysis, context["search_results"])
    return {stage_key: {**stage, "keywords": keywords, "analysis": analysis}}


async def _run_review(state: PicoState, stage_key: str) -> dict:
    stage = state[stage_key]
    decision = interrupt(
        {"stage": stage_key, "keywords": stage["keywords"], "analysis": stage["analysis"]}
    )
    message = decision.get("message", "")
    chat_history = stage["chat_history"] + [{"role": "user", "content": message}]

    if decision.get("action") == "approve":
        return {stage_key: {**stage, "chat_history": chat_history, "approved": True}}

    new_keywords = await llm_client.interpret_feedback(stage_key, message, stage)
    return {
        stage_key: {
            **stage,
            "chat_history": chat_history,
            "keywords": new_keywords,
            "approved": False,
        }
    }


def route_by_approval(stage_key: str):
    def _route(state: PicoState) -> str:
        return "approve" if state[stage_key]["approved"] else "revise"

    return _route


async def market_research_analyze_node(state: PicoState) -> dict:
    return await _run_analysis(state, "market_research", use_search=True)


async def market_research_review_node(state: PicoState) -> dict:
    return await _run_review(state, "market_research")


async def pestel_analyze_node(state: PicoState) -> dict:
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


async def pestel_review_node(state: PicoState) -> dict:
    return await _run_review(state, "pestel")


async def competitor_analyze_node(state: PicoState) -> dict:
    return await _run_analysis(state, "competitor_analysis", use_search=True)


async def competitor_review_node(state: PicoState) -> dict:
    return await _run_review(state, "competitor_analysis")


async def draft_node(state: PicoState) -> dict:
    draft = await llm_client.synthesize_draft(
        state["market_research"]["analysis"],
        state["pestel"]["analysis"],
        state["competitor_analysis"]["analysis"],
    )
    return {"draft": draft}
