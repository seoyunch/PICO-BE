from langgraph.graph import StateGraph, START, END

from app.graph.state import PicoState
from app.graph.nodes import (
    market_research_node,
    pestel_node,
    competitor_analysis_node,
    draft_node,
)


def build_graph():
    graph = StateGraph(PicoState)

    graph.add_node("market_research_node", market_research_node)
    graph.add_node("pestel_node", pestel_node)
    graph.add_node("competitor_analysis_node", competitor_analysis_node)
    graph.add_node("draft_node", draft_node)

    graph.add_edge(START, "market_research_node")
    graph.add_edge("market_research_node", "pestel_node")
    graph.add_edge("pestel_node", "competitor_analysis_node")
    graph.add_edge("competitor_analysis_node", "draft_node")
    graph.add_edge("draft_node", END)

    return graph.compile()


pico_graph = build_graph()
