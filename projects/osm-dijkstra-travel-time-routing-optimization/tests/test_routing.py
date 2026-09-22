import networkx as nx
import pytest

from src.routing import RouteResult


def test_route_result_unit_conversions() -> None:
    result = RouteResult(route=[1, 2], distance_m=2500.0, travel_time_s=900.0)
    assert result.distance_km == pytest.approx(2.5)
    assert result.travel_time_min == pytest.approx(15.0)


def test_dijkstra_prefers_lower_travel_time_not_shorter_distance() -> None:
    graph = nx.DiGraph()
    graph.add_edge("A", "B", travel_time=10, length=100)
    graph.add_edge("B", "D", travel_time=10, length=100)
    graph.add_edge("A", "C", travel_time=4, length=500)
    graph.add_edge("C", "D", travel_time=4, length=500)

    route = nx.shortest_path(graph, "A", "D", weight="travel_time", method="dijkstra")
    assert route == ["A", "C", "D"]
