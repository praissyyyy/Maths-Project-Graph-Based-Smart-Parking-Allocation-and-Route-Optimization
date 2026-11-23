"""
Dijkstra's Shortest Path Algorithm for Road Networks.
Calculates optimal routes, measures distance, execution time, and nodes explored.
"""

import time
import heapq
import networkx as nx
from typing import Tuple, List, Dict, Optional


def dijkstra_shortest_path(
    G: nx.DiGraph,
    source: str,
    target: str,
    weight: str = 'length'
) -> Tuple[Optional[List[str]], float, int, float]:
    """
    Computes shortest path from source to target using Dijkstra's algorithm.

    Returns:
        path (List[str] or None): List of node IDs forming the shortest path.
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

    # Priority queue stores tuples of (current_dist, node_id)
    pq = [(0.0, source)]
    distances: Dict[str, float] = {source: 0.0}
    predecessors: Dict[str, Optional[str]] = {source: None}
    visited = set()
    nodes_explored = 0

    while pq:
        curr_dist, u = heapq.heappop(pq)

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
            return path, curr_dist, nodes_explored, exec_time

        # Explore outgoing neighbors
        for v in G.neighbors(u):
            edge_data = G[u][v]
            edge_weight = float(edge_data.get(weight, 10.0))
            new_dist = curr_dist + edge_weight

            if new_dist < distances.get(v, float('inf')):
                distances[v] = new_dist
                predecessors[v] = u
                heapq.heappush(pq, (new_dist, v))

    exec_time = time.perf_counter() - start_time
    return None, float('inf'), nodes_explored, exec_time
