"""
Nearest Available Parking Allocation Algorithm.
Greedily assigns each vehicle to the closest parking facility that currently has remaining capacity.
"""

import time
import networkx as nx
from typing import List, Dict, Any
from algorithms.dijkstra import dijkstra_shortest_path


def run_nearest_available_allocation(
    G: nx.DiGraph,
    vehicles: List[Dict[str, Any]],
    facilities: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Executes Nearest Available parking allocation.

    Args:
        G: Directed road graph.
        vehicles: List of vehicle request dictionaries.
        facilities: List of facility dictionaries with capacity and available_spaces.

    Returns:
        Dictionary containing allocations, metrics, execution time, and facility states.
    """
    start_time = time.perf_counter()

    fac_map = {f["facility_id"]: dict(f) for f in facilities}
    remaining_capacity = {f["facility_id"]: f["available_spaces"] for f in facilities}
    total_capacity = {f["facility_id"]: f["total_capacity"] for f in facilities}
    initial_occupied = {f["facility_id"]: f["initial_occupied"] for f in facilities}

    assignments = []
    total_travel_distance = 0.0
    assigned_count = 0
    unassigned_count = 0

    for veh in vehicles:
        v_id = veh["vehicle_id"]
        start_node = str(veh["start_node"])

        best_facility_id = None
        best_distance = float('inf')
        best_path = []

        # Check all facilities with remaining capacity
        for f in facilities:
            f_id = f["facility_id"]
            if remaining_capacity[f_id] > 0:
                dest_node = str(f["node_id"])
                path, dist, _, _ = dijkstra_shortest_path(G, start_node, dest_node)
                if path is not None and dist < best_distance:
                    best_distance = dist
                    best_facility_id = f_id
                    best_path = path

        if best_facility_id is not None:
            remaining_capacity[best_facility_id] -= 1
            total_travel_distance += best_distance
            assigned_count += 1
            status = "Assigned"
            assigned_node = fac_map[best_facility_id]["node_id"]
        else:
            status = "Unassigned"
            unassigned_count += 1
            best_distance = 0.0
            best_path = []
            assigned_node = None

        assignments.append({
            "vehicle_id": v_id,
            "assigned_facility": best_facility_id,
            "status": status,
            "travel_distance": round(best_distance, 2),
            "start_node": start_node,
            "destination_node": assigned_node,
            "path": best_path
        })

    exec_time = time.perf_counter() - start_time
    total_vehicles = len(vehicles)
    avg_travel_distance = (total_travel_distance / assigned_count) if assigned_count > 0 else 0.0
    success_rate = (assigned_count / total_vehicles * 100.0) if total_vehicles > 0 else 0.0

    facility_utilization = {}
    for f in facilities:
        f_id = f["facility_id"]
        assigned_to_f = sum(1 for a in assignments if a["assigned_facility"] == f_id)
        current_occupied = initial_occupied[f_id] + assigned_to_f
        util_pct = (current_occupied / total_capacity[f_id]) * 100.0
        facility_utilization[f_id] = {
            "initial_occupied": initial_occupied[f_id],
            "newly_assigned": assigned_to_f,
            "current_occupied": current_occupied,
            "total_capacity": total_capacity[f_id],
            "remaining_available": remaining_capacity[f_id],
            "utilization_pct": round(util_pct, 2)
        }

    return {
        "algorithm": "Nearest Available",
        "total_vehicles": total_vehicles,
        "assigned_count": assigned_count,
        "unassigned_count": unassigned_count,
        "success_rate_pct": round(success_rate, 2),
        "total_travel_distance_m": round(total_travel_distance, 2),
        "avg_travel_distance_m": round(avg_travel_distance, 2),
        "execution_time_s": round(exec_time, 6),
        "facility_utilization": facility_utilization,
        "assignments": assignments
    }
