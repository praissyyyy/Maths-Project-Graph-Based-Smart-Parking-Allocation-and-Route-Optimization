"""
A* Search Algorithm for Road Networks.
Utilizes an admissible Haversine geographic heuristic for directed route optimization.
"""

import time
import heapq
import math
import networkx as nx
from typing import Tuple, List, Dict, Optional


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Computes great-circle distance between two coordinates in meters.
    Serves as an admissible and consistent heuristic: h(u, v) <= d_actual(u, v).
    """
    R = 6371000.0  # Earth radius in meters
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (math.sin(delta_phi / 2.0) ** 2 +
         math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2)
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return R * c


def astar_shortest_path(
    G: nx.DiGraph,
    source: str,
    target: str,
    weight: str = 'length'
) -> Tuple[Optional[List[str]], float, int, float]:
    """
    Computes shortest path from source to target using A* search with Haversine heuristic.

    Returns:
        path (List[str] or None): List of node IDs in optimal route.
        distance (float): Total route distance in meters.
        nodes_explored (int): Count of nodes popped/settled from priority queue.
        execution_time (float): Wall-clock time in seconds.
    """
    start_time = time.perf_counter()

    if source not in G or target not in G:
        exec_time = time.perf_counter() - start_time
        return None, float('inf'), 0, exec_time

    if source == target:
        exec_time = time.perf_counter() - start_time
        return [source], 0.0, 1, exec_time

    target_lat = G.nodes[target].get('y', 0.0)
    target_lon = G.nodes[target].get('x', 0.0)

    def heuristic(node: str) -> float:
        node_lat = G.nodes[node].get('y', 0.0)
        node_lon = G.nodes[node].get('x', 0.0)
        return haversine_distance(node_lat, node_lon, target_lat, target_lon)

    # Priority queue stores tuples of (f_score, g_score, node_id)
    h0 = heuristic(source)
    pq = [(h0, 0.0, source)]
    g_scores: Dict[str, float] = {source: 0.0}
    predecessors: Dict[str, Optional[str]] = {source: None}
    visited = set()
    nodes_explored = 0

    while pq:
        f, g, u = heapq.heappop(pq)

        if u in visited:
            continue
        visited.add(u)
        nodes_explored += 1

        if u == target:
            # Reconstruct path
            path = []
            curr = target
            while curr is not None:
                path.append(curr)
                curr = predecessors.get(curr)
            path.reverse()
            exec_time = time.perf_counter() - start_time
            return path, g, nodes_explored, exec_time

        for v in G.neighbors(u):
            edge_data = G[u][v]
            edge_weight = float(edge_data.get(weight, 10.0))
            tentative_g = g + edge_weight

            if tentative_g < g_scores.get(v, float('inf')):
                g_scores[v] = tentative_g
                f_score = tentative_g + heuristic(v)
                predecessors[v] = u
                heapq.heappush(pq, (f_score, tentative_g, v))

    exec_time = time.perf_counter() - start_time
    return None, float('inf'), nodes_explored, exec_time
