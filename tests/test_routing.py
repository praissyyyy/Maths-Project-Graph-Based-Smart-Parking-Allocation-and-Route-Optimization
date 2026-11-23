"""
Unit tests for Road Graph Loading, Dijkstra's Algorithm, and A* Search.
"""

import os
import pytest
import networkx as nx
from algorithms.graph_loader import load_or_fetch_road_network
from algorithms.dijkstra import dijkstra_shortest_path
from algorithms.astar import astar_shortest_path, haversine_distance


@pytest.fixture(scope="module")
def road_graph():
    graphml_path = os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        "data",
        "gandhipuram_road_network.graphml"
    )
    _, di_g = load_or_fetch_road_network(filepath=graphml_path)
    return di_g


def test_road_graph_loaded_correctly(road_graph):
    """Test 1: Verify road network graph contains nodes, directed edges, and edge lengths."""
    assert road_graph is not None
    assert road_graph.number_of_nodes() > 500
    assert road_graph.number_of_edges() > 1000
    assert isinstance(road_graph, nx.DiGraph)

    # Check node attributes
    sample_node = list(road_graph.nodes())[0]
    assert 'x' in road_graph.nodes[sample_node]
    assert 'y' in road_graph.nodes[sample_node]

    # Check edge length
    sample_edge = list(road_graph.edges(data=True))[0]
    assert 'length' in sample_edge[2]
    assert sample_edge[2]['length'] > 0


def test_haversine_distance():
    """Verify great-circle calculation on known coordinates."""
    # Gandhipuram to Coimbatore Railway Junction (~3 km)
    dist = haversine_distance(11.0182714, 76.9677744, 10.9990, 76.9640)
    assert 2000 < dist < 3000


def test_dijkstra_shortest_path(road_graph):
    """Test 8: Verify Dijkstra finds valid paths and returns positive distance."""
    scc = max(nx.strongly_connected_components(road_graph), key=len)
    nodes = list(scc)[:10]
    source = str(nodes[0])
    target = str(nodes[5])

    path, dist, explored, exec_time = dijkstra_shortest_path(road_graph, source, target)
    assert path is not None
    assert len(path) >= 1
    assert path[0] == source
    assert path[-1] == target
    assert dist > 0
    assert explored > 0
    assert exec_time >= 0

    # Verify path continuity in directed graph
    for i in range(len(path) - 1):
        assert road_graph.has_edge(path[i], path[i+1])


def test_astar_shortest_path(road_graph):
    """Test 9: Verify A* search finds optimal path with consistent distance."""
    scc = max(nx.strongly_connected_components(road_graph), key=len)
    nodes = list(scc)[:10]
    source = str(nodes[0])
    target = str(nodes[5])

    dijk_path, dijk_dist, dijk_exp, _ = dijkstra_shortest_path(road_graph, source, target)
    astar_path, astar_dist, astar_exp, _ = astar_shortest_path(road_graph, source, target)

    assert astar_path is not None
    assert astar_path[0] == source
    assert astar_path[-1] == target
    # Distance between Dijkstra and A* with admissible heuristic must be virtually identical
    assert abs(dijk_dist - astar_dist) < 1e-4

    # Path continuity in directed graph
    for i in range(len(astar_path) - 1):
        assert road_graph.has_edge(astar_path[i], astar_path[i+1])
