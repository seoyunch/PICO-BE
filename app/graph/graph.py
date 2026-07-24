from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from app.graph.nodes import analyze_node, draft_node, review_node, route_after_review
from app.graph.state import PicoState


def build_graph():
    graph = StateGraph(PicoState)

    graph.add_node("analyze_node", analyze_node)
    graph.add_node("review_node", review_node)
    graph.add_node("draft_node", draft_node)

    graph.add_edge(START, "analyze_node")
    graph.add_edge("analyze_node", "review_node")
    graph.add_conditional_edges(
        "review_node",
        route_after_review,
        {"analyze": "analyze_node", "review": "review_node", "draft": "draft_node"},
    )
    graph.add_edge("draft_node", END)

    return graph.compile(checkpointer=MemorySaver())


pico_graph = build_graph()
