from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from app.graph.nodes import (
    competitor_analyze_node,
    competitor_review_node,
    draft_node,
    market_research_analyze_node,
    market_research_review_node,
    pestel_analyze_node,
    pestel_review_node,
    route_by_approval,
)
from app.graph.state import PicoState


def build_graph():
    graph = StateGraph(PicoState)

    graph.add_node("market_research_analyze_node", market_research_analyze_node)
    graph.add_node("market_research_review_node", market_research_review_node)
    graph.add_node("pestel_analyze_node", pestel_analyze_node)
    graph.add_node("pestel_review_node", pestel_review_node)
    graph.add_node("competitor_analyze_node", competitor_analyze_node)
    graph.add_node("competitor_review_node", competitor_review_node)
    graph.add_node("draft_node", draft_node)

    graph.add_edge(START, "market_research_analyze_node")
    graph.add_edge("market_research_analyze_node", "market_research_review_node")
    graph.add_conditional_edges(
        "market_research_review_node",
        route_by_approval("market_research"),
        {
            "approve": "pestel_analyze_node",
            "revise": "market_research_analyze_node",
            "chat": "market_research_review_node",
        },
    )

    graph.add_edge("pestel_analyze_node", "pestel_review_node")
    graph.add_conditional_edges(
        "pestel_review_node",
        route_by_approval("pestel"),
        {
            "approve": "competitor_analyze_node",
            "revise": "pestel_analyze_node",
            "chat": "pestel_review_node",
        },
    )

    graph.add_edge("competitor_analyze_node", "competitor_review_node")
    graph.add_conditional_edges(
        "competitor_review_node",
        route_by_approval("competitor_analysis"),
        {
            "approve": "draft_node",
            "revise": "competitor_analyze_node",
            "chat": "competitor_review_node",
        },
    )

    graph.add_edge("draft_node", END)

    return graph.compile(checkpointer=MemorySaver())


pico_graph = build_graph()
