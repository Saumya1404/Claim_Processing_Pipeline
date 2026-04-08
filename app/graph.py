from __future__ import annotations

from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

from app.nodes.aggregator import aggregator_node
from app.nodes.bill import bill_node
from app.nodes.discharge import discharge_node
from app.nodes.id_agent import id_agent_node
from app.nodes.segregator import segregator_node


class ClaimState(TypedDict, total=False):
    claim_id: str
    pdf_path: str
    classified_pages: dict[str, list[int]]
    segregator_metadata: dict[str, Any]
    id_data: dict[str, Any]
    discharge_data: dict[str, Any]
    bill_data: dict[str, Any]
    errors: list[str]
    final_response: dict[str, Any]


def build_graph():
    graph = StateGraph(ClaimState)

    graph.add_node("segregator_node", segregator_node)
    graph.add_node("id_agent_node", id_agent_node)
    graph.add_node("discharge_node", discharge_node)
    graph.add_node("bill_node", bill_node)
    graph.add_node("aggregator_node", aggregator_node)

    graph.add_edge(START, "segregator_node")
    graph.add_edge("segregator_node", "id_agent_node")
    graph.add_edge("segregator_node", "discharge_node")
    graph.add_edge("segregator_node", "bill_node")

    graph.add_edge("id_agent_node", "aggregator_node")
    graph.add_edge("discharge_node", "aggregator_node")
    graph.add_edge("bill_node", "aggregator_node")

    graph.add_edge("aggregator_node", END)

    return graph.compile()


app_graph = build_graph()
